"""
Confidence-Weighted Ensemble Scoring & Verdict Mapping
======================================================
Pure functions used by the Synthesizer / Arbitrator agents.  Centralised here
so we can unit-test the maths without booting an LLM.
"""

from __future__ import annotations

from typing import Iterable, Optional

from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    DimensionScore,
    JobOpening,
    RiskAssessment,
    Verdict,
)


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    """Ensure the configured per-dimension weights sum to ~1.0."""
    total = sum(max(0.0, v) for v in weights.values())
    if total <= 0:
        return {k: 1.0 / len(weights) for k in weights}
    return {k: max(0.0, v) / total for k, v in weights.items()}


def confidence_weighted_score(
    dimension_scores: Iterable[DimensionScore],
    weights: dict[str, float],
) -> dict[str, float]:
    """Return weighted overall + per-dimension breakdown.

    Formula:
        overall = Σ (w_i × s_i × c_i) / Σ (w_i × c_i)
    """
    norm_weights = normalise_weights(weights)
    weighted_breakdown: dict[str, float] = {}
    numerator = 0.0
    denominator = 0.0

    for ds in dimension_scores:
        if ds.dimension == "risk":
            # Risk is treated separately as a soft cap (see apply_risk_cap).
            weighted_breakdown["risk"] = ds.score
            continue
        w = norm_weights.get(ds.dimension, 0.0)
        c = max(0.05, ds.confidence)  # avoid divide-by-zero & dampen low-confidence
        weighted_breakdown[ds.dimension] = ds.score
        numerator += w * ds.score * c
        denominator += w * c

    overall = numerator / denominator if denominator > 0 else 0.0
    weighted_breakdown["overall"] = round(overall, 2)
    return weighted_breakdown


def apply_risk_cap(
    overall: float,
    risk: RiskAssessment | None,
    config: JobMatchingConfig | None = None,
) -> float:
    """If the candidate has serious red flags, cap the overall score.

    Tiered caps are loaded from ``config`` (so ops can tune them per deployment
    via the ``JOB_MATCHING_RISK_CAP_*`` env vars). When ``config`` is ``None``
    we fall back to the historical defaults so unit tests and ad-hoc callers
    are unaffected.
    """
    if risk is None:
        return overall
    if config is None:
        severe_t, severe_cap = 30.0, 55.0
        moderate_t, moderate_cap = 50.0, 70.0
        mild_t, mild_cap = 65.0, 85.0
    else:
        severe_t = config.risk_cap_severe_threshold
        severe_cap = config.risk_cap_severe
        moderate_t = config.risk_cap_moderate_threshold
        moderate_cap = config.risk_cap_moderate
        mild_t = config.risk_cap_mild_threshold
        mild_cap = config.risk_cap_mild
    if risk.score < severe_t:
        return min(overall, severe_cap)
    if risk.score < moderate_t:
        return min(overall, moderate_cap)
    if risk.score < mild_t:
        return min(overall, mild_cap)
    return overall


def map_verdict(score: float, config: JobMatchingConfig) -> Verdict:
    """Map a final score (0-100) to one of the five hiring verdicts."""
    if score >= config.strong_hire_threshold:
        return Verdict.STRONG_HIRE
    if score >= config.hire_threshold:
        return Verdict.HIRE
    if score >= config.consider_threshold:
        return Verdict.CONSIDER
    if score >= 30:
        return Verdict.NO_HIRE
    return Verdict.STRONG_NO_HIRE


def aggregate_confidence(
    dimension_scores: Iterable[DimensionScore],
    weights: dict[str, float],
) -> float:
    """Weighted average of per-agent confidence."""
    norm = normalise_weights(weights)
    num = 0.0
    den = 0.0
    for ds in dimension_scores:
        if ds.dimension == "risk":
            continue
        w = norm.get(ds.dimension, 0.0)
        num += w * ds.confidence
        den += w
    return num / den if den > 0 else 0.7


_SENIOR_LEVEL_TOKENS = {
    "senior", "sr.", "sr",
    "staff", "principal", "lead",
    "director", "head", "vp", "chief",
}
_JUNIOR_LEVEL_TOKENS = {"junior", "jr.", "jr", "intern", "associate", "entry"}
_SELF_TAUGHT_TOKENS = {
    "self-taught", "self taught", "no degree required",
    "bootcamp", "or equivalent experience", "equivalent experience",
}


