"""
Milvus startup — connect and load collections on every FastAPI boot.

Ensures ``quanthire_resumes`` and ``quanthire_job_descriptions`` are in memory
after Milvus or API restarts (load state is not persisted across Milvus reboots).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Iterable

# pymilvus is not installed on Azure Non-Prod (pgvector replaces Milvus).
# All entry points below no-op or fail gracefully when it is absent.
try:
    from pymilvus import Collection, connections, utility

    PYMILVUS_AVAILABLE = True
except ImportError:
    Collection = connections = utility = None  # type: ignore[assignment]
    PYMILVUS_AVAILABLE = False

logger = logging.getLogger(__name__)

MILVUS_COLLECTIONS: tuple[str, ...] = (
    "quanthire_job_descriptions",
    "quanthire_resumes",
)

DEFAULT_LOAD_TIMEOUT = int(os.getenv("MILVUS_LOAD_TIMEOUT", "180"))


def milvus_host() -> str:
    try:
        from app.config import settings

        return settings.milvus_host
    except Exception:
        return os.getenv("MILVUS_HOST", "localhost")


def milvus_port() -> str:
    try:
        from app.config import settings

        return str(settings.milvus_port)
    except Exception:
        return os.getenv("MILVUS_PORT", "19530")


def _is_loaded(name: str) -> bool:
    try:
        return "Loaded" in str(utility.load_state(name))
    except Exception:
        return False


def _is_stuck_loading(name: str) -> bool:
    """True when Milvus reports a load in progress that never completes (0%)."""
    try:
        if _is_loaded(name):
            return False
        progress = utility.loading_progress(name)
        if isinstance(progress, dict):
            pct = progress.get("loading_progress")
            return pct is not None and pct not in ("100", 100)
        return "Loading" in str(utility.load_state(name))
    except Exception:
        return False


def _wait_loaded(name: str, timeout: int = DEFAULT_LOAD_TIMEOUT) -> None:
    wait_fn = getattr(utility, "wait_for_loading_complete", None)
    if wait_fn:
        wait_fn(name, timeout=timeout)
        return

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_loaded(name):
            return
        time.sleep(2)
    if not _is_loaded(name):
        raise TimeoutError(f"Collection '{name}' did not reach Loaded state within {timeout}s")


def _load_collection(name: str, *, timeout: int = DEFAULT_LOAD_TIMEOUT) -> None:
    if not utility.has_collection(name):
        logger.warning("Collection '%s' does not exist — skipping load", name)
        return

    if _is_loaded(name):
        entities = Collection(name).num_entities
        logger.info("Collection '%s' already loaded (%s entities)", name, entities)
        return

    col = Collection(name)

    if _is_stuck_loading(name):
        logger.warning("Collection '%s' stuck loading — releasing before retry", name)
        try:
            col.release()
            time.sleep(1)
        except Exception as exc:
            logger.debug("Release before reload (%s): %s", name, exc)

    logger.info("Loading collection '%s' into memory...", name)
    col.load(timeout=timeout)
    _wait_loaded(name, timeout=timeout)
    entities = col.num_entities
    logger.info("Collection '%s' loaded (%s entities)", name, entities)


def connect_and_load_collections(
    collections: Iterable[str] | None = None,
    *,
    load_timeout: int = DEFAULT_LOAD_TIMEOUT,
) -> None:
    """Connect to Milvus and load all configured collections into memory."""
    if not PYMILVUS_AVAILABLE:
        raise RuntimeError(
            "pymilvus is not installed — Milvus is disabled in this deployment "
            "(set MILVUS_ENABLED=false or install pymilvus)"
        )
    host = milvus_host()
    port = milvus_port()
    names = tuple(collections) if collections is not None else MILVUS_COLLECTIONS

    try:
        try:
            connections.disconnect("default")
        except Exception:
            pass

        connections.connect(
            alias="default",
            host=host,
            port=str(port),
            timeout=30,
        )
        logger.info("Milvus connected at %s:%s", host, port)
    except Exception as exc:
        logger.error("Milvus connection failed at %s:%s: %s", host, port, exc)
        raise

    for name in names:
        try:
            _load_collection(name, timeout=load_timeout)
        except Exception as exc:
            logger.error("Failed to load collection '%s': %s", name, exc)
            raise


def disconnect_milvus() -> None:
    """Release default Milvus connection on shutdown."""
    if not PYMILVUS_AVAILABLE:
        return
    try:
        connections.disconnect("default")
        logger.info("Milvus disconnected")
    except Exception as exc:
        logger.debug("Milvus disconnect: %s", exc)


def milvus_status() -> dict:
    """Return load state for health/readiness probes."""
    out: dict = {"host": milvus_host(), "port": milvus_port(), "collections": {}}
    if not PYMILVUS_AVAILABLE:
        out["connected"] = False
        out["available"] = False
        return out
    try:
        if not connections.has_connection("default"):
            out["connected"] = False
            return out
        out["connected"] = True
        for name in MILVUS_COLLECTIONS:
            if name not in utility.list_collections():
                out["collections"][name] = {"exists": False}
                continue
            col = Collection(name)
            out["collections"][name] = {
                "exists": True,
                "loaded": _is_loaded(name),
                "load_state": str(utility.load_state(name)),
                "entities": col.num_entities,
            }
    except Exception as exc:
        out["error"] = str(exc)
    return out
