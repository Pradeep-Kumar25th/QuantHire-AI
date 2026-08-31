"""Azure Non-Prod JD pipeline: structured JD JSON → Postgres + pgvector."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import Job, JobStatus
from app.services.pgvector_ingestion import PgVectorIngestionService

logger = logging.getLogger(__name__)


def _location_to_str(value: Any) -> Optional[str]:
    """Map structured JD location JSON to jobs.location (VARCHAR)."""
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        return text_value or None
    if isinstance(value, dict):
        city = str(value.get("city") or "").strip()
        country = str(value.get("country") or "").strip()
        work_model = str(value.get("work_model") or "").strip()
        parts = [part for part in (city, country) if part]
        text_value = ", ".join(parts)
        if work_model:
            text_value = f"{text_value} ({work_model})" if text_value else work_model
        return text_value or None
    text_value = str(value).strip()
    return text_value or None


def _requirements_to_str(jd_data: Dict[str, Any]) -> str:
    """Map structured qualifications to jobs.requirements (TEXT)."""
    rq = jd_data.get("required_qualifications")
    if isinstance(rq, dict):
        lines: list[str] = []
        for key, val in rq.items():
            label = str(key).replace("_", " ").strip().title()
            if isinstance(val, list):
                items = ", ".join(str(item) for item in val if item)
                if items:
                    lines.append(f"{label}: {items}")
            elif val:
                lines.append(f"{label}: {val}")
        if lines:
            return "\n".join(lines)[:50000]
    if isinstance(rq, list):
        return "\n".join(str(item) for item in rq if item)[:50000]
    if rq:
        return str(rq)[:50000]
    fallback = jd_data.get("requirements")
    if fallback:
        return str(fallback)[:50000]
    return ""


def _job_level_from_jd(jd_data: Dict[str, Any]) -> str:
    """Resolve job level from enterprise JD metadata."""
    metadata = jd_data.get("metadata")
    if isinstance(metadata, dict):
        level = metadata.get("job_level")
        if level:
            return str(level).strip()[:100]
    level = jd_data.get("job_level")
    if level:
        return str(level).strip()[:100]
    return ""


def _department_display_from_jd(jd_data: Dict[str, Any]) -> str:
    """Build a card-friendly department label from enterprise org fields."""
    import re

    department = str(jd_data.get("department") or "").strip()
    team = str(jd_data.get("team") or "").strip()
    division = str(jd_data.get("division") or "").strip()
    business_unit = str(jd_data.get("business_unit") or "").strip()
    metadata = jd_data.get("metadata")
    if isinstance(metadata, dict) and not business_unit:
        business_unit = str(metadata.get("business_unit") or "").strip()

    if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", department):
        parts = [department]
        if business_unit or division:
            parts.append(business_unit or division)
        return " / ".join(parts)[:100]

    parts = [part for part in (department, team, division or business_unit) if part]
    return " / ".join(parts)[:100] or department[:100] or ""


def _remote_allowed_from_jd(jd_data: Dict[str, Any]) -> bool:
    if jd_data.get("remote_allowed") is True:
        return True
    location = jd_data.get("location")
    if isinstance(location, dict):
        work_model = str(location.get("work_model") or "").lower()
        return work_model in ("remote", "hybrid")
    return False


def _parse_uuid(value: Optional[str]) -> Optional[UUID]:
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


class JDPipelineService:
    """Persist job descriptions for RAG and job matching on pgvector."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion = PgVectorIngestionService(session)

    async def _find_job_for_document(
        self,
        document_id: str,
        hint_id: Optional[UUID] = None,
    ) -> Optional[Job]:
        """Resolve the jobs row for a vector document id (supports legacy metadata links)."""
        if hint_id:
            job = await self.session.get(Job, hint_id)
            if job:
                return job

        doc_uuid = _parse_uuid(document_id)
        if doc_uuid:
            job = await self.session.get(Job, doc_uuid)
            if job:
                return job

        result = await self.session.execute(
            text(
                """
                SELECT id FROM jobs
                WHERE metadata->>'document_id' = :document_id
                LIMIT 1
                """
            ),
            {"document_id": str(document_id)},
        )
        row = result.first()
        if row:
            return await self.session.get(Job, row[0])

        return None

    async def store_jd(
        self,
        *,
        jd_data: Dict[str, Any],
        created_by: Optional[UUID] = None,
        job_row_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        document_id = jd_data.get("id") or str(job_row_id or uuid4())
        jd_data = {**jd_data, "id": document_id}

        job_title = jd_data.get("job_title") or jd_data.get("title") or "Untitled Role"
        department = _department_display_from_jd(jd_data) or str(jd_data.get("department") or "").strip()
        job_level = _job_level_from_jd(jd_data)
        description = jd_data.get("position_summary") or jd_data.get("raw_jd") or ""
        if isinstance(description, list):
            description = "\n".join(str(x) for x in description)

        location_text = _location_to_str(jd_data.get("location"))
        requirements_text = _requirements_to_str(jd_data)
        remote_allowed = _remote_allowed_from_jd(jd_data)

        job_uuid: Optional[UUID] = None
        existing_job = await self._find_job_for_document(
            str(document_id),
            hint_id=job_row_id,
        )
        if existing_job:
            existing_job.title = job_title
            existing_job.level = job_level
            existing_job.department = department
            existing_job.location = location_text
            existing_job.remote_allowed = remote_allowed
            existing_job.description = str(description)[:50000]
            existing_job.spec_json = jd_data
            existing_job.requirements = requirements_text
            metadata = dict(existing_job.extra_metadata or {})
            metadata.update(
                {
                    "pipeline": "azure_pgvector",
                    "document_id": str(document_id),
                }
            )
            existing_job.extra_metadata = metadata
            job_uuid = existing_job.id
            logger.info(
                "Updating existing job row %s for document_id=%s",
                job_uuid,
                document_id,
            )
        elif created_by:
            preferred_id = _parse_uuid(str(document_id)) or job_row_id or uuid4()
            job = Job(
                id=preferred_id,
                title=job_title,
                level=job_level,
                department=department,
                location=location_text,
                remote_allowed=remote_allowed,
                description=str(description)[:50000],
                requirements=requirements_text,
                spec_json=jd_data,
                status=JobStatus.DRAFT,
                created_by=created_by,
                extra_metadata={
                    "pipeline": "azure_pgvector",
                    "document_id": str(document_id),
                },
            )
            self.session.add(job)
            await self.session.flush()
            job_uuid = job.id
            logger.info(
                "Created job row %s aligned with document_id=%s",
                job_uuid,
                document_id,
            )

        stored_id = await self.ingestion.add_jd(jd_data, job_id=job_uuid)
        await self.session.commit()

        effective_job_id = str(job_uuid or document_id)
        return {
            "success": True,
            "job_id": effective_job_id,
            "postgres_job_id": str(job_uuid) if job_uuid else None,
            "storage_backend": "pgvector",
            "message": f"Job description saved to Postgres pgvector (ID: {effective_job_id})",
        }
