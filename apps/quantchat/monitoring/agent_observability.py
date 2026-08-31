"""
Agent Observability Manager
============================

Production-grade observability system for the QuantChat RAG pipeline.
Provides comprehensive monitoring, evaluation, auditing, alerting, and feedback.

7 Pillars of Agent Observability:
1. Tracing (LangSmith) — step-by-step pipeline visibility
2. Evaluation — RAG quality metrics (faithfulness, relevance, groundedness)
3. Cost & Token Tracking — per-query economics
4. Agent Decision Audit Trail — why the agent chose each path
5. Performance Metrics — P50/P95/P99 latencies, error rates
6. Alerting — threshold-based quality/latency/error alerts
7. User Feedback Loop — human-in-the-loop quality improvement
"""

import re
import time
import json
import hashlib
import statistics
import threading
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..config.logging_config import setup_logger
from ..utils.tracing import traceable, trace_metadata
from ..config.settings import (
    OBSERVABILITY_MAX_TRACES, OBSERVABILITY_MAX_ALERTS,
    OBSERVABILITY_ALERT_COOLDOWN_SECONDS,
    OBSERVABILITY_LATENCY_WARNING_MS, OBSERVABILITY_LATENCY_CRITICAL_MS,
    OBSERVABILITY_QUALITY_WARNING, OBSERVABILITY_CONFIDENCE_WARNING,
    OBSERVABILITY_ERROR_RATE_WARNING, OBSERVABILITY_HOURLY_COST_WARNING_USD,
    OBSERVABILITY_PII_REDACTION, OBSERVABILITY_ALERT_WEBHOOK_URL,
)

logger = setup_logger("agent_observability")


# ──────────────────────────────────────────────
#  PII REDACTION ENGINE (GDPR / COMPLIANCE)
# ──────────────────────────────────────────────

_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    (re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE_REDACTED]'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
    (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '[CARD_REDACTED]'),
]


def redact_pii(text: str) -> str:
    """Remove emails, phone numbers, SSNs, card numbers from text for compliance."""
    if not OBSERVABILITY_PII_REDACTION or not text:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ──────────────────────────────────────────────
#  STRUCTURED LOG FILTER (TRACE CORRELATION)
# ──────────────────────────────────────────────

_current_trace_id = threading.local()


class TraceContextFilter(logging.Filter):
    """Injects obs_trace_id into every log record for log/trace correlation."""
    def filter(self, record):
        record.obs_trace_id = getattr(_current_trace_id, 'value', '-')
        return True


def set_trace_context(trace_id: Optional[str]):
    """Set the current trace ID for structured log correlation."""
    _current_trace_id.value = trace_id or '-'


# ──────────────────────────────────────────────
#  DATA MODELS
# ──────────────────────────────────────────────

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertType(str, Enum):
    LATENCY_SPIKE = "latency_spike"
    QUALITY_DROP = "quality_drop"
    ERROR_RATE = "error_rate"
    COST_SPIKE = "cost_spike"
    LOW_CONFIDENCE = "low_confidence"
    HALLUCINATION_DETECTED = "hallucination_detected"