def _level_signal(job: JobOpening) -> str:
    """Classify JD seniority into 'senior' | 'junior' | 'mid' from level + title."""
    blob = " ".join(
        filter(None, [job.job_level or "", job.job_title or ""])
    ).lower()
    if any(tok in blob for tok in _SENIOR_LEVEL_TOKENS):
        return "senior"
    if any(tok in blob for tok in _JUNIOR_LEVEL_TOKENS):
        return "junior"
    return "mid"


def _education_explicit(job: JobOpening) -> bool:
    """True when the JD explicitly mentions a degree requirement."""
    edu = (job.education_requirement or "").lower()
    if not edu:
        return False
    if any(tok in edu for tok in _SELF_TAUGHT_TOKENS):
        return False
    return any(
        kw in edu
        for kw in ("bachelor", "master", "phd", "ph.d", "degree", "b.s", "m.s", "ba ", "b.a")
    )


def _tech_density(job: JobOpening) -> float:
    """Rough 0-1 score of how heavily a JD emphasises hard technical stack."""
    n_tools = len(job.tools_technologies or [])
    n_required = len(job.required_skills or [])
    raw = n_tools + n_required
    if raw <= 4:
        return 0.2
    if raw <= 8:
        return 0.5
    if raw <= 14:
        return 0.75
    return 1.0


def adaptive_weights(
    job: JobOpening,
    base_weights: dict[str, float],
    config: JobMatchingConfig,
) -> dict[str, float]:
    """Adjust base weights based on JD characteristics.

    Heuristics (kept simple and explainable so they can be defended in audits):
    * Senior / leadership JDs -> +experience, +culture, -growth.
    * Junior / entry JDs       -> +growth, -experience.
    * Tech-dense JDs           -> +skills, -culture.
    * No explicit degree req   -> -education, +growth.

    Each delta is bounded by ``config.adaptive_weight_max_shift`` after
    re-normalisation so weights remain on the simplex. Returns a NEW dict;
    the input is not mutated.
    """
    if not config.enable_adaptive_weights:
        return normalise_weights(base_weights)

    weights = dict(base_weights)
    cap = float(config.adaptive_weight_max_shift)

    level = _level_signal(job)
    if level == "senior":
        weights["experience"] = weights.get("experience", 0.0) + cap * 0.6
        weights["culture"] = weights.get("culture", 0.0) + cap * 0.3
        weights["growth"] = max(0.0, weights.get("growth", 0.0) - cap * 0.6)
    elif level == "junior":
        weights["growth"] = weights.get("growth", 0.0) + cap * 0.6
        weights["experience"] = max(0.0, weights.get("experience", 0.0) - cap * 0.5)

    density = _tech_density(job)
    if density >= 0.75:
        weights["skills"] = weights.get("skills", 0.0) + cap * 0.5
        weights["culture"] = max(0.0, weights.get("culture", 0.0) - cap * 0.3)
    elif density <= 0.2:
        weights["culture"] = weights.get("culture", 0.0) + cap * 0.3

    if not _education_explicit(job):
        weights["education"] = max(0.0, weights.get("education", 0.0) - cap * 0.5)
        weights["growth"] = weights.get("growth", 0.0) + cap * 0.2

    return normalise_weights(weights)


def specialist_score_variance(
    dimension_scores: Iterable[DimensionScore],
) -> float:
    """Population variance of non-risk specialist scores. 0 means unanimous.

    Used to decide whether the Critic LLM call can be safely skipped when
    the swarm is highly confident AND in agreement.
    """
    scores = [ds.score for ds in dimension_scores if ds.dimension != "risk"]
    if not scores:
        return 0.0
    mean = sum(scores) / len(scores)
    return sum((s - mean) ** 2 for s in scores) / len(scores)


def signed_contributions(
    dimension_scores: Iterable[DimensionScore],
    weights: dict[str, float],
    overall: float,
) -> dict[str, float]:
    """Compute each dimension's signed contribution to the overall score.

    Positive contribution = pulled the score up, negative = pulled it down.
    Used by the Explainability agent and the radar/breakdown UI.
    """
    norm = normalise_weights(weights)
    contributions: dict[str, float] = {}
    for ds in dimension_scores:
        if ds.dimension == "risk":
            continue
        w = norm.get(ds.dimension, 0.0)
        contributions[ds.dimension] = round(w * (ds.score - overall), 2)
    return contributions
