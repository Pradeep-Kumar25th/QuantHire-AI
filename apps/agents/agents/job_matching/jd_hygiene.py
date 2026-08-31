"""
JD Hygiene Agent (Layer 0 — Pre-flight)
=======================================
Runs ONCE per JD (cached) before any specialist scores a candidate.

Why this layer exists
---------------------
A bad JD poisons every downstream specialist:
* "Junior + 15 yrs experience" makes every single match low-confidence.
* Protected-attribute language ("young and energetic", "no career gaps")
  is a discrimination liability the moment a candidate is auto-rejected.
* Empty required_skills makes the SkillsAgent score on noise.

Without this layer, the orchestrator would happily grade 100 candidates
against a malformed JD and produce 100 questionable verdicts. Catching
the issue at the JD level is O(1); catching it after matching is O(n).

Design
------
* Pure-LLM agent that returns a :class:`JDHygieneReport`.
* Pre-call "static" guard: regex/length checks for the cheapest cases,
  short-circuiting the LLM when a JD is structurally trivially OK.
* Cached by content hash via :class:`JDAnalyzer`'s cache so re-running
  a match against the same JD doesn't pay the cost twice.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from agents.job_matching.cache import (
    Cache,
    InMemoryLRUCache,
    jd_content_hash,
)
from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    AgentThought,
    JDHygieneReport,
    JobOpening,
)
from agents.job_matching.llm_client import JobMatchingLLM
from agents.job_matching.prompts import build_jd_hygiene_prompt
from agents.job_matching.swarm_agents import _emit, _now, ThoughtSink

logger = logging.getLogger(__name__)


def _job_payload(job: JobOpening) -> dict:
    """Slim, cache-friendly JD payload — same convention as JDAnalyzer."""
    return {
        "jd_id": job.jd_id,
        "job_title": job.job_title,
        "department": job.department,
        "job_level": job.job_level,
        "location": job.location,
        "position_summary": (job.position_summary or "")[:1500],
        "responsibilities": (job.responsibilities or [])[:20],
        "required_skills": sorted(job.required_skills or []),
        "preferred_skills": sorted(job.preferred_skills or []),
        "tools_technologies": sorted(job.tools_technologies or []),
        "education_requirement": job.education_requirement,
        "experience_requirement": job.experience_requirement,
    }


def _missing_critical_fields(job: JobOpening) -> list[str]:
    """Fast static check before the LLM call."""
    missing: list[str] = []
    if not job.job_level or not job.job_level.strip():
        missing.append("job_level")
    if not job.required_skills:
        missing.append("required_skills")
    if not (job.position_summary or "").strip() and not (
        job.experience_requirement or ""
    ).strip():
        missing.append("position_summary")
    return missing


def _ok_report(job: JobOpening, summary: str) -> JDHygieneReport:
    return JDHygieneReport(
        is_acceptable=True,
        severity="ok",
        contradictions=[],
        protected_attribute_language=[],
        unrealistic_requirements=[],
        missing_critical_fields=_missing_critical_fields(job),
        suggestions=[],
        summary=summary,
    )


def _fallback_report(job: JobOpening) -> JDHygieneReport:
    """Used when the LLM call itself fails — we never block on agent failure."""
    missing = _missing_critical_fields(job)
    return JDHygieneReport(
        is_acceptable=True,
        severity="warn" if missing else "ok",
        contradictions=[],
        protected_attribute_language=[],
        unrealistic_requirements=[],
        missing_critical_fields=missing,
        suggestions=(
            ["Hygiene agent failed to run; recommend manual JD review."]
            if missing
            else []
        ),
        summary=(
            "JD hygiene check failed to run; defaulting to 'matchable' so the "
            "swarm is not blocked. The recruiter should review the JD manually."
        ),
    )


# ---------------------------------------------------------------------------


class JDHygieneAgent:
    """Pre-flight JD audit. Cached and idempotent per-JD."""

    name = "JDHygieneAgent"

    def __init__(
        self,
        config: JobMatchingConfig,
        llm: JobMatchingLLM | None = None,
        cache: Optional[Cache] = None,
    ) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(
            config,
            temperature=config.specialist_temperature,
            model_override=config.llm_specialist_model,
        )
        self._cache: Cache = cache or InMemoryLRUCache(max_size=2048)

    @staticmethod
    def _cache_key(job: JobOpening, content_hash: str) -> str:
        return f"jd_hygiene:{job.jd_id}:{content_hash}"

    async def run(
        self,
        job: JobOpening,
        sink: ThoughtSink | None = None,
    ) -> JDHygieneReport:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="OBSERVE",
                thought=f"Running JD hygiene check on '{job.job_title}'",
                state="PRE_FLIGHT",
                timestamp=_now(),
            ),
        )

        payload = _job_payload(job)
        ch = jd_content_hash(payload)
        key = self._cache_key(job, ch)

        cached = await self._cache.get(key)
        if cached is not None:
            try:
                report = JDHygieneReport.model_validate(cached)
                await _emit(
                    sink,
                    AgentThought(
                        agent=self.name,
                        phase="REFLECT",
                        thought=f"JD hygiene cached — {report.severity.upper()}",
                        state="PRE_FLIGHT",
                        timestamp=_now(),
                        metadata={"cache": "hit", "severity": report.severity},
                    ),
                )
                return report
            except Exception:
                pass  # stale shape, recompute

        # If the JD looks trivially OK (no missing critical fields, sensible
        # required_skills count, no obvious red phrases), skip the LLM call.
        # This keeps the cost of the new layer at ~$0 for healthy JDs.
        missing = _missing_critical_fields(job)
        if not missing and self._looks_trivially_ok(job):
            report = _ok_report(
                job,
                summary="JD passed static hygiene checks; LLM audit skipped.",
            )
            await self._cache.set(key, report.model_dump(), ttl_seconds=24 * 3600)
            await _emit(
                sink,
                AgentThought(
                    agent=self.name,
                    phase="REFLECT",
                    thought="JD hygiene OK (static fast-path).",
                    state="PRE_FLIGHT",
                    timestamp=_now(),
                    metadata={"severity": "ok", "fast_path": True},
                ),
            )
            return report

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="ACT",
                thought="Running deep LLM hygiene audit on this JD",
                state="PRE_FLIGHT",
                timestamp=_now(),
            ),
        )

        prompt = build_jd_hygiene_prompt(json.dumps(payload, default=str))
        try:
            raw = await self.llm.acall_structured(
                prompt, schema_model=JDHygieneReport, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("JDHygieneAgent failed: %s", exc, exc_info=True)
            report = _fallback_report(job)
            await self._cache.set(key, report.model_dump(), ttl_seconds=300)
            return report

        try:
            report = JDHygieneReport.model_validate(raw)
        except Exception as exc:
            logger.warning("JDHygieneAgent parse failed: %s", exc)
            report = _fallback_report(job)

        # Defence in depth: if any protected-attribute phrase was returned but
        # severity says "ok", upgrade to "block".
        if report.protected_attribute_language and report.severity == "ok":
            report = report.model_copy(
                update={"severity": "block", "is_acceptable": False}
            )

        # Always report static-detected missing fields, even if the LLM didn't
        # surface them.
        for f in missing:
            if f not in report.missing_critical_fields:
                report.missing_critical_fields.append(f)

        await self._cache.set(key, report.model_dump(), ttl_seconds=24 * 3600)

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"JD hygiene complete — {report.severity.upper()}",
                state="PRE_FLIGHT",
                timestamp=_now(),
                metadata={
                    "severity": report.severity,
                    "issues": (
                        len(report.contradictions)
                        + len(report.protected_attribute_language)
                        + len(report.unrealistic_requirements)
                        + len(report.missing_critical_fields)
                    ),
                },
            ),
        )
        return report

    @staticmethod
    def _looks_trivially_ok(job: JobOpening) -> bool:
        """Cheap static heuristic to skip the LLM for clean JDs."""
        if not job.required_skills or len(job.required_skills) > 25:
            return False  # empty or laundry-list
        # Catch the most common protected-attribute red flags so we don't
        # silently fast-path them past the LLM.
        haystack = " ".join(
            filter(
                None,
                [
                    job.job_title or "",
                    job.position_summary or "",
                    " ".join(job.responsibilities or []),
                ],
            )
        ).lower()
        red_flags = (
            "young and energetic",
            "digital native",
            "recent graduate only",
            "no career gap",
            "native english speaker",
            "must be male",
            "must be female",
            "fresh graduate only",
        )
        if any(rf in haystack for rf in red_flags):
            return False
        return True
