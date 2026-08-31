"""Blocker regression tests (audit CRITICAL items)."""

from fastapi.testclient import TestClient


def test_sse_accepts_access_token_query_param(monkeypatch):
    """EventSource cannot send Authorization — query token must work for match-stream."""
    monkeypatch.setenv("AUTH_MODE", "basic")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/api/v1/job-matching/match-stream",
        params={"candidate_id": "c1", "jd_id": "j1", "access_token": "not-a-valid-jwt"},
    )
    # Invalid token → 401, not 422 missing header
    assert response.status_code == 401


def test_protected_jobs_return_401_without_token(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "basic")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    client = TestClient(app)
    response = client.get("/api/v1/jobs/")
    assert response.status_code == 401


def test_login_is_public_without_token(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "basic")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    async def _no_user(_db, _email):
        return None

    monkeypatch.setattr("app.api.v1.auth.get_user_by_email", _no_user)

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong"},
    )
    assert response.status_code in (401, 422)


def test_gdpr_export_not_fake_success(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "basic")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    client = TestClient(app)
    response = client.post("/api/v1/gdpr/export")
    assert response.status_code in (401, 501)
    if response.status_code == 501:
        assert "not implemented" in response.json()["detail"].lower()


def test_azure_nonprod_allows_bff_cluster_host(monkeypatch):
    """BFF calls backend with Kubernetes service DNS — must not 400."""
    monkeypatch.setenv("APP_ENV", "nonprod")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "azure-nonprod")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    client = TestClient(app)
    response = client.get(
        "/healthz",
        headers={"Host": "quanthire-backend.quanthire-nonprod.svc.cluster.local"},
    )
    assert response.status_code == 200


def test_k8s_probes_use_localhost_host_header(monkeypatch):
    """Kubelet probes must pass TrustedHostMiddleware (Host: Pod IP otherwise fails)."""
    monkeypatch.setenv("APP_ENV", "nonprod")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "azure-nonprod")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    client = TestClient(app)
    response = client.get("/healthz", headers={"Host": "localhost"})
    assert response.status_code == 200
    response = client.get("/readyz", headers={"Host": "localhost"})
    assert response.status_code in (200, 503)
