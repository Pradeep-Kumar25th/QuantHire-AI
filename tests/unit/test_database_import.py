"""Ensure database module imports cleanly (SyntaxError regression)."""


def test_database_module_imports():
    from app.database import create_engine, engine, check_db_health  # noqa: F401

    assert create_engine is not None


def test_async_engine_created_for_nonprod_with_database_url(monkeypatch):
    """Sync QueuePool on create_async_engine silently broke hardened startup."""
    postgres_url = (
        "postgresql+asyncpg://user:pass@localhost:5432/quanthire_ai?sslmode=require"
    )
    monkeypatch.setenv("DATABASE_URL", postgres_url)
    monkeypatch.setenv("APP_ENV", "nonprod")
    monkeypatch.setenv("DEPLOYMENT_TARGET", "azure-nonprod")
    monkeypatch.setenv("DEBUG", "false")

    from app.config import get_settings, settings

    get_settings.cache_clear()
    monkeypatch.setattr(settings, "database_url", postgres_url)

    from app.database import create_engine as build_engine

    built = build_engine()
    assert built is not None, "async engine must be created for nonprod when DATABASE_URL is set"


def test_azure_nonprod_skips_uuid_ossp_in_init_db():
    """Azure Postgres does not allow-list uuid-ossp; app uses Python uuid4."""
    from pathlib import Path

    content = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "database.py"
    text = content.read_text(encoding="utf-8")
    assert "if settings.is_azure_nonprod:" in text
    assert "skipping uuid-ossp/pg_trgm" in text


def test_check_db_health_does_not_await_result_close():
    """Regression: await result.close() breaks async health check (returns None)."""
    from pathlib import Path

    content = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "database.py"
    text = content.read_text(encoding="utf-8")
    assert "await result.close()" not in text
    assert "conn.scalar" in text

