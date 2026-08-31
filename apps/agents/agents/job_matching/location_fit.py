"""
Location-Fit Agent (Layer 0 — Pre-flight, hybrid deterministic + LLM)
=====================================================================
Catches one of the most common hard rejects in real hiring:

    "Strong candidate, but the role is US-only and they're in Berlin."

The orchestrator runs this BEFORE the swarm so we never spend 8 LLM calls
grading a candidate who can't be hired anyway. Output is pure metadata —
it does NOT enter the dimension-weighted ensemble. Recruiters see it as
its own banner in the run HUD.

Two-tier strategy
-----------------
1. **Deterministic fast-path** (default).
   * Both fields parsed; if they share a country/region/timezone, fit=ok.
   * If JD says remote, fit=ok regardless of country (with a time-zone
     overlap note).
   * If both fields parsed and there is a hard country/region mismatch
     and the JD is NOT remote, fit=block.

2. **LLM fallback** (only when the deterministic check is `unknown`).
   * Reads candidate.raw_text + job.raw_text + job.position_summary to
     catch nuance like "open to relocation" or "remote within EU".
   * Cached per (candidate_id, jd_content_hash) so we never repeat the
     LLM call for the same pair.

This module ships with NO external libs (no geopy, no pytz). The location
parsing is intentionally simple — false-warns are preferable to false-OKs
because the warning is informational, not a hard reject by default.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from agents.job_matching.cache import (
    Cache,
    InMemoryLRUCache,
    jd_content_hash,
)
from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    AgentThought,
    CandidateProfile,
    JobOpening,
    LocationFitReport,
)
from agents.job_matching.llm_client import JobMatchingLLM
from agents.job_matching.swarm_agents import _emit, _now, ThoughtSink

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

# Approximate UTC offsets for major hubs. We use these to compute
# working-hour overlap. Resolution is deliberately coarse — getting it
# precise would need pytz + a real geocoder.
_TZ_OFFSETS_HOURS: dict[str, float] = {
    # North America
    "san francisco": -8, "seattle": -8, "los angeles": -8, "portland": -8, "vancouver": -8,
    "denver": -7, "salt lake city": -7, "phoenix": -7,
    "chicago": -6, "austin": -6, "dallas": -6, "houston": -6, "minneapolis": -6,
    "new york": -5, "boston": -5, "toronto": -5, "atlanta": -5, "miami": -5, "montreal": -5,
    "halifax": -4, "san juan": -4,
    "mexico city": -6,
    # South America
    "sao paulo": -3, "buenos aires": -3, "rio de janeiro": -3, "santiago": -3,
    # Europe
    "london": 0, "dublin": 0, "lisbon": 0,
    "paris": 1, "berlin": 1, "amsterdam": 1, "madrid": 1, "rome": 1, "stockholm": 1,
    "zurich": 1, "munich": 1, "milan": 1, "warsaw": 1, "copenhagen": 1, "oslo": 1,
    "athens": 2, "helsinki": 2, "istanbul": 3, "moscow": 3,
    # MEA
    "dubai": 4, "abu dhabi": 4, "tel aviv": 2, "cairo": 2, "lagos": 1,
    "johannesburg": 2, "nairobi": 3, "riyadh": 3,
    # Asia / Pacific
    "bangalore": 5.5, "bengaluru": 5.5, "mumbai": 5.5, "delhi": 5.5, "hyderabad": 5.5,
    "chennai": 5.5, "pune": 5.5, "kolkata": 5.5, "noida": 5.5, "gurgaon": 5.5,
    "karachi": 5, "lahore": 5, "dhaka": 6,
    "singapore": 8, "hong kong": 8, "shanghai": 8, "beijing": 8, "taipei": 8,
    "seoul": 9, "tokyo": 9, "osaka": 9,
    "jakarta": 7, "bangkok": 7, "manila": 8, "ho chi minh": 7, "hanoi": 7,
    "sydney": 10, "melbourne": 10, "brisbane": 10, "auckland": 12, "wellington": 12,
}

# Country-keyword aliases (for the country-mismatch block check).
_COUNTRY_ALIASES: dict[str, str] = {
    "us": "USA", "usa": "USA", "united states": "USA", "u.s.": "USA",
    "u.s.a.": "USA", "america": "USA",
    "uk": "UK", "u.k.": "UK", "united kingdom": "UK", "britain": "UK", "england": "UK",
    "ireland": "Ireland", "germany": "Germany", "france": "France", "spain": "Spain",
    "italy": "Italy", "netherlands": "Netherlands", "holland": "Netherlands",
    "switzerland": "Switzerland", "sweden": "Sweden", "norway": "Norway",
    "denmark": "Denmark", "finland": "Finland", "poland": "Poland",
    "canada": "Canada", "mexico": "Mexico", "brazil": "Brazil", "argentina": "Argentina",
    "australia": "Australia", "new zealand": "New Zealand",
    "india": "India", "pakistan": "Pakistan", "bangladesh": "Bangladesh",
    "singapore": "Singapore", "hong kong": "Hong Kong", "china": "China",
    "japan": "Japan", "south korea": "South Korea", "korea": "South Korea",
    "vietnam": "Vietnam", "thailand": "Thailand", "philippines": "Philippines",
    "indonesia": "Indonesia", "uae": "UAE", "u.a.e.": "UAE",
    "united arab emirates": "UAE", "saudi arabia": "Saudi Arabia",
    "israel": "Israel", "egypt": "Egypt", "south africa": "South Africa",
    "nigeria": "Nigeria", "kenya": "Kenya",
}

# Common "remote" / "hybrid" keywords that override location matching.
_REMOTE_PHRASES = (
    "remote",
    "fully remote",
    "100% remote",
    "anywhere",
    "work from anywhere",
    "wfa",
    "globally remote",
    "remote-first",
)
_HYBRID_PHRASES = ("hybrid",)
_RELOCATION_PHRASES = (
    "open to relocation",
    "willing to relocate",
    "will relocate",
    "open to relocate",
    "relocation possible",
    "happy to relocate",
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _normalise(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def _detect_country(text: str) -> Optional[str]:
    """Return canonical country name if a recognised alias is in `text`."""
    norm = _normalise(text)
    if not norm:
        return None
    # Sort longest-first so "south africa" wins over "africa".
    for alias in sorted(_COUNTRY_ALIASES.keys(), key=len, reverse=True):
        # Word-boundary-ish: surrounded by space/punct or string boundary.
        if re.search(rf"(^|[^a-z]){re.escape(alias)}([^a-z]|$)", norm):
            return _COUNTRY_ALIASES[alias]
    return None


def _detect_tz_offset(text: str) -> Optional[float]:
    """Return UTC offset in hours if a recognised hub city is in `text`."""
    norm = _normalise(text)
    if not norm:
        return None
    for hub in sorted(_TZ_OFFSETS_HOURS.keys(), key=len, reverse=True):
        if re.search(rf"(^|[^a-z]){re.escape(hub)}([^a-z]|$)", norm):
            return _TZ_OFFSETS_HOURS[hub]
    return None


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    norm = _normalise(text)
    return any(p in norm for p in phrases)


def _is_remote_role(job: JobOpening) -> bool:
    haystack = " ".join(
        [
            job.location or "",
            job.position_summary or "",
            job.raw_text or "",
        ]
    )
    return _has_phrase(haystack, _REMOTE_PHRASES)


def _candidate_open_to_relocation(candidate: CandidateProfile) -> bool:
    return _has_phrase(candidate.raw_text or "", _RELOCATION_PHRASES)


def _tz_overlap_hours(c_offset: float | None, j_offset: float | None) -> float | None:
    """Approx working-hour overlap between two UTC offsets (assume both
    work 9 AM - 6 PM local). Returns None when either side is unknown."""
    if c_offset is None or j_offset is None:
        return None
    diff = abs(c_offset - j_offset)
    overlap = max(0.0, 9.0 - diff)
    return round(overlap, 1)


# ---------------------------------------------------------------------------
# Deterministic check
# ---------------------------------------------------------------------------


def _deterministic_assess(
    candidate: CandidateProfile, job: JobOpening
) -> LocationFitReport:
    """Pure-Python first pass. May return fit='unknown' to defer to the LLM."""
    c_loc = candidate.location or ""
    j_loc = job.location or ""

    is_remote = _is_remote_role(job)
    c_country = _detect_country(c_loc) or _detect_country(candidate.raw_text or "")
    j_country = _detect_country(j_loc) or _detect_country(
        " ".join(filter(None, [job.position_summary, job.raw_text]))
    )
    c_tz = _detect_tz_offset(c_loc) or _detect_tz_offset(candidate.raw_text or "")
    j_tz = _detect_tz_offset(j_loc) or _detect_tz_offset(
        " ".join(filter(None, [job.position_summary, job.raw_text]))
    )
    overlap = _tz_overlap_hours(c_tz, j_tz)
    open_to_reloc = _candidate_open_to_relocation(candidate)

    # ---- decisions ----------------------------------------------------------
    reasons: list[str] = []
    suggestions: list[str] = []
    requires_relocation = False

    if is_remote:
        reasons.append(
            "Role is remote — location compatibility is not a hard filter."
        )
        if overlap is not None:
            reasons.append(
                f"Approx working-hour overlap: {overlap}h between candidate and team."
            )
            if overlap < 3:
                fit = "warn"
                suggestions.append(
                    "Confirm time-zone overlap is acceptable; <3h is hard for sync collaboration."
                )
            else:
                fit = "ok"
        else:
            fit = "ok"
        return LocationFitReport(
            fit=fit,
            candidate_location=c_loc or None,
            job_location=j_loc or None,
            is_remote_role=True,
            requires_relocation=False,
            time_zone_overlap_hours=overlap,
            reasons=reasons,
            suggestions=suggestions,
            summary=(
                "Remote role — location-fit is permissive; minor time-zone caveats "
                "may apply."
            ),
        )

    # On-site or hybrid
    if c_country and j_country:
        if c_country == j_country:
            fit = "ok"
            reasons.append(
                f"Candidate and role both in {c_country}."
            )
            return LocationFitReport(
                fit=fit,
                candidate_location=c_loc or None,
                job_location=j_loc or None,
                is_remote_role=False,
                requires_relocation=False,
                time_zone_overlap_hours=overlap,
                reasons=reasons,
                summary=f"Same-country fit ({c_country}).",
            )
        # Country mismatch on a non-remote role.
        if open_to_reloc:
            requires_relocation = True
            reasons.append(
                f"Country mismatch ({c_country} -> {j_country}) but candidate "
                f"states openness to relocation."
            )
            suggestions.append(
                "Confirm the company supports relocation / visa sponsorship for this role."
            )
            return LocationFitReport(
                fit="warn",
                candidate_location=c_loc or None,
                job_location=j_loc or None,
                is_remote_role=False,
                requires_relocation=True,
                time_zone_overlap_hours=overlap,
                reasons=reasons,
                suggestions=suggestions,
                summary=(
                    f"Cross-country move required ({c_country} → {j_country}); "
                    f"candidate stated relocation intent."
                ),
            )
        # Hard mismatch.
        reasons.append(
            f"Hard country mismatch: candidate in {c_country}, role in {j_country}, "
            f"role is not remote, no relocation intent stated on resume."
        )
        suggestions.append(
            "Either widen the role to remote OR confirm sponsorship and relocation budget."
        )
        return LocationFitReport(
            fit="block",
            candidate_location=c_loc or None,
            job_location=j_loc or None,
            is_remote_role=False,
            requires_relocation=True,
            time_zone_overlap_hours=overlap,
            reasons=reasons,
            suggestions=suggestions,
            summary=(
                f"Country mismatch ({c_country} vs {j_country}); on-site role; "
                f"no relocation signal — likely hard reject."
            ),
        )

    # Unknown — defer to LLM if available.
    return LocationFitReport(
        fit="unknown",
        candidate_location=c_loc or None,
        job_location=j_loc or None,
        is_remote_role=is_remote,
        requires_relocation=False,
        time_zone_overlap_hours=overlap,
        reasons=[
            "Could not unambiguously parse country / city from resume or JD; "
            "deferring to LLM fallback."
        ],
        summary="Insufficient location data — verifier could not decide.",
    )


# ---------------------------------------------------------------------------
# LLM fallback
# ---------------------------------------------------------------------------


_LLM_PROMPT = (
    "You are the Location-Fit Agent. Decide whether the candidate's location\n"
    "is compatible with the job's location requirements.\n\n"
    "Treat the following as ONE of:\n"
    "  * `ok`     — same country / region OR fully remote.\n"
    "  * `warn`   — different country but candidate stated relocation\n"
    "                intent OR job allows hybrid with significant overlap.\n"
    "  * `block`  — hard mismatch and the role is not remote and the\n"
    "                candidate has no stated relocation intent.\n"
    "  * `unknown`— genuinely insufficient data; do NOT guess.\n\n"
    "Return JSON:\n"
    "{\n"
    '  "fit": "ok|warn|block|unknown",\n'
    '  "candidate_location": "<best-guess string or null>",\n'
    '  "job_location": "<best-guess string or null>",\n'
    '  "is_remote_role": <true|false|null>,\n'
    '  "requires_relocation": <true|false>,\n'
    '  "time_zone_overlap_hours": <number or null>,\n'
    '  "reasons": ["..."],\n'
    '  "suggestions": ["..."],\n'
    '  "summary": "<one paragraph>",\n'
    '  "agent_name": "LocationFitAgent"\n'
    "}\n\n"
    "Return ONLY the JSON object. No prose.\n"
)


def _build_llm_prompt(candidate: CandidateProfile, job: JobOpening) -> str:
    return "\n\n".join(
        [
            _LLM_PROMPT,
            f"=== CANDIDATE LOCATION FIELD ===\n{candidate.location or '(empty)'}",
            f"=== CANDIDATE RESUME EXCERPT (first 3000 chars) ===\n"
            f"{(candidate.raw_text or '')[:3000]}",
            f"=== JOB LOCATION FIELD ===\n{job.location or '(empty)'}",
            f"=== JOB POSITION SUMMARY ===\n{job.position_summary or '(empty)'}",
            f"=== JOB RAW EXCERPT (first 1500 chars) ===\n{(job.raw_text or '')[:1500]}",
        ]
    )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class LocationFitAgent:
    """Pre-flight location / time-zone / remote-eligibility check.

    Hybrid: deterministic first, LLM fallback only on `unknown`. Cached
    per (candidate_id, jd_content_hash) so repeated matches against the
    same JD never repeat the LLM call.
    """

    name = "LocationFitAgent"

    def __init__(
        self,
        config: JobMatchingConfig,
        llm: JobMatchingLLM | None = None,
        cache: Optional[Cache] = None,
    ) -> None:
        self.config = config
        # Lazy: only instantiate the LLM if we actually fall back to it.
        self._llm = llm
        self._cache: Cache = cache or InMemoryLRUCache(max_size=2048)

    @staticmethod
    def _cache_key(candidate: CandidateProfile, job: JobOpening, ch: str) -> str:
        return f"location_fit:{candidate.candidate_id}:{job.jd_id}:{ch}"

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        sink: ThoughtSink | None = None,
    ) -> LocationFitReport:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="OBSERVE",
                thought="Checking location / time-zone compatibility",
                state="PRE_FLIGHT",
                timestamp=_now(),
            ),
        )

        ch = jd_content_hash(
            {
                "jd_id": job.jd_id,
                "location": job.location,
                "position_summary": (job.position_summary or "")[:1000],
            }
        )
        key = self._cache_key(candidate, job, ch)
        cached = await self._cache.get(key)
        if cached is not None:
            try:
                report = LocationFitReport.model_validate(cached)
                await _emit(
                    sink,
                    AgentThought(
                        agent=self.name,
                        phase="REFLECT",
                        thought=f"Location fit cached: {report.fit.upper()}",
                        state="PRE_FLIGHT",
                        timestamp=_now(),
                        metadata={"cache": "hit", "fit": report.fit},
                    ),
                )
                return report
            except Exception:
                pass

        # ---- deterministic first pass ----
        det_report = _deterministic_assess(candidate, job)
        if det_report.fit != "unknown":
            await self._cache.set(key, det_report.model_dump(), ttl_seconds=24 * 3600)
            await _emit(
                sink,
                AgentThought(
                    agent=self.name,
                    phase="REFLECT",
                    thought=f"Location fit: {det_report.fit.upper()} (deterministic)",
                    state="PRE_FLIGHT",
                    timestamp=_now(),
                    metadata={"fit": det_report.fit, "fast_path": True},
                ),
            )
            return det_report

        # ---- LLM fallback when deterministic check is genuinely unsure ----
        if self._llm is None:
            self._llm = JobMatchingLLM(
                self.config,
                temperature=self.config.specialist_temperature,
                model_override=self.config.llm_specialist_model,
            )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="ACT",
                thought="Deterministic check ambiguous — running LLM fallback",
                state="PRE_FLIGHT",
                timestamp=_now(),
            ),
        )

        try:
            raw = await self._llm.acall_structured(
                _build_llm_prompt(candidate, job),
                schema_model=LocationFitReport,
                retry_on_parse_error=2,
            )
        except Exception as exc:
            logger.error("LocationFitAgent LLM fallback failed: %s", exc, exc_info=True)
            # Fail-open: do NOT block on agent failure. Surface as warn so a
            # recruiter eyeballs it.
            report = det_report.model_copy(
                update={
                    "fit": "warn",
                    "summary": (
                        "Location-fit agent failed to run; defaulting to 'warn' "
                        "so a recruiter can verify manually."
                    ),
                    "reasons": det_report.reasons
                    + ["LLM fallback failed; manual review recommended."],
                }
            )
            await self._cache.set(key, report.model_dump(), ttl_seconds=300)
            return report

        try:
            report = LocationFitReport.model_validate(raw)
        except Exception as exc:
            logger.warning("LocationFitAgent parse failed: %s", exc)
            report = det_report.model_copy(update={"fit": "warn"})

        await self._cache.set(key, report.model_dump(), ttl_seconds=24 * 3600)
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"Location fit: {report.fit.upper()} (LLM-aided)",
                state="PRE_FLIGHT",
                timestamp=_now(),
                metadata={"fit": report.fit, "llm_fallback": True},
            ),
        )
        return report
