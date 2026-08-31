"""
LangSmith Tracing Utilities
============================

Centralized LangSmith integration for the QuantChat RAG pipeline.
Provides a graceful fallback when LangSmith is not installed or configured.

Usage:
    from ..utils.tracing import traceable, trace_metadata

    @traceable(run_type="chain", name="MyComponent")
    def my_function(...):
        ...
        trace_metadata({"chunks": 42, "score": 0.95})
"""

import os
import functools
from typing import Any, Dict, Optional
from ..config.logging_config import setup_logger

logger = setup_logger("tracing")

LANGSMITH_AVAILABLE = False
_traceable_fn = None

try:
    from langsmith import traceable as _ls_traceable
    from langsmith.run_helpers import get_current_run_tree

    if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true":
        LANGSMITH_AVAILABLE = True
        _traceable_fn = _ls_traceable
        logger.info("LangSmith tracing ENABLED for QuantChat RAG pipeline")
    else:
        logger.info("LangSmith installed but LANGCHAIN_TRACING_V2 is not 'true' — tracing disabled")
except ImportError:
    logger.info("LangSmith not installed — tracing disabled (pip install langsmith)")
    get_current_run_tree = None


def traceable(run_type: str = "chain", name: Optional[str] = None, **kwargs):
    """
    Drop-in @traceable decorator.
    Traces to LangSmith when available, otherwise a no-op passthrough.

    Args:
        run_type: "chain", "retriever", "llm", "tool", "embedding"
        name: Display name in LangSmith dashboard
    """
    if LANGSMITH_AVAILABLE and _traceable_fn:
        return _traceable_fn(run_type=run_type, name=name, **kwargs)

    def noop_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        return wrapper
    return noop_decorator


def trace_metadata(metadata: Dict[str, Any]):
    """
    Attach metadata to the current LangSmith run (e.g., chunk counts, scores).
    No-op when LangSmith is not active.
    """
    if not LANGSMITH_AVAILABLE or not get_current_run_tree:
        return

    try:
        run_tree = get_current_run_tree()
        if run_tree:
            if run_tree.extra is None:
                run_tree.extra = {}
            if "metadata" not in run_tree.extra:
                run_tree.extra["metadata"] = {}
            run_tree.extra["metadata"].update(metadata)
    except Exception as e:
        logger.debug(f"Failed to attach trace metadata: {e}")
