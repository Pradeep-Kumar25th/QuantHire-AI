"""
Postgres / pgvector data access for job matching (Azure Non-Prod path).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from agents.job_matching.enterprise_models import CandidateProfile, JobOpening

logger = logging.getLogger(__name__)


def _ensure_api_on_path() -> None:
    import sys
    from pathlib import Path

    apps_root = Path(__file__).resolve().parents[3]
    api_root = apps_root / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))


def _run_coro(coro: Any) -> Any:
    """Run *coro* from sync code; safe even under a running event loop."""
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Called from inside a running loop: never re-enter it and never share
    # its loop-bound asyncpg connections — run on a dedicated thread + loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _pg_session():
    """AsyncSession context over a dedicated NullPool engine.

    The API's shared engine is bound to the main event loop; these fetches may
    run on temporary loops, so each call uses its own short-lived engine.
    """
    from contextlib import asynccontextmanager

    _ensure_api_on_path()

    @asynccontextmanager
    async def _ctx():
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.database import _asyncpg_url_and_ssl

        raw_url = os.getenv("DATABASE_URL", "").strip()
        if not raw_url:
            raise RuntimeError("DATABASE_URL is required for pgvector data access")
        db_url, ssl_arg = _asyncpg_url_and_ssl(raw_url)
        connect_args: dict[str, Any] = {
            "server_settings": {"application_name": "quanthire-job-matching"},
            "command_timeout": 60,
            "timeout": 30,
        }
        if ssl_arg is not None:
            connect_args["ssl"] = ssl_arg
        engine = create_async_engine(db_url, poolclass=NullPool, connect_args=connect_args)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                yield session
        finally:
            await engine.dispose()

    return _ctx()


def pgvector_data_access_enabled() -> bool:
    if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
        return True
    if os.getenv("MILVUS_ENABLED", "true").strip().lower() in ("0", "false", "no"):
        return bool(os.getenv("DATABASE_URL"))
    store = os.getenv("VECTOR_STORE") or os.getenv("VECTOR_STORE_TYPE") or ""
    return store.strip().lower() == "pgvector"


def _split_skills(text: str | None) -> list[str]:
    if not text:
        return []
    items: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^[\u2022\-\*\d\.\)]+\s*", "", line.strip())
        for token in re.split(r"[,/;|]", line):
            token = token.strip().rstrip(".")
            if token and len(token) <= 80:
                items.append(token)
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:60]


def _profile_from_candidate_row(candidate: Any, chunks: list[dict[str, Any]]) -> CandidateProfile:
    profile_json = candidate.profile_json or {}
    skill_names = [
        s.get("name") if isinstance(s, dict) else str(s)
        for s in (profile_json.get("skills") or [])
    ]
    technical_skills: list[str] = []
    soft_skills: list[str] = []
    tools: list[str] = []
    for item in profile_json.get("skills") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        category = str(item.get("category") or "technical").lower()
        if category in {"soft", "soft_skill", "interpersonal", "language", "spoken_language"}:
            soft_skills.append(name)
        elif category in {"tool", "tools", "platform", "framework"}:
            tools.append(name)
        else:
            technical_skills.append(name)
    if not technical_skills:
        technical_skills = skill_names or _split_skills(
            next(
                (
                    chunk.get("chunk_text")
                    for chunk in chunks
                    if (chunk.get("section_type") or "").lower() == "skills"
                ),
                "",
            )
        )

    sections: dict[str, str] = {}
    raw_text = candidate.raw_resume_text or ""
    for chunk in chunks:
        section = (chunk.get("section_type") or "").strip()
        if section:
            sections.setdefault(section, "")
            sections[section] += "\n" + (chunk.get("chunk_text") or "")

    for chunk in chunks:
        if chunk.get("full_content"):
            raw_text = chunk["full_content"]
            break

    positions = []
    for exp in profile_json.get("experience") or []:
        if isinstance(exp, dict):
            positions.append(exp)

    degrees = []
    universities = []
    for edu in profile_json.get("education") or []:
        if isinstance(edu, dict):
            if edu.get("degree"):
                degrees.append(str(edu["degree"]))
            if edu.get("institution"):
                universities.append(str(edu["institution"]))

    certs = []
    for cert in profile_json.get("certificates") or []:
        if isinstance(cert, dict) and cert.get("name"):
            certs.append(str(cert["name"]))

    total_years = profile_json.get("total_years_experience")
    if total_years is None and positions:
        total_years = float(len(positions))
    try:
        total_years_float = float(total_years or 0.0)
    except (TypeError, ValueError):
        total_years_float = 0.0

    headline = profile_json.get("summary") or profile_json.get("headline")

    return CandidateProfile(
        candidate_id=str(candidate.id),
        name=candidate.name or "Unknown",
        email=candidate.email,
        location=candidate.location,
        headline=headline,
        total_years_experience=total_years_float,
        current_role=positions[0].get("title") if positions else None,
        technical_skills=technical_skills,
        soft_skills=soft_skills,
        tools=tools,
        certifications=certs,
        degrees=degrees,
        universities=universities,
        industries=[],
        positions=positions,
        raw_text=raw_text,
    )


async def _fetch_candidates_async() -> list[CandidateProfile]:
    _ensure_api_on_path()

    from sqlalchemy import select
    from app.models.candidates import Candidate
    from app.models.document_chunks import DocumentChunk

    profiles: list[CandidateProfile] = []
    async with _pg_session() as session:
        result = await session.execute(
            select(Candidate).where(Candidate.is_active == True).order_by(Candidate.created_at.desc())  # noqa: E712
        )
        candidates = list(result.scalars().all())
        for candidate in candidates:
            chunks_result = await session.execute(
                select(DocumentChunk).where(DocumentChunk.candidate_id == candidate.id).limit(200)
            )
            chunks = [
                {
                    "section_type": row.section_type,
                    "chunk_text": row.chunk_text,
                    "full_content": row.full_content,
                }
                for row in chunks_result.scalars().all()
            ]
            profiles.append(_profile_from_candidate_row(candidate, chunks))
    return profiles


async def _fetch_candidate_async(candidate_id: str) -> Optional[CandidateProfile]:
    from uuid import UUID

    _ensure_api_on_path()

    from sqlalchemy import select
    from app.models.candidates import Candidate
    from app.models.document_chunks import DocumentChunk

    try:
        cid = UUID(candidate_id)
    except ValueError:
        return None

    async with _pg_session() as session:
        result = await session.execute(select(Candidate).where(Candidate.id == cid))
        candidate = result.scalar_one_or_none()
        if not candidate:
            return None
        chunks_result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.candidate_id == cid).limit(200)
        )
        chunks = [
            {
                "section_type": row.section_type,
                "chunk_text": row.chunk_text,
                "full_content": row.full_content,
            }
            for row in chunks_result.scalars().all()
        ]
        return _profile_from_candidate_row(candidate, chunks)


def list_candidates_pg() -> list[CandidateProfile]:
    return _run_coro(_fetch_candidates_async())


def get_candidate_pg(candidate_id: str) -> Optional[CandidateProfile]:
    return _run_coro(_fetch_candidate_async(candidate_id))


def list_jds_pg() -> list[JobOpening]:
    return _run_coro(_fetch_jds_async())


def get_jd_pg(jd_id: str) -> Optional[JobOpening]:
    return _run_coro(_fetch_jd_async(jd_id))


def _chunk_rows_to_milvus_shape(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "document_id": row.document_id,
            "section_type": row.section_type,
            "chunk_text": row.chunk_text,
            "full_content": row.full_content,
            "entity_name": row.entity_name,
        }
        for row in rows
    ]


async def _fetch_jds_async() -> list[JobOpening]:
    from agents.job_matching.data_access import _opening_from_chunks

    _ensure_api_on_path()

    from sqlalchemy import select
    from app.models.document_chunks import DocumentChunk

    openings: list[JobOpening] = []
    async with _pg_session() as session:
        doc_ids_result = await session.execute(
            select(DocumentChunk.document_id)
            .where(DocumentChunk.document_type.in_(["job_description", "jd"]))
            .distinct()
        )
        doc_ids = [row[0] for row in doc_ids_result.all()]
        for doc_id in doc_ids:
            chunks_result = await session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == doc_id).limit(200)
            )
            chunks = _chunk_rows_to_milvus_shape(list(chunks_result.scalars().all()))
            opening = _opening_from_chunks(doc_id, chunks)
            if opening:
                openings.append(opening)
    return openings


async def _fetch_jd_async(jd_id: str) -> Optional[JobOpening]:
    from agents.job_matching.data_access import _opening_from_chunks

    _ensure_api_on_path()

    from sqlalchemy import select
    from app.models.document_chunks import DocumentChunk

    async with _pg_session() as session:
        chunks_result = await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == jd_id).limit(200)
        )
        chunks = _chunk_rows_to_milvus_shape(list(chunks_result.scalars().all()))
        if not chunks:
            return None
        return _opening_from_chunks(jd_id, chunks)
