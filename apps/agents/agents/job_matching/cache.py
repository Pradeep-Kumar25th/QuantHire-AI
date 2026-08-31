"""
Match-Result Cache
==================
Two-tier cache for ``MatchResult`` and per-JD ``JDAnalysis`` objects.

Why a cache?
------------
* A typical recruiter re-opens the same shortlist 5–10 times per day.
* Re-running the swarm produces almost the same answer (deterministic prior
  dominates) but costs the full LLM budget.
* When ranking N candidates against one JD, the JD-derived analysis is
  identical — we cache it once.

Design
------
* :class:`Cache` is a tiny protocol so callers can be tested with an
  in-memory implementation.
* :class:`InMemoryLRUCache` is the default — perfectly fine for a single
  replica; thread-safe via ``asyncio.Lock`` (we serialise on writes only).
* :class:`RedisCache` is opt-in via ``match_cache_redis_url`` — used in
  multi-replica deployments where two requests for the same shortlist may
  hit different workers.

Both implementations store JSON-encoded payloads so cached objects survive
restarts (Redis) and are de-coupled from the live Pydantic class hierarchy.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional, Protocol


logger = logging.getLogger(__name__)


# Bumped whenever the agentic pipeline (prompts / scoring / models) changes
# in a way that invalidates previously cached results. Append-only: every
# bump implicitly purges the cache because keys no longer collide.
PIPELINE_VERSION = "v3-2026-05"


class Cache(Protocol):
    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    async def clear(self) -> None: ...


# ---------------------------------------------------------------------------
# In-memory LRU
# ---------------------------------------------------------------------------


class InMemoryLRUCache:
    """A tiny, thread-safe (within a single asyncio loop) LRU.

    We don't pull in ``cachetools`` to avoid one more dependency for the
    most common deployment shape (single API replica behind a load balancer).
    """

    def __init__(self, max_size: int = 4096) -> None:
        self._max_size = max(1, max_size)
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                self._store.pop(key, None)
                return None
            # Touch -> move to most-recent
            self._store.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


# ---------------------------------------------------------------------------
# Redis (optional)
# ---------------------------------------------------------------------------


class RedisCache:
    """Redis-backed cache.

    Lazy-imports ``redis.asyncio`` so the dependency stays optional. If Redis
    is unreachable on first call, we degrade gracefully: log a warning and
    behave as a no-op (returns ``None`` from ``get``, drops ``set``).
    """

    def __init__(self, redis_url: str, namespace: str = "job_matching") -> None:
        self._url = redis_url
        self._namespace = namespace
        self._client: Any = None
        self._healthy = True

    def _full_key(self, key: str) -> str:
        return f"{self._namespace}:{PIPELINE_VERSION}:{key}"

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from redis import asyncio as aioredis  # type: ignore

            self._client = aioredis.from_url(self._url, decode_responses=True)
            return self._client
        except ImportError:
            logger.warning(
                "match_cache_redis_url is set but redis is not installed; "
                "falling back to no-op behaviour."
            )
            self._healthy = False
            return None
        except Exception as exc:
            logger.warning("Failed to construct Redis client (%s); cache disabled.", exc)
            self._healthy = False
            return None

    async def get(self, key: str) -> Optional[Any]:
        if not self._healthy:
            return None
        client = await self._ensure_client()
        if client is None:
            return None
        try:
            raw = await client.get(self._full_key(key))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis GET failed (%s); disabling cache for this process.", exc)
            self._healthy = False
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if not self._healthy:
            return
        client = await self._ensure_client()
        if client is None:
            return
        try:
            await client.set(
                self._full_key(key), json.dumps(value, default=str), ex=ttl_seconds
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis SET failed (%s); disabling cache for this process.", exc)
            self._healthy = False

    async def clear(self) -> None:
        # We deliberately don't FLUSHDB; just let TTLs expire. Tests use
        # InMemoryLRUCache which has a real clear().
        return


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _stable_repr(value: Any) -> str:
    """Stable JSON repr that won't reorder dict keys (so hashes are deterministic)."""
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def match_cache_key(
    *,
    candidate_id: str,
    jd_id: str,
    weights: dict[str, float],
    model: str,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Hash everything that would change a MatchResult's content.

    NOT keyed on temperature alone (covered by ``model``) or on streaming flags
    (the result shape is the same). DOES include ``model`` and the pipeline
    version so a model swap or prompt update implicitly invalidates entries.
    """
    payload = {
        "candidate_id": candidate_id,
        "jd_id": jd_id,
        "weights": {k: round(float(v), 4) for k, v in (weights or {}).items()},
        "model": model,
        "extra": extra or {},
        "pipeline": PIPELINE_VERSION,
    }
    digest = hashlib.sha256(_stable_repr(payload).encode("utf-8")).hexdigest()
    return f"match:{digest[:32]}"


def jd_analysis_cache_key(jd_id: str, jd_content_hash: str) -> str:
    return f"jd_analysis:{jd_id}:{jd_content_hash}"


def jd_content_hash(jd_payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_repr(jd_payload).encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_cache(
    redis_url: Optional[str] = None,
    max_size: int = 4096,
) -> Cache:
    """Pick the right cache backend from config."""
    if redis_url:
        return RedisCache(redis_url=redis_url)
    return InMemoryLRUCache(max_size=max_size)
