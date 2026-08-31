"""Azure Non-Prod resume pipeline: Blob → DI → LLM parse → Postgres + pgvector."""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.parsing.agent import ParsingAgent
from agents.rag.embeddings import EmbeddingService
from app.config import settings
from app.models.candidates import Candidate, CandidateEmbedding
from app.services.pgvector_ingestion import PgVectorIngestionService
from app.services.resume_profile_converter import (
    _estimate_total_years,
    parsing_agent_to_resume_format,
)

logger = logging.getLogger(__name__)

_parsing_agent: ParsingAgent | None = None
_parsing_agent_lock = threading.Lock()


def get_parsing_agent() -> ParsingAgent:
    """Return a process-wide ParsingAgent instance."""
    global _parsing_agent
    if _parsing_agent is None:
        with _parsing_agent_lock:
            if _parsing_agent is None:
                logger.info("Initializing ParsingAgent singleton")
                _parsing_agent = ParsingAgent()
    return _parsing_agent


def _is_real_email(email: str) -> bool:
    text = (email or "").strip().lower()
    if not text or "@" not in text:
        return False
    if text.endswith("@upload.local") or text.startswith("unknown-"):
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text))


class ResumePipelineService:
    """End-to-end resume processing for pgvector / Azure Non-Prod."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.parsing_agent = get_parsing_agent()
        self.ingestion = PgVectorIngestionService(session)
        self.embedding_service = EmbeddingService()

    async def parse_and_store(
        self,
        *,
        resume_text: str,
        resume_id: str,
        raw_blob_ref: Optional[str] = None,
        pdf_extraction_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not resume_text or len(resume_text.strip()) < 50:
            raise ValueError("Resume text is empty or too short to parse")

        parse_result = await self.parsing_agent.run_with_tracking({"resume_text": resume_text})
        if not parse_result.success:
            raise ValueError(parse_result.error or "Resume parsing failed")

        flat_parsed = parse_result.output
        from app.services.resume_completeness import enrich_parsed_for_enterprise

        flat_parsed, completeness = enrich_parsed_for_enterprise(resume_text, flat_parsed)
        total_years = _estimate_total_years(
            (flat_parsed.get("experience") or []) + (flat_parsed.get("internships") or [])
        )
        flat_parsed["total_years_experience"] = total_years

        parsed_data = parsing_agent_to_resume_format(
            flat_parsed,
            resume_id=resume_id,
            resume_text=resume_text,
            parsing_method="ENTERPRISE_PARSING_AGENT",
        )
        if pdf_extraction_method:
            parsed_data["pdf_extraction_method"] = pdf_extraction_method
        if raw_blob_ref:
            parsed_data["raw_blob_ref"] = raw_blob_ref

        emails = flat_parsed.get("emails") or []
        phones = flat_parsed.get("phones") or []
        locations = flat_parsed.get("locations") or []
        ambiguous = flat_parsed.get("ambiguous_fields") or []

        candidate, updated_existing = await self._upsert_candidate(
            flat_parsed=flat_parsed,
            resume_id=resume_id,
            resume_text=resume_text,
            emails=emails,
            phones=phones,
            locations=locations,
            ambiguous=ambiguous,
            raw_blob_ref=raw_blob_ref,
            pdf_extraction_method=pdf_extraction_method,
        )

        parsed_data["id"] = str(candidate.id)
        document_id = await self.ingestion.add_resume(
            parsed_data,
            candidate_id=candidate.id,
        )
        parsed_data["candidate_id"] = str(candidate.id)

        await self._store_candidate_embedding(candidate, resume_text, flat_parsed)

        processed_blob_ref = await self._finalize_blob(raw_blob_ref)
        if processed_blob_ref:
            meta = dict(candidate.source_metadata or {})
            meta["processed_blob_ref"] = processed_blob_ref
            candidate.source_metadata = meta
            parsed_data["processed_blob_ref"] = processed_blob_ref

        await self.session.commit()
        await self.session.refresh(candidate)

        action = "updated" if updated_existing else "created"
        return {
            "success": True,
            "resume_id": resume_id,
            "candidate_id": str(candidate.id),
            "document_id": document_id,
            "parsed_data": parsed_data,
            "storage_backend": "pgvector",
            "chunks_stored": True,
            "candidate_action": action,
            "screening_report": parsed_data.get("screening_report"),
        }

    async def _upsert_candidate(
        self,
        *,
        flat_parsed: Dict[str, Any],
        resume_id: str,
        resume_text: str,
        emails: list[Any],
        phones: list[Any],
        locations: list[Any],
        ambiguous: list[Any],
        raw_blob_ref: Optional[str],
        pdf_extraction_method: Optional[str],
    ) -> Tuple[Candidate, bool]:
        email = str(emails[0]).strip() if emails else f"unknown-{resume_id}@upload.local"
        candidate: Optional[Candidate] = None
        updated_existing = False

        if _is_real_email(email):
            result = await self.session.execute(
                select(Candidate).where(Candidate.email == email)
            )
            candidate = result.scalar_one_or_none()
            if candidate:
                updated_existing = True
                logger.info("Updating existing candidate by email: %s", email)

        if candidate is None:
            candidate = Candidate(
                email=email,
                source="resume_parsing_upload",
            )
            self.session.add(candidate)

        parsed_name = flat_parsed.get("name")
        candidate.name = (
            (str(parsed_name).strip() if parsed_name else "")
            or candidate.name
            or "Unknown"
        )
        if _is_real_email(email):
            candidate.email = email
        candidate.phone = str(phones[0]).strip() if phones else candidate.phone
        candidate.location = str(locations[0]).strip() if locations else candidate.location
        candidate.raw_resume_ref = raw_blob_ref or candidate.raw_resume_ref
        candidate.raw_resume_text = resume_text
        candidate.profile_json = flat_parsed
        candidate.parsing_confidence = float(flat_parsed.get("confidence") or 0.0)
        candidate.missing_fields = list(
            (flat_parsed.get("completeness") or {}).get("gaps_for_hr_review")
            or flat_parsed.get("ambiguous_fields")
            or []
        )
        candidate.source = "resume_parsing_upload"
        candidate.source_metadata = {
            "resume_id": resume_id,
            "pdf_extraction_method": pdf_extraction_method,
            "pipeline": "azure_pgvector",
            "parser": "enterprise_parsing_agent",
            "completeness_grade": (flat_parsed.get("completeness") or {}).get(
                "completeness_grade"
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }
        candidate.is_active = True

        await self.session.flush()
        return candidate, updated_existing

    async def _finalize_blob(self, raw_blob_ref: Optional[str]) -> Optional[str]:
        if not raw_blob_ref or settings.storage_backend != "azure_blob":
            return None
        try:
            from app.integrations.azure_blob import blob_storage_enabled, get_blob_storage

            if not blob_storage_enabled():
                return None
            processed_ref = await get_blob_storage().move_to_processed(raw_blob_ref)
            logger.info("Resume moved to processed container: %s", processed_ref)
            return processed_ref
        except Exception as exc:
            logger.warning("Failed to move resume blob to processed container: %s", exc)
            return None

    async def _store_candidate_embedding(
        self,
        candidate: Candidate,
        resume_text: str,
        flat_parsed: Dict[str, Any],
    ) -> None:
        if not settings.database_url:
            logger.warning("DATABASE_URL not set; skipping candidate_embeddings row")
            return

        skill_text = " ".join(
            s.get("name", "") if isinstance(s, dict) else str(s)
            for s in (flat_parsed.get("skills") or [])
        )
        summary = flat_parsed.get("summary") or ""
        profile_text = f"{candidate.name} {summary} {skill_text} {resume_text[:2000]}".strip()
        embedding = await self.embedding_service.generate_embedding(profile_text)

        from agents.rag.unified_embeddings import embedding_model_label

        model_label = embedding_model_label()

        result = await self.session.execute(
            select(CandidateEmbedding).where(
                CandidateEmbedding.candidate_id == candidate.id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.vector = embedding
            existing.model = model_label
            existing.updated_at = datetime.utcnow()
        else:
            self.session.add(
                CandidateEmbedding(
                    candidate_id=candidate.id,
                    vector=embedding,
                    model=model_label,
                )
            )
        await self.session.flush()
        logger.info(
            "Candidate embedding stored (candidate_id=%s, model=%s, dims=%s)",
            candidate.id,
            model_label,
            len(embedding),
        )
