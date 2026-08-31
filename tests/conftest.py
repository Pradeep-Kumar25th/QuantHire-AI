"""Shared pytest configuration."""

import os

import pytest

# Isolate pytest from developer .env (Azure DATABASE_URL, DEPLOYMENT_TARGET, etc.)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("AUTH_MODE", "none")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")
os.environ.setdefault("DEPLOYMENT_TARGET", "local")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("AUTH_MODE", "none")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-32-chars-minimum")
    os.environ.setdefault("DEPLOYMENT_TARGET", "local")


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
