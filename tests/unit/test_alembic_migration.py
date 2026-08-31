"""Alembic migration safety checks (audit Q13)."""

import importlib.util
from pathlib import Path

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "api"
    / "alembic"
    / "versions"
    / "migrate_embeddings_to_bge.py"
)


def test_embeddings_migration_source_skips_delete_for_768():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "vector(768)" in source
    assert "if candidate_vector_type == \"vector(768)\"" in source
    assert source.index("DELETE FROM candidate_embeddings") > source.index("vector(768)")
