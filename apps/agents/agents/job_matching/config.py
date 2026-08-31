"""
Job Matching Configuration
==========================
Enterprise-grade configuration for the Job Matching agentic system.

Mirrors the patterns used by ``apps.agents.agents.jd_generation.config`` so the
two systems share the same Vertex AI / Milvus / LangSmith infrastructure.
No hardcoded values - everything is read from environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agents.gcp_vertex_credentials import vertex_credential_source_available

logger = logging.getLogger(__name__)


def _default_llm_provider() -> str:
    """Resolve provider from LLM_PROVIDER env (azure_openai on AKS)."""
    from agents.llm.chat_factory import llm_provider

    return llm_provider()


def _default_llm_model() -> str:
    """Resolve model from env / Azure deployment, never a hardcoded name."""
    from agents.llm.chat_factory import primary_llm_model

    return primary_llm_model()


def _default_llm_fallback_model() -> str:
    from agents.llm.chat_factory import fallback_llm_model

    return fallback_llm_model()


class JobMatchingConfig(BaseSettings):
    """Configuration for the Job Matching agentic system."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JOB_MATCHING_",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    # ------------------------------------------------------------------ LLM
    llm_provider: str = Field(default_factory=_default_llm_provider, description="LLM provider")
    llm_model: str = Field(default_factory=_default_llm_model, description="Primary LLM")
    llm_fallback_model: str = Field(
        default_factory=_default_llm_fallback_model,
        description="Fallback LLM (same as primary by default)",
    )
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(
        default=8192,
        ge=512,
        le=65536,
        description="Must be high enough for long JSON (flags, issues, cards); 2048 truncates mid-object.",
    )

    # Specialist agents run with low temperature for deterministic scoring;
    # the synthesiser / advisor can use a slightly higher temperature.
    specialist_temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    debate_temperature: float = Field(default=0.4, ge=0.0, le=1.0)
    advisor_temperature: float = Field(default=0.6, ge=0.0, le=1.0)

    # Request application/json from Vertex for structured agent outputs (reduces markdown + token waste).
    vertex_json_response: bool = Field(default=True)
    # LangChain ChatVertexAI retries transient errors; lower this to fail faster on bad model/region (e.g. 404).
    vertex_max_retries: int = Field(default=2, ge=0, le=10)
    # Pass a Pydantic schema as Vertex's native ``response_schema`` rather than relying on
    # prompt-engineered JSON. Drops the regex-extraction code path on the happy path; we
    # still fall back to text-+-extract if a structured call fails.
    enable_structured_output: bool = Field(default=True)

    # ------------------------------------------------------------------ Model tiering
    # Optional cheaper models per tier (unset / blank inherits ``llm_model`` — same model
    # everywhere when root ``LLM_MODEL`` is gemini-2.5-pro).
    llm_specialist_model: Optional[str] = Field(
        default=None,
        description="Model for Layer-2 specialists + bias auditor. None / blank = llm_model.",
    )
    llm_synthesis_model: Optional[str] = Field(
        default=None,
        description="Model used by Synthesizer/Critic/Arbitrator. None = use llm_model.",
    )
    llm_advisor_model: Optional[str] = Field(
        default=None,
        description="Model for HRAdvisor + Explainability. None / blank = llm_model.",
    )

    # ------------------------------------------------------------------ Vertex AI
    gcp_project: Optional[str] = Field(default=None)
    gcp_location: str = Field(default="us-central1")

    # ------------------------------------------------------------------ Milvus
    # Host/port must match apps/quantchat/config/settings.py (MILVUS_HOST / MILVUS_PORT).
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530, ge=1, le=65535)
    # Must match apps/quantchat/config/settings.py JD_COLLECTION where DocumentIngestion writes.
    jd_collection_name: str = Field(default="quanthire_job_descriptions")
    resume_collection_name: str = Field(default="quanthire_resumes")
    milvus_connection_timeout: int = Field(default=10, ge=1)

    # ------------------------------------------------------------------ Embeddings
    embedding_model: str = Field(default="BAAI/bge-base-en-v1.5")
    embedding_dimension: int = Field(default=768)

    # ------------------------------------------------------------------ Retrieval
    jd_retrieval_top_k: int = Field(default=10, ge=1, le=100)
    jd_retrieval_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    # ------------------------------------------------------------------ Workflow
    # NOTE: ``max_retries`` / ``retry_delay`` are accepted for backwards
    # compatibility with older .env files but are no-ops; LLM-level retries are
    # handled by ``vertex_max_retries`` (passed straight to ChatVertexAI) and the
    # per-call ``acall_json`` JSON-parse retry loop. Leaving them here so loading
    # a stale .env doesn't fail validation.
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_delay: float = Field(default=1.5, ge=0.1, le=10.0)
    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description=(
            "Hard ceiling for an end-to-end match (or single rank-candidate "
            "scoring). Wraps the orchestrator pipeline via asyncio.wait_for."
        ),
    )
    parallel_swarm: bool = Field(
        default=True,
        description="Run Layer 2 specialists in parallel (asyncio.gather)",
    )
    swarm_llm_max_concurrent: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "Max simultaneous Vertex LLM calls for the whole job-matching pipeline "
            "(specialists, risk, synthesis, etc.). Lower this if you see 429 quota errors."
        ),
    )
    debate_rounds: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Number of critic ↔ synthesiser debate rounds",
    )
    debate_convergence_delta: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
        description=(
            "Stop iterating debate rounds once the Synthesizer's score moves "
            "less than this between rounds (in points)."
        ),
    )
    skip_critic_confidence_threshold: float = Field(
        default=0.88,
        ge=0.0,
        le=1.0,
        description=(
            "Skip the Critic LLM call when synthesis confidence is at least this "
            "high AND specialist scores agree (variance below "
            "skip_critic_score_variance_max). Saves one LLM round-trip per match."
        ),
    )
    skip_critic_score_variance_max: float = Field(
        default=120.0,
        ge=0.0,
        description=(
            "Maximum population variance of specialist scores (in points^2) under "
            "which the Critic may be skipped if confidence is also high."
        ),
    )

    # ------------------------------------------------------------------ Peer awareness ("swarm" pass)
    enable_peer_awareness: bool = Field(
        default=False,
        description=(
            "Optional second-pass where each specialist sees a brief summary of "
            "peer findings and may revise its CONFIDENCE only (not score). "
            "This is the closest thing to true swarm-style local interaction; "
            "off by default because it adds one extra LLM call per specialist."
        ),
    )
    peer_awareness_max_summary_chars: int = Field(default=240, ge=80, le=2000)

    # ------------------------------------------------------------------ Adaptive weighting
    enable_adaptive_weights: bool = Field(
        default=True,
        description=(
            "Adjust the per-dimension weights based on JD characteristics "
            "(seniority, tech density, education explicitness) before scoring."
        ),
    )
    adaptive_weight_max_shift: float = Field(
        default=0.10,
        ge=0.0,
        le=0.30,
        description=(
            "Maximum absolute change applied to any single dimension weight by "
            "the adaptive calibrator (after re-normalisation)."
        ),
    )

    # ------------------------------------------------------------------ Match-result cache
    # Recruiters re-open the same shortlist repeatedly. Memoising the full MatchResult by
    # (candidate, jd, weights, model, prompt-version) hash drops repeat-view latency from
    # ~30s to <50ms on cache hit.
    enable_match_cache: bool = Field(default=True)
    match_cache_ttl_seconds: int = Field(default=86400, ge=60, le=7 * 86400)
    match_cache_max_size: int = Field(default=4096, ge=64, le=100_000)
    match_cache_redis_url: Optional[str] = Field(
        default=None,
        description=(
            "Optional Redis URL (e.g. redis://localhost:6379/2). When unset, an in-process "
            "LRU is used instead — perfectly fine for single-replica deployments."
        ),
    )

    # ------------------------------------------------------------------ JD pre-analysis
    enable_jd_preanalysis: bool = Field(
        default=True,
        description=(
            "Compute a structured JDAnalysis once per JD (level/density/must-haves) and "
            "inject it into specialist prompts + the adaptive-weight calibrator. Cached by "
            "JD content hash."
        ),
    )

    # ------------------------------------------------------------------ Evidence verifier (Layer 2.7)
    enable_evidence_verifier: bool = Field(
        default=True,
        description=(
            "Deterministic, no-LLM check that every Evidence.quote emitted by "
            "the swarm actually appears in candidate.raw_text / job.raw_text. "
            "Fabricated quotes are stripped and the offending specialist's "
            "confidence is downgraded so the ensemble naturally trusts it less. "
            "Default ON — turning it off allows hallucinated quotes through to "
            "the recruiter UI and is NOT recommended for production."
        ),
    )

    # ------------------------------------------------------------------ Location fit (pre-flight)
    enable_location_fit: bool = Field(
        default=True,
        description=(
            "Pre-flight location / time-zone / remote-eligibility check. "
            "Hybrid agent: deterministic first pass (free), LLM fallback only "
            "when the deterministic result is 'unknown'. Cached per "
            "(candidate, jd_content_hash). Default ON; surfaced as a metadata "
            "signal in MatchResult.metadata.location_fit. Set False to skip."
        ),
    )
    location_fit_block_on_severe: bool = Field(
        default=False,
        description=(
            "If True and the location-fit agent returns fit='block', the "
            "orchestrator marks the run with a hard logistical reject "
            "(metadata flag). Default False so the swarm still runs and the "
            "recruiter sees the score even when the candidate cannot ultimately "
            "be hired — useful for talent-pool building."
        ),
    )

    # ------------------------------------------------------------------ JD hygiene (pre-flight)
    enable_jd_hygiene: bool = Field(
        default=True,
        description=(
            "Pre-flight JD audit (Layer 0). Catches malformed / biased / contradictory JDs "
            "BEFORE any specialist scores a candidate. Cached per-JD content hash; "
            "trivially-OK JDs skip the LLM call entirely. Set False to disable."
        ),
    )
    jd_hygiene_block_on_severe: bool = Field(
        default=False,
        description=(
            "If True and the hygiene agent returns severity='block', the orchestrator "
            "refuses to match. Default False so deployments can roll out hygiene as a "
            "warning-only feature first."
        ),
    )

    # ------------------------------------------------------------------ Embedding fast-path
    # Cosine similarity between candidate and JD embeddings. Way below threshold => obvious
    # reject (skip the whole swarm); way above => obvious strong-hire shortcut. Saves up to
    # 11 LLM calls per match on the easy ~10–20% of cases.
    enable_embedding_fast_path: bool = Field(default=False)
    fast_path_reject_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    fast_path_strong_hire_threshold: float = Field(default=0.92, ge=0.0, le=1.0)

    # ------------------------------------------------------------------ Scoring
    # Per-dimension default weights for the ensemble.  These can be overridden
    # at request-time so HR can prioritise different criteria per role.
    # 8 dimensions total. Defaults sum to 1.00. The `normalise_weights` helper
    # in `scoring.py` rescales any per-request override that doesn't sum to 1.
    weight_skills: float = Field(default=0.26, ge=0.0, le=1.0)
    weight_experience: float = Field(default=0.18, ge=0.0, le=1.0)
    weight_education: float = Field(default=0.08, ge=0.0, le=1.0)
    weight_domain: float = Field(default=0.13, ge=0.0, le=1.0)
    weight_culture: float = Field(default=0.09, ge=0.0, le=1.0)
    weight_growth: float = Field(default=0.09, ge=0.0, le=1.0)
    weight_projects: float = Field(
        default=0.12,
        ge=0.0,
        le=1.0,
        description=(
            "Weight for the Projects/Portfolio dimension — concrete demonstrated "
            "use of skills. Distinct from `weight_skills` (which grades the "
            "skills LIST). Higher values reward candidates with real artefacts."
        ),
    )
    weight_risk: float = Field(default=0.05, ge=0.0, le=1.0)

    # Strong-hire threshold and the cut-off for shortlisting.
    strong_hire_threshold: float = Field(default=82.0, ge=0.0, le=100.0)
    hire_threshold: float = Field(default=68.0, ge=0.0, le=100.0)
    consider_threshold: float = Field(default=52.0, ge=0.0, le=100.0)

    # ------------------------------------------------------------------ Risk caps (post-ensemble)
    # Each pair: when risk_score < threshold, cap the overall score at `cap`.
    # Lower risk score = more red flags. Tunable per deployment without code change.
    risk_cap_severe_threshold: float = Field(default=30.0, ge=0.0, le=100.0)
    risk_cap_severe: float = Field(default=55.0, ge=0.0, le=100.0)
    risk_cap_moderate_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    risk_cap_moderate: float = Field(default=70.0, ge=0.0, le=100.0)
    risk_cap_mild_threshold: float = Field(default=65.0, ge=0.0, le=100.0)
    risk_cap_mild: float = Field(default=85.0, ge=0.0, le=100.0)

    # ------------------------------------------------------------------ Score deviation caps (debate phase)
    synthesizer_llm_deviation: float = Field(
        default=5.0,
        ge=0.0,
        le=20.0,
        description="Max ± points the Synthesizer LLM may diverge from the deterministic prior.",
    )
    arbitrator_llm_deviation: float = Field(
        default=4.0,
        ge=0.0,
        le=20.0,
        description="Max ± points the Arbitrator LLM may diverge from the deterministic post-critic score.",
    )
    critic_adjustment_application: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fraction of the Critic's suggested adjustment applied deterministically by the Arbitrator.",
    )

    # ------------------------------------------------------------------ Autonomous features
    # ``enable_autonomous_reasoning``, ``enable_self_reflection`` and
    # ``enable_adaptive_planning`` are reserved aspirational flags that older
    # config files set; they do NOT currently gate behaviour. Behaviour is
    # already realised by the always-on debate + bias audit + adaptive weights
    # path. Kept as no-ops so legacy .env files keep validating.
    enable_autonomous_reasoning: bool = Field(default=True)
    enable_self_reflection: bool = Field(default=True)
    enable_adaptive_planning: bool = Field(default=True)
    enable_error_recovery: bool = Field(default=True)  # gates LLM fallback model
    enable_critic_debate: bool = Field(default=True)
    enable_bias_audit: bool = Field(default=True)

    # ------------------------------------------------------------------ Observability
    langsmith_api_key: Optional[str] = Field(default=None)
    langsmith_project: str = Field(default="quanthire-ai")
    langsmith_tracing_enabled: bool = Field(default=True)

    # ------------------------------------------------------------------ Streaming
    enable_sse_streaming: bool = Field(default=True)

    # ------------------------------------------------------------------ Validators
    @field_validator("llm_provider", mode="before")
    @classmethod
    def _provider(cls, v: Optional[str]) -> str:
        from agents.llm.chat_factory import llm_provider

        env = os.getenv("LLM_PROVIDER")
        if env:
            return env.strip().lower()
        if v:
            return str(v).strip().lower()
        return llm_provider()

    @field_validator("llm_model", mode="before")
    @classmethod
    def _model(cls, v: Optional[str]) -> str:
        from agents.llm.chat_factory import primary_llm_model

        env = os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL")
        if env:
            return env.strip()
        if v:
            return str(v).strip()
        return primary_llm_model()

    @field_validator("swarm_llm_max_concurrent", mode="before")
    @classmethod
    def _swarm_llm_max_concurrent(cls, v: Any) -> int:
        for key in ("JOB_MATCHING_SWARM_LLM_MAX_CONCURRENT", "SWARM_LLM_MAX_CONCURRENT"):
            env = os.getenv(key)
            if env and str(env).strip():
                try:
                    return max(1, min(8, int(str(env).strip())))
                except ValueError:
                    pass
        if v is not None and v != "":
            try:
                return max(1, min(8, int(v)))
            except (TypeError, ValueError):
                pass
        return 2

    @field_validator("llm_fallback_model", mode="before")
    @classmethod
    def _fallback_model(cls, v: Optional[str]) -> str:
        from agents.llm.chat_factory import fallback_llm_model

        env = os.getenv("LLM_FALLBACK_MODEL")
        if env and env.strip():
            return env.strip()
        if v:
            return str(v).strip()
        return fallback_llm_model()

    @field_validator("llm_specialist_model", "llm_advisor_model", "llm_synthesis_model", mode="before")
    @classmethod
    def _tier_model_blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @model_validator(mode="after")
    def _inherit_tier_models_from_primary(self):
        from agents.llm.chat_factory import primary_llm_model

        primary = (self.llm_model or "").strip() or primary_llm_model()
        specialist = (
            None
            if self.llm_specialist_model is None
            else str(self.llm_specialist_model).strip()
        )
        advisor = (
            None
            if self.llm_advisor_model is None
            else str(self.llm_advisor_model).strip()
        )
        if not specialist:
            self.llm_specialist_model = primary
        if not advisor:
            self.llm_advisor_model = primary
        return self

    @field_validator("gcp_project", mode="before")
    @classmethod
    def _project(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return v.strip()
        return os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")

    @field_validator("gcp_location", mode="before")
    @classmethod
    def _location(cls, v: Optional[str]) -> str:
        # Field default is "us-central1", so Pydantic passes that as `v` and would
        # shadow root `.env` keys like `GCP_LOCATION` unless we prefer env first.
        for key in (
            "GCP_LOCATION",
            "JOB_MATCHING_GCP_LOCATION",
            "GOOGLE_CLOUD_REGION",
        ):
            env = os.getenv(key)
            if env and env.strip():
                return env.strip()
        if v and str(v).strip():
            return str(v).strip()
        return "us-central1"

    @field_validator("milvus_host", mode="before")
    @classmethod
    def _milvus_host(cls, v: Optional[str]) -> str:
        for key in ("JOB_MATCHING_MILVUS_HOST", "MILVUS_HOST"):
            env = os.getenv(key)
            if env and env.strip():
                return env.strip()
        if v and str(v).strip():
            return str(v).strip()
        return "localhost"

    @field_validator("milvus_port", mode="before")
    @classmethod
    def _milvus_port(cls, v: Any) -> int:
        for key in ("JOB_MATCHING_MILVUS_PORT", "MILVUS_PORT"):
            env = os.getenv(key)
            if env and env.strip():
                try:
                    return int(env.strip())
                except ValueError:
                    pass
        if v is not None and v != "":
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
        return 19530

    @field_validator("jd_collection_name", mode="before")
    @classmethod
    def _jd_collection(cls, v: Optional[str]) -> str:
        """Prefer explicit env so job matching stays aligned with QuantChat ingestion."""
        for key in ("MILVUS_JD_COLLECTION", "JD_COLLECTION", "QUANTHIRE_JD_COLLECTION"):
            env = os.getenv(key)
            if env and env.strip():
                return env.strip()
        if v and str(v).strip():
            return str(v).strip()
        return "quanthire_job_descriptions"

    @field_validator("resume_collection_name", mode="before")
    @classmethod
    def _resume_collection(cls, v: Optional[str]) -> str:
        for key in ("MILVUS_RESUME_COLLECTION", "RESUME_COLLECTION", "QUANTHIRE_RESUME_COLLECTION"):
            env = os.getenv(key)
            if env and env.strip():
                return env.strip()
        if v and str(v).strip():
            return str(v).strip()
        return "quanthire_resumes"

    @field_validator("langsmith_api_key", mode="before")
    @classmethod
    def _ls_key(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return v.strip()
        return os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")

    # ------------------------------------------------------------------ Helpers
    @property
    def is_vertex_ai_configured(self) -> bool:
        return bool(self.gcp_project and vertex_credential_source_available())

    @property
    def is_llm_configured(self) -> bool:
        provider = (self.llm_provider or "vertexai").strip().lower()
        if provider == "azure_openai":
            from agents.llm.chat_factory import is_azure_openai_configured

            return is_azure_openai_configured()
        if self.llm_provider == "openai":
            from agents.llm.chat_factory import is_openai_configured

            return is_openai_configured()
        return self.is_vertex_ai_configured

    @property
    def is_langsmith_configured(self) -> bool:
        return bool(self.langsmith_api_key) and self.langsmith_tracing_enabled

    @property
    def default_weights(self) -> dict[str, float]:
        return {
            "skills": self.weight_skills,
            "experience": self.weight_experience,
            "education": self.weight_education,
            "domain": self.weight_domain,
            "culture": self.weight_culture,
            "growth": self.weight_growth,
            "projects": self.weight_projects,
            "risk": self.weight_risk,
        }

    def get_llm_config(self) -> dict:
        provider = (self.llm_provider or "vertexai").strip().lower()
        if provider == "azure_openai":
            from agents.llm.chat_factory import is_azure_openai_configured

            if not is_azure_openai_configured():
                raise ValueError(
                    "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and "
                    "AZURE_OPENAI_API_KEY when LLM_PROVIDER=azure_openai."
                )
            return {
                "model": self.llm_model,
                "provider": "azure_openai",
                "temperature": self.llm_temperature,
                "max_tokens": min(self.llm_max_tokens, 16384),
                "fallback_model": self.llm_fallback_model,
            }
        if provider == "openai":
            from agents.llm.chat_factory import is_openai_configured

            if not is_openai_configured():
                raise ValueError(
                    "OPENAI_API_KEY is not configured. Required when LLM_PROVIDER=openai."
                )
            return {
                "model": self.llm_model,
                "provider": "openai",
                "temperature": self.llm_temperature,
                "max_tokens": min(self.llm_max_tokens, 16384),
                "fallback_model": self.llm_fallback_model,
            }
        if not self.gcp_project:
            raise ValueError(
                "GCP_PROJECT_ID is not configured. Vertex AI is required when LLM_PROVIDER=vertexai."
            )
        return {
            "model": self.llm_model,
            "provider": "vertexai",
            "project": self.gcp_project,
            "location": self.gcp_location,
            "temperature": self.llm_temperature,
            "max_tokens": min(self.llm_max_tokens, 16384),
            "fallback_model": self.llm_fallback_model,
        }

    def validate(self) -> None:
        if not self.is_llm_configured:
            if self.llm_provider == "openai":
                raise ValueError(
                    "OpenAI not configured. Set OPENAI_API_KEY when LLM_PROVIDER=openai."
                )
            raise ValueError(
                "Vertex AI not configured. Set GCP_PROJECT_ID and ADC, "
                "or set LLM_PROVIDER=openai with OPENAI_API_KEY."
            )


_config: Optional[JobMatchingConfig] = None


def _job_matching_env_file_candidates() -> list[Path]:
    """Ordered list of .env paths (repo layout: apps/agents/agents/job_matching/config.py)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent.parent.parent
    cwd = Path.cwd()
    return [
        cwd / ".env",
        cwd / "apps" / "api" / ".env",
        cwd / "apps" / "agents" / ".env",
        root / ".env",
        root / "apps" / "api" / ".env",
        root / "apps" / "agents" / ".env",
    ]


def get_config() -> JobMatchingConfig:
    """Return a process-wide singleton configuration instance."""
    global _config
    if _config is not None:
        return _config

    try:
        from agents.llm.chat_factory import ensure_llm_env, llm_provider

        ensure_llm_env()
        if llm_provider() not in ("openai", "azure_openai"):
            from agents.gcp_vertex_credentials import bootstrap_vertex_adc

            bootstrap_vertex_adc(load_env=True, log_status=False)
    except Exception as exc:
        logger.debug("Vertex ADC bootstrap failed: %s", exc)

    env_path = next((p for p in _job_matching_env_file_candidates() if p.exists()), None)

    if env_path:
        _config = JobMatchingConfig(_env_file=str(env_path))  # type: ignore[arg-type]
    else:
        _config = JobMatchingConfig()

    try:
        _config.validate()
    except ValueError as exc:  # pragma: no cover - logged for ops only
        logger.warning("Job-matching configuration validation warning: %s", exc)

    return _config


def reset_config() -> None:
    """Reset the singleton (for tests)."""
    global _config
    _config = None
