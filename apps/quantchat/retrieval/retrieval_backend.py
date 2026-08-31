"""Unified vector retrieval backend selection for ingest and read paths."""

from __future__ import annotations

import os


def use_pgvector_retrieval() -> bool:
    """Return True when QuantChat should use Postgres pgvector instead of Milvus."""
    deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
    if deployment in ("azure-nonprod", "production", "prod", "staging"):
        return True

    vector_store = (
        os.getenv("VECTOR_STORE") or os.getenv("VECTOR_STORE_TYPE") or ""
    ).strip().lower()
    if vector_store == "pgvector":
        return True
    if vector_store == "milvus":
        return False

    try:
        import sys
        from pathlib import Path

        api_root = Path(__file__).resolve().parents[2] / "api"
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))
        from app.config import settings

        return settings.use_pgvector_pipeline
    except Exception:
        pass

    milvus_enabled = os.getenv("MILVUS_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    return not milvus_enabled
