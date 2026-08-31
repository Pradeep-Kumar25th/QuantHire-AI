"""
RAG Monitor
===========

Tracks performance metrics, quality, and usage for observability.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
from ..config.logging_config import setup_logger
from ..config.settings import ENABLE_MONITORING, LOG_QUERY_LATENCY, LOG_RETRIEVAL_METRICS, LOG_LLM_USAGE

logger = setup_logger("rag_monitor")

class RAGMonitor:
    """
    Monitors RAG pipeline performance and quality.
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.enabled = ENABLE_MONITORING
    
    def track_query(
        self,
        query: str,
        response: str,
        latency: float,
        chunks_retrieved: int,
        chunks_used: int,
        intent: str,
        source: str
    ):
        """Track query metrics."""
        if not self.enabled:
            return
        
        metric = {
            "timestamp": datetime.now().isoformat(),
            "query": query[:100],  # Truncate for storage
            "response_length": len(response),
            "latency": latency,
            "chunks_retrieved": chunks_retrieved,
            "chunks_used": chunks_used,
            "intent": intent,
            "source": source
        }
        
        self.metrics["queries"].append(metric)
        
        if LOG_QUERY_LATENCY:
            logger.info(f"Query metrics: latency={latency:.2f}s, chunks={chunks_used}, intent={intent}")
    
    def track_retrieval(
        self,
        query: str,
        vector_count: int,
        keyword_count: int,
        fused_count: int,
        reranked_count: int
    ):
        """Track retrieval metrics."""
        if not self.enabled or not LOG_RETRIEVAL_METRICS:
            return
        
        logger.info(f"Retrieval metrics: vector={vector_count}, keyword={keyword_count}, "
                   f"fused={fused_count}, reranked={reranked_count}")
    
    def track_llm_usage(
        self,
        model: str,
        tokens_used: int,
        cost: float = 0.0
    ):
        """Track LLM usage."""
        if not self.enabled or not LOG_LLM_USAGE:
            return
        
        logger.info(f"LLM usage: model={model}, tokens={tokens_used}, cost=${cost:.4f}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        if not self.metrics["queries"]:
            return {"status": "no_data"}
        
        queries = self.metrics["queries"]
        
        return {
            "total_queries": len(queries),
            "avg_latency": sum(q["latency"] for q in queries) / len(queries),
            "avg_chunks_used": sum(q["chunks_used"] for q in queries) / len(queries),
            "intent_distribution": self._count_intents(queries),
            "source_distribution": self._count_sources(queries)
        }
    
    def _count_intents(self, queries: list) -> Dict[str, int]:
        """Count queries by intent."""
        counts = defaultdict(int)
        for q in queries:
            counts[q["intent"]] += 1
        return dict(counts)
    
    def _count_sources(self, queries: list) -> Dict[str, int]:
        """Count queries by source."""
        counts = defaultdict(int)
        for q in queries:
            counts[q["source"]] += 1
        return dict(counts)
