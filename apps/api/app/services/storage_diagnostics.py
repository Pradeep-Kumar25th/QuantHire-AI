"""Vector store diagnostics for Azure pgvector and legacy Milvus paths."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


async def get_pgvector_stats(session: AsyncSession) -> Dict[str, Any]:
    """Return document counts from Postgres pgvector tables."""
    try:
        resume_result = await session.execute(
            text(
                "SELECT COUNT(DISTINCT document_id) FROM document_chunks "
                "WHERE document_type = 'resume'"
            )
        )
        jd_result = await session.execute(
            text(
                "SELECT COUNT(DISTINCT document_id) FROM document_chunks "
                "WHERE document_type IN ('job_description', 'jd')"
            )
        )
        num_resumes = int(resume_result.scalar() or 0)
        num_jds = int(jd_result.scalar() or 0)
        return {
            "connected": True,
            "storage_backend": "pgvector",
            "num_resumes": num_resumes,
            "num_jds": num_jds,
            "num_entities": num_resumes + num_jds,
        }
    except Exception as exc:
        logger.warning("pgvector diagnostics failed: %s", exc)
        return {
            "connected": False,
            "storage_backend": "pgvector",
            "num_resumes": 0,
            "num_jds": 0,
            "num_entities": 0,
            "error": str(exc),
        }


def get_milvus_collection_stats(
    *,
    resume_collection: Optional[str] = None,
    jd_collection: Optional[str] = None,
) -> Dict[str, Any]:
    """Return Milvus collection stats for legacy local dev."""
    from apps.quantchat.config.settings import JD_COLLECTION, RESUME_COLLECTION

    resume_collection = resume_collection or RESUME_COLLECTION
    jd_collection = jd_collection or JD_COLLECTION

    status: Dict[str, Any] = {
        "connected": False,
        "storage_backend": "milvus",
        "num_resumes": 0,
        "num_jds": 0,
        "num_entities": 0,
        "resume_collection": resume_collection,
        "jd_collection": jd_collection,
    }

    try:
        from pymilvus import Collection, connections, utility

        if not connections.has_connection("default"):
            return status

        status["connected"] = True
        if utility.has_collection(resume_collection):
            collection = Collection(resume_collection)
            status["num_resumes"] = collection.num_entities
        if utility.has_collection(jd_collection):
            collection = Collection(jd_collection)
            status["num_jds"] = collection.num_entities
        status["num_entities"] = status["num_resumes"] + status["num_jds"]
    except Exception as exc:
        status["error"] = str(exc)
        logger.warning("Milvus diagnostics failed: %s", exc)

    return status


async def get_vector_store_stats(session: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Unified vector store stats for status endpoints."""
    if settings.use_pgvector_pipeline:
        if session is None:
            return {
                "connected": False,
                "storage_backend": "pgvector",
                "error": "database session required for pgvector diagnostics",
            }
        return await get_pgvector_stats(session)

    return get_milvus_collection_stats()