class FeedbackRating(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

@dataclass
class QueryTrace:
    """Complete trace of a single query through the pipeline."""
    trace_id: str
    timestamp: str
    query: str
    session_id: str
    
    # Pipeline decisions
    intent: str = ""
    domain: str = ""
    pipeline_route: str = ""
    entity_names: List[str] = field(default_factory=list)
    
    # Retrieval metrics
    query_variations: int = 0
    vector_chunks: int = 0
    keyword_chunks: int = 0
    fused_chunks: int = 0
    reranked_chunks: int = 0
    context_chunks: int = 0
    context_tokens: int = 0
    
    # Quality metrics
    intent_confidence: float = 0.0
    response_confidence: float = 0.0
    confidence: float = 0.0
    validation_passed: bool = True
    hallucination_risk: float = 0.0
    groundedness_score: float = 0.0
    relevance_score: float = 0.0
    faithfulness_score: float = 0.0
    
    # Cost metrics
    llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    
    # Performance
    total_latency_ms: float = 0.0
    step_latencies: Dict[str, float] = field(default_factory=dict)
    
    # Response
    response_length: int = 0
    source: str = ""
    cached: bool = False
    error: Optional[str] = None
    
    # Feedback
    user_feedback: Optional[str] = None
    feedback_comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Alert:
    """Observability alert."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: str
    metric_value: float
    threshold: float
    trace_id: Optional[str] = None
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "trace_id": self.trace_id,
            "acknowledged": self.acknowledged,
        }


# ──────────────────────────────────────────────
#  TOKEN COST ESTIMATOR
# ──────────────────────────────────────────────

# Gemini pricing (per 1M tokens, approx)
MODEL_COSTS = {
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro-002": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}


def estimate_tokens(text: str) -> int:
    """Approximate token count (1 token ~ 4 chars for English)."""
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS.get("gemini-2.5-pro"))
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


# ──────────────────────────────────────────────
#  RAG EVALUATION ENGINE
# ──────────────────────────────────────────────

class RAGEvaluator:
    """
    Evaluates RAG response quality without requiring an additional LLM call.
    Uses heuristic-based scoring for real-time evaluation.
    """
    
    def evaluate(
        self,
        query: str,
        response: str,
        context: str,
        entity_names: List[str] = None,
    ) -> Dict[str, float]:
        """
        Evaluate RAG quality across three dimensions.
        
        Returns:
            scores dict with faithfulness, relevance, groundedness (0.0-1.0)
        """
        faithfulness = self._score_faithfulness(response, context, entity_names)
        relevance = self._score_relevance(query, response)
        groundedness = self._score_groundedness(response, context)
        
        return {
            "faithfulness": round(faithfulness, 3),
            "relevance": round(relevance, 3),
            "groundedness": round(groundedness, 3),
            "overall": round((faithfulness + relevance + groundedness) / 3, 3),
        }
    
    def _score_faithfulness(self, response: str, context: str, entity_names: list = None) -> float:
        """Does the response only contain information from the context?"""
        import re
        score = 1.0
        response_lower = response.lower()
        context_lower = context.lower()
        
        # Penalty: numbers in response not in context
        resp_numbers = set(re.findall(r'\b\d{2,}\b', response))
        ctx_numbers = set(re.findall(r'\b\d{2,}\b', context))
        novel_numbers = resp_numbers - ctx_numbers
        score -= min(0.3, len(novel_numbers) * 0.05)
        
        # Penalty: entity names in response not in context
        if entity_names:
            for name in entity_names:
                if name.lower() in response_lower and name.lower() not in context_lower:
                    score -= 0.15
        
        # Penalty: fabrication patterns
        fabrication_signals = [
            r"i believe", r"i think", r"probably", r"likely",
            r"it seems", r"as far as i know",
        ]
        for pattern in fabrication_signals:
            if re.search(pattern, response_lower):
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_relevance(self, query: str, response: str) -> float:
        """Does the response address the query?"""
        query_words = set(w.lower() for w in query.split() if len(w) > 3)
        response_words = set(w.lower() for w in response.split() if len(w) > 3)
        
        if not query_words:
            return 0.5
        
        overlap = len(query_words & response_words)
        coverage = overlap / len(query_words)
        
        # High coverage = relevant response
        if coverage >= 0.6:
            return min(1.0, 0.7 + coverage * 0.3)
        elif coverage >= 0.3:
            return 0.5 + coverage * 0.5
        else:
            return max(0.2, coverage * 2)
    
    def _score_groundedness(self, response: str, context: str) -> float:
        """Are the claims in the response supported by context?"""
        response_sentences = [s.strip() for s in response.split('.') if len(s.strip()) > 20]
        
        if not response_sentences:
            return 0.5
        
        context_lower = context.lower()
        grounded_count = 0
        
        for sentence in response_sentences:
            sentence_words = set(w.lower() for w in sentence.split() if len(w) > 4)
            if not sentence_words:
                continue
            
            ctx_overlap = sum(1 for w in sentence_words if w in context_lower)
            if ctx_overlap / max(len(sentence_words), 1) >= 0.4:
                grounded_count += 1
        
        return grounded_count / max(len(response_sentences), 1)


# ──────────────────────────────────────────────
#  AGENT OBSERVABILITY MANAGER
# ──────────────────────────────────────────────

class AgentObservabilityManager:
    """
    Central observability hub for the entire QuantChat pipeline.
    
    Tracks every query through: tracing, evaluation, costing,
    auditing, performance, alerting, and feedback.
    """
    
    # Alerting thresholds (driven by config/settings.py → env vars)
    LATENCY_WARNING_MS = OBSERVABILITY_LATENCY_WARNING_MS
    LATENCY_CRITICAL_MS = OBSERVABILITY_LATENCY_CRITICAL_MS
    CONFIDENCE_WARNING = OBSERVABILITY_CONFIDENCE_WARNING
    QUALITY_WARNING = OBSERVABILITY_QUALITY_WARNING
    ERROR_RATE_WARNING = OBSERVABILITY_ERROR_RATE_WARNING
    HOURLY_COST_WARNING_USD = OBSERVABILITY_HOURLY_COST_WARNING_USD
    ALERT_COOLDOWN_SECONDS = OBSERVABILITY_ALERT_COOLDOWN_SECONDS
    
    # Retention (configurable)
    MAX_TRACES = OBSERVABILITY_MAX_TRACES
    MAX_ALERTS = OBSERVABILITY_MAX_ALERTS
    MAX_FEEDBACK = 5_000
    
    def __init__(self):
        self._lock = threading.Lock()
        self.traces: deque = deque(maxlen=self.MAX_TRACES)
        self.alerts: deque = deque(maxlen=self.MAX_ALERTS)
        self.feedback_log: deque = deque(maxlen=self.MAX_FEEDBACK)
        self.evaluator = RAGEvaluator()
        self._webhook_handlers: List[Callable] = []
        
        # Running statistics
        self._latencies: deque = deque(maxlen=1000)
        self._error_count = 0
        self._total_count = 0
        self._hourly_cost: Dict[str, float] = defaultdict(float)
        self._intent_counts: Dict[str, int] = defaultdict(int)
        self._quality_scores: deque = deque(maxlen=500)
        self._confidence_scores: deque = deque(maxlen=500)
        self._last_alert_time: Dict[str, float] = {}
        
        logger.info(
            f"AgentObservabilityManager initialized "
            f"(pii_redaction={OBSERVABILITY_PII_REDACTION}, "
            f"webhook={'configured' if OBSERVABILITY_ALERT_WEBHOOK_URL else 'none'})"
        )
    
    # ─── TRACE LIFECYCLE ─────────────────────
    
    def start_trace(self, query: str, session_id: str) -> str:
        """Start a new query trace. Returns trace_id."""
        trace_id = hashlib.md5(
            f"{query}{session_id}{time.time()}".encode()
        ).hexdigest()[:16]
        
        set_trace_context(trace_id)
        
        trace = QueryTrace(
            trace_id=trace_id,
            timestamp=datetime.now().isoformat(),
            query=redact_pii(query[:500]),
            session_id=session_id,
        )
        with self._lock:
            self.traces.append(trace)
            self._total_count += 1
        return trace_id
    
    def get_current_trace(self, trace_id: str) -> Optional[QueryTrace]:
        """Retrieve trace by ID."""
        for trace in reversed(self.traces):
            if trace.trace_id == trace_id:
                return trace
        return None
    
    def record_intent(
        self, trace_id: str, intent: str, domain: str,
        entity_names: List[str], pipeline_route: str,
        confidence: float = 0.0
    ):
        """Record intent classification decision."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        
        trace.intent = intent
        trace.domain = domain
        trace.entity_names = entity_names
        trace.pipeline_route = pipeline_route
        trace.intent_confidence = confidence
        
        self._intent_counts[intent] += 1
    
    def record_retrieval(
        self, trace_id: str, query_variations: int,
        vector_chunks: int, keyword_chunks: int,
        fused_chunks: int, reranked_chunks: int
    ):
        """Record retrieval stage metrics."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        
        trace.query_variations = query_variations
        trace.vector_chunks = vector_chunks
        trace.keyword_chunks = keyword_chunks
        trace.fused_chunks = fused_chunks
        trace.reranked_chunks = reranked_chunks
    
    def record_context(self, trace_id: str, chunks_used: int, context_text: str):
        """Record context building metrics."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        
        trace.context_chunks = chunks_used
        trace.context_tokens = estimate_tokens(context_text)
    
    def record_llm_call(
        self, trace_id: str, model: str,
        input_text: str, output_text: str
    ):
        """Record a single LLM call with cost estimation."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        cost = estimate_cost(model, input_tokens, output_tokens)
        
        trace.llm_calls += 1
        trace.total_input_tokens += input_tokens
        trace.total_output_tokens += output_tokens
        trace.estimated_cost_usd += cost
        
        # Accumulate hourly cost
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        self._hourly_cost[hour_key] += cost
    
    def record_step_latency(self, trace_id: str, step_name: str, latency_ms: float):
        """Record latency for a pipeline step."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        trace.step_latencies[step_name] = round(latency_ms, 2)
    
    def complete_trace(
        self, trace_id: str,
        response: str, context: str,
        source: str, confidence: float,
        total_latency_ms: float,
        validation_passed: bool = True,
        cached: bool = False,
        error: Optional[str] = None
    ):
        """Finalize trace with response quality evaluation."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            return
        
        trace.response_length = len(response)
        trace.source = source
        trace.response_confidence = confidence
        trace.confidence = confidence
        trace.total_latency_ms = round(total_latency_ms, 2)
        trace.validation_passed = validation_passed
        trace.cached = cached
        trace.error = error
        
        # Track latency and errors (thread-safe)
        with self._lock:
            self._latencies.append(total_latency_ms)
            if error:
                self._error_count += 1
        
        # RAG quality evaluation (skip for cached/general/error)
        if context and source in ("rag_pipeline", "rag") and not cached and not error:
            eval_scores = self.evaluator.evaluate(
                query=trace.query,
                response=response,
                context=context,
                entity_names=trace.entity_names,
            )
            trace.faithfulness_score = eval_scores["faithfulness"]
            trace.relevance_score = eval_scores["relevance"]
            trace.groundedness_score = eval_scores["groundedness"]
            trace.hallucination_risk = round(1.0 - eval_scores["faithfulness"], 3)
            
            self._quality_scores.append(eval_scores["overall"])
        
        self._confidence_scores.append(confidence)
        
        # Check for alerts
        self._check_alerts(trace)
        
        # Attach observability metadata to LangSmith trace
        trace_metadata({
            "obs_trace_id": trace_id,
            "faithfulness": trace.faithfulness_score,
            "relevance": trace.relevance_score,
            "groundedness": trace.groundedness_score,
            "hallucination_risk": trace.hallucination_risk,
            "estimated_cost_usd": trace.estimated_cost_usd,
            "llm_calls": trace.llm_calls,
            "total_tokens": trace.total_input_tokens + trace.total_output_tokens,
        })
        
        logger.info(
            f"Trace {trace_id} complete: "
            f"latency={total_latency_ms:.0f}ms, "
            f"confidence={confidence:.2f}, "
            f"cost=${trace.estimated_cost_usd:.4f}, "
            f"quality={trace.faithfulness_score:.2f}/{trace.relevance_score:.2f}/{trace.groundedness_score:.2f}"
        )
        
        set_trace_context(None)
    
    # ─── FEEDBACK ────────────────────────────
    
    def record_feedback(
        self, trace_id: str, rating: str,
        comment: Optional[str] = None
    ) -> bool:
        """Record user feedback for a query."""
        trace = self.get_current_trace(trace_id)
        if not trace:
            logger.warning(f"Trace {trace_id} not found for feedback")
            return False
        
        trace.user_feedback = rating
        trace.feedback_comment = comment
        
        self.feedback_log.append({
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "query": trace.query,
            "intent": trace.intent,
            "rating": rating,
            "comment": redact_pii(comment) if comment else None,
            "confidence": trace.confidence,
            "faithfulness": trace.faithfulness_score,
        })
        
        # Alert on negative feedback with high confidence (quality issue)
        if rating == FeedbackRating.NEGATIVE.value and trace.confidence >= 0.7:
            self._emit_alert(
                AlertType.QUALITY_DROP,
                AlertSeverity.WARNING,
                f"Negative feedback on high-confidence response (conf={trace.confidence:.2f})",
                metric_value=trace.confidence,
                threshold=0.7,
                trace_id=trace_id,
            )
        
        logger.info(f"Feedback recorded: trace={trace_id}, rating={rating}")
        return True
    
    # ─── ALERTING ────────────────────────────
    
    def _check_alerts(self, trace: QueryTrace):
        """Evaluate alert conditions for a completed trace."""
        # Latency alerts
        if trace.total_latency_ms >= self.LATENCY_CRITICAL_MS:
            self._emit_alert(
                AlertType.LATENCY_SPIKE, AlertSeverity.CRITICAL,
                f"Critical latency: {trace.total_latency_ms:.0f}ms (query: {trace.query[:60]})",
                metric_value=trace.total_latency_ms,
                threshold=self.LATENCY_CRITICAL_MS,
                trace_id=trace.trace_id,
            )
        elif trace.total_latency_ms >= self.LATENCY_WARNING_MS:
            self._emit_alert(
                AlertType.LATENCY_SPIKE, AlertSeverity.WARNING,
                f"High latency: {trace.total_latency_ms:.0f}ms (query: {trace.query[:60]})",
                metric_value=trace.total_latency_ms,
                threshold=self.LATENCY_WARNING_MS,
                trace_id=trace.trace_id,
            )
        
        # Low confidence alert
        if trace.confidence < self.CONFIDENCE_WARNING and trace.source != "general_knowledge":
            self._emit_alert(
                AlertType.LOW_CONFIDENCE, AlertSeverity.WARNING,
                f"Low confidence response: {trace.confidence:.2f} for intent={trace.intent}",
                metric_value=trace.confidence,
                threshold=self.CONFIDENCE_WARNING,
                trace_id=trace.trace_id,
            )
        
        # Hallucination risk alert
        if trace.hallucination_risk >= 0.5:
            self._emit_alert(
                AlertType.HALLUCINATION_DETECTED, AlertSeverity.CRITICAL,
                f"High hallucination risk: {trace.hallucination_risk:.2f} (faithfulness={trace.faithfulness_score:.2f})",
                metric_value=trace.hallucination_risk,
                threshold=0.5,
                trace_id=trace.trace_id,
            )
        
        # Quality degradation (rolling average)
        if len(self._quality_scores) >= 10:
            recent_avg = statistics.mean(list(self._quality_scores)[-10:])
            if recent_avg < self.QUALITY_WARNING:
                self._emit_alert(
                    AlertType.QUALITY_DROP, AlertSeverity.WARNING,
                    f"Quality degradation: rolling avg={recent_avg:.2f} (threshold={self.QUALITY_WARNING})",
                    metric_value=recent_avg,
                    threshold=self.QUALITY_WARNING,
                )
        
        # Error rate alert
        if self._total_count >= 20:
            error_rate = self._error_count / self._total_count
            if error_rate >= self.ERROR_RATE_WARNING:
                self._emit_alert(
                    AlertType.ERROR_RATE, AlertSeverity.CRITICAL,
                    f"Error rate: {error_rate:.1%} ({self._error_count}/{self._total_count})",
                    metric_value=error_rate,
                    threshold=self.ERROR_RATE_WARNING,
                )
        
        # Hourly cost alert
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        if self._hourly_cost.get(hour_key, 0) >= self.HOURLY_COST_WARNING_USD:
            self._emit_alert(
                AlertType.COST_SPIKE, AlertSeverity.WARNING,
                f"Hourly cost: ${self._hourly_cost[hour_key]:.2f} (threshold=${self.HOURLY_COST_WARNING_USD})",
                metric_value=self._hourly_cost[hour_key],
                threshold=self.HOURLY_COST_WARNING_USD,
            )
    
    def _emit_alert(
        self, alert_type: AlertType, severity: AlertSeverity,
        message: str, metric_value: float, threshold: float,
        trace_id: Optional[str] = None
    ):
        """Create and store an alert with cooldown deduplication."""
        now = time.time()
        cooldown_key = f"{alert_type.value}:{severity.value}"
        with self._lock:
            last_time = self._last_alert_time.get(cooldown_key, 0)
            if now - last_time < self.ALERT_COOLDOWN_SECONDS:
                return
            self._last_alert_time[cooldown_key] = now
        
        alert_id = hashlib.md5(
            f"{alert_type}{message}{now}".encode()
        ).hexdigest()[:12]
        
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now().isoformat(),
            metric_value=metric_value,
            threshold=threshold,
            trace_id=trace_id,
        )
        
        self.alerts.append(alert)
        
        log_fn = logger.critical if severity == AlertSeverity.CRITICAL else logger.warning
        log_fn(f"ALERT [{severity.value}] {alert_type.value}: {message}")
        
        # Dispatch to webhook (Slack, PagerDuty, etc.) — non-blocking
        self._dispatch_webhook(alert)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    # ─── DASHBOARD METRICS ───────────────────
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get P50/P95/P99 latencies and throughput metrics."""
        latencies = list(self._latencies)
        
        if not latencies:
            return {"status": "no_data", "total_queries": 0}
        
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        
        return {
            "total_queries": self._total_count,
            "total_errors": self._error_count,
            "error_rate": round(self._error_count / max(self._total_count, 1), 4),
            "latency": {
                "p50_ms": round(sorted_lat[int(n * 0.5)], 2),
                "p95_ms": round(sorted_lat[int(n * 0.95)], 2),
                "p99_ms": round(sorted_lat[int(n * 0.99)], 2),
                "avg_ms": round(statistics.mean(sorted_lat), 2),
                "min_ms": round(min(sorted_lat), 2),
                "max_ms": round(max(sorted_lat), 2),
            },
            "sample_count": n,
        }
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get RAG quality evaluation metrics."""
        quality = list(self._quality_scores)
        confidence = list(self._confidence_scores)
        
        if not quality:
            return {"status": "no_data"}
        
        # Gather per-dimension scores from recent traces
        recent_traces = [t for t in self.traces if t.faithfulness_score > 0][-100:]
        
        return {
            "quality": {
                "avg_overall": round(statistics.mean(quality), 3) if quality else 0,
                "avg_faithfulness": round(
                    statistics.mean(t.faithfulness_score for t in recent_traces), 3
                ) if recent_traces else 0,
                "avg_relevance": round(
                    statistics.mean(t.relevance_score for t in recent_traces), 3
                ) if recent_traces else 0,
                "avg_groundedness": round(
                    statistics.mean(t.groundedness_score for t in recent_traces), 3
                ) if recent_traces else 0,
            },
            "confidence": {
                "avg": round(statistics.mean(confidence), 3) if confidence else 0,
                "min": round(min(confidence), 3) if confidence else 0,
            },
            "hallucination": {
                "high_risk_count": sum(
                    1 for t in recent_traces if t.hallucination_risk >= 0.5
                ),
                "avg_risk": round(
                    statistics.mean(t.hallucination_risk for t in recent_traces), 3
                ) if recent_traces else 0,
            },
            "sample_count": len(quality),
        }
    
    def get_cost_metrics(self) -> Dict[str, Any]:
        """Get token usage and cost metrics."""
        recent_traces = list(self.traces)[-200:]
        
        if not recent_traces:
            return {"status": "no_data"}
        
        traced_with_cost = [t for t in recent_traces if t.llm_calls > 0]
        
        total_cost = sum(t.estimated_cost_usd for t in traced_with_cost)
        total_input = sum(t.total_input_tokens for t in traced_with_cost)
        total_output = sum(t.total_output_tokens for t in traced_with_cost)
        total_llm_calls = sum(t.llm_calls for t in traced_with_cost)
        
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        
        return {
            "total_cost_usd": round(total_cost, 4),
            "current_hour_cost_usd": round(self._hourly_cost.get(hour_key, 0), 4),
            "avg_cost_per_query_usd": round(
                total_cost / max(len(traced_with_cost), 1), 6
            ),
            "tokens": {
                "total_input": total_input,
                "total_output": total_output,
                "avg_input_per_query": total_input // max(len(traced_with_cost), 1),
                "avg_output_per_query": total_output // max(len(traced_with_cost), 1),
            },
            "llm_calls": {
                "total": total_llm_calls,
                "avg_per_query": round(
                    total_llm_calls / max(len(traced_with_cost), 1), 1
                ),
            },
            "sample_count": len(traced_with_cost),
        }
    
    def get_agent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent agent decision audit trail."""
        recent = list(self.traces)[-limit:]
        
        return [
            {
                "trace_id": t.trace_id,
                "timestamp": t.timestamp,
                "query": t.query,
                "decision": {
                    "intent": t.intent,
                    "domain": t.domain,
                    "pipeline": t.pipeline_route,
                    "entities": t.entity_names,
                },
                "outcome": {
                    "intent_confidence": t.intent_confidence,
                    "response_confidence": t.response_confidence,
                    "source": t.source,
                    "latency_ms": t.total_latency_ms,
                    "cached": t.cached,
                    "error": t.error,
                    "step_latencies": t.step_latencies,
                },
                "quality": {
                    "faithfulness": t.faithfulness_score,
                    "relevance": t.relevance_score,
                    "groundedness": t.groundedness_score,
                    "hallucination_risk": t.hallucination_risk,
                },
                "cost_usd": t.estimated_cost_usd,
                "feedback": t.user_feedback,
            }
            for t in reversed(recent)
        ]
    
    def get_alerts(self, unacknowledged_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        alerts = list(self.alerts)
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        return [a.to_dict() for a in reversed(alerts[-limit:])]
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        feedback = list(self.feedback_log)
        
        if not feedback:
            return {"status": "no_feedback", "total": 0}
        
        ratings = defaultdict(int)
        for f in feedback:
            ratings[f.get("rating", "unknown")] += 1
        
        negative_with_high_conf = [
            f for f in feedback
            if f.get("rating") == "negative" and f.get("confidence", 0) >= 0.7
        ]
        
        return {
            "total": len(feedback),
            "distribution": dict(ratings),
            "satisfaction_rate": round(
                ratings.get("positive", 0) / max(len(feedback), 1), 3
            ),
            "quality_issues": len(negative_with_high_conf),
            "recent_negative": [
                {"query": f["query"], "comment": f.get("comment"), "intent": f.get("intent")}
                for f in negative_with_high_conf[-5:]
            ],
        }
    
    # ─── ENTERPRISE: WEBHOOK DISPATCH ────────
    
    def _dispatch_webhook(self, alert: Alert):
        """Send alert to external webhook (Slack, PagerDuty, etc.) — fire-and-forget."""
        if not OBSERVABILITY_ALERT_WEBHOOK_URL:
            return
        
        for hook_fn in self._webhook_handlers:
            try:
                hook_fn(alert.to_dict())
            except Exception as e:
                logger.debug(f"Webhook handler failed: {e}")
        
        def _send():
            try:
                import urllib.request
                payload = json.dumps({
                    "text": f"[{alert.severity.value.upper()}] {alert.alert_type.value}: {alert.message}",
                    "alert": alert.to_dict(),
                }).encode("utf-8")
                req = urllib.request.Request(
                    OBSERVABILITY_ALERT_WEBHOOK_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                logger.debug(f"Webhook dispatch failed: {e}")
        
        threading.Thread(target=_send, daemon=True).start()
    
    def register_webhook_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Register a custom webhook handler for alerts."""
        self._webhook_handlers.append(handler)
    
    # ─── ENTERPRISE: TRACE EXPORT ─────────────
    
    def export_traces(self, limit: int = 1000, since: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export traces as serializable dicts for persistence to DB/file/S3.
        
        Args:
            limit: Max traces to export
            since: ISO timestamp — only export traces after this time
        
        Returns:
            List of trace dicts ready for JSON serialization
        """
        traces = list(self.traces)
        
        if since:
            traces = [t for t in traces if t.timestamp >= since]
        
        return [t.to_dict() for t in traces[-limit:]]
    
    def export_traces_jsonl(self, limit: int = 1000) -> str:
        """Export traces in JSON Lines format (one JSON object per line)."""
        traces = self.export_traces(limit=limit)
        return "\n".join(json.dumps(t) for t in traces)
    
    # ─── ENTERPRISE: HEALTH STATUS ────────────
    
    def get_health(self) -> Dict[str, Any]:
        """Observability subsystem health check."""
        now = datetime.now()
        recent_traces = [t for t in self.traces if t.timestamp >= (now - timedelta(minutes=5)).isoformat()]
        recent_errors = [t for t in recent_traces if t.error]
        unack_critical = sum(
            1 for a in self.alerts
            if not a.acknowledged and a.severity == AlertSeverity.CRITICAL
        )
        
        if unack_critical > 0:
            health_status = "degraded"
        elif self._total_count == 0:
            health_status = "idle"
        else:
            health_status = "healthy"
        
        return {
            "status": health_status,
            "uptime_queries": self._total_count,
            "traces_stored": len(self.traces),
            "traces_capacity_pct": round(len(self.traces) / max(self.MAX_TRACES, 1) * 100, 1),
            "alerts_stored": len(self.alerts),
            "unacknowledged_critical": unack_critical,
            "last_5min": {
                "queries": len(recent_traces),
                "errors": len(recent_errors),
                "error_rate": round(len(recent_errors) / max(len(recent_traces), 1), 4),
            },
            "pii_redaction_enabled": OBSERVABILITY_PII_REDACTION,
            "webhook_configured": bool(OBSERVABILITY_ALERT_WEBHOOK_URL),
            "timestamp": now.isoformat(),
        }
    
    # ─── ENTERPRISE: PROMETHEUS METRICS ───────
    
    def get_prometheus_metrics(self) -> str:
        """
        Render metrics in Prometheus text exposition format.
        Scrapeable by Prometheus, Grafana Agent, Datadog, etc.
        """
        lines = []
        
        lines.append("# HELP quantchat_queries_total Total queries processed")
        lines.append("# TYPE quantchat_queries_total counter")
        lines.append(f"quantchat_queries_total {self._total_count}")
        
        lines.append("# HELP quantchat_errors_total Total query errors")
        lines.append("# TYPE quantchat_errors_total counter")
        lines.append(f"quantchat_errors_total {self._error_count}")
        
        latencies = sorted(self._latencies) if self._latencies else []
        if latencies:
            n = len(latencies)
            lines.append("# HELP quantchat_latency_ms Query latency in milliseconds")
            lines.append("# TYPE quantchat_latency_ms summary")
            lines.append(f'quantchat_latency_ms{{quantile="0.5"}} {latencies[int(n*0.5)]:.2f}')
            lines.append(f'quantchat_latency_ms{{quantile="0.95"}} {latencies[int(n*0.95)]:.2f}')
            lines.append(f'quantchat_latency_ms{{quantile="0.99"}} {latencies[int(n*0.99)]:.2f}')
            lines.append(f"quantchat_latency_ms_sum {sum(latencies):.2f}")
            lines.append(f"quantchat_latency_ms_count {n}")
        
        quality = list(self._quality_scores)
        if quality:
            lines.append("# HELP quantchat_quality_score RAG quality score (0-1)")
            lines.append("# TYPE quantchat_quality_score gauge")
            lines.append(f"quantchat_quality_score {statistics.mean(quality):.4f}")
        
        hour_key = datetime.now().strftime("%Y-%m-%d-%H")
        lines.append("# HELP quantchat_cost_current_hour_usd Current hour LLM cost")
        lines.append("# TYPE quantchat_cost_current_hour_usd gauge")
        lines.append(f"quantchat_cost_current_hour_usd {self._hourly_cost.get(hour_key, 0):.6f}")
        
        lines.append("# HELP quantchat_alerts_unacknowledged Unacknowledged alert count")
        lines.append("# TYPE quantchat_alerts_unacknowledged gauge")
        unack = sum(1 for a in self.alerts if not a.acknowledged)
        lines.append(f"quantchat_alerts_unacknowledged {unack}")
        
        for intent, count in self._intent_counts.items():
            lines.append(f'quantchat_intent_total{{intent="{intent}"}} {count}')
        
        feedback = list(self.feedback_log)
        pos = sum(1 for f in feedback if f.get("rating") == "positive")
        neg = sum(1 for f in feedback if f.get("rating") == "negative")
        lines.append("# HELP quantchat_feedback_total User feedback counts")
        lines.append("# TYPE quantchat_feedback_total counter")
        lines.append(f'quantchat_feedback_total{{rating="positive"}} {pos}')
        lines.append(f'quantchat_feedback_total{{rating="negative"}} {neg}')
        
        lines.append("")
        return "\n".join(lines)
    
    # ─── FULL DASHBOARD ──────────────────────
    
    def get_full_dashboard(self) -> Dict[str, Any]:
        """Get complete observability dashboard data."""
        return {
            "timestamp": datetime.now().isoformat(),
            "health": self.get_health(),
            "performance": self.get_performance_metrics(),
            "quality": self.get_quality_metrics(),
            "cost": self.get_cost_metrics(),
            "alerts": {
                "total": len(self.alerts),
                "unacknowledged": sum(1 for a in self.alerts if not a.acknowledged),
                "recent": self.get_alerts(limit=10),
            },
            "feedback": self.get_feedback_summary(),
            "intent_distribution": dict(self._intent_counts),
            "recent_decisions": self.get_agent_decisions(limit=10),
        }
