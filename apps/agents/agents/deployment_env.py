"""Deployment environment helpers shared by JD generation agents."""

from __future__ import annotations

import os


def deployment_target() -> str:
    return os.getenv("DEPLOYMENT_TARGET", "").strip().lower()


def is_azure_nonprod() -> bool:
    return deployment_target() == "azure-nonprod"


def vector_store_type() -> str:
    return (
        os.getenv("VECTOR_STORE", "").strip().lower()
        or os.getenv("VECTOR_STORE_TYPE", "").strip().lower()
    )


def milvus_enabled() -> bool:
    return os.getenv("MILVUS_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def should_skip_local_vector_storage() -> bool:
    """Skip in-workflow Milvus/embeddings when API handles pgvector persistence."""
    if is_azure_nonprod():
        return True
    if not milvus_enabled():
        return True
    return vector_store_type() == "pgvector"
