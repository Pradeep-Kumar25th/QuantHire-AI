"""
JD Pre-Analysis
===============
Compute a structured digest of a Job Opening *once* and cache it. The same
JD is hit by every specialist for every candidate during ranking; without
this cache, we'd derive the same level / density / education-explicitness
signals N×M times.

The output is a small Pydantic model so it can be serialised into prompts
(or cached across processes) cleanly. It is also used by the adaptive-weight
calibrator instead of re-deriving the same signals from raw text.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from agents.job_matching.cache import (
    Cache,
    InMemoryLRUCache,
    jd_analysis_cache_key,
    jd_content_hash,
)
from agents.job_matching.enterprise_models import JobOpening

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lexicons (kept here so they're trivially overrideable in unit tests)
# ---------------------------------------------------------------------------

_SENIOR_TOKENS = {
    "senior", "sr.", "sr",
    "staff", "principal", "lead",
    "director", "head", "vp", "chief", "manager",
}
_JUNIOR_TOKENS = {"junior", "jr.", "jr", "intern", "associate", "entry", "graduate"}
_SELF_TAUGHT_TOKENS = {
    "self-taught", "self taught", "no degree required",
    "bootcamp", "or equivalent experience", "equivalent experience",
}
_DEGREE_TOKENS = ("bachelor", "master", "phd", "ph.d", "degree", "b.s", "m.s", "ba ", "b.a")


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class JDAnalysis(BaseModel):
    """Structured, deterministic summary of a JD's quantitative shape."""

    jd_id: str
    level_signal: str = Field(..., description="'senior' | 'mid' | 'junior'")
    tech_density: float = Field(..., ge=0.0, le=1.0)
    education_explicit: bool
    self_taught_friendly: bool
    must_have_count: int = Field(..., ge=0)
    nice_to_have_count: int = Field(..., ge=0)
    has_leadership_signal: bool
    has_remote_signal: bool
    summary: str = Field(..., description="One-line human-readable digest used in prompts.")


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------


def _level_signal(job: JobOpening) -> str:
    blob = " ".join(filter(None, [job.job_level or "", job.job_title or ""])).lower()
    if any(tok in blob for tok in _SENIOR_TOKENS):
        return "senior"
    if any(tok in blob for tok in _JUNIOR_TOKENS):
        return "junior"
    return "mid"


def _education_explicit(job: JobOpening) -> tuple[bool, bool]:
    """Return (explicit_degree_required, self_taught_friendly)."""
    edu = (job.education_requirement or "").lower()
    self_taught_friendly = any(tok in edu for tok in _SELF_TAUGHT_TOKENS)
    if not edu:
        return False, self_taught_friendly
    if self_taught_friendly:
        return False, True
    return any(kw in edu for kw in _DEGREE_TOKENS), False


def _tech_density(job: JobOpening) -> float:
    raw = len(job.tools_technologies or []) + len(job.required_skills or [])
    if raw <= 4:
        return 0.2
    if raw <= 8:
        return 0.5
    if raw <= 14:
        return 0.75
    return 1.0


def _has_leadership(job: JobOpening) -> bool:
    haystack = " ".join(
        filter(
            None,
            [
                job.position_summary or "",
                " ".join(job.responsibilities or []),
                " ".join(job.soft_skills or []),
            ],
        )
    ).lower()
    return any(
        kw in haystack
        for kw in ("lead", "mentor", "manage", "team of", "people manager", "stakeholder")
    )


def _has_remote(job: JobOpening) -> bool:
    haystack = " ".join(
        filter(None, [job.position_summary or "", job.location or ""])
    ).lower()
    return any(kw in haystack for kw in ("remote", "anywhere", "distributed", "wfh"))


def _build_analysis(job: JobOpening) -> JDAnalysis:
    explicit, self_taught = _education_explicit(job)
    density = _tech_density(job)
    lvl = _level_signal(job)
    must = len(job.required_skills or [])
    nice = len(job.preferred_skills or [])

    summary = (
        f"{lvl}-level {job.job_title!r}; tech_density={density:.2f}; "
        f"required={must}, preferred={nice}; "
        f"degree_required={explicit}; "
        f"leadership={'yes' if _has_leadership(job) else 'no'}; "
        f"remote={'yes' if _has_remote(job) else 'no'}"
    )

    return JDAnalysis(
        jd_id=job.jd_id,
        level_signal=lvl,
        tech_density=density,
        education_explicit=explicit,
        self_taught_friendly=self_taught,
        must_have_count=must,
        nice_to_have_count=nice,
        has_leadership_signal=_has_leadership(job),
        has_remote_signal=_has_remote(job),
        summary=summary,
    )


def _content_payload(job: JobOpening) -> dict:
    """Slim dict used to derive the cache key — excludes raw_text noise."""
    return {
        "jd_id": job.jd_id,
        "title": job.job_title,
        "level": job.job_level,
        "required": sorted(job.required_skills or []),
        "preferred": sorted(job.preferred_skills or []),
        "tools": sorted(job.tools_technologies or []),
        "edu": job.education_requirement,
        "summary": (job.position_summary or "")[:500],
    }


class JDAnalyzer:
    """Cached JDAnalysis producer; safe to call many times per JD."""

    def __init__(self, cache: Optional[Cache] = None) -> None:
        self._cache: Cache = cache or InMemoryLRUCache(max_size=2048)

    async def analyse(self, job: JobOpening) -> JDAnalysis:
        ch = jd_content_hash(_content_payload(job))
        key = jd_analysis_cache_key(job.jd_id, ch)
        cached = await self._cache.get(key)
        if cached is not None:
            try:
                return JDAnalysis.model_validate(cached)
            except Exception:
                # Stale shape from an older PIPELINE_VERSION; recompute.
                pass

        analysis = _build_analysis(job)
        await self._cache.set(key, analysis.model_dump(), ttl_seconds=24 * 3600)
        return analysis

    def analyse_sync(self, job: JobOpening) -> JDAnalysis:
        """Synchronous fallback for unit tests / callers that don't want asyncio."""
        return _build_analysis(job)
