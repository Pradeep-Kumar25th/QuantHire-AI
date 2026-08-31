"""
Job Matching Orchestrator
=========================
Coordinates the four-layer Hierarchical Specialist Swarm with Debate (HSS-D)
flow:

    Layer 1  Pre-flight        — load candidate + JD from Milvus.
    Layer 2  Specialist Swarm  — 6 parallel specialists + RiskAgent; Bias Auditor after.
    Layer 3  Debate            — Synthesizer ↔ Critic ↔ Arbitrator.
    Layer 4  Insights          — HRAdvisor + Explainability.

Provides both a *blocking* ``run`` method (used by the FastAPI endpoint that
returns JSON) and a *streaming* ``stream`` async generator (used by the SSE
endpoint that powers the live UI).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from agents.job_matching.cache import (
    Cache,
    build_cache,
    match_cache_key,
)
from agents.job_matching.config import JobMatchingConfig, get_config
from agents.job_matching.data_access import (
    get_candidate,
    get_jd,
    list_candidates,
    list_jds,
)
from agents.job_matching.debate_agents import (
    ArbitratorAgent,
    CriticAgent,
    SynthesizerAgent,
)
from agents.job_matching.enterprise_models import (
    AgentThought,
    BiasAudit,
    CandidateMatchSummary,
    CandidateProfile,
    CriticChallenge,
    DimensionScore,
    JobOpening,
    MatchResult,
    RankingResult,
    RiskAssessment,
    SynthesisResult,
)
from agents.job_matching.evidence_verifier import EvidenceVerifier
from agents.job_matching.fast_path import (
    build_obvious_reject,
    build_obvious_strong_hire,
    compute_similarity,
)
from agents.job_matching.insight_agents import ExplainabilityAgent, HRAdvisorAgent
from agents.job_matching.jd_analysis import JDAnalysis, JDAnalyzer
from agents.job_matching.jd_hygiene import JDHygieneAgent
from agents.job_matching.llm_client import JobMatchingLLM, ensure_vertex_credentials
from agents.job_matching.location_fit import LocationFitAgent
from agents.job_matching.scoring import (
    adaptive_weights,
    normalise_weights,
    specialist_score_variance,
)
from agents.job_matching.swarm_agents import build_swarm

logger = logging.getLogger(__name__)


def _compute_swarm_health(
    dimension_scores: list[DimensionScore],
    risk: RiskAssessment | None,
    bias_audit: BiasAudit | None,
) -> dict[str, Any]:
    """Surface whether Layer-2/2.5 agents used real LLM output or error fallbacks."""
    neutral_marker = "neutral fallback"
    core_scores = [ds for ds in dimension_scores if ds.dimension != "risk"]
    neutral_specialists = sum(
        1 for ds in core_scores if neutral_marker in (ds.summary or "").lower()
    )
    health: dict[str, Any] = {
        "specialist_count": len(core_scores),
        "specialists_neutral_fallback": neutral_specialists,
        "all_specialists_real_scores": bool(core_scores)
        and neutral_specialists == 0,
    }
    if risk is not None and "defaulting to low-risk" in (risk.summary or "").lower():
        health["risk_agent_placeholder"] = True
    if bias_audit is not None and "defaulting to fair assumption" in (
        bias_audit.summary or ""
    ).lower():
        health["bias_auditor_placeholder"] = True
    return health


def _now() -> str:
    return datetime.utcnow().isoformat()


async def _noop_none() -> None:
    """Awaitable placeholder used when a pre-flight stage is disabled, so the
    parallel ``asyncio.gather`` keeps a stable shape regardless of toggles."""
    return None


class JobMatchingOrchestrator:
    """Top-level orchestrator for the matching swarm."""

    def __init__(self, config: Optional[JobMatchingConfig] = None) -> None:
        self.config: JobMatchingConfig = config or get_config()
        try:
            self.config.validate()
        except ValueError as exc:
            logger.warning("Job matching config warning: %s", exc)

        ensure_vertex_credentials(self.config)
        from agents.llm.chat_factory import llm_status

        logger.info("Job matching LLM ready: %s", llm_status())

        # ---- Model-tiered LLM clients --------------------------------------
        # Specialist / synthesis / advisor tiers default to llm_model (same model
        # project-wide unless JOB_MATCHING_LLM_*MODEL overrides).
        # HRAdvisor + Explainability stay on the cheap tier — neither needs
        # the synthesis-level reasoning bandwidth.
        self._llm_swarm = JobMatchingLLM(
            self.config,
            temperature=self.config.specialist_temperature,
            model_override=self.config.llm_specialist_model,
        )
        self._specialists, self._risk_agent, self._bias_agent = build_swarm(
            self.config, self._llm_swarm
        )
        self._llm_debate = JobMatchingLLM(
            self.config,
            temperature=self.config.debate_temperature,
            model_override=self.config.llm_synthesis_model,
        )
        self._synthesizer = SynthesizerAgent(self.config, self._llm_debate)
        self._critic = CriticAgent(self.config, self._llm_debate)
        self._arbitrator = ArbitratorAgent(self.config, self._llm_debate)
        self._llm_advisor = JobMatchingLLM(
            self.config,
            temperature=self.config.advisor_temperature,
            model_override=self.config.llm_advisor_model,
        )
        self._advisor = HRAdvisorAgent(self.config, self._llm_advisor)
        self._llm_explain = JobMatchingLLM(
            self.config,
            temperature=self.config.specialist_temperature,
            model_override=self.config.llm_advisor_model,
        )
        self._explainer = ExplainabilityAgent(self.config, self._llm_explain)

        # ---- Caches & analysis ---------------------------------------------
        self._match_cache: Cache | None = (
            build_cache(
                redis_url=self.config.match_cache_redis_url,
                max_size=self.config.match_cache_max_size,
            )
            if self.config.enable_match_cache
            else None
        )
        self._jd_analyzer = JDAnalyzer() if self.config.enable_jd_preanalysis else None
        self._jd_hygiene = (
            JDHygieneAgent(self.config, self._llm_swarm)
            if self.config.enable_jd_hygiene
            else None
        )
        # LocationFit is hybrid (deterministic first, LLM fallback). LLM is
        # lazy-instantiated inside the agent so most matches pay zero cost.
        self._location_fit_agent = (
            LocationFitAgent(self.config, llm=None)
            if self.config.enable_location_fit
            else None
        )

        logger.info(
            "JobMatchingOrchestrator ready ("
            "swarm_model=%s, synthesis_model=%s, advisor_model=%s, "
            "parallel_swarm=%s, swarm_llm_max_concurrent=%s, debate_rounds=%s, peer_awareness=%s, "
            "adaptive_weights=%s, jd_preanalysis=%s, fast_path=%s, cache=%s, "
            "structured_output=%s)",
            self._llm_swarm.model_name,
            self._llm_debate.model_name,
            self._llm_advisor.model_name,
            self.config.parallel_swarm,
            self.config.swarm_llm_max_concurrent,
            self.config.debate_rounds,
            self.config.enable_peer_awareness,
            self.config.enable_adaptive_weights,
            self.config.enable_jd_preanalysis,
            self.config.enable_embedding_fast_path,
            "redis" if self.config.match_cache_redis_url else (
                "lru" if self.config.enable_match_cache else "off"
            ),
            self.config.enable_structured_output,
        )

    # ------------------------------------------------------------------ data
    def list_available_candidates(self) -> list[CandidateProfile]:
        return list_candidates(self.config.resume_collection_name)

    def list_available_jds(self) -> list[JobOpening]:
        return list_jds(self.config.jd_collection_name)

    def _load_candidate(self, candidate_id: str) -> CandidateProfile:
        candidate = get_candidate(candidate_id, self.config.resume_collection_name)
        if not candidate:
            raise ValueError(f"Candidate {candidate_id!r} not found in data store")
        return candidate

    def _load_jd(self, jd_id: str) -> JobOpening:
        jd = get_jd(jd_id, self.config.jd_collection_name)
        if not jd:
            raise ValueError(f"JD {jd_id!r} not found in data store")
        return jd

    # ------------------------------------------------------------------ blocking entry-point
    async def amatch(
        self,
        candidate_id: str,
        jd_id: str,
        weights: Optional[dict[str, float]] = None,
    ) -> MatchResult:
        return await self._run_with_timeout(
            self._run(candidate_id, jd_id, weights, sink=None),
            label=f"amatch({candidate_id}->{jd_id})",
        )

    async def _run_with_timeout(self, coro, label: str) -> MatchResult:
        """Wrap any pipeline coroutine in the configured ``timeout_seconds`` budget.

        Without this guard a single hung Vertex call (e.g. region outage,
        network partition) could pin a request worker indefinitely. We expose
        ``label`` so the timeout error message is actionable in logs.
        """
        timeout = self.config.timeout_seconds
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            logger.error("%s exceeded %ss budget; aborting", label, timeout)
            raise TimeoutError(
                f"Job-matching pipeline exceeded the configured "
                f"timeout_seconds={timeout} budget for {label}."
            ) from exc

    def match(
        self,
        candidate_id: str,
        jd_id: str,
        weights: Optional[dict[str, float]] = None,
    ) -> MatchResult:
        return asyncio.run(self.amatch(candidate_id, jd_id, weights))

    # ------------------------------------------------------------------ streaming entry-point
    async def stream(
        self,
        candidate_id: str,
        jd_id: str,
        weights: Optional[dict[str, float]] = None,
    ) -> AsyncIterator[dict]:
        """Yield SSE-friendly events as the swarm progresses."""
        queue: asyncio.Queue = asyncio.Queue()
        sentinel: object = object()

        async def sink(thought: AgentThought) -> None:
            await queue.put(("thought", thought.model_dump()))

        async def runner() -> None:
            try:
                result = await self._run_with_timeout(
                    self._run(candidate_id, jd_id, weights, sink=sink),
                    label=f"stream({candidate_id}->{jd_id})",
                )
                await queue.put(("result", result.model_dump(mode="json")))
            except Exception as exc:  # pragma: no cover - bubble up via queue
                logger.error("Streaming match failed: %s", exc, exc_info=True)
                await queue.put(("error", {"message": str(exc)}))
            finally:
                await queue.put(("done", sentinel))

        task = asyncio.create_task(runner())
        try:
            while True:
                event_type, payload = await queue.get()
                if event_type == "done":
                    break
                yield {"event": event_type, "data": payload}
        finally:
            # If the SSE consumer disconnects mid-stream, cancel the runner so
            # we don't keep burning Vertex tokens after the client is gone.
            if not task.done():
                task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    # ------------------------------------------------------------------ ranking
    async def arank(
        self,
        jd_id: str,
        candidate_ids: Optional[list[str]] = None,
        weights: Optional[dict[str, float]] = None,
        max_concurrency: int = 3,
    ) -> RankingResult:
        jd = self._load_jd(jd_id)
        if candidate_ids is None:
            profiles = list_candidates(self.config.resume_collection_name)
        else:
            profiles = [
                p
                for p in (
                    get_candidate(cid, self.config.resume_collection_name)
                    for cid in candidate_ids
                )
                if p is not None
            ]

        # JD-derived adaptive weights are identical for every candidate against
        # the same JD — compute once and reuse to save n*specialists prompt-tokens.
        base_weights = normalise_weights(weights or self.config.default_weights)
        precomputed_weights = adaptive_weights(jd, base_weights, self.config)

        sem = asyncio.Semaphore(max_concurrency)

        async def score_one(cand: CandidateProfile) -> CandidateMatchSummary | None:
            async with sem:
                try:
                    result = await self._run_with_timeout(
                        self._run(
                            cand.candidate_id,
                            jd.jd_id,
                            weights,
                            sink=None,
                            prefetched_jd=jd,
                            precomputed_weights=precomputed_weights,
                        ),
                        label=f"rank-candidate({cand.candidate_id})",
                    )
                    return CandidateMatchSummary(
                        candidate_id=result.candidate_id,
                        candidate_name=cand.name,
                        overall_score=result.overall_score,
                        verdict=result.verdict,
                        top_strengths=result.synthesis.top_strengths[:3],
                        top_gaps=result.synthesis.top_gaps[:3],
                        confidence=result.confidence,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Ranking candidate %s failed: %s", cand.candidate_id, exc)
                    return None

        summaries = await asyncio.gather(*(score_one(c) for c in profiles))
        ranked = sorted(
            (s for s in summaries if s is not None),
            key=lambda s: s.overall_score,
            reverse=True,
        )
        return RankingResult(
            jd_id=jd.jd_id,
            job_title=jd.job_title,
            candidates=ranked,
            metadata={
                "candidate_count": len(ranked),
                "adaptive_weights": precomputed_weights,
            },
        )

    def rank(
        self,
        jd_id: str,
        candidate_ids: Optional[list[str]] = None,
        weights: Optional[dict[str, float]] = None,
        max_concurrency: int = 3,
    ) -> RankingResult:
        return asyncio.run(self.arank(jd_id, candidate_ids, weights, max_concurrency))

    # ------------------------------------------------------------------ Layer 2 helpers
    async def _run_swarm(
        self,
        candidate: CandidateProfile,
        jd: JobOpening,
        sink,
        jd_analysis: JDAnalysis | None = None,
    ) -> tuple[list[DimensionScore], RiskAssessment | None]:
        """Fan out specialists + RiskAgent. Resilient to per-task exceptions."""
        specialist_tasks = [
            spec.run(candidate, jd, sink=sink, jd_analysis=jd_analysis)
            for spec in self._specialists
        ]
        risk_task = self._risk_agent.run(
            candidate, jd, sink=sink, jd_analysis=jd_analysis
        )

        if self.config.parallel_swarm:
            # return_exceptions=True so a single rogue exception (e.g. transient
            # network error not caught by the specialist) cannot kill the whole match.
            results = await asyncio.gather(
                *specialist_tasks, risk_task, return_exceptions=True
            )
        else:
            # Sequential mode (useful for low-quota / debugging environments)
            results = []
            for coro in specialist_tasks + [risk_task]:
                try:
                    results.append(await coro)
                except Exception as exc:  # noqa: BLE001
                    results.append(exc)

        specialist_scores: list[DimensionScore] = []
        for spec, result in zip(self._specialists, results[:-1]):
            if isinstance(result, DimensionScore):
                specialist_scores.append(result)
            else:
                logger.error(
                    "Specialist %s raised %s; using fallback score",
                    spec.name,
                    type(result).__name__ if isinstance(result, BaseException) else "non-DimensionScore",
                )
                specialist_scores.append(spec._fallback_score())

        risk_result = results[-1]
        if isinstance(risk_result, RiskAssessment):
            risk_assessment: RiskAssessment | None = risk_result
        elif isinstance(risk_result, BaseException):
            # Falling back to None would silently SKIP the risk cap — that's a
            # safety regression. Use the agent's explicit low-risk placeholder
            # so downstream scoring stays well-defined and the swarm-health
            # heuristic still detects this as a degraded run.
            logger.error(
                "RiskAgent raised %s; using fallback assessment (no cap applied because score=70).",
                type(risk_result).__name__,
            )
            risk_assessment = self._risk_agent.fallback_assessment()
        else:
            risk_assessment = None

        return specialist_scores, risk_assessment

    async def _peer_awareness_pass(
        self,
        specialist_scores: list[DimensionScore],
        sink,
    ) -> list[DimensionScore]:
        """Lightweight 'swarm' phase — each specialist sees peer summaries and may
        revise its ``confidence`` (never its score) given peer agreement / dissent.
        """
        max_chars = self.config.peer_awareness_max_summary_chars

        def peer_summary_for(target: DimensionScore) -> str:
            lines = []
            for ds in specialist_scores:
                if ds.dimension == target.dimension:
                    continue
                summary = (ds.summary or "").strip().replace("\n", " ")
                if len(summary) > max_chars:
                    summary = summary[: max_chars - 1] + "…"
                lines.append(
                    f"- {ds.dimension}: score={ds.score:.0f} conf={ds.confidence:.2f} :: {summary}"
                )
            return "\n".join(lines)

        # Map dimension -> specialist instance for quick lookup
        spec_by_dim = {spec.dimension: spec for spec in self._specialists}

        async def revise(score: DimensionScore) -> DimensionScore:
            spec = spec_by_dim.get(score.dimension)
            if spec is None:
                return score
            return await spec.revise_confidence(
                own_score=score, peer_summary=peer_summary_for(score), sink=sink
            )

        revised = await asyncio.gather(
            *(revise(s) for s in specialist_scores), return_exceptions=True
        )
        out: list[DimensionScore] = []
        for original, result in zip(specialist_scores, revised):
            out.append(result if isinstance(result, DimensionScore) else original)
        return out

    # ------------------------------------------------------------------ Layer 3 helpers
    async def _run_debate(
        self,
        specialist_scores: list[DimensionScore],
        risk: RiskAssessment | None,
        bias_audit: BiasAudit | None,
        active_weights: dict[str, float],
        sink,
    ):
        """Iterative Synthesizer ↔ Critic loop, terminated by the Arbitrator.

        - Runs at most ``debate_rounds`` rounds.
        - Stops early when the Synthesizer's overall score moves less than
          ``debate_convergence_delta`` between rounds.
        - Skips the Critic entirely (saves an LLM call) when synthesis confidence
          is high AND specialists agree (low score variance).
        """
        synthesis: SynthesisResult | None = None
        critic: CriticChallenge | None = None
        critic_skipped = False
        critic_disabled = False
        rounds_executed = 0

        for round_idx in range(max(1, self.config.debate_rounds)):
            rounds_executed = round_idx + 1
            previous_synthesis = synthesis
            previous_critic = critic
            synthesis = await self._synthesizer.run(
                specialist_scores,
                risk,
                bias_audit,
                active_weights,
                sink=sink,
                prior_critic=previous_critic,
            )

            if not self.config.enable_critic_debate or self.config.debate_rounds <= 0:
                critic = CriticChallenge(
                    is_overall_score_justified=True,
                    blind_spots=[],
                    counter_arguments=[],
                    suggested_score_adjustment=0.0,
                    summary="Critic disabled.",
                )
                critic_disabled = True
                break

            if self._should_skip_critic(synthesis, specialist_scores):
                critic_skipped = True
                await sink(
                    AgentThought(
                        agent="Critic",
                        phase="REFLECT",
                        thought=(
                            f"Critic skipped — synthesis confidence "
                            f"{synthesis.confidence:.2f} ≥ "
                            f"{self.config.skip_critic_confidence_threshold:.2f} "
                            "and specialists agreed."
                        ),
                        state="DEBATE",
                        timestamp=_now(),
                        metadata={"skipped": True, "round": round_idx + 1},
                    )
                )
                critic = CriticChallenge(
                    is_overall_score_justified=True,
                    blind_spots=[],
                    counter_arguments=[],
                    suggested_score_adjustment=0.0,
                    summary="Critic skipped — high-confidence consensus from the swarm.",
                )
                break

            critic = await self._critic.run(
                synthesis, specialist_scores, risk, bias_audit, sink=sink
            )

            # Convergence detection: stop iterating once the round-over-round
            # delta is small enough.
            if previous_synthesis is not None:
                delta = abs(synthesis.overall_score - previous_synthesis.overall_score)
                if delta < self.config.debate_convergence_delta:
                    await sink(
                        AgentThought(
                            agent="Orchestrator",
                            phase="REFLECT",
                            thought=(
                                f"Debate converged after round {round_idx + 1} "
                                f"(Δ={delta:.2f} < {self.config.debate_convergence_delta:.2f})"
                            ),
                            state="DEBATE",
                            timestamp=_now(),
                            metadata={"round": round_idx + 1, "delta": delta},
                        )
                    )
                    break

        assert synthesis is not None  # loop runs at least once
        if critic is None:
            critic = CriticChallenge(
                is_overall_score_justified=True,
                blind_spots=[],
                counter_arguments=[],
                suggested_score_adjustment=0.0,
                summary="Critic disabled.",
            )
            critic_disabled = True

        arbitrator = await self._arbitrator.run(synthesis, critic, risk, sink=sink)
        return synthesis, critic, arbitrator, {
            "critic_skipped": critic_skipped,
            "critic_disabled": critic_disabled,
            "rounds_executed": rounds_executed,
        }

    def _should_skip_critic(
        self,
        synthesis: SynthesisResult,
        specialist_scores: list[DimensionScore],
    ) -> bool:
        """True when synthesis confidence is high AND the swarm broadly agrees."""
        if not self.config.enable_critic_debate:
            return True
        if synthesis.confidence < self.config.skip_critic_confidence_threshold:
            return False
        variance = specialist_score_variance(specialist_scores)
        return variance <= self.config.skip_critic_score_variance_max

    # ------------------------------------------------------------------ core pipeline
    async def _run(
        self,
        candidate_id: str,
        jd_id: str,
        weights: Optional[dict[str, float]],
        sink,
        prefetched_jd: Optional[JobOpening] = None,
        precomputed_weights: Optional[dict[str, float]] = None,
    ) -> MatchResult:
        start = time.perf_counter()
        thoughts: list[AgentThought] = []

        async def collecting_sink(t: AgentThought) -> None:
            thoughts.append(t)
            if sink is not None:
                await sink(t)

        # ----- Layer 1: pre-flight ------------------------------------------------
        await collecting_sink(
            AgentThought(
                agent="Orchestrator",
                phase="OBSERVE",
                thought=f"Loading candidate {candidate_id} and JD {jd_id} from data store",
                state="PRE_FLIGHT",
                timestamp=_now(),
            )
        )
        candidate = self._load_candidate(candidate_id)
        jd = prefetched_jd or self._load_jd(jd_id)

        base_weights = normalise_weights(weights or self.config.default_weights)
        if precomputed_weights is not None:
            active_weights = precomputed_weights
        else:
            active_weights = adaptive_weights(jd, base_weights, self.config)

        # ---- Cache lookup (Layer 0a) ---------------------------------------
        cache_key = match_cache_key(
            candidate_id=candidate.candidate_id,
            jd_id=jd.jd_id,
            weights=active_weights,
            model=self._llm_debate.model_name,
            extra={
                "peer": self.config.enable_peer_awareness,
                "rounds": self.config.debate_rounds,
            },
        )
        if self._match_cache is not None:
            cached = await self._match_cache.get(cache_key)
            if cached is not None:
                try:
                    cached_result = MatchResult.model_validate(cached)
                    cached_result.metadata["served_from_cache"] = True
                    await collecting_sink(
                        AgentThought(
                            agent="Orchestrator",
                            phase="DONE",
                            thought="Cache hit — returning previously computed verdict.",
                            state="DONE",
                            timestamp=_now(),
                            metadata={"cache": "hit"},
                        )
                    )
                    return cached_result
                except Exception as exc:
                    logger.debug("Cache entry malformed (%s); recomputing.", exc)

        # ---- Fast-path (Layer 0b) ------------------------------------------
        if self.config.enable_embedding_fast_path:
            similarity = compute_similarity(candidate, jd)
            if similarity is not None:
                if similarity < self.config.fast_path_reject_threshold:
                    await collecting_sink(
                        AgentThought(
                            agent="Orchestrator",
                            phase="DONE",
                            thought=(
                                f"Fast-path reject: cosine={similarity:.2f} "
                                f"< {self.config.fast_path_reject_threshold:.2f}"
                            ),
                            state="DONE",
                            timestamp=_now(),
                            metadata={"fast_path": "reject", "similarity": similarity},
                        )
                    )
                    result = build_obvious_reject(candidate, jd, similarity, self.config)
                    result.metadata["weights"] = active_weights
                    if self._match_cache is not None:
                        await self._match_cache.set(
                            cache_key, result.model_dump(mode="json"),
                            ttl_seconds=self.config.match_cache_ttl_seconds,
                        )
                    return result
                if similarity > self.config.fast_path_strong_hire_threshold:
                    await collecting_sink(
                        AgentThought(
                            agent="Orchestrator",
                            phase="DONE",
                            thought=(
                                f"Fast-path strong-hire: cosine={similarity:.2f} "
                                f"> {self.config.fast_path_strong_hire_threshold:.2f}"
                            ),
                            state="DONE",
                            timestamp=_now(),
                            metadata={"fast_path": "strong_hire", "similarity": similarity},
                        )
                    )
                    result = build_obvious_strong_hire(candidate, jd, similarity, self.config)
                    result.metadata["weights"] = active_weights
                    if self._match_cache is not None:
                        await self._match_cache.set(
                            cache_key, result.model_dump(mode="json"),
                            ttl_seconds=self.config.match_cache_ttl_seconds,
                        )
                    return result

        # ---- Pre-flight (Layer 0): analysis + hygiene + location fit -------
        # All three run in parallel since they only depend on JD (or JD +
        # candidate for location). Hygiene + location are cached by content
        # hash, so subsequent matches against the same JD pay zero extra cost.
        jd_analysis: JDAnalysis | None = None
        jd_hygiene_dump: dict[str, Any] | None = None
        location_fit_dump: dict[str, Any] | None = None

        preflight_tasks: list[asyncio.Future | asyncio.Task] = []
        if self._jd_analyzer is not None:
            preflight_tasks.append(
                asyncio.ensure_future(self._jd_analyzer.analyse(jd))
            )
        else:
            preflight_tasks.append(asyncio.ensure_future(_noop_none()))
        if self._jd_hygiene is not None:
            preflight_tasks.append(
                asyncio.ensure_future(self._jd_hygiene.run(jd, sink=collecting_sink))
            )
        else:
            preflight_tasks.append(asyncio.ensure_future(_noop_none()))
        if self._location_fit_agent is not None:
            preflight_tasks.append(
                asyncio.ensure_future(
                    self._location_fit_agent.run(candidate, jd, sink=collecting_sink)
                )
            )
        else:
            preflight_tasks.append(asyncio.ensure_future(_noop_none()))

        try:
            preflight_results = await asyncio.gather(
                *preflight_tasks, return_exceptions=True
            )
        finally:
            # Avoid "Task was destroyed but it is pending!" if gather raises.
            for t in preflight_tasks:
                if not t.done():
                    t.cancel()

        # JD analysis result
        ana_res = preflight_results[0]
        if isinstance(ana_res, JDAnalysis):
            jd_analysis = ana_res
            await collecting_sink(
                AgentThought(
                    agent="Orchestrator",
                    phase="OBSERVE",
                    thought=f"JDAnalysis cached: {jd_analysis.summary}",
                    state="PRE_FLIGHT",
                    timestamp=_now(),
                    metadata={"jd_analysis": jd_analysis.model_dump()},
                )
            )
        elif isinstance(ana_res, BaseException):
            logger.warning("JDAnalyzer failed: %s", ana_res)

        # JD hygiene result
        hyg_res = preflight_results[1]
        if isinstance(hyg_res, BaseException):
            logger.warning("JDHygieneAgent failed: %s", hyg_res)
        elif hyg_res is not None:
            jd_hygiene_dump = hyg_res.model_dump()
            if hyg_res.severity == "block" and self.config.jd_hygiene_block_on_severe:
                await collecting_sink(
                    AgentThought(
                        agent="Orchestrator",
                        phase="DONE",
                        thought=(
                            f"JD hygiene BLOCKED this match: "
                            f"{hyg_res.summary[:140]}"
                        ),
                        state="DONE",
                        timestamp=_now(),
                        metadata={"jd_hygiene": jd_hygiene_dump, "blocked": True},
                    )
                )
                raise ValueError(
                    f"JD '{jd.jd_id}' failed hygiene check (severity=block). "
                    f"Issues: {hyg_res.summary}"
                )

        # Location-fit result
        loc_res = preflight_results[2]
        if isinstance(loc_res, BaseException):
            logger.warning("LocationFitAgent failed: %s", loc_res)
        elif loc_res is not None:
            location_fit_dump = loc_res.model_dump()
            if loc_res.fit == "block" and self.config.location_fit_block_on_severe:
                await collecting_sink(
                    AgentThought(
                        agent="Orchestrator",
                        phase="DONE",
                        thought=(
                            f"Location fit BLOCKED this match: {loc_res.summary[:140]}"
                        ),
                        state="DONE",
                        timestamp=_now(),
                        metadata={"location_fit": location_fit_dump, "blocked": True},
                    )
                )
                raise ValueError(
                    f"Candidate '{candidate.candidate_id}' is not location-compatible "
                    f"with JD '{jd.jd_id}'. Reasons: {loc_res.summary}"
                )

        if self.config.enable_adaptive_weights and active_weights != base_weights:
            shifts = {
                k: round(active_weights.get(k, 0.0) - base_weights.get(k, 0.0), 3)
                for k in base_weights
            }
            await collecting_sink(
                AgentThought(
                    agent="Orchestrator",
                    phase="PLAN",
                    thought=(
                        "Adaptive weight calibration: "
                        + ", ".join(
                            f"{k}{'+' if v >= 0 else ''}{v}" for k, v in shifts.items() if v != 0
                        )
                        or "no shift"
                    ),
                    state="PRE_FLIGHT",
                    timestamp=_now(),
                    metadata={"weights_active": active_weights, "weights_base": base_weights},
                )
            )

        await collecting_sink(
            AgentThought(
                agent="Orchestrator",
                phase="PLAN",
                thought=(
                    f"Dispatching {len(self._specialists)} specialists "
                    f"+ RiskAgent in parallel (asyncio.gather)"
                ),
                state="PRE_FLIGHT",
                timestamp=_now(),
            )
        )

        # ----- Layer 2: parallel specialist swarm ---------------------------------
        specialist_scores, risk = await self._run_swarm(
            candidate, jd, collecting_sink, jd_analysis=jd_analysis
        )

        # ----- Layer 2.7: deterministic groundedness verification ----------------
        # Verifies every Evidence quote is actually present in the resume / JD,
        # strips fabricated quotes, and shaves the confidence of specialists
        # that hallucinated heavily. Zero LLM cost, sub-millisecond.
        # NOTE: verifier state is kept LOCAL to this `_run` call (not on `self`)
        # because the orchestrator is shared across concurrent ranking calls.
        groundedness_dump: dict[str, Any] | None = None
        local_verifier: EvidenceVerifier | None = None
        local_groundedness = None
        if self.config.enable_evidence_verifier:
            try:
                local_verifier = EvidenceVerifier(candidate, jd)
                local_groundedness = local_verifier.verify_swarm(
                    specialist_scores, risk
                )
                groundedness_dump = local_groundedness.model_dump()
                await collecting_sink(
                    AgentThought(
                        agent="EvidenceVerifier",
                        phase="REFLECT",
                        thought=(
                            f"Evidence groundedness: "
                            f"{local_groundedness.grounded_evidence}/"
                            f"{local_groundedness.total_evidence} verified "
                            f"({local_groundedness.overall_pct * 100:.0f}%); "
                            f"{local_groundedness.fabricated_evidence} fabricated quote(s) stripped."
                        ),
                        state="SWARM",
                        timestamp=_now(),
                        metadata={
                            "overall_pct": local_groundedness.overall_pct,
                            "fabricated": local_groundedness.fabricated_evidence,
                            "raw_text_available": local_groundedness.raw_text_available,
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001 — never block on verifier failure
                logger.error("EvidenceVerifier failed: %s", exc, exc_info=True)
                local_verifier = None
                local_groundedness = None

        # Optional peer-awareness pass (the "swarm" interaction layer)
        if self.config.enable_peer_awareness and len(specialist_scores) >= 2:
            specialist_scores = await self._peer_awareness_pass(
                specialist_scores, collecting_sink
            )

        # Bias auditor uses all swarm outputs as context
        bias_audit: BiasAudit | None = None
        if self.config.enable_bias_audit:
            specialist_payload = [s.model_dump() for s in specialist_scores]
            if risk is not None:
                specialist_payload.append({"risk": risk.model_dump()})
            bias_audit = await self._bias_agent.run(
                candidate, jd, specialist_payload, sink=collecting_sink
            )

        # ----- Layer 3: iterative debate -----------------------------------------
        synthesis, critic, arbitrator, debate_meta = await self._run_debate(
            specialist_scores=specialist_scores,
            risk=risk,
            bias_audit=bias_audit,
            active_weights=active_weights,
            sink=collecting_sink,
        )

        # ----- Layer 4: insights -------------------------------------------------
        advisor_task = self._advisor.run(
            candidate, jd, arbitrator, specialist_scores, risk, sink=collecting_sink
        )
        explainer_task = self._explainer.run(
            candidate,
            jd,
            arbitrator,
            synthesis,
            specialist_scores,
            active_weights,
            sink=collecting_sink,
        )
        insights, explainability = await asyncio.gather(advisor_task, explainer_task)

        # ----- Layer 4.5: re-verify Explainability card evidence -----------------
        # The cards may surface new Evidence quotes; we run the same
        # deterministic verifier over them so the recruiter never sees a
        # fabricated quote in the final explainability tab.
        if (
            local_verifier is not None
            and local_groundedness is not None
            and explainability.cards
        ):
            try:
                local_verifier.verify_explainability_cards(
                    local_groundedness, explainability.cards
                )
                groundedness_dump = local_groundedness.model_dump()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Explainability re-verification failed: %s", exc)

        elapsed = time.perf_counter() - start
        swarm_health = _compute_swarm_health(specialist_scores, risk, bias_audit)

        # ----- Final result ------------------------------------------------------
        match_result = MatchResult(
            candidate_id=candidate.candidate_id,
            jd_id=jd.jd_id,
            job_title=jd.job_title,
            overall_score=arbitrator.final_score,
            verdict=arbitrator.verdict,
            confidence=arbitrator.confidence,
            dimension_scores=specialist_scores,
            risk=risk,
            bias_audit=bias_audit,
            synthesis=synthesis,
            critic=critic,
            arbitrator=arbitrator,
            insights=insights,
            explainability=explainability,
            agent_thoughts=thoughts,
            metadata={
                "elapsed_seconds": round(elapsed, 2),
                "candidate_name": candidate.name,
                "weights": active_weights,
                "weights_base": base_weights,
                "weights_adapted": (
                    self.config.enable_adaptive_weights and active_weights != base_weights
                ),
                "swarm_size": len(self._specialists) + 1,  # +1 for risk
                "debate_enabled": self.config.enable_critic_debate,
                "debate_rounds_configured": self.config.debate_rounds,
                "debate_rounds_executed": debate_meta["rounds_executed"],
                "critic_skipped": debate_meta["critic_skipped"],
                "critic_disabled": debate_meta["critic_disabled"],
                "peer_awareness_enabled": self.config.enable_peer_awareness,
                "bias_audit_enabled": self.config.enable_bias_audit,
                "run_id": str(uuid.uuid4()),
                "completed_at": _now(),
                "swarm_health": swarm_health,
                "jd_hygiene": jd_hygiene_dump,
                "location_fit": location_fit_dump,
                "groundedness": groundedness_dump,
            },
        )

        await collecting_sink(
            AgentThought(
                agent="Orchestrator",
                phase="DONE",
                thought=(
                    f"Match complete in {elapsed:.1f}s — verdict {arbitrator.verdict.value} "
                    f"({arbitrator.final_score:.1f}/100)"
                ),
                state="DONE",
                timestamp=_now(),
                metadata={"elapsed_seconds": elapsed},
            )
        )

        # ---- Write-back to cache --------------------------------------------
        if self._match_cache is not None:
            try:
                await self._match_cache.set(
                    cache_key,
                    match_result.model_dump(mode="json"),
                    ttl_seconds=self.config.match_cache_ttl_seconds,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Cache write-back failed (%s); ignoring.", exc)

        return match_result
