"""
Loop-safe Postgres access for QuantChat retrievers.

The QueryRouter pipeline is synchronous, but it can be invoked from inside a
running FastAPI event loop. Two rules keep pgvector access safe here:

1. Never call ``asyncio.run`` while a loop is running in the current thread —
   run the coroutine on a dedicated thread instead.
2. Never reuse the API's shared asyncpg engine from a different event loop —
   asyncpg connections are bound to the loop that created them. Each retrieval
   uses a short-lived NullPool engine that is disposed before the loop closes.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator


def _ensure_api_on_path() -> None:
    apps_root = Path(__file__).resolve().parents[2]
    api_root = apps_root / "api"
    for path in (str(api_root), str(apps_root)):
        if path not in sys.path:
            sys.path.insert(0, path)


def run_coro_blocking(coro) -> Any:
    """Run *coro* to completion from synchronous code.

    Safe both from plain threads (uses ``asyncio.run``) and from code that is
    accidentally executed inside a running event loop (runs on a helper
    thread so the outer loop is never re-entered).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


@asynccontextmanager
async def pg_session() -> AsyncIterator[Any]:
    """Yield an AsyncSession bound to a dedicated, loop-local engine.

    The engine uses NullPool and is disposed on exit, so no connection ever
    outlives the (possibly temporary) event loop it was created on.
    """
    _ensure_api_on_path()
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.database import _asyncpg_url_and_ssl

    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        try:
            from app.config import settings

            raw_url = (settings.database_url or "").strip()
        except Exception:
            raw_url = ""
    if not raw_url:
        raise RuntimeError("DATABASE_URL is required for pgvector retrieval")

    db_url, ssl_arg = _asyncpg_url_and_ssl(raw_url)
    connect_args: dict[str, Any] = {
        "server_settings": {"application_name": "quanthire-quantchat"},
        "command_timeout": 60,
        "timeout": 30,
    }
    if ssl_arg is not None:
        connect_args["ssl"] = ssl_arg

    engine = create_async_engine(db_url, poolclass=NullPool, connect_args=connect_args)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()
