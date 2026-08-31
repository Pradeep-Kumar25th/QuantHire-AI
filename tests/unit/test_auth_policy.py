"""Auth policy unit tests."""

from app.core.auth_policy import auth_enforced, basic_auth_enforced


def test_auth_not_enforced_locally(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("AUTH_MODE", "none")
    from app.config import Settings

    settings = Settings()
    assert settings.auth_mode == "none"
    assert auth_enforced() is False
    assert basic_auth_enforced() is False


def test_auth_enforced_on_azure_nonprod(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TARGET", "azure-nonprod")
    monkeypatch.delenv("AUTH_MODE", raising=False)
    from app.config import Settings

    settings = Settings()
    assert settings.auth_mode == "basic"
    assert auth_enforced() is True


def test_auth_enforced_when_basic_mode(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("AUTH_MODE", "basic")
    from app.config import Settings

    Settings()
    assert auth_enforced() is True
