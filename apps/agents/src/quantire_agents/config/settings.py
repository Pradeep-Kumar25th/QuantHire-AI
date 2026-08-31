"""
Configuration Management for QuantHire AI Agents
=================================================

Enterprise-level configuration management using Pydantic settings.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _quantire_vertex_credentials_ready() -> bool:
    """Match agents.gcp_vertex_credentials: ADC by default; SA key if explicitly allowed."""
    if not os.getenv("GCP_PROJECT_ID"):
        return False
    try:
        from agents.gcp_vertex_credentials import vertex_credential_source_available

        return vertex_credential_source_available()
    except ImportError:
        if os.getenv("GCP_ALLOW_SERVICE_ACCOUNT_KEY", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if raw:
                path = os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))
                if os.path.isfile(path):
                    return True
        custom = os.getenv("GCP_ADC_CREDENTIALS_PATH") or os.getenv("GOOGLE_ADC_CREDENTIALS")
        if custom:
            p = os.path.expandvars(os.path.expanduser(custom.strip().strip('"')))
            if p and os.path.isfile(p):
                return True
        appdata = os.environ.get("APPDATA")
        paths: list[str] = []
        if appdata:
            paths.append(
                os.path.join(appdata, "gcloud", "application_default_credentials.json")
            )
        paths.append(
            os.path.join(
                os.path.expanduser("~"),
                ".config",
                "gcloud",
                "application_default_credentials.json",
            )
        )
        return any(os.path.isfile(p) for p in paths)


class AgentSettings(BaseSettings):
    """Agent configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # LLM Configuration (Vertex AI Only)
    # Standard Gemini API keys are deprecated - use Vertex AI
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key (Optional/Deactivated)"
    )
    bedrock_api_key: Optional[str] = Field(
        default=None,
        description="Bedrock API key (Optional) - loaded from AWS_BEARER_TOKEN_BEDROCK or BEDROCK_API_KEY"
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for Bedrock"
    )
    llm_model_name: str = Field(
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        description="LLM model to use"
    )
    llm_provider: str = Field(
        default="bedrock",
        description="LLM provider (bedrock, google, groq, etc.)"
    )
    llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response consistency"
    )
    llm_max_output_tokens: int = Field(
        default=4096,
        ge=1,
        le=8192,
        description="Maximum output tokens for LLM"
    )
    
    # Agent Configuration
    agent_max_iterations: int = Field(
        default=3,  # Reduced from 5 to 3 for faster processing
        ge=1,
        le=10,
        description="Maximum agent iterations"
    )
    agent_verbose: bool = Field(
        default=True,
        description="Enable verbose agent logging"
    )
    agent_return_intermediate_steps: bool = Field(
        default=True,
        description="Return intermediate steps for debugging"
    )
    
    # Embedding Configuration
    embedding_model_name: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="Sentence transformer model for embeddings"
    )
    embedding_dimension: int = Field(
        default=768,
        description="Embedding vector dimension"
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
        default="quanthire_resumes",
        description="Milvus collection name for resumes"
    )
    milvus_connection_timeout: int = Field(
        default=10,
        ge=1,
        description="Milvus connection timeout in seconds"
    )
    milvus_search_limit: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum similar candidates to retrieve"
    )
    
    # Performance Configuration
    resume_text_truncate_length: int = Field(
        default=2000,  # Reduced from 3000 to 2000 for faster processing
        ge=1000,
        description="Maximum resume text length for agent processing"
    )
    enable_rag_enhancement: bool = Field(
        default=True,
        description="Enable RAG enhancement for extracted data"
    )
    enable_fallback_parsing: bool = Field(
        default=True,
        description="Enable fallback to regex parsing if agent fails"
    )
    
    # Security Configuration
    enable_pii_redaction: bool = Field(
        default=True,
        description="Enable PII redaction before LLM calls"
    )
    security_status: str = Field(
        default="HYBRID_SECURE",
        description="Security status indicator"
    )
    
    @field_validator("bedrock_api_key", mode="before")
    @classmethod
    def validate_bedrock_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Load Bedrock API key from environment."""
        if v and v.strip():
            return v.strip()
        return os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY") or None
    
    @field_validator("aws_region", mode="before")
    @classmethod
    def validate_aws_region(cls, v: Optional[str]) -> str:
        """Load AWS region from environment."""
        env_region = os.getenv("AWS_REGION")
        if env_region:
            return env_region.strip()
        if v:
            return v.strip()
        return "us-east-1"
    
    @field_validator("llm_provider", mode="before")
    @classmethod
    def validate_llm_provider(cls, v: Optional[str]) -> str:
        """Load LLM provider from environment."""
        env_provider = os.getenv("LLM_PROVIDER")
        if env_provider:
            return env_provider.strip().lower()
        if v:
            return v.strip().lower()
        return "vertexai"  # Default to Vertex AI
    
    @field_validator("llm_model_name", mode="before")
    @classmethod
    def validate_llm_model_name(cls, v: Optional[str]) -> str:
        """Load LLM model from environment."""
        env_model = os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL")
        if env_model:
            return env_model.strip()
        if v:
            return v.strip()
        prov = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        return "gpt-4o" if prov == "openai" else "gemini-2.5-pro"
    
    @field_validator("groq_api_key", mode="before")
    @classmethod
    def validate_groq_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Load Groq API key if present (optional/deactivated)."""
        if v and v.strip():
            return v.strip()
        return os.getenv("GROQ_API_KEY") or None

    @property
    def is_vertex_ai_configured(self) -> bool:
        """Vertex AI: GCP project + ADC file, or service-account path if allowed."""
        return _quantire_vertex_credentials_ready()
    
    @property
    def is_bedrock_configured(self) -> bool:
        """Check if Bedrock API is configured."""
        return bool(self.bedrock_api_key)
    
    @property
    def is_api_configured(self) -> bool:
        """Check if API is configured for the current provider."""
        if self.llm_provider == "bedrock":
            return bool(self.bedrock_api_key)
        if self.llm_provider == "openai":
            return bool(os.getenv("OPENAI_API_KEY", "").strip())
        if self.llm_provider == "azure_openai":
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
            if endpoint and api_key:
                return True
            try:
                from agents.llm.chat_factory import is_azure_openai_configured

                return is_azure_openai_configured()
            except ImportError:
                return bool(endpoint)
        return self.is_vertex_ai_configured


# Global settings instance
_settings: Optional[AgentSettings] = None


def get_settings() -> AgentSettings:
    """Get global agent settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = AgentSettings()
    return _settings


def reset_settings() -> None:
    """Reset global settings (useful for testing)."""
    global _settings
    _settings = None















