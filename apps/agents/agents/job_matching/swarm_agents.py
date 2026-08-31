"""
Layer 2 — Specialist Swarm Agents
=================================
Each specialist is a small, independent agent that scores ONE dimension of
the candidate↔JD match.  They are designed to run **in parallel** via
``asyncio.gather`` from the orchestrator.

Every specialist follows the same lifecycle:
    1. ``observe``  — read its slice of the state.
    2. ``think + act`` — call the LLM with its specialist prompt.
    3. ``reflect`` — emit an :class:`AgentThought` for the streaming UI.

The output is a strongly-typed Pydantic model (``DimensionScore`` /
``RiskAssessment`` / ``BiasAudit``) so the synthesiser can rely on shape.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    AgentThought,
    BiasAudit,
    CandidateProfile,
    DimensionLiteral,
    DimensionScore,
    Evidence,
    JobOpening,
    RiskAssessment,
)
from agents.job_matching.jd_analysis import JDAnalysis
from agents.job_matching.llm_client import JobMatchingLLM
from agents.job_matching.prompts import (
    BIAS_AUDIT_PROMPT,
    CULTURE_AGENT_PROMPT,
    DOMAIN_AGENT_PROMPT,
    EDUCATION_AGENT_PROMPT,
    EXPERIENCE_AGENT_PROMPT,
    GROWTH_AGENT_PROMPT,
    PROJECTS_AGENT_PROMPT,
    RISK_AGENT_PROMPT,
    SKILLS_AGENT_PROMPT,
    build_specialist_prompt,
)

logger = logging.getLogger(__name__)


def _confidence_0_1(val: Any, default: float = 0.5) -> float:
    """Models often return 0–100 for confidence; DimensionScore expects 0–1."""
    try:
        x = float(val)
    except (TypeError, ValueError):
        return default
    if x > 1.0 and x <= 100.0:
        x = x / 100.0
    return max(0.0, min(1.0, x))


ThoughtSink = Callable[[AgentThought], Awaitable[None]]


def _now() -> str:
    return datetime.utcnow().isoformat()


async def _emit(sink: ThoughtSink | None, thought: AgentThought) -> None:
    if sink is not None:
        try:
            await sink(thought)
        except Exception as exc:  # pragma: no cover - sink failures shouldn't break run
            logger.warning("Failed to emit thought from %s: %s", thought.agent, exc)


def _candidate_brief(candidate: CandidateProfile) -> dict[str, Any]:
    """A trimmed candidate JSON suitable for prompt injection."""
    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "headline": candidate.headline,
        "current_role": candidate.current_role,
        "total_years_experience": candidate.total_years_experience,
        "technical_skills": candidate.technical_skills,
        "soft_skills": candidate.soft_skills,
        "tools": candidate.tools,
        "certifications": candidate.certifications,
        "degrees": candidate.degrees,
        "industries": candidate.industries,
        "positions": candidate.positions[:8],
        "raw_text_excerpt": (candidate.raw_text or "")[:6000],
    }


def _job_brief(job: JobOpening) -> dict[str, Any]:
    return {
        "jd_id": job.jd_id,
        "job_title": job.job_title,
        "department": job.department,
        "location": job.location,
        "job_level": job.job_level,
        "position_summary": job.position_summary,
        "responsibilities": job.responsibilities,
        "required_skills": job.required_skills,
        "preferred_skills": job.preferred_skills,
        "tools_technologies": job.tools_technologies,
        "soft_skills": job.soft_skills,
        "education_requirement": job.education_requirement,
        "experience_requirement": job.experience_requirement,
    }


# ============================================================================
# BASE SPECIALIST
# ============================================================================


class BaseSpecialistAgent:
    """Common machinery shared by every Layer-2 specialist."""

    name: str = "BaseSpecialist"
    dimension: DimensionLiteral
    role_prompt: str

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.specialist_temperature)

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        sink: ThoughtSink | None = None,
        jd_analysis: JDAnalysis | None = None,
    ) -> DimensionScore:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="OBSERVE",
                thought=f"Analysing {self.dimension} fit for '{candidate.name}' vs '{job.job_title}'",
                state="SWARM",
                timestamp=_now(),
            ),
        )

        # Pre-computed JDAnalysis (cheap, deterministic) is injected as extra
        # context — saves the model from re-deriving level/density/edu signals
        # for every specialist call against the same JD.
        extra_context = ""
        if jd_analysis is not None:
            extra_context = f"=== JD STRUCTURED ANALYSIS ===\n{jd_analysis.summary}\n"

        prompt = build_specialist_prompt(
            self.role_prompt,
            json.dumps(_candidate_brief(candidate), default=str),
            json.dumps(_job_brief(job), default=str),
            extra_context=extra_context,
        )

        try:
            await _emit(
                sink,
                AgentThought(
                    agent=self.name,
                    phase="ACT",
                    thought=f"Scoring the {self.dimension} dimension via Vertex AI",
                    state="SWARM",
                    timestamp=_now(),
                ),
            )
            # Native response_schema enforcement on the happy path; falls back
            # to text-extract JSON-mode automatically if Vertex rejects the
            # schema or the LangChain build doesn't support it.
            payload = await self.llm.acall_structured(
                prompt, schema_model=DimensionScore, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("%s failed: %s", self.name, exc, exc_info=True)
            await _emit(
                sink,
                AgentThought(
                    agent=self.name,
                    phase="REFLECT",
                    thought=f"Specialist failed, falling back to neutral score: {exc}",
                    state="SWARM",
                    timestamp=_now(),
                ),
            )
            return self._fallback_score()

        score = self._parse(payload)

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"{self.dimension} score: {score.score:.1f}/100 (conf {score.confidence:.2f})",
                action=score.summary[:140],
                state="SWARM",
                timestamp=_now(),
                metadata={"dimension": self.dimension, "score": score.score},
            ),
        )
        return score

    def _parse(self, payload: dict[str, Any]) -> DimensionScore:
        try:
            payload.setdefault("dimension", self.dimension)
            payload.setdefault("agent_name", self.name)
            evidence_payload = payload.get("evidence") or []
            evidence: list[Evidence] = []
            for item in evidence_payload[:5]:
                if not isinstance(item, dict):
                    continue
                try:
                    evidence.append(Evidence(**item))
                except Exception:
                    continue
            return DimensionScore(
                dimension=self.dimension,
                score=float(payload.get("score", 50.0)),
                confidence=_confidence_0_1(payload.get("confidence", 0.5)),
                summary=str(payload.get("summary", "")).strip()[:1500],
                strengths=[str(s) for s in (payload.get("strengths") or [])][:8],
                gaps=[str(g) for g in (payload.get("gaps") or [])][:8],
                evidence=evidence,
                agent_name=self.name,
            )
        except Exception as exc:
            logger.warning("%s parse failed: %s", self.name, exc)
            return self._fallback_score()

    def _fallback_score(self) -> DimensionScore:
        return DimensionScore(
            dimension=self.dimension,
            score=50.0,
            confidence=0.3,
            summary="Specialist could not produce a verdict; using neutral fallback.",
            strengths=[],
            gaps=[],
            evidence=[],
            agent_name=self.name,
        )

    async def revise_confidence(
        self,
        own_score: DimensionScore,
        peer_summary: str,
        sink: ThoughtSink | None = None,
    ) -> DimensionScore:
        """Optional swarm-style peer-awareness pass.

        Given a short summary of every other specialist's verdict, this
        agent may revise ONLY its own ``confidence`` (not its score) — this
        emulates "local interaction" that swarm intelligence relies on, while
        keeping the ensemble math safe (one agent can't unilaterally pull
        another agent's score down). Returns the (possibly updated) score.
        """
        if not peer_summary:
            return own_score

        prompt = (
            f"You are the {self.name}. You already produced this verdict for the "
            f"'{self.dimension}' dimension:\n"
            f"{json.dumps(own_score.model_dump(), default=str)}\n\n"
            f"Here is what the OTHER specialists in the swarm reported:\n"
            f"{peer_summary}\n\n"
            "If their findings strongly contradict yours OR strongly corroborate "
            "yours, revise ONLY your `confidence` field (0-1). Do NOT change the "
            "score. Return strict JSON: {\"confidence\": <0..1>, \"reason\": \"...\"}.\n"
            + 'No prose outside the JSON.'
        )

        try:
            payload = await self.llm.acall_json(prompt, retry_on_parse_error=2)
        except Exception as exc:
            logger.warning("%s peer-awareness pass failed: %s", self.name, exc)
            return own_score

        new_conf = _confidence_0_1(payload.get("confidence", own_score.confidence))
        if abs(new_conf - own_score.confidence) < 0.05:
            return own_score

        revised = own_score.model_copy(update={"confidence": new_conf})
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=(
                    f"Peer-awareness pass: confidence "
                    f"{own_score.confidence:.2f} -> {new_conf:.2f}"
                ),
                action=str(payload.get("reason", ""))[:140],
                state="SWARM",
                timestamp=_now(),
                metadata={"dimension": self.dimension, "old_conf": own_score.confidence, "new_conf": new_conf},
            ),
        )
        return revised


# ============================================================================
# SEVEN CONCRETE SPECIALISTS
# ============================================================================


class SkillsAgent(BaseSpecialistAgent):
    name = "SkillsAgent"
    dimension: DimensionLiteral = "skills"
    role_prompt = SKILLS_AGENT_PROMPT


class ExperienceAgent(BaseSpecialistAgent):
    name = "ExperienceAgent"
    dimension: DimensionLiteral = "experience"
    role_prompt = EXPERIENCE_AGENT_PROMPT


class EducationAgent(BaseSpecialistAgent):
    name = "EducationAgent"
    dimension: DimensionLiteral = "education"
    role_prompt = EDUCATION_AGENT_PROMPT


class DomainAgent(BaseSpecialistAgent):
    name = "DomainAgent"
    dimension: DimensionLiteral = "domain"
    role_prompt = DOMAIN_AGENT_PROMPT


class CultureAgent(BaseSpecialistAgent):
    name = "CultureAgent"
    dimension: DimensionLiteral = "culture"
    role_prompt = CULTURE_AGENT_PROMPT


class GrowthAgent(BaseSpecialistAgent):
    name = "GrowthAgent"
    dimension: DimensionLiteral = "growth"
    role_prompt = GROWTH_AGENT_PROMPT


class ProjectsAgent(BaseSpecialistAgent):
    """Scores demonstrated, hands-on application of skills via projects / OSS.

    Distinct from SkillsAgent (which grades the skills LIST) — this agent
    grades whether the candidate actually USED those skills in concrete,
    role-relevant artefacts. Critical for engineering / ML / design roles.
    """

    name = "ProjectsAgent"
    dimension: DimensionLiteral = "projects"
    role_prompt = PROJECTS_AGENT_PROMPT


# ============================================================================
# RISK AGENT — different output shape
# ============================================================================


class RiskAgent:
    name = "RiskAgent"
    role_prompt = RISK_AGENT_PROMPT

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.specialist_temperature)

    @staticmethod
    def fallback_assessment() -> RiskAssessment:
        """Default 'low-risk-assumption' placeholder used whenever the agent fails.

        Exposed as a classmethod so callers (e.g. the orchestrator) can use the
        SAME placeholder when they sidestep the agent entirely (cancellation,
        unexpected exception escaping ``asyncio.gather``).
        """
        return RiskAssessment(
            score=70.0,
            confidence=0.3,
            flags=[],
            summary="Risk agent failed to run; defaulting to low-risk assumption.",
        )

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        sink: ThoughtSink | None = None,
        jd_analysis: JDAnalysis | None = None,
    ) -> RiskAssessment:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="OBSERVE",
                thought=f"Scanning '{candidate.name}' for hiring risks",
                state="SWARM",
                timestamp=_now(),
            ),
        )

        extra_context = ""
        if jd_analysis is not None:
            extra_context = f"=== JD STRUCTURED ANALYSIS ===\n{jd_analysis.summary}\n"

        prompt = build_specialist_prompt(
            self.role_prompt,
            json.dumps(_candidate_brief(candidate), default=str),
            json.dumps(_job_brief(job), default=str),
            extra_context=extra_context,
        )

        try:
            await _emit(
                sink,
                AgentThought(
                    agent=self.name,
                    phase="ACT",
                    thought="Scanning resume for gaps, hopping, inconsistencies, stack drift",
                    state="SWARM",
                    timestamp=_now(),
                ),
            )
            payload = await self.llm.acall_structured(
                prompt, schema_model=RiskAssessment, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("%s failed: %s", self.name, exc)
            return self.fallback_assessment()

        flags: list[dict[str, str]] = []
        for item in (payload.get("flags") or [])[:10]:
            if not isinstance(item, dict):
                continue
            flags.append(
                {
                    "category": str(item.get("category", "other"))[:40],
                    "severity": str(item.get("severity", "low"))[:10],
                    "description": str(item.get("description", ""))[:400],
                    "evidence": str(item.get("evidence", ""))[:400],
                }
            )

        risk = RiskAssessment(
            score=float(payload.get("score", 70.0)),
            confidence=_confidence_0_1(payload.get("confidence", 0.6)),
            flags=flags,
            summary=str(payload.get("summary", ""))[:1000],
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"Risk score {risk.score:.1f}/100 with {len(risk.flags)} flag(s)",
                state="SWARM",
                timestamp=_now(),
                metadata={"flag_count": len(risk.flags)},
            ),
        )
        return risk


# ============================================================================
# BIAS AUDITOR — runs *after* specialists, before debate
# ============================================================================


class BiasAuditorAgent:
    name = "BiasAuditor"
    role_prompt = BIAS_AUDIT_PROMPT

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.specialist_temperature)

    async def run(
        self,
        candidate: CandidateProfile,
        job: JobOpening,
        specialist_outputs: Any,
        sink: ThoughtSink | None = None,
    ) -> BiasAudit:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="OBSERVE",
                thought="Auditing the swarm's outputs for fairness and bias",
                state="SWARM",
                timestamp=_now(),
            ),
        )

        prompt = "\n\n".join(
            [
                self.role_prompt,
                f"=== CANDIDATE PROFILE ===\n{json.dumps(_candidate_brief(candidate), default=str)}",
                f"=== JOB OPENING ===\n{json.dumps(_job_brief(job), default=str)}",
                f"=== SWARM OUTPUTS ===\n{json.dumps(specialist_outputs, default=str)[:8000]}",
                "Return ONLY valid JSON.",
            ]
        )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=BiasAudit, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("BiasAuditor failed: %s", exc)
            return BiasAudit(
                is_fair=True,
                confidence=0.3,
                issues=[],
                mitigations=[],
                summary="Bias auditor failed to run; defaulting to fair assumption.",
            )

        audit = BiasAudit(
            is_fair=bool(payload.get("is_fair", True)),
            confidence=_confidence_0_1(payload.get("confidence", 0.7)),
            issues=[str(i)[:300] for i in (payload.get("issues") or [])][:8],
            mitigations=[str(m)[:300] for m in (payload.get("mitigations") or [])][:8],
            summary=str(payload.get("summary", ""))[:1000],
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"Bias audit complete — {'FAIR' if audit.is_fair else 'CONCERNS RAISED'}",
                state="SWARM",
                timestamp=_now(),
                metadata={"is_fair": audit.is_fair, "issue_count": len(audit.issues)},
            ),
        )
        return audit


# ============================================================================
# FACTORY
# ============================================================================


def build_swarm(
    config: JobMatchingConfig, llm: JobMatchingLLM | None = None
) -> tuple[
    list[BaseSpecialistAgent],
    RiskAgent,
    BiasAuditorAgent,
]:
    """Instantiate every Layer-2 specialist (sharing one LLM client).

    The shared LLM is constructed against ``llm_specialist_model``, which defaults to
    the primary ``llm_model`` unless ``JOB_MATCHING_LLM_SPECIALIST_MODEL`` is set.
    Synthesis / critic / arbitrator use their own ``JobMatchingLLM`` instances in the
    orchestrator.
    """
    shared_llm = llm or JobMatchingLLM(
        config,
        temperature=config.specialist_temperature,
        model_override=config.llm_specialist_model,
    )
    specialists: list[BaseSpecialistAgent] = [
        SkillsAgent(config, shared_llm),
        ExperienceAgent(config, shared_llm),
        EducationAgent(config, shared_llm),
        DomainAgent(config, shared_llm),
        CultureAgent(config, shared_llm),
        GrowthAgent(config, shared_llm),
        ProjectsAgent(config, shared_llm),
    ]
    risk_agent = RiskAgent(config, shared_llm)
    bias_agent = BiasAuditorAgent(config, shared_llm)
    return specialists, risk_agent, bias_agent
