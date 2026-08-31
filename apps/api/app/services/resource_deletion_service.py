"""Delete jobs and candidates with pgvector / embedding cleanup for QuantChat."""

from __future__ import annotations

import inspect
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.applications import Application
from app.models.candidates import Candidate, CandidateEmbedding
from app.models.document_chunks import DocumentChunk
from app.models.jobs import Job, JobEmbedding
from app.services.pgvector_ingestion import PgVectorIngestionService

logger = logging.getLogger(__name__)


def _job_document_ids(job: Job) -> set[str]:
    """Collect JD vector document ids linked to this job row."""
    metadata = job.extra_metadata or {}
    spec = job.spec_json if isinstance(job.spec_json, dict) else {}
    ids = {str(job.id)}
    for candidate in (
        metadata.get("document_id"),
        spec.get("id"),
        spec.get("job_id"),
        spec.get("milvus_id"),
        (spec.get("metadata") or {}).get("document_id") if isinstance(spec.get("metadata"), dict) else None,
    ):
        if candidate and str(candidate).strip():
            ids.add(str(candidate).strip())
    return ids


def _candidate_document_ids(candidate: Candidate) -> set[str]:
    """Collect resume vector document ids linked to this candidate."""
    profile = candidate.profile_json if isinstance(candidate.profile_json, dict) else {}
    source_meta = candidate.source_metadata if isinstance(candidate.source_metadata, dict) else {}
    ids = {str(candidate.id)}
    for candidate_id in (
        profile.get("id"),
        profile.get("resume_id"),
        source_meta.get("resume_id"),
        source_meta.get("document_id"),
    ):
        if candidate_id and str(candidate_id).strip():
            ids.add(str(candidate_id).strip())
    return ids


class ResourceDeletionService:
    """Centralized delete flows that keep Postgres and vector indexes in sync."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion = PgVectorIngestionService(session)

    async def count_job_applications(self, job_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.job_id == job_id)
        )
        return int(result.scalar_one() or 0)

    async def count_candidate_applications(self, candidate_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.candidate_id == candidate_id)
        )
        return int(result.scalar_one() or 0)

    async def purge_job_vectors(self, *, job: Job) -> int:
        removed = 0
        doc_ids = _job_document_ids(job)

        for doc_id in doc_ids:
            removed += await self.ingestion.delete_document(doc_id)

        result = await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.job_id == job.id)
        )
        removed += int(result.rowcount or 0)

        embed_result = await self.session.execute(
            delete(JobEmbedding).where(JobEmbedding.job_id == job.id)
        )
        removed += int(embed_result.rowcount or 0)

        await self.session.flush()
        logger.info(
            "Purged %s JD vector chunk(s) for job_id=%s",
            removed,
            job.id,
        )
        return removed

    async def purge_candidate_vectors(
        self,
        *,
        candidate_id: UUID,
        document_id: Optional[str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        extra_document_ids: Optional[set[str]] = None,
    ) -> int:
        removed = 0
        doc_ids = {str(candidate_id)}
        if document_id:
            doc_ids.add(str(document_id))
        if extra_document_ids:
            doc_ids.update(extra_document_ids)

        for doc_id in doc_ids:
            removed += await self.ingestion.delete_document(doc_id)

        result = await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.candidate_id == candidate_id)
        )
        removed += int(result.rowcount or 0)

        if name or email:
            await self.ingestion._dedupe_by_candidate(name or "Unknown", email or "")

        embed_result = await self.session.execute(
            delete(CandidateEmbedding).where(CandidateEmbedding.candidate_id == candidate_id)
        )
        removed += int(embed_result.rowcount or 0)

        await self.session.flush()
        logger.info(
            "Purged resume vectors/embeddings for candidate_id=%s (approx %s rows)",
            candidate_id,
            removed,
        )
        return removed

    async def delete_job(self, job: Job) -> dict:
        application_count = await self.count_job_applications(job.id)
        if application_count > 0:
            raise ValueError(
                f"Cannot delete job with {application_count} active application(s). "
                "Archive or reassign applications first."
            )

        chunks_removed = await self.purge_job_vectors(job=job)

        delete_result = self.session.delete(job)
        if inspect.isawaitable(delete_result):
            await delete_result
        await self.session.commit()

        return {
            "job_id": str(job.id),
            "chunks_removed": chunks_removed,
            "message": "Job and indexed JD content removed from QuantChat.",
        }

    async def delete_candidate(self, candidate: Candidate) -> dict:
        application_count = await self.count_candidate_applications(candidate.id)
        if application_count > 0:
            raise ValueError(
                f"Cannot remove candidate with {application_count} application(s) "
                "in the pipeline. Withdraw applications first."
            )

        profile = candidate.profile_json or {}
        doc_ids = _candidate_document_ids(candidate)
        primary_document_id = (
            profile.get("id") or profile.get("resume_id") or str(candidate.id)
        )
        chunks_removed = await self.purge_candidate_vectors(
            candidate_id=candidate.id,
            document_id=str(primary_document_id),
            name=candidate.name,
            email=candidate.email,
            extra_document_ids=doc_ids,
        )

        candidate.is_active = False
        candidate.deletion_requested = True
        await self.session.commit()

        return {
            "candidate_id": str(candidate.id),
            "chunks_removed": chunks_removed,
            "message": "Candidate removed from talent pool and QuantChat index.",
        }
