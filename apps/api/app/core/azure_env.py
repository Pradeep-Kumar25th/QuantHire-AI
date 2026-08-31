"""Sync Azure Non-Prod settings into process env for the shared agents LLM layer."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def sync_azure_env_from_settings(settings: Settings) -> None:
    """Publish API settings to os.environ without overriding explicit env vars."""
    pairs: dict[str, str | None] = {
        "DEPLOYMENT_TARGET": settings.deployment_target,
        "LLM_PROVIDER": settings.llm_provider,
        "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
        "AZURE_OPENAI_API_VERSION": settings.azure_openai_api_version,
        "AZURE_OPENAI_CHAT_DEPLOYMENT": settings.azure_openai_chat_deployment,
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": settings.azure_openai_embedding_deployment,
        "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
        "AZURE_STORAGE_CONNECTION_STRING": settings.azure_storage_connection_string,
        "AZURE_STORAGE_ACCOUNT_NAME": settings.azure_storage_account_name,
        "AZURE_STORAGE_CONTAINER": settings.azure_storage_container,
        "AZURE_STORAGE_CONTAINER_PROCESSED": settings.azure_storage_container_processed,
        "AZURE_STORAGE_BLOB_ENDPOINT": settings.azure_storage_blob_endpoint,
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": settings.azure_document_intelligence_endpoint,
        "AZURE_DOCUMENT_INTELLIGENCE_MODEL": settings.azure_document_intelligence_model,
        "AZURE_DOCUMENT_INTELLIGENCE_API_KEY": settings.azure_document_intelligence_api_key,
        "STORAGE_TYPE": settings.storage_backend,
        "VECTOR_STORE": settings.vector_store_type,
        "VECTOR_STORE_TYPE": settings.vector_store_type,
        "MILVUS_ENABLED": "false" if not settings.milvus_enabled else "true",
        "MILVUS_AUTO_LOAD": "false" if not settings.milvus_auto_load else "true",
        "DATABASE_URL": settings.database_url,
        "EMBEDDING_PROVIDER": "azure_openai"
        if settings.is_azure_nonprod
        else os.getenv("EMBEDDING_PROVIDER"),
        "EMBEDDING_DIMENSION": os.getenv("EMBEDDING_DIMENSION", "768"),
        "LANGGRAPH_CHECKPOINT_BACKEND": "memory" if settings.is_azure_nonprod else None,
    }

    for key, value in pairs.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            os.environ.setdefault(key, text)

    if settings.llm_provider == "azure_openai":
        os.environ.setdefault("LLM_MODEL", settings.azure_openai_chat_deployment)
        os.environ.setdefault("LLM_MODEL_NAME", settings.azure_openai_chat_deployment)
        os.environ.setdefault("OPENAI_MODEL", settings.azure_openai_chat_deployment)

    if settings.azure_document_intelligence_enabled:
        os.environ.setdefault("AZURE_DOCUMENT_INTELLIGENCE_ENABLED", "true")
    else:
        os.environ.setdefault("AZURE_DOCUMENT_INTELLIGENCE_ENABLED", "false")
