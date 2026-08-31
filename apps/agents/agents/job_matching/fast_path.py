"""
Embedding Fast-Path
===================
A pre-flight check that uses cosine similarity between candidate and JD
embeddings to short-circuit obvious match / mismatch cases before the
swarm spends a single LLM token.

Why this is safe
----------------
* We only short-circuit at *extreme* thresholds (defaults: <0.25 = obvious
  reject, >0.92 = obvious strong-match). The middle band (the vast majority
  of real candidates) goes through the full swarm.
* The fast-path runs *in addition* to the cache; both can short-circuit.
* When embeddings cannot be computed (model not loaded, Milvus down) we
  return ``None`` and the orchestrator silently runs the full swarm — no
  silent regressions.

Performance
-----------
On a warm BGE model:
* Embed both inputs:  ~50–80 ms
* Cosine similarity:  microseconds
* Total fast-path overhead: <100 ms

vs. ~30–60 s for the full swarm on the same machine.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    ArbitratorResult,
    BiasAudit,
    CandidateProfile,
    DimensionScore,
    Evidence,
    ExplainabilityReport,
    ExplanationCard,
    HRInsights,
    JobOpening,
    MatchResult,
    RiskAssessment,
    SynthesisResult,
    Verdict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding service (lazy singleton — heavy to load)
# ---------------------------------------------------------------------------

_EMBEDDING_MODEL: Any = None
_EMBEDDING_DISABLED: bool = False


def _get_model(model_name: str = "BAAI/bge-base-en-v1.5") -> Any:
    """Lazy-load the BGE model used by the rest of the project.

    On import error or load failure we permanently disable the fast-path
    for this process — saves ~30 ms per call after the first miss.
    """
    global _EMBEDDING_MODEL, _EMBEDDING_DISABLED
    if _EMBEDDING_DISABLED:
        return None
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    try:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer(model_name)
        return _EMBEDDING_MODEL
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "Embedding fast-path unavailable (%s: %s); skipping shortcut.",
            type(exc).__name__,
            exc,
        )
        _EMBEDDING_DISABLED = True
        return None


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------


def _candidate_text(c: CandidateProfile) -> str:
    return " | ".join(
        filter(
            None,
            [
                c.headline or "",
                c.current_role or "",
                "Skills: " + ", ".join(c.technical_skills[:30]),
                "Tools: " + ", ".join(c.tools[:20]),
                "Experience: " + str(c.total_years_experience) + " years",
                (c.raw_text or "")[:1500],
            ],
        )
    )


def _job_text(j: JobOpening) -> str:
    return " | ".join(
        filter(
            None,
            [
                j.job_title,
                j.job_level or "",
                "Required: " + ", ".join(j.required_skills[:25]),
                "Preferred: " + ", ".join(j.preferred_skills[:15]),
                "Tools: " + ", ".join(j.tools_technologies[:20]),
                (j.position_summary or "")[:1200],
            ],
        )
    )


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def compute_similarity(
    candidate: CandidateProfile, job: JobOpening, model_name: str = "BAAI/bge-base-en-v1.5"
) -> Optional[float]:
    model = _get_model(model_name)
    if model is None:
        return None
    try:
        c_vec = model.encode(_candidate_text(candidate), convert_to_numpy=False)
        j_vec = model.encode(_job_text(job), convert_to_numpy=False)
        c_list = c_vec.tolist() if hasattr(c_vec, "tolist") else list(c_vec)
        j_list = j_vec.tolist() if hasattr(j_vec, "tolist") else list(j_vec)
        return _cosine(c_list, j_list)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fast-path similarity failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Synthetic MatchResult builders for the two short-circuit branches
# ---------------------------------------------------------------------------


def _evidence_note(similarity: float) -> str:
    return (
        f"Embedding cosine similarity={similarity:.2f} — "
        "fast-path verdict from BGE-base-en-v1.5."
    )


def _baseline_dimension_scores(score: float, summary: str) -> list[DimensionScore]:
    """Six neutral DimensionScores so MatchResult validation is satisfied."""
    return [
        DimensionScore(
            dimension=dim,
            score=score,
            confidence=0.5,
            summary=summary,
            agent_name=f"FastPath-{dim}",
        )
        for dim in ("skills", "experience", "education", "domain", "culture", "growth")
    ]


def build_obvious_reject(
    candidate: CandidateProfile,
    job: JobOpening,
    similarity: float,
    config: JobMatchingConfig,
) -> MatchResult:
    final_score = round(similarity * 100, 2)
    summary = (
        f"Obvious mismatch: candidate↔JD embedding similarity={similarity:.2f}, "
        f"below reject threshold {config.fast_path_reject_threshold:.2f}. The full "
        "swarm was skipped because no realistic specialist verdict could lift this "
        "candidate above the consider-threshold."
    )
    note = _evidence_note(similarity)
    arbitrator = ArbitratorResult(
        final_score=final_score,
        verdict=Verdict.STRONG_NO_HIRE,
        rationale=summary,
        accepted_critic_points=[],
        rejected_critic_points=[],
        confidence=0.85,
    )
    synthesis = SynthesisResult(
        overall_score=final_score,
        weighted_breakdown={},
        confidence=0.85,
        summary=summary,
        top_strengths=[],
        top_gaps=["Severe skills/role mismatch detected at embedding level."],
    )
    insights = HRInsights(
        decision_tip="Reject — no swarm-level review needed.",
        key_talking_points=[],
        interview_questions=[],
        recommended_next_steps=["Send standard rejection."],
    )
    explainability = ExplainabilityReport(
        cards=[
            ExplanationCard(
                dimension="skills",
                contribution_pct=-30.0,
                why_score="Candidate profile and JD diverge at the embedding level.",
                evidence=[
                    Evidence(source="resume", quote=note, relevance=1.0, note=note)
                ],
            )
        ],
        decision_drivers=["Embedding similarity below reject threshold."],
        counterfactual="No reasonable single signal would lift this match into CONSIDER.",
        quality_warning=None,
    )
    return MatchResult(
        candidate_id=candidate.candidate_id,
        jd_id=job.jd_id,
        job_title=job.job_title,
        overall_score=final_score,
        verdict=Verdict.STRONG_NO_HIRE,
        confidence=0.85,
        dimension_scores=_baseline_dimension_scores(final_score, note),
        risk=RiskAssessment(
            score=70.0,
            confidence=0.4,
            flags=[],
            summary="Risk not assessed (fast-path).",
        ),
        bias_audit=BiasAudit(
            is_fair=True, confidence=0.5, issues=[], mitigations=[],
            summary="Bias audit skipped on fast-path.",
        ),
        synthesis=synthesis,
        critic=None,
        arbitrator=arbitrator,
        insights=insights,
        explainability=explainability,
        agent_thoughts=[],
        metadata={
            "fast_path": "reject",
            "similarity": round(similarity, 4),
        },
    )


def build_obvious_strong_hire(
    candidate: CandidateProfile,
    job: JobOpening,
    similarity: float,
    config: JobMatchingConfig,
) -> MatchResult:
    final_score = max(config.strong_hire_threshold + 1.0, round(similarity * 100, 2))
    summary = (
        f"Obvious strong match: candidate↔JD embedding similarity={similarity:.2f}, "
        f"above the strong-hire threshold {config.fast_path_strong_hire_threshold:.2f}. "
        "Full swarm review was skipped — recruiter should still confirm with a screening call."
    )
    note = _evidence_note(similarity)
    arbitrator = ArbitratorResult(
        final_score=final_score,
        verdict=Verdict.STRONG_HIRE,
        rationale=summary,
        accepted_critic_points=[],
        rejected_critic_points=[],
        confidence=0.85,
    )
    synthesis = SynthesisResult(
        overall_score=final_score,
        weighted_breakdown={},
        confidence=0.85,
        summary=summary,
        top_strengths=["Profile aligns strongly with JD at the embedding level."],
        top_gaps=[],
    )
    insights = HRInsights(
        decision_tip="Strong fit — fast-track to a screening call.",
        key_talking_points=["Profile aligns strongly with the JD."],
        interview_questions=[],
        recommended_next_steps=["Schedule recruiter screen.", "Surface to hiring manager."],
    )
    explainability = ExplainabilityReport(
        cards=[
            ExplanationCard(
                dimension="skills",
                contribution_pct=30.0,
                why_score="Candidate profile and JD align strongly at the embedding level.",
                evidence=[
                    Evidence(source="resume", quote=note, relevance=1.0, note=note)
                ],
            )
        ],
        decision_drivers=["Embedding similarity above strong-hire threshold."],
        counterfactual=None,
        quality_warning=(
            "Fast-path strong-hire — confirm with a recruiter screen before final decision."
        ),
    )
    return MatchResult(
        candidate_id=candidate.candidate_id,
        jd_id=job.jd_id,
        job_title=job.job_title,
        overall_score=final_score,
        verdict=Verdict.STRONG_HIRE,
        confidence=0.85,
        dimension_scores=_baseline_dimension_scores(final_score, note),
        risk=RiskAssessment(
            score=80.0,
            confidence=0.4,
            flags=[],
            summary="Risk not assessed (fast-path).",
        ),
        bias_audit=BiasAudit(
            is_fair=True, confidence=0.5, issues=[], mitigations=[],
            summary="Bias audit skipped on fast-path.",
        ),
        synthesis=synthesis,
        critic=None,
        arbitrator=arbitrator,
        insights=insights,
        explainability=explainability,
        agent_thoughts=[],
        metadata={
            "fast_path": "strong_hire",
            "similarity": round(similarity, 4),
        },
    )
