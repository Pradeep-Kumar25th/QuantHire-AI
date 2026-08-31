"""
PgVector Retriever
==================

Semantic search over document_chunks when Milvus is disabled (Azure / pgvector).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from .pg_async import pg_session, run_coro_blocking

logger = logging.getLogger(__name__)


def _apps_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_api_path() -> None:
    apps_root = _apps_root()
    api_root = apps_root / "api"
    for path in (str(api_root), str(apps_root)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _ensure_agents_path() -> None:
    agents_parent = _apps_root() / "agents"
    if agents_parent.is_dir() and str(agents_parent) not in sys.path:
        sys.path.insert(0, str(agents_parent))


def _filter_kwargs(filters: Dict[str, Any]) -> Dict[str, Any]:
    entity_names = filters.get("entity_names") or []
    return {
        "document_type": filters.get("document_type"),
        "entity_name": (
            filters.get("entity_name")
            or filters.get("candidate_name")
            or (entity_names[0] if len(entity_names) == 1 else None)
        ),
        "entity_names": entity_names if len(entity_names) > 1 else None,
        "document_id": filters.get("document_id"),
        "section_type": filters.get("section_type"),
    }


class PgVectorRetriever:
    """Retrieve RAG chunks from Postgres pgvector."""

    def retrieve(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return run_coro_blocking(self._retrieve_async(query, filters or {}))

    async def _retrieve_async(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        _ensure_api_path()
        _ensure_agents_path()
        from agents.rag.unified_embeddings import encode_text
        from app.services.pgvector_ingestion import PgVectorIngestionService

        filter_kwargs = _filter_kwargs(filters)
        query_emb = encode_text(query)
        limit = int(os.getenv("MAX_CHUNKS_PER_RETRIEVER", "200"))

        async with pg_session() as session:
            service = PgVectorIngestionService(session)
            rows = await service.search_chunks(
                query_emb,
                top_k=limit,
                **filter_kwargs,
            )
            # Do not broaden entity filters — that can return stale chunks from other JDs.
            if not rows and filter_kwargs.get("document_id"):
                logger.info(
                    "PgVector document_id filter returned 0 rows for %s",
                    filter_kwargs.get("document_id"),
                )

        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "document_id": row["document_id"],
                    "document_type": row["document_type"],
                    "entity_name": row["entity_name"],
                    "section_type": row["section_type"],
                    "chunk_text": row["chunk_text"],
                    "full_content": row["full_content"],
                    "score": row["score"],
                    "retriever": "pgvector",
                }
            )
        return results
