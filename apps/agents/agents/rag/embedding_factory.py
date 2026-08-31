"""Embedding provider factory — local SentenceTransformer or Azure OpenAI."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def embedding_provider() -> str:
    """Return ``local`` or ``azure_openai``."""
    raw = os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
    if raw in ("azure_openai", "azure"):
        return "azure_openai"
    if raw in ("local", "bge", "sentence_transformers"):
        return "local"
    if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
        if is_azure_embeddings_configured():
            return "azure_openai"
    return raw or "local"


def create_azure_embeddings(**kwargs: Any) -> Any:
    """Build LangChain AzureOpenAIEmbeddings when Azure keys are present."""
    from langchain_openai import AzureOpenAIEmbeddings

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    deployment = os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
    ).strip()
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    dimensions = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    embed_kwargs: dict[str, Any] = {
        "azure_endpoint": endpoint,
        "azure_deployment": deployment,
        "api_version": api_version,
        "dimensions": dimensions,
        **kwargs,
    }
    if api_key:
        embed_kwargs["api_key"] = api_key
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        embed_kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
    return AzureOpenAIEmbeddings(**embed_kwargs)


def is_azure_embeddings_configured() -> bool:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if not endpoint:
        return False
    if os.getenv("AZURE_OPENAI_API_KEY", "").strip():
        return True
    try:
        import azure.identity  # noqa: F401

        return True
    except ImportError:
        return False
