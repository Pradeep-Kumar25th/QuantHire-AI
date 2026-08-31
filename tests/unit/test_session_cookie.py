"""Session cookie security tests."""

from starlette.responses import Response

from app.core import session_cookie
from app.core.session_cookie import (
    SESSION_COOKIE_NAME,
    attach_session_cookies,
    clear_session_cookies,
    should_omit_token_from_body,
)


def test_attach_session_cookies_sets_httponly(monkeypatch):
    monkeypatch.setattr(session_cookie, "_cookie_secure", lambda: True)
    response = Response()
    attach_session_cookies(response, "jwt-token-value")
    raw = response.headers.get("set-cookie") or ""
    assert SESSION_COOKIE_NAME in raw
    assert "httponly" in raw.lower()


def test_clear_session_cookies(monkeypatch):
    monkeypatch.setattr(session_cookie, "_cookie_secure", lambda: False)
    response = Response()
    clear_session_cookies(response)
    assert "set-cookie" in response.headers


def test_should_omit_token_from_body_when_hardened(monkeypatch):
    monkeypatch.setattr(session_cookie, "_cookie_secure", lambda: True)
    assert should_omit_token_from_body() is True
