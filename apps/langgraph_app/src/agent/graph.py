"""LangGraph Studio entrypoint.

LangGraph Studio expects this module to export a `graph` object.
We point it at the repo's existing JD-generation workflow.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict


def _build_fallback_template_graph():
    """Simple 1-node graph so Studio still starts if JD wiring fails."""

    class Context(TypedDict):
        """Context parameters for the agent."""

        my_configurable_param: str

    @dataclass
    class State:
        """Input state for the agent."""

        changeme: str = "example"

    async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
        """Process input and returns output."""
        return {
            "changeme": "output from call_model. "
            f"Configured with {(runtime.context or {}).get('my_configurable_param')}"
        }

    return (
        StateGraph(State, context_schema=Context)
        .add_node(call_model)
        .add_edge("__start__", "call_model")
        .compile(name="LangGraph Studio Fallback")
    )


# Ensure the repo's `agents` package is importable when running from `apps/langgraph_app`.
APPS_DIR = Path(__file__).resolve().parents[3]  # .../apps
PROJECT_ROOT = APPS_DIR.parent  # .../
AGENTS_PKG_PARENT = APPS_DIR / "agents"  # .../apps/agents (contains the `agents/` package)
sys.path.append(str(AGENTS_PKG_PARENT))

# Load project root env so `os.getenv("GCP_PROJECT_ID")` etc. work
# (JD workflow validation uses `os.getenv`, not pydantic settings).
load_dotenv(str(PROJECT_ROOT / ".env"), override=True)
try:
    _agents_parent = APPS_DIR / "agents"
    if _agents_parent.is_dir() and str(_agents_parent) not in sys.path:
        sys.path.insert(0, str(_agents_parent))
    from agents.llm.chat_factory import ensure_llm_env, llm_provider

    ensure_llm_env()
    if llm_provider() != "openai":
        from agents.gcp_vertex_credentials import bootstrap_vertex_adc

        bootstrap_vertex_adc(load_env=False, log_status=True)
except Exception as _adc_exc:
    print(f"[langgraph_app] LLM env bootstrap skipped: {_adc_exc}")


# Primary: your existing JD-generation workflow.
try:
    from agents.jd_generation.state_machine import JDGenerationWorkflow

    try:
        # Full init (enables running nodes in Studio)
        _workflow = JDGenerationWorkflow()
        graph = _workflow.compiled_graph
    except Exception:
        # If heavy deps/env (Vertex AI, SentenceTransformer download, Milvus, etc.)
        # prevent full initialization, still compile the graph structure so Studio
        # can show nodes and edges.
        _workflow = JDGenerationWorkflow.__new__(JDGenerationWorkflow)
        graph = _workflow._build_graph().compile(name="JD Generation (structure only)")
except Exception as e:  # pragma: no cover (environment-dependent)
    # If optional heavy deps (vertexai/crewai/milvus) or env vars aren't available,
    # still allow Studio to start using a minimal template graph.
    print(f"[langgraph_app] Failed to load JDGenerationWorkflow: {e}")
    graph = _build_fallback_template_graph()
