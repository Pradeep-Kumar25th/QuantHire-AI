"""Lazy QueryRouter initialization shared by QuantChat and resume analysis."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_query_router: Any = None
QUERY_ROUTER_AVAILABLE = False
QUERY_ROUTER_INIT_ERROR: Optional[str] = None


def ensure_query_router():
    """Return the QueryRouter singleton, initializing on first successful call."""
    global _query_router, QUERY_ROUTER_AVAILABLE, QUERY_ROUTER_INIT_ERROR

    if _query_router is not None:
        return _query_router

    try:
        from apps.quantchat import get_query_router

        _query_router = get_query_router()
        QUERY_ROUTER_AVAILABLE = True
        QUERY_ROUTER_INIT_ERROR = None
        logger.info("QueryRouter initialized")
    except Exception as exc:
        QUERY_ROUTER_AVAILABLE = False
        QUERY_ROUTER_INIT_ERROR = str(exc)
        logger.error(
            "Failed to initialize QueryRouter singleton: %s",
            exc,
            exc_info=True,
        )

    return _query_router
