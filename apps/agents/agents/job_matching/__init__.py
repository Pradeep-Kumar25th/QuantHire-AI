"""
Job Matching Agentic AI System
==============================

Hierarchical Specialist Swarm with Multi-Agent Debate (HSS-D) for matching
candidate resumes against stored Job Descriptions.

Architecture
------------
Layer 1 — Pre-flight (sequential):
    * Resume Ingestion Agent     — normalises the candidate profile
    * JD Retrieval Agent         — hybrid RAG against Milvus to fetch JDs

Layer 2 — Parallel Specialist Swarm (asyncio.gather / LangGraph Send):
    * Skills Match Agent         — hard / technical stack overlap
    * Experience Analyst Agent   — years, seniority, role progression
    * Education & Certifications Agent
    * Domain / Industry Expertise Agent
    * Culture & Soft Skills Agent
    * Growth Trajectory Agent    — learning curve & potential
    * Red Flag & Risk Agent      — gaps, hopping, inconsistencies
    * Bias & Fairness Auditor    — non-discriminatory analysis

Layer 3 — Debate & Synthesis:
    * Synthesizer Agent          — confidence-weighted ensemble
    * Critic Agent               — challenges synthesis, surfaces blind spots
    * Arbitrator Agent           — finalises score + verdict

Layer 4 — Insights & Action:
    * HR Advisor Agent           — interview questions, decision tips
    * Explainability Agent       — evidence-quote attribution per dimension

Public surface
--------------
``JobMatchingOrchestrator`` is the entry point used by the FastAPI route.
"""

from agents.job_matching.cache import (
    Cache,
    InMemoryLRUCache,
    PIPELINE_VERSION,
    RedisCache,
    build_cache,
    match_cache_key,
)
from agents.job_matching.config import JobMatchingConfig, get_config
from agents.job_matching.enterprise_models import (
    DimensionGrounding,
    EvidenceGrounding,
    GroundednessReport,
    JDHygieneReport,
    LocationFitReport,
)
from agents.job_matching.evidence_verifier import EvidenceVerifier
from agents.job_matching.fast_path import compute_similarity
from agents.job_matching.jd_analysis import JDAnalysis, JDAnalyzer
from agents.job_matching.jd_hygiene import JDHygieneAgent
from agents.job_matching.location_fit import LocationFitAgent
from agents.job_matching.orchestrator import JobMatchingOrchestrator

__all__ = [
    "JobMatchingConfig",
    "JobMatchingOrchestrator",
    "JDAnalysis",
    "JDAnalyzer",
    "JDHygieneAgent",
    "JDHygieneReport",
    "LocationFitAgent",
    "LocationFitReport",
    "EvidenceVerifier",
    "GroundednessReport",
    "DimensionGrounding",
    "EvidenceGrounding",
    "Cache",
    "InMemoryLRUCache",
    "RedisCache",
    "build_cache",
    "match_cache_key",
    "PIPELINE_VERSION",
    "compute_similarity",
    "get_config",
]
