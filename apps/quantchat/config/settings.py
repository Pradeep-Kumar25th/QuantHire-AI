"""
QuantChat AI Configuration Settings
====================================

Production-ready configuration for QuantChat RAG system.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

# Load .env file from project root
from dotenv import load_dotenv
_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env", override=False)

# Milvus Configuration
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
RESUME_COLLECTION = "quanthire_resumes"
JD_COLLECTION = "quanthire_job_descriptions"
UNIFIED_COLLECTION = "quanthire_documents"  # Optional unified collection

# Embedding Configuration
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768
MAX_FULL_CONTENT_LENGTH = 65535  # Milvus limit for VARCHAR

# Milvus Search Parameters
# Note: ef=128 matches milvus_schema.py for optimal recall
# Higher ef = better recall but slower search
SEARCH_PARAMS = {
    "metric_type": "COSINE",
    "params": {"ef": 128}  # HNSW search parameter (matches schema for high recall)
}

# Retrieval Limits (Maximized for comprehensive coverage)
# Gemini 2.5 has 1M token context - use 50% for safety margin
MAX_CHUNKS_PER_RETRIEVER = 200  # Chunks retrieved per retriever (increased from 100)
MAX_CHUNKS_AFTER_RRF = 100  # Chunks after RRF fusion (increased from 60)
MAX_CHUNKS_RERRANK = 75  # Chunks sent to reranker (increased from 50)
MAX_CONTEXT_CHUNKS = 100  # Chunks included in context (increased from 50)
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "500000"))  # Context token limit (50% of 1M)

# RRF Constants
RRF_K = 100  # RRF parameter (higher = more weight on top results)

# Chunk Sizes (Optimized for Milvus storage and semantic coherence)
# NOTE: Milvus chunk_text max_length is 5000 - keeping 10% safety margin
# Context prefixes like "[John Doe's Skills]" add ~30-50 chars
RESUME_CHUNK_SIZE = 4500  # Characters per resume chunk (10% margin - increased to reduce truncation)
JD_CHUNK_SIZE = 4500  # Characters per JD chunk (10% margin)

# Output Token Limits (Increased for full document display)
MAX_OUTPUT_TOKENS_DEFAULT = 8192  # Default for RAG queries
MAX_OUTPUT_TOKENS_FULL_DOC = 16384  # For full document retrieval (no truncation)

# Query Expansion
ENABLE_QUERY_EXPANSION = True
MAX_QUERY_VARIATIONS = 3  # Number of query variations to generate
ENABLE_MULTI_QUERY = True  # Generate multiple query perspectives

# Reranking
ENABLE_RERANKING = True
RERANK_STAGE1_LIMIT = 75  # Cross-encoder rerank limit (increased from 50)
RERANK_STAGE2_LIMIT = 30  # LLM-based rerank limit (increased from 20)
ENABLE_LLM_RERANKING = False  # LLM-based reranking (slower but more accurate)

# Context Building
ENABLE_CONTEXT_COMPRESSION = False  # Disabled - compression causes data loss
CONTEXT_COMPRESSION_THRESHOLD = 50000  # Increased threshold (only if compression is enabled)
ENABLE_SMART_SELECTION = True  # Relevance-based chunk selection
DISABLE_CHUNK_TRUNCATION_FOR_FULL_DOC = True  # Never truncate when showing full document

# Conversation Memory (Increased for better multi-turn conversations)
ENABLE_CONVERSATION_MEMORY = True
MAX_CONVERSATION_HISTORY = 25  # Number of previous turns to remember (increased from 10)
MAX_TRACKED_ENTITIES = 30  # Maximum entities to track per session (increased from 10)

# LLM Configuration (OpenAI, Azure OpenAI, or Vertex AI)
_llm_prov = os.getenv("LLM_PROVIDER", "openai").strip().lower()
if _llm_prov == "azure_openai":
    _default_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
elif _llm_prov == "openai":
    _default_model = "gpt-4o"
else:
    _default_model = "gemini-2.5-pro"
LLM_PROVIDER = _llm_prov
LLM_MODEL = os.getenv("LLM_MODEL", os.getenv("LLM_MODEL_NAME", _default_model))
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", LLM_MODEL)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# API Rate Limiting
API_MAX_REQUESTS_PER_MINUTE = int(os.getenv("API_MAX_REQUESTS_PER_MINUTE", "50"))
API_MIN_INTERVAL_SECONDS = float(os.getenv("API_MIN_INTERVAL_SECONDS", "0.2"))

# Error Handling
ENABLE_FALLBACKS = True
FALLBACK_TO_CACHE = True
FALLBACK_TO_CHUNKS = True  # Return chunks directly if LLM fails

# Monitoring
ENABLE_MONITORING = True
LOG_QUERY_LATENCY = True
LOG_RETRIEVAL_METRICS = True
LOG_LLM_USAGE = True

# Caching
ENABLE_EMBEDDING_CACHE = True
ENABLE_QUERY_CACHE = True
CACHE_TTL_SECONDS = 3600  # 1 hour

# Agent Observability
ENABLE_OBSERVABILITY = os.getenv("ENABLE_OBSERVABILITY", "true").lower() in ("true", "1", "yes")
OBSERVABILITY_MAX_TRACES = int(os.getenv("OBSERVABILITY_MAX_TRACES", "10000"))
OBSERVABILITY_MAX_ALERTS = int(os.getenv("OBSERVABILITY_MAX_ALERTS", "1000"))
OBSERVABILITY_ALERT_COOLDOWN_SECONDS = int(os.getenv("OBSERVABILITY_ALERT_COOLDOWN_SECONDS", "60"))
OBSERVABILITY_LATENCY_WARNING_MS = int(os.getenv("OBSERVABILITY_LATENCY_WARNING_MS", "10000"))
OBSERVABILITY_LATENCY_CRITICAL_MS = int(os.getenv("OBSERVABILITY_LATENCY_CRITICAL_MS", "30000"))
OBSERVABILITY_QUALITY_WARNING = float(os.getenv("OBSERVABILITY_QUALITY_WARNING", "0.5"))
OBSERVABILITY_CONFIDENCE_WARNING = float(os.getenv("OBSERVABILITY_CONFIDENCE_WARNING", "0.4"))
OBSERVABILITY_ERROR_RATE_WARNING = float(os.getenv("OBSERVABILITY_ERROR_RATE_WARNING", "0.1"))
OBSERVABILITY_HOURLY_COST_WARNING_USD = float(os.getenv("OBSERVABILITY_HOURLY_COST_WARNING_USD", "5.0"))

# Enterprise Observability
OBSERVABILITY_PII_REDACTION = os.getenv("OBSERVABILITY_PII_REDACTION", "true").lower() in ("true", "1", "yes")
OBSERVABILITY_ALERT_WEBHOOK_URL = os.getenv("OBSERVABILITY_ALERT_WEBHOOK_URL", "")
OBSERVABILITY_TRACE_LOG_CORRELATION = os.getenv("OBSERVABILITY_TRACE_LOG_CORRELATION", "true").lower() in ("true", "1", "yes")
