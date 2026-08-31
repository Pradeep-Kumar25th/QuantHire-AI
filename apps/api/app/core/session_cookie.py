"""HttpOnly session cookie helpers (mitigates H-1: token in localStorage)."""

from __future__ import annotations

from fastapi import Response

from app.config import settings

SESSION_COOKIE_NAME = "quanthire_session"
AUTH_FLAG_COOKIE_NAME = "quanthire_auth"


def session_cookie_max_age() -> int:
    return int(settings.jwt_expiration_hours * 3600)


def _cookie_secure() -> bool:
    return settings.is_hardened


def attach_session_cookies(response: Response, access_token: str) -> None:
    """Set HttpOnly JWT session cookie (+ non-sensitive auth flag for Next.js middleware)."""
    max_age = session_cookie_max_age()
    secure = _cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=AUTH_FLAG_COOKIE_NAME,
        value="1",
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=max_age,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    """Remove session cookies on logout."""
    secure = _cookie_secure()
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite="strict",
    )
    response.delete_cookie(
        AUTH_FLAG_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite="strict",
    )


def should_omit_token_from_body() -> bool:
    """In hardened envs, JWT is cookie-only — not returned in JSON."""
    return _cookie_secure()
