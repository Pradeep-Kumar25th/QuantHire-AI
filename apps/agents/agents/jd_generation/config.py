"""
JD Generation Configuration
===========================
Enterprise-grade configuration management for JD generation system.
No hardcoded values - everything is configurable.
"""

import logging
import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agents.gcp_vertex_credentials import vertex_credential_source_available

logger = logging.getLogger(__name__)


def _default_llm_provider() -> str:
    """Resolve provider from LLM_PROVIDER env (azure_openai on AKS)."""
    from agents.llm.chat_factory import llm_provider

    return llm_provider()


def _default_llm_model() -> str:
    """Resolve model from env / Azure deployment, never a hardcoded name."""
    from agents.llm.chat_factory import primary_llm_model

    return primary_llm_model()


def _default_llm_fallback_model() -> str:
    from agents.llm.chat_factory import fallback_llm_model

    return fallback_llm_model()


class JDGenerationConfig(BaseSettings):
    """
    Configuration for JD Generation system.
    
    All values are loaded from environment variables with sensible defaults.
    No hardcoded values - fully configurable for enterprise deployment.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="JD_GENERATION_",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )
    
    # LLM Configuration (Vertex AI Only)
    # Standard Gemini API keys are deprecated - use Vertex AI
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key (Optional/Deactivated) - loaded from GROQ_API_KEY environment variable"
    )
    bedrock_api_key: Optional[str] = Field(
        default=None,
        description="Bedrock API key (Optional) - loaded from AWS_BEARER_TOKEN_BEDROCK or BEDROCK_API_KEY environment variable"
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for Bedrock - loaded from AWS_REGION environment variable"
    )
    llm_provider: str = Field(
        default_factory=_default_llm_provider,
        description="LLM provider - loaded from LLM_PROVIDER environment variable"
    )
    llm_model: str = Field(
        default_factory=_default_llm_model,
        description="LLM model to use - loaded from LLM_MODEL / LLM_MODEL_NAME / AZURE_OPENAI_CHAT_DEPLOYMENT environment variables"
    )
    llm_fallback_model: str = Field(
        default_factory=_default_llm_fallback_model,
        description="Fallback LLM model to use if primary model fails - loaded from LLM_FALLBACK_MODEL environment variable"
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature"
    )
    llm_max_tokens: int = Field(
        default=4096,  # Claude 3.5 Sonnet supports up to 200K context, 8K output
        ge=1,
        le=65536,
        description="Maximum output tokens"
    )
    
    # LangSmith Configuration
    langsmith_api_key: Optional[str] = Field(
        default=None,
        description="LangSmith API key for observability"
    )
    langsmith_project: str = Field(
        default="quanthire-ai",
        description="LangSmith project name"
    )
    langsmith_tracing_enabled: bool = Field(
        default=True,
        description="Enable LangSmith tracing"
    )
    
    # Workflow Configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts"
    )
    retry_delay: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Retry delay in seconds"
    )
    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Workflow timeout in seconds"
    )
    
    # RAG Configuration
    rag_similar_jobs_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum similar jobs to retrieve"
    )
    rag_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for RAG retrieval"
    )
    
    # Milvus Configuration
    milvus_host: str = Field(
        default="localhost",
        description="Milvus server host"
    )
    milvus_port: int = Field(
        default=19530,
        ge=1,
        le=65535,
        description="Milvus server port"
    )
    milvus_collection_name: str = Field(
        default="quanthire_job_descriptions",
        description="Milvus collection name"
    )
    milvus_connection_timeout: int = Field(
        default=10,
        ge=1,
        description="Milvus connection timeout"
    )
    
    # Embedding Configuration
    embedding_model: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="Embedding model name"
    )
    embedding_dimension: int = Field(
        default=768,
        description="Embedding vector dimension"
    )
    
    # Agent Configuration
    agent_verbose: bool = Field(
        default=True,
        description="Enable verbose agent logging"
    )
    agent_max_iterations: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum agent iterations"
    )
    # OTPAR Autonomous Features - Each agent does Observe, Think, Plan, Act, Reflect
    # These enhance the reasoning quality within each agent's OTPAR cycle
    enable_autonomous_reasoning: bool = Field(
        default=True,
        description="Enable autonomous reasoning in OTPAR cycle (OBSERVE/THINK phases)"
    )
    enable_self_reflection: bool = Field(
        default=True,
        description="Enable self-reflection in OTPAR cycle (REFLECT phase)"
    )
    enable_adaptive_planning: bool = Field(
        default=True,
        description="Enable adaptive planning in OTPAR cycle (PLAN phase)"
    )
    enable_error_recovery: bool = Field(
        default=True,
        description="Enable error recovery (recommended to keep enabled)"
    )
    
    # Performance Configuration
    enable_caching: bool = Field(
        default=True,
        description="Enable result caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="Cache TTL in seconds"
    )
    enable_parallel_processing: bool = Field(
        default=False,
        description="Enable parallel agent processing"
    )
    
    # Security Configuration
    enable_pii_redaction: bool = Field(
        default=True,
        description="Enable PII redaction"
    )
    max_input_length: int = Field(
        default=10000,
        ge=100,
        description="Maximum input length"
    )
    
    # Monitoring Configuration
    enable_metrics: bool = Field(
        default=True,
        description="Enable performance metrics"
    )
    metrics_export_interval: int = Field(
        default=60,
        ge=10,
        description="Metrics export interval in seconds"
    )
    
    @field_validator("llm_model", mode="before")
    @classmethod
    def validate_llm_model(cls, v: Optional[str]) -> str:
        """
        Load LLM model from environment variables.
        Priority: LLM_MODEL_NAME > LLM_MODEL > provided value > default
        """
        # Check environment variables first
        env_model = os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL")
        if env_model:
            logger.info(f"✅ Using LLM model from environment: {env_model}")
            return env_model.strip()
        
        # Use provided value or default
        if v:
            return v.strip()
        
        from agents.llm.chat_factory import primary_llm_model

        return primary_llm_model()

    @field_validator("llm_fallback_model", mode="before")
    @classmethod
    def validate_llm_fallback_model(cls, v: Optional[str]) -> str:
        from agents.llm.chat_factory import fallback_llm_model

        env = os.getenv("LLM_FALLBACK_MODEL")
        if env and env.strip():
            return env.strip()
        if v:
            return str(v).strip()
        return fallback_llm_model()
    
    @field_validator("llm_provider", mode="before")
    @classmethod
    def validate_llm_provider(cls, v: Optional[str]) -> str:
        """Load LLM provider from environment."""
        from agents.llm.chat_factory import llm_provider

        env_provider = os.getenv("LLM_PROVIDER")
        if env_provider:
            return env_provider.strip().lower()
        if v:
            return v.strip().lower()
        return llm_provider()
    
    @field_validator("aws_region", mode="before")
    @classmethod
    def validate_aws_region(cls, v: Optional[str]) -> str:
        """Load AWS region from environment."""
        env_region = os.getenv("AWS_REGION")
        if env_region:
            return env_region.strip()
        if v:
            return v.strip()
        return "us-east-1"  # Default region
    
    @field_validator("bedrock_api_key", mode="before")
    @classmethod
    def validate_bedrock_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Load Bedrock API key from environment."""
        if v and v.strip():
            return v.strip()
        return os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY") or None
    
    @field_validator("groq_api_key", mode="before")
    @classmethod
    def validate_optional_groq_key(cls, v: Optional[str]) -> Optional[str]:
        """Load optional Groq API key if present."""
        if v and v.strip():
            return v.strip()
        return os.getenv("GROQ_API_KEY") or None
    
    @property
    def is_bedrock_configured(self) -> bool:
        """Check if Bedrock API is configured."""
        return bool(self.bedrock_api_key)
    
    @property
    def is_vertex_ai_configured(self) -> bool:
        """Check if Vertex AI is configured."""
        return bool(os.getenv("GCP_PROJECT_ID") and vertex_credential_source_available())

    @property
    def is_llm_configured(self) -> bool:
        """True when the active LLM provider has credentials."""
        provider = (self.llm_provider or "vertexai").strip().lower()
        if provider == "azure_openai":
            from agents.llm.chat_factory import is_azure_openai_configured

            return is_azure_openai_configured()
        if provider == "openai":
            from agents.llm.chat_factory import is_openai_configured

            return is_openai_configured()
        return self.is_vertex_ai_configured
    
    @property
    def is_langsmith_configured(self) -> bool:
        """Check if LangSmith is configured."""
        return self.langsmith_api_key is not None and self.langsmith_tracing_enabled
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration from environment/fields."""
        provider = (self.llm_provider or "vertexai").strip().lower()
        model = self.llm_model

        if provider == "azure_openai":
            from agents.llm.chat_factory import is_azure_openai_configured

            if not is_azure_openai_configured():
                raise ValueError(
                    "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT and "
                    "AZURE_OPENAI_API_KEY when LLM_PROVIDER=azure_openai."
                )
            return {
                "model": model,
                "provider": "azure_openai",
                "temperature": self.llm_temperature,
                "max_tokens": min(self.llm_max_tokens, 16384),
                "fallback_model": self.llm_fallback_model,
            }

        if provider == "openai":
            from agents.llm.chat_factory import is_openai_configured

            if not is_openai_configured():
                raise ValueError(
                    "OPENAI_API_KEY environment variable not set. "
                    "Required when LLM_PROVIDER=openai."
                )
            return {
                "model": model,
                "provider": "openai",
                "temperature": self.llm_temperature,
                "max_tokens": min(self.llm_max_tokens, 16384),
                "fallback_model": self.llm_fallback_model,
            }

        gcp_project = os.getenv("GCP_PROJECT_ID")
        if not gcp_project:
            raise ValueError(
                "GCP_PROJECT_ID environment variable not set. "
                "Vertex AI is required when LLM_PROVIDER=vertexai."
            )

        return {
            "model": model,
            "provider": "vertexai",
            "project": gcp_project,
            "location": os.getenv("GCP_LOCATION", "us-central1"),
            "temperature": self.llm_temperature,
            "max_tokens": min(self.llm_max_tokens, 8192),
            "fallback_model": self.llm_fallback_model,
        }
    
    def get_langsmith_config(self) -> dict:
        """Get LangSmith configuration dictionary."""
        return {
            "api_key": self.langsmith_api_key,
            "project": self.langsmith_project,
            "tracing_enabled": self.langsmith_tracing_enabled,
        }
    
    def get_milvus_config(self) -> dict:
        """Get Milvus configuration dictionary."""
        return {
            "host": self.milvus_host,
            "port": self.milvus_port,
            "collection_name": self.milvus_collection_name,
            "connection_timeout": self.milvus_connection_timeout,
        }
    
    def validate(self) -> None:
        """Validate configuration."""
        if self.llm_provider == "bedrock" and not self.is_bedrock_configured:
            raise ValueError(
                "Bedrock API key not configured. "
                "Set AWS_BEARER_TOKEN_BEDROCK or BEDROCK_API_KEY environment variable."
            )
        
        if not self.is_llm_configured:
            if self.llm_provider == "openai":
                raise ValueError(
                    "OpenAI not configured. Set OPENAI_API_KEY when LLM_PROVIDER=openai."
                )
            raise ValueError(
                "Vertex AI not configured. Set GCP_PROJECT_ID and ADC, "
                "or set LLM_PROVIDER=openai with OPENAI_API_KEY."
            )


# Global configuration instance
_config: Optional[JDGenerationConfig] = None


def get_config() -> JDGenerationConfig:
    """Get global configuration instance (singleton pattern)."""
    global _config
    if _config is None:
        # Try to load .env file from multiple locations
        from pathlib import Path
        
        try:
            from agents.llm.chat_factory import ensure_llm_env, llm_provider, project_env_file_candidates

            ensure_llm_env()
            if llm_provider() not in ("openai", "azure_openai"):
                from agents.gcp_vertex_credentials import bootstrap_vertex_adc

                bootstrap_vertex_adc(load_env=True, log_status=False)
            env_file = next(
                (str(p) for p in project_env_file_candidates() if p.is_file()),
                None,
            )
            if env_file:
                logger.info("JD generation using env file: %s", env_file)
        except Exception as exc:
            logger.warning("Vertex ADC bootstrap failed: %s", exc)
            env_file = None

        # Create config with explicit env_file if found
        if env_file:
            _config = JDGenerationConfig(_env_file=env_file)
        else:
            _config = JDGenerationConfig()
            logger.warning("No .env file found, using environment variables only")
        
        if _config.is_llm_configured:
            logger.info(
                "LLM configured: provider=%s model=%s",
                _config.llm_provider,
                _config.llm_model,
            )
        else:
            logger.error(
                "LLM not configured. For OpenAI set OPENAI_API_KEY; "
                "for Vertex set GCP_PROJECT_ID and ADC."
            )
        
        try:
            _config.validate()
        except ValueError as e:
            logger.warning(f"Configuration validation warning: {e}")
    
    return _config



def reset_config() -> None:
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None

