"""Auth policy helpers for basic auth (v1) vs future Entra."""

from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from app.config import get_settings
from app.core.deps import get_current_user


def auth_enforced() -> bool:
    """True when API routes must require a valid JWT."""
    settings = get_settings()
    if settings.auth_mode == "basic":
        return True
    if settings.is_azure_nonprod:
        return True
    return False


def basic_auth_enforced() -> bool:
    """Backward-compatible alias."""
    return auth_enforced()


async def require_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """
    Default-deny authentication for protected routers.

    When auth is enforced, every route on the router must present a valid JWT.
    Use ``allow_anonymous_user`` on specific public endpoints (login, health).
    """
    if not auth_enforced():
        return None
    return await get_current_user(request, authorization)


async def require_user_when_basic_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """Require JWT when auth is enforced (alias for route-level Depends)."""
    return await require_authenticated_user(request, authorization)


async def allow_anonymous_user() -> None:
    """Explicit opt-out for public routes on otherwise protected routers."""
    return None
