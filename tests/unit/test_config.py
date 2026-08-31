"""Config hardening unit tests."""

from app.config import Settings


def test_is_hardened_for_nonprod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "nonprod")
    settings = Settings()
    assert settings.is_hardened is True
    assert settings.is_development is False


def test_is_development_for_local(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    settings = Settings()
    assert settings.is_development is True
    assert settings.is_hardened is False
