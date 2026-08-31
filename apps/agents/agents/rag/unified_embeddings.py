"""Unified embedding encoder for pgvector (local BGE or Azure OpenAI Foundry)."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))
LOCAL_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

_local_encoder = None
_azure_embeddings = None


def active_embedding_provider() -> str:
    from agents.rag.embedding_factory import embedding_provider

    return embedding_provider()


def embedding_model_label() -> str:
    if active_embedding_provider() == "azure_openai":
        deployment = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
        ).strip()
        return f"azure_openai:{deployment}"
    return LOCAL_EMBEDDING_MODEL


def _get_local_encoder():
    global _local_encoder
    if _local_encoder is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model: %s", LOCAL_EMBEDDING_MODEL)
        _local_encoder = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    return _local_encoder


def _get_azure_embeddings():
    global _azure_embeddings
    if _azure_embeddings is None:
        from agents.rag.embedding_factory import create_azure_embeddings

        _azure_embeddings = create_azure_embeddings(dimensions=EMBEDDING_DIMENSION)
        logger.info(
            "Azure OpenAI embeddings ready (deployment=%s, dimensions=%s)",
            os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            EMBEDDING_DIMENSION,
        )
    return _azure_embeddings


def encode_texts(
    texts: List[str],
    *,
    show_progress_bar: bool = False,
) -> List[List[float]]:
    """Encode one or more texts to vectors for pgvector storage/search."""
    cleaned = [(t or "").replace("\n", " ").strip() for t in texts]
    if not cleaned or not any(cleaned):
        raise ValueError("No text provided for embedding")

    provider = active_embedding_provider()
    if provider == "azure_openai":
        client = _get_azure_embeddings()
        vectors = client.embed_documents(cleaned)
        return [list(map(float, v)) for v in vectors]

    encoder = _get_local_encoder()
    embeddings = encoder.encode(cleaned, show_progress_bar=show_progress_bar)
    return [emb.tolist() for emb in embeddings]


def encode_text(text: str, *, show_progress_bar: bool = False) -> List[float]:
    return encode_texts([text], show_progress_bar=show_progress_bar)[0]
