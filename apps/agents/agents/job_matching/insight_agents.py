"""
Layer 4 — Insight Agents
========================
* HRAdvisorAgent      — Action-oriented guidance for the recruiter.
* ExplainabilityAgent — Per-dimension, evidence-backed rationale.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    AgentThought,
    ArbitratorResult,
    CandidateProfile,
    DimensionScore,
    Evidence,
    ExplainabilityReport,
    ExplanationCard,
    HRInsights,
    InterviewQuestion,
    JobOpening,
    RiskAssessment,
    SynthesisResult,
)
from agents.job_matching.llm_client import JobMatchingLLM
from agents.job_matching.prompts import (
    build_advisor_prompt,
    build_explainability_prompt,
)
from agents.job_matching.scoring import signed_contributions
from agents.job_matching.swarm_agents import _emit, _now, ThoughtSink

logger = logging.getLogger(__name__)

_NEUTRAL_FALLBACK_MARKER = "neutral fallback"


def _all_core_dimensions_are_neutral_placeholder(
    dimension_scores: list[DimensionScore],
) -> bool:
    """True when every non-risk specialist used the swarm neutral fallback (LLM failure)."""
    core = [ds for ds in dimension_scores if ds.dimension != "risk"]
    if not core:
        return False
    return all(
        _NEUTRAL_FALLBACK_MARKER in (ds.summary or "").lower() for ds in core
    )


def _candidate_excerpt(candidate: CandidateProfile, limit: int = 4000) -> str:
    parts = [
        f"Candidate: {candidate.name}",
        f"Headline: {candidate.headline or candidate.current_role or ''}",
        f"Years: {candidate.total_years_experience}",
        f"Skills: {', '.join(candidate.technical_skills[:25])}",
        f"Tools: {', '.join(candidate.tools[:20])}",
        f"Certifications: {', '.join(candidate.certifications[:10])}",
        f"Education: {', '.join(candidate.degrees[:6])}",
    ]
    if candidate.raw_text:
        parts.append("\n--- Resume excerpt ---\n" + candidate.raw_text[:limit])
    return "\n".join(parts)


def _job_excerpt(job: JobOpening, limit: int = 3000) -> str:
    parts = [
        f"Title: {job.job_title}",
        f"Department: {job.department or ''}",
        f"Level: {job.job_level or ''}",
        f"Required Skills: {', '.join(job.required_skills[:25])}",
        f"Preferred Skills: {', '.join(job.preferred_skills[:15])}",
        f"Tools: {', '.join(job.tools_technologies[:20])}",
    ]
    if job.position_summary:
        parts.append(job.position_summary[:1500])
    if job.raw_text:
        parts.append("\n--- JD excerpt ---\n" + job.raw_text[:limit])
    return "\n".join(parts)


# ============================================================================
# HR ADVISOR
# ============================================================================


class HRAdvisorAgent:
    name = "HRAdvisor"

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.advisor_temperature)

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        arbitrator: ArbitratorResult,
        dimension_scores: list[DimensionScore],
        risk: RiskAssessment | None,
        sink: ThoughtSink | None = None,
    ) -> HRInsights:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="THINK",
                thought="Translating verdict into recruiter-ready actions",
                state="INSIGHT",
                timestamp=_now(),
            ),
        )

        specialist_payload = [
            {
                "dimension": ds.dimension,
                "score": ds.score,
                "summary": ds.summary,
                "strengths": ds.strengths,
                "gaps": ds.gaps,
            }
            for ds in dimension_scores
        ]
        if risk:
            specialist_payload.append(
                {
                    "dimension": "risk",
                    "score": risk.score,
                    "flags": risk.flags,
                    "summary": risk.summary,
                }
            )

        prompt = build_advisor_prompt(
            candidate_json=_candidate_excerpt(candidate),
            job_json=_job_excerpt(job),
            arbitrator_json=json.dumps(arbitrator.model_dump(), default=str),
            specialist_outputs_json=json.dumps(specialist_payload, default=str),
        )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=HRInsights, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("HRAdvisor failed: %s", exc)
            payload = {}

        questions: list[InterviewQuestion] = []
        for item in (payload.get("interview_questions") or [])[:8]:
            if not isinstance(item, dict):
                continue
            try:
                questions.append(
                    InterviewQuestion(
                        question=str(item.get("question", ""))[:500],
                        category=str(item.get("category", "technical")).lower(),  # type: ignore[arg-type]
                        rationale=str(item.get("rationale", ""))[:500],
                        targets_dimension=item.get("targets_dimension") or None,
                    )
                )
            except Exception:
                continue

        insights = HRInsights(
            decision_tip=str(payload.get("decision_tip", arbitrator.verdict.value))[:300],
            key_talking_points=[str(p) for p in (payload.get("key_talking_points") or [])][:6],
            interview_questions=questions,
            recommended_next_steps=[
                str(s) for s in (payload.get("recommended_next_steps") or [])
            ][:6],
            salary_band_hint=(
                str(payload.get("salary_band_hint"))[:200]
                if payload.get("salary_band_hint")
                else None
            ),
            onboarding_focus_areas=[
                str(o) for o in (payload.get("onboarding_focus_areas") or [])
            ][:6],
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"Generated {len(insights.interview_questions)} interview questions",
                state="INSIGHT",
                timestamp=_now(),
            ),
        )
        return insights


# ============================================================================
# EXPLAINABILITY
# ============================================================================


class ExplainabilityAgent:
    name = "ExplainabilityAgent"

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.specialist_temperature)

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        arbitrator: ArbitratorResult,
        synthesis: SynthesisResult,
        dimension_scores: list[DimensionScore],
        weights: dict[str, float],
        sink: ThoughtSink | None = None,
    ) -> ExplainabilityReport:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="THINK",
                thought="Building per-dimension explanation cards with evidence",
                state="INSIGHT",
                timestamp=_now(),
            ),
        )

        # Deterministic contribution baseline
        det_contribs = signed_contributions(
            dimension_scores, weights, arbitrator.final_score
        )

        prompt = build_explainability_prompt(
            arbitrator_json=json.dumps(arbitrator.model_dump(), default=str),
            weighted_breakdown_json=json.dumps(
                synthesis.weighted_breakdown, default=str
            ),
            specialist_outputs_json=json.dumps(
                [
                    {
                        "dimension": ds.dimension,
                        "score": ds.score,
                        "confidence": ds.confidence,
                        "summary": ds.summary,
                        "strengths": ds.strengths,
                        "gaps": ds.gaps,
                    }
                    for ds in dimension_scores
                ],
                default=str,
            ),
            candidate_excerpt=_candidate_excerpt(candidate, limit=2500),
            jd_excerpt=_job_excerpt(job, limit=1800),
        )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=ExplainabilityReport, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("Explainability failed: %s", exc)
            payload = {}

        # Build cards keyed by dimension. The LLM contributes only:
        #   * `why_score` — qualitative reason (1-2 sentences).
        #   * `evidence`  — verbatim quotes from resume / JD.
        # `contribution_pct` is taken DETERMINISTICALLY from
        # `signed_contributions(...)` — the LLM is not allowed to invent or
        # drift this number, since it must add up to ~100 across dims.
        valid_dims = {ds.dimension for ds in dimension_scores}
        llm_cards_by_dim: dict[str, dict[str, Any]] = {}
        for item in (payload.get("cards") or [])[:10]:
            if not isinstance(item, dict):
                continue
            dim = item.get("dimension")
            if dim in valid_dims and dim not in llm_cards_by_dim:
                llm_cards_by_dim[dim] = item

        cards: list[ExplanationCard] = []
        for ds in dimension_scores:
            llm_item = llm_cards_by_dim.get(ds.dimension, {})
            evidence: list[Evidence] = []
            for e in (llm_item.get("evidence") or [])[:3]:
                if not isinstance(e, dict):
                    continue
                try:
                    evidence.append(Evidence(**e))
                except Exception:
                    continue
            # Fall back to the specialist's own evidence when the LLM didn't
            # provide any (or hallucinated invalid evidence).
            if not evidence and ds.evidence:
                evidence = ds.evidence[:2]
            why_score = (
                str(llm_item.get("why_score", "")).strip()[:600]
                or (ds.summary[:400] or f"{ds.dimension} score: {ds.score:.1f}")
            )
            cards.append(
                ExplanationCard(
                    dimension=ds.dimension,
                    contribution_pct=round(det_contribs.get(ds.dimension, 0.0), 2),
                    why_score=why_score,
                    evidence=evidence,
                )
            )

        quality_warning: str | None = None
        if _all_core_dimensions_are_neutral_placeholder(dimension_scores):
            quality_warning = (
                "Specialists did not receive usable LLM output, so each dimension "
                "used the neutral placeholder (50/100). The ensemble overall is then "
                "~50 as well, so contribution vs overall shows +0 pts — that is "
                "expected arithmetic, not evidence of a flat match. Restore Vertex "
                "access (model id, GCP_LOCATION/global vs regional, billing, preview "
                "allowlisting) and re-run."
            )

        report = ExplainabilityReport(
            cards=cards,
            decision_drivers=[
                str(d) for d in (payload.get("decision_drivers") or [])
            ][:5],
            counterfactual=(
                str(payload.get("counterfactual"))[:500]
                if payload.get("counterfactual")
                else None
            ),
            quality_warning=quality_warning,
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="DONE",
                thought=f"Built {len(report.cards)} explanation cards",
                state="INSIGHT",
                timestamp=_now(),
            ),
        )
        return report
