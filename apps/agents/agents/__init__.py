"""QuantHireAI Agents Package."""

# Only import modules that actually exist to avoid import errors
# JD Generation is the main active agent system
try:
    from agents.jd_generation import (
        JDGenerationOrchestrator,
        JDGenerationConfig,
        get_config,
    )
    JD_GENERATION_AVAILABLE = True
except ImportError:
    JD_GENERATION_AVAILABLE = False

# Optional imports for other agents (may not exist)
try:
    from agents.parsing.agent import ParsingAgent
except ImportError:
    ParsingAgent = None

try:
    from agents.spec.agent import SpecAgent
except ImportError:
    SpecAgent = None

try:
    from agents.matching.agent import MatchingAgent
except ImportError:
    MatchingAgent = None

try:
    from agents.decision.agent import DecisionAgent
except ImportError:
    DecisionAgent = None

__all__ = [
    "JDGenerationOrchestrator",
    "JDGenerationConfig",
    "get_config",
    "ParsingAgent",
    "SpecAgent",
    "MatchingAgent",
    "DecisionAgent",
]

