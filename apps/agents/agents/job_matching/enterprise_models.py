"""
Enterprise Pydantic Models for Job Matching
===========================================
Strongly-typed contracts shared across every agent in the swarm.

These models double as the structured output schema we ask the LLM to honour
(via prompt engineering + JSON parsing).  Keeping them in one place means a
single source of truth for the API, frontend, agents and tests.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# CORE PRIMITIVES
# ============================================================================

DimensionLiteral = Literal[
    "skills",
    "experience",
    "education",
    "domain",
    "culture",
    "growth",
    "projects",
    "risk",
]


class Verdict(str, Enum):
    """Hiring recommendation verdict."""

    STRONG_HIRE = "STRONG_HIRE"
    HIRE = "HIRE"
    CONSIDER = "CONSIDER"
    NO_HIRE = "NO_HIRE"
    STRONG_NO_HIRE = "STRONG_NO_HIRE"


class Evidence(BaseModel):
    """A quoted piece of evidence from the resume or JD."""

    source: Literal["resume", "jd"] = Field(..., description="Where the quote came from")
    quote: str = Field(..., description="Verbatim quote from the source")
    relevance: float = Field(0.7, ge=0.0, le=1.0, description="How relevant 0-1")
    note: Optional[str] = Field(None, description="Why this evidence matters")


# ============================================================================
# RESUME / JD NORMALISED VIEWS
# ============================================================================


class CandidateProfile(BaseModel):
    """A normalised view of a candidate suitable for downstream agents."""

    candidate_id: str
    name: str = "Unknown"
    email: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    total_years_experience: float = 0.0
    current_role: Optional[str] = None
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    degrees: list[str] = Field(default_factory=list)
    universities: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    raw_text: Optional[str] = None  # Full resume text for evidence extraction


class JobOpening(BaseModel):
    """A normalised view of a Job Description used as the matching target."""

    jd_id: str
    job_title: str
    department: Optional[str] = None
    location: Optional[str] = None
    job_level: Optional[str] = None
    position_summary: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    tools_technologies: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    education_requirement: Optional[str] = None
    experience_requirement: Optional[str] = None
    raw_text: Optional[str] = None


# ============================================================================
# SPECIALIST AGENT OUTPUT (Layer 2)
# ============================================================================


class DimensionScore(BaseModel):
    """A score from a single specialist agent for a single dimension."""

    dimension: DimensionLiteral
    score: float = Field(..., ge=0.0, le=100.0, description="0-100 dimension score")
    confidence: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Self-reported confidence — multiplied into ensemble weighting",
    )
    summary: str = Field(..., description="One-paragraph rationale")
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    agent_name: str

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


class RiskAssessment(BaseModel):
    """Structured red-flag / risk audit."""

    score: float = Field(..., ge=0.0, le=100.0, description="100 = no risk, 0 = high risk")
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    flags: list[dict[str, str]] = Field(
        default_factory=list,
        description="Each flag: {category, severity, description, evidence}",
    )
    summary: str
    agent_name: str = "RiskAgent"


class BiasAudit(BaseModel):
    """Fairness and bias auditor's report."""

    is_fair: bool
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)
    summary: str
    agent_name: str = "BiasAuditor"


class EvidenceGrounding(BaseModel):
    """Per-evidence-item grounding outcome from the deterministic verifier."""

    grounded: bool
    classification: Literal[
        "verbatim",
        "paraphrase",
        "weak_overlap",
        "fabricated",
        "too_short",
        "no_source_text",
    ]
    quote_preview: str = Field(..., description="First 80 chars of the offending quote.")
    source: Literal["resume", "jd"]


class DimensionGrounding(BaseModel):
    """Per-dimension groundedness rollup."""

    dimension: str
    evidence_total: int = 0
    evidence_grounded: int = 0
    grounded_pct: float = Field(0.0, ge=0.0, le=1.0)
    confidence_penalty_applied: float = Field(
        0.0, ge=0.0, le=1.0, description="How much we shaved off this dim's confidence."
    )
    items: list[EvidenceGrounding] = Field(default_factory=list)


