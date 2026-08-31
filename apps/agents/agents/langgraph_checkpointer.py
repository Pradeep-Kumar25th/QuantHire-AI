"""LangGraph checkpoint backends — Postgres on Azure, in-memory for local dev."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

_checkpointer: Any = None
_pg_pool: Any = None  # kept alive for the process lifetime


def _database_url_for_checkpoints() -> Optional[str]:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return None
    # psycopg expects postgresql:// not postgresql+asyncpg://
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def _checkpoint_setup_timeout_seconds() -> float:
    raw = os.getenv("LANGGRAPH_CHECKPOINT_SETUP_TIMEOUT_SECONDS", "45").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 45.0


def _should_use_postgres_checkpointer() -> bool:
    backend = os.getenv("LANGGRAPH_CHECKPOINT_BACKEND", "").strip().lower()
    if backend == "memory":
        return False
    if backend == "postgres":
        return True
    # JD generation is single-request on Azure; default to MemorySaver unless
    # an operator explicitly sets LANGGRAPH_CHECKPOINT_BACKEND=postgres.
    if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
        return False
    return False


def _try_postgres_checkpointer(db_url: str) -> Optional[Tuple[Any, Any]]:
    """Initialize Postgres checkpointer; return (pool, saver) or None on failure."""
    setup_timeout = _checkpoint_setup_timeout_seconds()
    pool = None
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg_pool import ConnectionPool

        # NOTE: PostgresSaver.from_conn_string() is a context manager and
        # cannot be used as a long-lived saver. Use a connection pool that
        # lives for the whole process instead (documented pattern).
        logger.info("Opening LangGraph checkpoint Postgres pool...")
        pool = ConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0},
        )
        pool.open(wait=True, timeout=30)
        saver = PostgresSaver(pool)
        logger.info(
            "Running LangGraph checkpoint schema setup (timeout=%ss)...",
            setup_timeout,
        )

        def _setup() -> None:
            saver.setup()  # create checkpoint tables if missing

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_setup)
            try:
                future.result(timeout=setup_timeout)
            except FuturesTimeoutError as exc:
                raise TimeoutError(
                    f"Postgres checkpoint setup timed out after {setup_timeout}s"
                ) from exc

        logger.info("LangGraph Postgres checkpointer enabled")
        return pool, saver
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres not installed; using MemorySaver"
        )
    except Exception as exc:
        logger.warning("Postgres checkpointer unavailable (%s)", exc)
        if pool is not None:
            try:
                pool.close()
            except Exception:
                pass
    return None


def get_langgraph_checkpointer():
    """Return a process-wide LangGraph checkpointer (Postgres preferred on Azure)."""
    global _checkpointer, _pg_pool
    if _checkpointer is not None:
        return _checkpointer

    db_url = _database_url_for_checkpoints()
    use_postgres = _should_use_postgres_checkpointer()

    if use_postgres and db_url:
        result = _try_postgres_checkpointer(db_url)
        if result is not None:
            _pg_pool, _checkpointer = result
            return _checkpointer
        logger.warning(
            "Falling back to MemorySaver for LangGraph checkpoints "
            "(JD generation does not require durable checkpoints)"
        )

    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()
    logger.info("LangGraph MemorySaver checkpointer enabled")
    return _checkpointer
