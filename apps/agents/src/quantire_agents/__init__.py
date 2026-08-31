"""
QuantHire AI Agents - Enterprise-Grade Autonomous AI Resume Parsing Agent
=========================================================================

This package provides enterprise-level AI agents for resume parsing with:
- Autonomous decision-making using LangChain AgentExecutor
- RAG (Retrieval-Augmented Generation) integration
- Hybrid architecture security
- Comprehensive error handling and logging
- Type-safe interfaces
- Performance optimizations
"""

__version__ = "1.0.0"
__author__ = "QuantHire AI Team"

from quantire_agents.resume_parser.agent import ResumeParsingAgent
from quantire_agents.resume_parser.models import ParsedResumeData, ResumeParsingResult
from quantire_agents.resume_parser.exceptions import (
    ResumeParsingError,
    AgentInitializationError,
    MilvusConnectionError,
    LLMServiceError,
)

__all__ = [
    "ResumeParsingAgent",
    "ParsedResumeData",
    "ResumeParsingResult",
    "ResumeParsingError",
    "AgentInitializationError",
    "MilvusConnectionError",
    "LLMServiceError",
]