class GroundednessReport(BaseModel):
    """End-to-end groundedness audit attached to MatchResult.metadata.

    The verifier ran a deterministic substring + token-overlap check over
    every Evidence quote emitted by the swarm. Fabricated evidence has been
    stripped from the output the recruiter sees; this report explains
    *why*.
    """

    overall_pct: float = Field(0.0, ge=0.0, le=1.0)
    total_evidence: int = 0
    grounded_evidence: int = 0
    fabricated_evidence: int = 0
    raw_text_available: bool = True
    per_dimension: list[DimensionGrounding] = Field(default_factory=list)
    risk_grounded_pct: float = Field(0.0, ge=0.0, le=1.0)
    explainability_grounded_pct: float = Field(0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
    agent_name: str = "EvidenceVerifier"


class LocationFitReport(BaseModel):
    """Pre-flight location / time-zone / remote-eligibility check.

    Often the FIRST hard filter in real hiring: a US-only role and a
    candidate with no US presence is an immediate reject regardless of
    how strong the swarm score is. We surface this as a metadata signal
    (and optionally hard-block) so the orchestrator never wastes a full
    swarm run on a logistical no-go.
    """

    fit: Literal["ok", "warn", "block", "unknown"] = Field(
        ...,
        description=(
            "ok = compatible; warn = needs relocation / time-zone shift; "
            "block = incompatible (different country, no remote allowed); "
            "unknown = insufficient data."
        ),
    )
    candidate_location: Optional[str] = None
    job_location: Optional[str] = None
    is_remote_role: Optional[bool] = None
    requires_relocation: bool = False
    time_zone_overlap_hours: Optional[float] = Field(
        None,
        description="Approx working-hour overlap (4+ recommended for collaboration).",
    )
    reasons: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    summary: str
    agent_name: str = "LocationFitAgent"


class JDHygieneReport(BaseModel):
    """JD pre-flight hygiene check: surfaces malformed / biased JDs.

    Runs once per JD (cached) BEFORE any specialist scores a candidate, so
    we never grade 100 candidates against a JD that has e.g. contradictory
    requirements or protected-attribute language.
    """

    is_acceptable: bool = Field(
        ..., description="False = the JD should be rewritten before matching."
    )
    severity: Literal["ok", "warn", "block"] = Field(
        "ok",
        description=(
            "ok = no issues; warn = matches still run but recruiter is "
            "alerted; block = orchestrator should refuse to match."
        ),
    )
    contradictions: list[str] = Field(
        default_factory=list,
        description="Internally contradictory requirements (e.g. 'junior' but '15+ yrs').",
    )
    protected_attribute_language: list[str] = Field(
        default_factory=list,
        description="Phrases that imply / require protected attributes (age, gender, etc.).",
    )
    unrealistic_requirements: list[str] = Field(
        default_factory=list,
        description="Requirements that are statistically improbable to meet.",
    )
    missing_critical_fields: list[str] = Field(
        default_factory=list,
        description="JD fields that are blank but should not be (e.g. job_level).",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Concrete rewrite suggestions for the recruiter.",
    )
    summary: str
    agent_name: str = "JDHygieneAgent"


# ============================================================================
# DEBATE LAYER (Layer 3)
# ============================================================================


class SynthesisResult(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0)
    weighted_breakdown: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    top_strengths: list[str] = Field(default_factory=list)
    top_gaps: list[str] = Field(default_factory=list)
    agent_name: str = "Synthesizer"


class CriticChallenge(BaseModel):
    """The Critic agent's challenges to the Synthesizer's verdict."""

    is_overall_score_justified: bool
    blind_spots: list[str] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    suggested_score_adjustment: float = Field(
        0.0,
        ge=-30.0,
        le=30.0,
        description="Critic's recommended adjustment to overall_score (capped)",
    )
    summary: str
    agent_name: str = "Critic"


class ArbitratorResult(BaseModel):
    """Final post-debate verdict produced by the Arbitrator."""

    final_score: float = Field(..., ge=0.0, le=100.0)
    verdict: Verdict
    rationale: str
    accepted_critic_points: list[str] = Field(default_factory=list)
    rejected_critic_points: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    agent_name: str = "Arbitrator"


# ============================================================================
# INSIGHT LAYER (Layer 4)
# ============================================================================


class InterviewQuestion(BaseModel):
    question: str
    category: Literal[
        "technical",
        "behavioural",
        "experience",
        "scenario",
        "culture",
        "leadership",
    ] = "technical"
    rationale: str
    targets_dimension: Optional[DimensionLiteral] = None


class HRInsights(BaseModel):
    """Action-oriented HR Advisor output."""

    decision_tip: str
    key_talking_points: list[str] = Field(default_factory=list)
    interview_questions: list[InterviewQuestion] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    salary_band_hint: Optional[str] = None
    onboarding_focus_areas: list[str] = Field(default_factory=list)
    agent_name: str = "HRAdvisor"


class ExplanationCard(BaseModel):
    """Per-dimension explainability card with evidence quotes."""

    dimension: DimensionLiteral
    contribution_pct: float = Field(..., ge=-100.0, le=100.0)
    why_score: str
    evidence: list[Evidence] = Field(default_factory=list)


class ExplainabilityReport(BaseModel):
    cards: list[ExplanationCard] = Field(default_factory=list)
    decision_drivers: list[str] = Field(default_factory=list)
    counterfactual: Optional[str] = Field(
        None,
        description="What would push this candidate into the next tier",
    )
    quality_warning: Optional[str] = Field(
        None,
        description="Set when outputs are placeholders (e.g. LLM failure) so UI is not misread",
    )
    agent_name: str = "ExplainabilityAgent"


# ============================================================================
# AGENT THOUGHT (live stream)
# ============================================================================


class AgentThought(BaseModel):
    """A single thought emitted by an agent (used for streaming)."""

    agent: str
    phase: Literal["OBSERVE", "THINK", "PLAN", "ACT", "REFLECT", "SWARM", "DEBATE", "INSIGHT", "DONE"]
    thought: str
    action: Optional[str] = None
    state: Optional[str] = None
    timestamp: Optional[str] = None
    autonomous: bool = True
    metadata: Optional[dict[str, Any]] = None


# ============================================================================
# MATCH RESULT (final API contract)
# ============================================================================


class MatchResult(BaseModel):
    """The end-to-end output of a single resume → JD matching run."""

    candidate_id: str
    jd_id: str
    job_title: str

    overall_score: float = Field(..., ge=0.0, le=100.0)
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)

    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    risk: Optional[RiskAssessment] = None
    bias_audit: Optional[BiasAudit] = None

    synthesis: SynthesisResult
    critic: Optional[CriticChallenge] = None
    arbitrator: ArbitratorResult

    insights: HRInsights
    explainability: ExplainabilityReport

    agent_thoughts: list[AgentThought] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateMatchSummary(BaseModel):
    """Compact ranking-grid view for `/match-candidates` endpoint."""

    candidate_id: str
    candidate_name: str
    overall_score: float
    verdict: Verdict
    top_strengths: list[str] = Field(default_factory=list)
    top_gaps: list[str] = Field(default_factory=list)
    confidence: float


class RankingResult(BaseModel):
    """Output of ranking a JD against many candidates."""

    jd_id: str
    job_title: str
    candidates: list[CandidateMatchSummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
