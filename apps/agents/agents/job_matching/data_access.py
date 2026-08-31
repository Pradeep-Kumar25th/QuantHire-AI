"""
Data Access Helpers for Job Matching
====================================
Read-only adapters that turn the Milvus chunks produced by
``apps.quantchat.ingestion.document_ingestion`` back into the
``CandidateProfile`` and ``JobOpening`` Pydantic models the agents consume.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from agents.job_matching.enterprise_models import CandidateProfile, JobOpening

logger = logging.getLogger(__name__)


# ============================================================================
# MILVUS CONNECTION & COLLECTION ALIASES
# ============================================================================


def _ensure_milvus_connection() -> None:
    """Ensure pymilvus default alias is connected (same cluster as QuantChat ingestion)."""
    try:
        from pymilvus import connections
    except ImportError:
        return
    try:
        if connections.has_connection("default"):
            return
    except Exception:
        pass

    host = os.getenv("JOB_MATCHING_MILVUS_HOST") or os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("JOB_MATCHING_MILVUS_PORT") or os.getenv("MILVUS_PORT", "19530")
    try:
        from agents.job_matching.config import get_config

        cfg = get_config()
        host = cfg.milvus_host
        port = str(cfg.milvus_port)
    except Exception:
        port = str(port)

    try:
        connections.connect(alias="default", host=host, port=str(port), timeout=30)
        logger.debug("Job matching connected to Milvus at %s:%s", host, port)
    except Exception as exc:
        logger.error(
            "Job matching could not connect to Milvus at %s:%s: %s",
            host,
            port,
            exc,
        )
        raise


def _jd_collection_names_to_try(primary: str) -> list[str]:
    """
    Try configured name first, then QuantChat ``JD_COLLECTION``, then legacy alias.

    Document ingestion writes to ``quanthire_job_descriptions``; older matching code
    used ``quanthire_jds``.
    """
    fallbacks = ("quanthire_job_descriptions", "quanthire_jds")
    out: list[str] = []
    for name in (primary, *fallbacks):
        n = (name or "").strip()
        if n and n not in out:
            out.append(n)
    return out


# ============================================================================
# TEXT UTILITIES
# ============================================================================


def _split_lines(text: str | None) -> list[str]:
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _split_skills(text: str | None) -> list[str]:
    """Split a skills paragraph into atomic skills."""
    if not text:
        return []
    items: list[str] = []
    for line in _split_lines(text):
        # Strip bullet markers
        line = re.sub(r"^[\u2022\-\*\d\.\)]+\s*", "", line)
        if line.endswith(":"):
            continue
        # Try comma split, fallback to slashes
        for token in re.split(r"[,/;|]", line):
            token = token.strip().rstrip(".")
            if token and len(token) <= 80:
                items.append(token)
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:60]


def _years_from_text(text: str | None) -> float:
    if not text:
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)", text, re.I)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


# ============================================================================
# MILVUS LOADERS
# ============================================================================


def _collection_is_loaded(name: str) -> bool:
    """Return True when Milvus reports the collection is already loaded."""
    try:
        from pymilvus import utility

        state = utility.load_state(name)
        state_name = getattr(state, "name", None) or str(state)
        return str(state_name).endswith("Loaded")
    except Exception:
        return False


def _load_collection(name: str, *, timeout: int = 120) -> Any:
    """Load a Milvus collection if it exists, else return None."""
    _ensure_milvus_connection()
    try:
        from pymilvus import Collection, utility

        if not utility.has_collection(name):
            logger.warning("Milvus collection %s does not exist", name)
            return None

        if _collection_is_loaded(name):
            return Collection(name)

        coll = Collection(name)
        try:
            progress = utility.loading_progress(name)
            if progress and progress.get("loading_progress") not in (None, "100"):
                logger.warning(
                    "Milvus collection %s stuck loading (%s) — releasing and retrying",
                    name,
                    progress,
                )
                try:
                    coll.release()
                except Exception:
                    pass
        except Exception:
            pass

        coll.load(timeout=timeout)
        return coll
    except Exception as exc:  # pragma: no cover - infra failure
        logger.error("Failed to load Milvus collection %s: %s", name, exc)
        return None


def _query_chunks(collection: Any, expr: str, limit: int = 200) -> list[dict[str, Any]]:
    """Run a metadata query and return chunk dictionaries."""
    if collection is None:
        return []
    try:
        return collection.query(
            expr=expr,
            output_fields=[
                "document_id",
                "document_type",
                "entity_name",
                "section_type",
                "chunk_text",
                "full_content",
                "created_at",
            ],
            limit=limit,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Milvus query failed (%s): %s", expr, exc)
        return []


def _all_chunks(collection: Any, document_type: str, limit: int = 5000) -> list[dict[str, Any]]:
    """Pull every chunk of a given document_type."""
    expr = f'document_type == "{document_type}"'
    return _query_chunks(collection, expr, limit=limit)


# ============================================================================
# RESUMES → CandidateProfile
# ============================================================================


def list_candidates(resume_collection_name: str = "quanthire_resumes") -> list[CandidateProfile]:
    """Return every candidate currently stored in Milvus or Postgres."""
    from agents.job_matching.data_access_pg import (
        list_candidates_pg,
        pgvector_data_access_enabled,
    )

    if pgvector_data_access_enabled():
        return list_candidates_pg()

    collection = _load_collection(resume_collection_name)
    if collection is None:
        return []
    chunks = _all_chunks(collection, "resume")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        doc_id = chunk.get("document_id")
        if not doc_id:
            continue
        grouped.setdefault(doc_id, []).append(chunk)

    profiles: list[CandidateProfile] = []
    for doc_id, doc_chunks in grouped.items():
        profile = _profile_from_chunks(doc_id, doc_chunks)
        if profile:
            profiles.append(profile)
    return profiles


def get_candidate(
    candidate_id: str,
    resume_collection_name: str = "quanthire_resumes",
) -> Optional[CandidateProfile]:
    try:
        from agents.job_matching.data_access_pg import (
            get_candidate_pg,
            pgvector_data_access_enabled,
        )

        if pgvector_data_access_enabled():
            profile = get_candidate_pg(candidate_id)
            if profile:
                return profile
    except Exception as exc:
        logger.warning("Postgres candidate lookup failed, using Milvus: %s", exc)

    collection = _load_collection(resume_collection_name)
    if collection is None:
        return None
    chunks = _query_chunks(collection, f'document_id == "{candidate_id}"', limit=200)
    if not chunks:
        return None
    return _profile_from_chunks(candidate_id, chunks)


def _profile_from_chunks(doc_id: str, chunks: list[dict[str, Any]]) -> Optional[CandidateProfile]:
    if not chunks:
        return None

    sections: dict[str, str] = {}
    for chunk in chunks:
        section = (chunk.get("section_type") or "").strip()
        if not section:
            continue
        sections.setdefault(section, "")
        sections[section] += "\n" + (chunk.get("chunk_text") or "")

    # Merge the canonical full_content from chunk-0 (storage optimisation)
    full_content = ""
    for chunk in chunks:
        if chunk.get("full_content"):
            full_content = chunk["full_content"]
            break

    name = chunks[0].get("entity_name") or "Unknown"

    personal = sections.get("Personal Info", "")
    email_match = re.search(r"Email:\s*(\S+@\S+)", personal)
    location_match = re.search(r"Location:\s*(.+)", personal)
    headline_match = re.search(r"Title:\s*(.+)", personal)

    skills_text = sections.get("Skills", "")
    technical_skills = _split_skills(skills_text)

    soft_skills_text = sections.get("Soft Skills", "")
    soft_skills = _split_skills(soft_skills_text) if soft_skills_text else []

    tools_text = sections.get("Tools", "")
    tools = _split_skills(tools_text) if tools_text else []

    certifications = _split_skills(sections.get("Certifications", ""))
    degrees = _split_lines(sections.get("Education", ""))[:10]

    experience_text = sections.get("Experience", "")
    total_years = _years_from_text(experience_text)

    current_role = None
    role_match = re.search(r"Current Role:\s*(.+)", experience_text, re.I)
    if role_match:
        current_role = role_match.group(1).strip()
    elif headline_match:
        current_role = headline_match.group(1).strip()

    # Crude position parsing — looks for "Title @ Company (start - end)" lines
    positions: list[dict[str, Any]] = []
    for line in _split_lines(experience_text):
        if "@" in line and len(line) < 200:
            positions.append({"raw": line})
    positions = positions[:20]

    industries: list[str] = []
    industry_text = sections.get("Industries", "")
    if industry_text:
        industries = _split_skills(industry_text)

    return CandidateProfile(
        candidate_id=doc_id,
        name=name or "Unknown",
        email=email_match.group(1) if email_match else None,
        location=location_match.group(1).strip() if location_match else None,
        headline=headline_match.group(1).strip() if headline_match else None,
        total_years_experience=total_years,
        current_role=current_role,
        technical_skills=technical_skills,
        soft_skills=soft_skills,
        tools=tools,
        certifications=certifications,
        degrees=degrees,
        universities=[],
        industries=industries,
        positions=positions,
        raw_text=full_content[:20000] if full_content else None,
    )


# ============================================================================
# JOB DESCRIPTIONS → JobOpening
# ============================================================================


def list_jds(jd_collection_name: str = "quanthire_job_descriptions") -> list[JobOpening]:
    """Return every JD currently stored in Postgres pgvector or Milvus."""
    from agents.job_matching.data_access_pg import (
        list_jds_pg,
        pgvector_data_access_enabled,
    )

    if pgvector_data_access_enabled():
        return list_jds_pg()

    for coll_name in _jd_collection_names_to_try(jd_collection_name):
        collection = _load_collection(coll_name)
        if collection is None:
            continue
        chunks = _all_chunks(collection, "jd")
        if not chunks:
            logger.info(
                "Job matching: collection %r has no JD chunks (document_type==jd); trying next alias",
                coll_name,
            )
            continue
        grouped: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks:
            doc_id = chunk.get("document_id")
            if not doc_id:
                continue
            grouped.setdefault(doc_id, []).append(chunk)

        openings: list[JobOpening] = []
        for doc_id, doc_chunks in grouped.items():
            opening = _opening_from_chunks(doc_id, doc_chunks)
            if opening:
                openings.append(opening)
        if openings:
            logger.info(
                "Job matching: listed %s JD(s) from Milvus collection %r",
                len(openings),
                coll_name,
            )
            return openings

    logger.warning(
        "Job matching: no JDs found in collections %s",
        _jd_collection_names_to_try(jd_collection_name),
    )
    return []


def get_jd(jd_id: str, jd_collection_name: str = "quanthire_job_descriptions") -> Optional[JobOpening]:
    try:
        from agents.job_matching.data_access_pg import (
            get_jd_pg,
            pgvector_data_access_enabled,
        )

        if pgvector_data_access_enabled():
            opening = get_jd_pg(jd_id)
            if opening:
                return opening
    except Exception as exc:
        logger.warning("Postgres JD lookup failed, using Milvus: %s", exc)

    for coll_name in _jd_collection_names_to_try(jd_collection_name):
        collection = _load_collection(coll_name)
        if collection is None:
            continue
        chunks = _query_chunks(collection, f'document_id == "{jd_id}"', limit=200)
        if not chunks:
            continue
        return _opening_from_chunks(jd_id, chunks)
    return None


def _opening_from_chunks(doc_id: str, chunks: list[dict[str, Any]]) -> Optional[JobOpening]:
    if not chunks:
        return None

    sections: dict[str, str] = {}
    for chunk in chunks:
        section = (chunk.get("section_type") or "").strip()
        if not section:
            continue
        sections.setdefault(section, "")
        sections[section] += "\n" + (chunk.get("chunk_text") or "")

    full_content = ""
    for chunk in chunks:
        if chunk.get("full_content"):
            full_content = chunk["full_content"]
            break

    job_title = chunks[0].get("entity_name") or "Untitled Role"

    dept_raw = (sections.get("Department") or "").strip()
    department = None
    dept_match = re.search(r"Department:\s*(.+)", dept_raw, re.I) if dept_raw else None
    if dept_match:
        department = dept_match.group(1).strip()
    elif dept_raw:
        department = dept_raw.split("\n")[0].strip()[:240]

    location_text = (sections.get("Location") or "").strip()
    location = None
    if location_text:
        loc_match = re.search(r"Location:\s*(.+)", location_text, re.I)
        location = (
            loc_match.group(1).strip()
            if loc_match
            else location_text.split("\n")[0].strip()
        )[:240]

    job_level = None
    level_match = re.search(r"(?:Level|Job Level):\s*(.+)", sections.get("Job Level", ""), re.I)
    if level_match:
        job_level = level_match.group(1).strip()

    summary = sections.get("Position Summary", "").strip() or None

    responsibilities = _split_lines(sections.get("Responsibilities", ""))
    required_skills = _split_skills(sections.get("Required Qualifications", ""))
    preferred_skills = _split_skills(sections.get("Preferred Qualifications", ""))
    tools = _split_skills(sections.get("Tools & Technologies", ""))
    soft_skills = _split_skills(sections.get("Soft Skills", ""))

    education_requirement = None
    rq = sections.get("Required Qualifications", "")
    edu_match = re.search(r"Education[:\*]+\s*(.+)", rq, re.I)
    if edu_match:
        education_requirement = edu_match.group(1).strip()

    experience_requirement = None
    exp_match = re.search(r"Experience[:\*]+\s*(.+)", rq, re.I)
    if exp_match:
        experience_requirement = exp_match.group(1).strip()

    return JobOpening(
        jd_id=doc_id,
        job_title=job_title,
        department=department,
        location=location,
        job_level=job_level,
        position_summary=summary,
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        tools_technologies=tools,
        soft_skills=soft_skills,
        education_requirement=education_requirement,
        experience_requirement=experience_requirement,
        raw_text=full_content[:20000] if full_content else None,
    )
