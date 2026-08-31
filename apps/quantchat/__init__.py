"""
QuantChat AI - Enterprise RAG System
=====================================

Production-ready RAG implementation for QuantChat AI chatbot.
"""

from pathlib import Path
import sys

# Align Vertex auth with API: ADC-only default before any ChatVertexAI usage.
_qc_root = Path(__file__).resolve().parent.parent
for _agents_parent in (
    _qc_root / "agents",
    Path("/agents"),
):
    if _agents_parent.is_dir() and str(_agents_parent) not in sys.path:
        sys.path.insert(0, str(_agents_parent))
        break
try:
    from agents.llm.chat_factory import ensure_llm_env, llm_provider

    ensure_llm_env()
    if llm_provider() not in ("openai", "azure_openai"):
        from agents.gcp_vertex_credentials import bootstrap_vertex_adc

        bootstrap_vertex_adc(load_env=False, log_status=False)
except Exception:
    pass

from typing import Optional
from .core.query_router import QueryRouter

# Singleton instance
_query_router_instance: Optional[QueryRouter] = None

def get_query_router() -> QueryRouter:
    """Get singleton QueryRouter instance."""
    global _query_router_instance
    if _query_router_instance is None:
        _query_router_instance = QueryRouter()
    return _query_router_instance

__all__ = ["QueryRouter", "get_query_router"]
