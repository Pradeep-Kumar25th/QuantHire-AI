"""Embedding generation service — Azure OpenAI or local SentenceTransformer."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def _ensure_agents_path() -> None:
    agents_parent = Path(__file__).resolve().parents[3] / "agents"
    if agents_parent.is_dir() and str(agents_parent) not in sys.path:
        sys.path.insert(0, str(agents_parent))


class EmbeddingService:
    """Generate embeddings for candidate/job auxiliary vectors."""

    def __init__(self, model: str = "BAAI/bge-base-en-v1.5") -> None:
        self.model_name = model

    async def generate_embedding(self, text: str) -> List[float]:
        _ensure_agents_path()
        from agents.rag.unified_embeddings import encode_text

        # encode_text is sync (HTTP / local model) — keep the event loop free
        return await asyncio.to_thread(encode_text, text)

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        _ensure_agents_path()
        from agents.rag.unified_embeddings import encode_texts

        return await asyncio.to_thread(encode_texts, texts)
