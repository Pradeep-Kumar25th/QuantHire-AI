"""
Layer 3 — Debate Agents
=======================
Implements the **multi-agent debate** pattern:

    Synthesizer  →  Critic  →  Arbitrator

The Synthesizer fuses the Layer-2 specialist outputs into a single verdict.
The Critic challenges that verdict and surfaces blind-spots.  The Arbitrator
weighs both sides and produces the final score and verdict.

This loop consistently outperforms a single-agent verdict on long-horizon
reasoning tasks (the empirical finding behind ChatEval, MAD, and most
production "judge" pipelines).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from agents.job_matching.config import JobMatchingConfig
from agents.job_matching.enterprise_models import (
    AgentThought,
    ArbitratorResult,
    BiasAudit,
    CriticChallenge,
    DimensionScore,
    RiskAssessment,
    SynthesisResult,
    Verdict,
)
from agents.job_matching.llm_client import JobMatchingLLM
from agents.job_matching.prompts import (
    build_arbitrator_prompt,
    build_critic_prompt,
    build_synthesizer_prompt,
)
from agents.job_matching.scoring import (
    aggregate_confidence,
    apply_risk_cap,
    confidence_weighted_score,
    map_verdict,
    normalise_weights,
)
from agents.job_matching.swarm_agents import ThoughtSink, _emit, _now

logger = logging.getLogger(__name__)


def _serialise_specialists(
    dimension_scores: list[DimensionScore],
    risk: RiskAssessment | None,
) -> list[dict[str, Any]]:
    out = [
        {
            "dimension": ds.dimension,
            "score": ds.score,
            "confidence": ds.confidence,
            "summary": ds.summary,
            "strengths": ds.strengths,
            "gaps": ds.gaps,
            "agent": ds.agent_name,
        }
        for ds in dimension_scores
    ]
    if risk:
        out.append(
            {
                "dimension": "risk",
                "score": risk.score,
                "confidence": risk.confidence,
                "summary": risk.summary,
                "flags": risk.flags,
                "agent": "RiskAgent",
            }
        )
    return out


# ============================================================================
# SYNTHESIZER
# ============================================================================


class SynthesizerAgent:
    name = "Synthesizer"

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.debate_temperature)

    async def run(
        self,
        dimension_scores: list[DimensionScore],
        risk: RiskAssessment | None,
        bias_audit: BiasAudit | None,
        weights: dict[str, float],
        sink: ThoughtSink | None = None,
        prior_critic: "CriticChallenge | None" = None,
    ) -> SynthesisResult:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="THINK",
                thought=(
                    "Re-fusing specialist outputs after critic round"
                    if prior_critic is not None
                    else f"Fusing {len(dimension_scores)} specialist outputs into a single verdict"
                ),
                state="DEBATE",
                timestamp=_now(),
            ),
        )

        # Compute the deterministic ensemble first — gives the LLM a strong prior.
        breakdown = confidence_weighted_score(dimension_scores, weights)
        deterministic_overall = breakdown.get("overall", 0.0)
        deterministic_overall = apply_risk_cap(deterministic_overall, risk, self.config)
        deterministic_confidence = aggregate_confidence(dimension_scores, weights)

        prompt = build_synthesizer_prompt(
            specialist_outputs_json=json.dumps(
                _serialise_specialists(dimension_scores, risk), default=str
            ),
            weights_json=json.dumps(normalise_weights(weights)),
            bias_audit_json=json.dumps(
                bias_audit.model_dump() if bias_audit else {}, default=str
            ),
        )
        deviation_cap = float(self.config.synthesizer_llm_deviation)
        prompt += (
            f"\n\n=== DETERMINISTIC PRIOR (do NOT diverge by more than ±{deviation_cap:g}) ===\n"
            f"prior_overall_score = {deterministic_overall:.2f}\n"
            f"prior_confidence    = {deterministic_confidence:.2f}\n"
        )
        if prior_critic is not None:
            prompt += (
                "\n=== CRITIC FEEDBACK FROM PREVIOUS ROUND ===\n"
                f"{json.dumps(prior_critic.model_dump(), default=str)}\n"
                "Address the blind-spots above. You may move toward the critic's "
                "suggested adjustment, but you remain bound by the deterministic prior "
                "deviation cap.\n"
            )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=SynthesisResult, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("Synthesizer failed: %s", exc)
            payload = {}

        # Trust deterministic math; allow LLM to nudge by ±synthesizer_llm_deviation
        deviation = float(self.config.synthesizer_llm_deviation)
        llm_overall = float(payload.get("overall_score", deterministic_overall))
        adjusted_overall = max(
            deterministic_overall - deviation,
            min(deterministic_overall + deviation, llm_overall),
        )
        adjusted_overall = apply_risk_cap(adjusted_overall, risk, self.config)

        synthesis = SynthesisResult(
            overall_score=round(adjusted_overall, 2),
            weighted_breakdown={
                k: round(v, 2) for k, v in breakdown.items() if k != "overall"
            },
            confidence=float(payload.get("confidence", deterministic_confidence)),
            summary=str(payload.get("summary", "")).strip()[:1500]
            or "Verdict synthesised from specialist swarm.",
            top_strengths=[str(s) for s in (payload.get("top_strengths") or [])][:6],
            top_gaps=[str(g) for g in (payload.get("top_gaps") or [])][:6],
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=f"Synthesis complete — overall {synthesis.overall_score:.1f}",
                state="DEBATE",
                timestamp=_now(),
                metadata={"overall": synthesis.overall_score},
            ),
        )
        return synthesis


# ============================================================================
# CRITIC
# ============================================================================


class CriticAgent:
    name = "Critic"

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.debate_temperature)

    async def run(
        self,
        synthesis: SynthesisResult,
        dimension_scores: list[DimensionScore],
        risk: RiskAssessment | None,
        bias_audit: BiasAudit | None,
        sink: ThoughtSink | None = None,
    ) -> CriticChallenge:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="THINK",
                thought="Challenging the synthesizer's verdict for blind-spots",
                state="DEBATE",
                timestamp=_now(),
            ),
        )

        prompt = build_critic_prompt(
            synthesis_json=json.dumps(synthesis.model_dump(), default=str),
            specialist_outputs_json=json.dumps(
                _serialise_specialists(dimension_scores, risk), default=str
            ),
            bias_audit_json=json.dumps(
                bias_audit.model_dump() if bias_audit else {}, default=str
            ),
        )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=CriticChallenge, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("Critic failed: %s", exc)
            payload = {}

        challenge = CriticChallenge(
            is_overall_score_justified=bool(
                payload.get("is_overall_score_justified", True)
            ),
            blind_spots=[str(s) for s in (payload.get("blind_spots") or [])][:6],
            counter_arguments=[str(c) for c in (payload.get("counter_arguments") or [])][
                :6
            ],
            suggested_score_adjustment=max(
                -15.0,
                min(15.0, float(payload.get("suggested_score_adjustment", 0.0))),
            ),
            summary=str(payload.get("summary", "")).strip()[:1500]
            or "Critic accepted the synthesizer's verdict.",
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="REFLECT",
                thought=(
                    "Synthesis accepted"
                    if challenge.is_overall_score_justified
                    else f"Suggested adjustment: {challenge.suggested_score_adjustment:+.1f}"
                ),
                state="DEBATE",
                timestamp=_now(),
                metadata={
                    "blind_spots": len(challenge.blind_spots),
                    "adjustment": challenge.suggested_score_adjustment,
                },
            ),
        )
        return challenge


# ============================================================================
# ARBITRATOR
# ============================================================================


class ArbitratorAgent:
    name = "Arbitrator"

    def __init__(self, config: JobMatchingConfig, llm: JobMatchingLLM | None = None) -> None:
        self.config = config
        self.llm = llm or JobMatchingLLM(config, temperature=config.debate_temperature)

    async def run(
        self,
        synthesis: SynthesisResult,
        critic: CriticChallenge,
        risk: RiskAssessment | None,
        sink: ThoughtSink | None = None,
    ) -> ArbitratorResult:
        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="THINK",
                thought="Arbitrating between Synthesizer and Critic for the final verdict",
                state="DEBATE",
                timestamp=_now(),
            ),
        )

        thresholds = {
            "STRONG_HIRE": self.config.strong_hire_threshold,
            "HIRE": self.config.hire_threshold,
            "CONSIDER": self.config.consider_threshold,
        }
        prompt = build_arbitrator_prompt(
            synthesis_json=json.dumps(synthesis.model_dump(), default=str),
            critic_json=json.dumps(critic.model_dump(), default=str),
            thresholds_json=json.dumps(thresholds),
        )

        try:
            payload = await self.llm.acall_structured(
                prompt, schema_model=ArbitratorResult, retry_on_parse_error=2
            )
        except Exception as exc:
            logger.error("Arbitrator failed: %s", exc)
            payload = {}

        # Apply a config-driven fraction of the critic's suggested adjustment.
        adjustment_factor = float(self.config.critic_adjustment_application)
        deterministic_adjustment = critic.suggested_score_adjustment * adjustment_factor
        deterministic_final = synthesis.overall_score + deterministic_adjustment
        deterministic_final = max(0.0, min(100.0, deterministic_final))
        deterministic_final = apply_risk_cap(deterministic_final, risk, self.config)

        # Blend with the LLM's verdict (capped)
        deviation = float(self.config.arbitrator_llm_deviation)
        llm_final = float(payload.get("final_score", deterministic_final))
        blended = max(
            deterministic_final - deviation,
            min(deterministic_final + deviation, llm_final),
        )
        blended = round(max(0.0, min(100.0, blended)), 2)

        verdict_str = str(payload.get("verdict", "")).upper()
        if verdict_str in {v.value for v in Verdict}:
            verdict = Verdict(verdict_str)
        else:
            verdict = map_verdict(blended, self.config)

        accepted = [str(p) for p in (payload.get("accepted_critic_points") or [])][:6]
        rejected = [str(p) for p in (payload.get("rejected_critic_points") or [])][:6]

        result = ArbitratorResult(
            final_score=blended,
            verdict=verdict,
            rationale=str(payload.get("rationale", "")).strip()[:2000]
            or "Final verdict produced by the swarm orchestrator.",
            accepted_critic_points=accepted,
            rejected_critic_points=rejected,
            confidence=float(payload.get("confidence", synthesis.confidence)),
        )

        await _emit(
            sink,
            AgentThought(
                agent=self.name,
                phase="DONE",
                thought=f"FINAL: {verdict.value} ({blended:.1f}/100)",
                state="DEBATE",
                timestamp=_now(),
                metadata={"final_score": blended, "verdict": verdict.value},
            ),
        )
        return result
