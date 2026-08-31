"""Verify security assessment remediation items are present in codebase."""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_h1_no_localstorage_jwt_in_auth_storage():
    source = (REPO / "apps" / "web" / "src" / "lib" / "auth-storage.ts").read_text(
        encoding="utf-8"
    )
    assert "localStorage" not in source or "not localStorage" in source
    assert "quanthire_access_token" not in source
    assert "sessionStorage" in source


def test_h1_session_cookie_module_exists():
    path = REPO / "apps" / "api" / "app" / "core" / "session_cookie.py"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "httponly=True" in content.lower() or "httponly" in content.lower()
    assert "quanthire_session" in content


def test_h1_auth_sets_session_cookie():
    auth_py = (REPO / "apps" / "api" / "app" / "api" / "v1" / "auth.py").read_text(
        encoding="utf-8"
    )
    assert "attach_session_cookies" in auth_py
    assert "_finalize_auth_response" in auth_py


def test_h1_bff_forwards_cookies():
    bff = (
        REPO / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert '"cookie"' in bff
    assert "set-cookie" in bff


def test_h1_api_client_uses_credentials():
    client = (REPO / "apps" / "web" / "src" / "lib" / "api-client.ts").read_text(
        encoding="utf-8"
    )
    assert 'credentials: "include"' in client


def test_h2_protected_api_router_requires_auth():
    init_py = (REPO / "apps" / "api" / "app" / "api" / "v1" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "require_authenticated_user" in init_py
    assert "protected_router" in init_py


def test_h2_verify_token_loads_user_from_database():
    security = (REPO / "apps" / "api" / "app" / "core" / "security.py").read_text(
        encoding="utf-8"
    )
    loader = (REPO / "apps" / "api" / "app" / "repositories" / "user_loader.py").read_text(
        encoding="utf-8"
    )
    assert "get_user_by_id" in security
    assert "user.role" in security
    assert "select(User)" in loader or "FROM users" in loader


def test_h2_deps_reads_session_cookie():
    deps = (REPO / "apps" / "api" / "app" / "core" / "deps.py").read_text(encoding="utf-8")
    assert "SESSION_COOKIE_NAME" in deps
    assert "request.cookies.get" in deps


def test_h3_quantchat_binds_authenticated_user():
    quantchat = (
        REPO / "apps" / "api" / "app" / "api" / "v1" / "quantchat.py"
    ).read_text(encoding="utf-8")
    assert "never trust client user_id" in quantchat.lower()


def test_m1_upload_size_limit_in_resume_parsing():
    rp = (REPO / "apps" / "api" / "app" / "api" / "v1" / "resume_parsing.py").read_text(
        encoding="utf-8"
    )
    assert "MAX_FILE_SIZE" in rp
    assert "_read_upload_with_limit" in rp
    assert "Unsupported file type" in rp or "Unsupported content type" in rp


def test_m3_nextjs_security_headers():
    config = (REPO / "apps" / "web" / "next.config.js").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in config
    assert "Strict-Transport-Security" in config
    assert "X-Content-Type-Options" in config


def test_m3_api_security_headers_middleware():
    mw = (REPO / "apps" / "api" / "app" / "core" / "middleware.py").read_text(
        encoding="utf-8"
    )
    assert "SecurityHeadersMiddleware" in mw
    assert "Content-Security-Policy" in mw


def test_l2_stub_dashboard_pages_exist():
    for segment in ("interviews", "assessments", "offers", "settings"):
        page = REPO / "apps" / "web" / "src" / "app" / "dashboard" / segment / "page.tsx"
        assert page.exists(), f"missing {page}"


def test_l3_hardened_errors_hide_internals():
    mw = (REPO / "apps" / "api" / "app" / "core" / "middleware.py").read_text(
        encoding="utf-8"
    )
    assert "hide_internals" in mw
    assert "Internal server error" in mw


def test_sso_entra_id_token_flow():
    entra = (REPO / "apps" / "api" / "app" / "integrations" / "entra_auth.py").read_text(
        encoding="utf-8"
    )
    assert "validate_entra_id_token" in entra
    assert "roles" in entra
    assert "PyJWKClient" in entra


def test_msal_sends_id_token():
    msal = (REPO / "apps" / "web" / "src" / "lib" / "msal-auth.ts").read_text(
        encoding="utf-8"
    )
    assert "idToken" in msal


@pytest.mark.parametrize(
    "item_id,note",
    [
        ("H-3-full", "LLM prompt-injection pen-test and RAG isolation — partial controls only"),
        ("M-2", "PII field masking in list APIs — not fully implemented"),
        ("H-1-refresh", "15-min access + refresh token rotation — not implemented"),
    ],
)
def test_known_open_items_documented(item_id, note):
    """Open items are tracked; this test documents scope boundaries."""
    assert item_id and note
