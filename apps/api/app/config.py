"""Configuration management for QuantHireAI API."""

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "QuantHireAI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # Deployment target: local | azure-nonprod
    deployment_target: str = Field(default="local")

    # Auth v1 (Entra deferred per platform) — "none" locally, "basic" on azure-nonprod
    auth_mode: str = Field(default="none")  # none | basic | entra

    # Azure Non-Prod platform (real discovered values — secrets via AKS Secrets)
    azure_subscription_id: str = "6c1005fd-2b1b-40be-a39b-e10615db8ee6"
    azure_aks_cluster: str = "aks-ail-npd-we-01"
    azure_aks_resource_group: str = "rg-ail-wkload-npd-we-01"
    k8s_namespace: str = "quanthire-nonprod"
    bff_backend_url: str = "http://quanthire-backend.quanthire-nonprod.svc.cluster.local:8000"
    acr_login_server: str = "crailnpdwe01.azurecr.io"

    postgres_host: str = "psql-ail-npd-we-01.postgres.database.azure.com"
    postgres_db: str = "quanthire_ai"
    postgres_port: int = 5432
    postgres_sslmode: str = "require"

    azure_openai_endpoint: str = "https://aif-ail-npd-we-01.openai.azure.com/"
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_chat_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"
    azure_openai_api_key: Optional[str] = Field(default=None)

    azure_storage_account_name: str = "dlsailnpdqc01"
    azure_storage_container: str = "quanthire-uploads"
    azure_storage_container_processed: str = "quanthire-processed"
    azure_storage_blob_endpoint: str = "https://dlsailnpdqc01.blob.core.windows.net/"
    azure_storage_connection_string: Optional[str] = Field(default=None)

    azure_document_intelligence_endpoint: str = (
        "https://di-ail-npd-we-01.cognitiveservices.azure.com/"
    )
    azure_document_intelligence_model: str = "prebuilt-layout"
    azure_document_intelligence_enabled: bool = True
    azure_document_intelligence_api_key: Optional[str] = Field(default=None)

    # AKS secret names (values created via kubectl — not in Git)
    k8s_secret_db: str = "quanthire-db-secret"
    k8s_secret_blob: str = "quanthire-blob-secret"
    k8s_secret_aoai: str = "quanthire-aoai-secret"
    k8s_secret_di: str = "quanthire-di-secret"
    k8s_secret_auth: str = "quanthire-auth-secret"

    # Database
    database_url: Optional[str] = Field(
        default=None
    )
    database_sync_url: Optional[str] = Field(
        default=None
    )
    db_pool_size: int = 20
    db_max_overflow: int = 0
    db_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Vector Store
    vector_store_type: str = "pgvector"  # pgvector, milvus, pinecone, qdrant
    milvus_host: str = Field(default="localhost")
    milvus_port: int = Field(default=19530)
    milvus_auto_load: bool = Field(default=True)
    milvus_enabled: bool = Field(default=True)
    milvus_load_timeout: int = Field(default=180)
    pinecone_api_key: Optional[str] = None
    pinecone_environment: Optional[str] = None
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None

    # LLM Providers (Vertex AI is primary)
    groq_api_key: str = Field(default="")
    groq_model: str = "llama-3.3-70b-versatile"
    # Gemini Developer API key deprecated — use Vertex AI (GCP_PROJECT_ID + ADC by default)
    gcp_project_id: Optional[str] = Field(default=None)
    gcp_location: str = Field(default="us-central1")
    gemini_model: str = "gemini-2.5-pro"
    openai_api_key: str = Field(default="")
    openai_model: str = "gpt-4o"
    # ✅ STANDARDIZED: Using bge-base-en-v1.5 (768 dimensions) across entire project
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dimension: int = 768
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = "claude-sonnet-4-20250514"
    llm_provider: str = Field(default="openai")  # openai, vertexai, groq, anthropic, bedrock
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_fallback_enabled: bool = True
    llm_daily_budget_usd: float = 100.0

    # Amazon Bedrock Configuration
    bedrock_jd_generation_model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_jd_generation_fallback: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_jd_generation_budget: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_resume_parsing_model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_resume_parsing_fallback: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_resume_parsing_budget: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_chatbot_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_chatbot_complex: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"

    # Microsoft Graph API (calendar/email integrations)
    microsoft_client_id: Optional[str] = None
    microsoft_client_secret: Optional[str] = None
    microsoft_tenant_id: Optional[str] = None

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@quanthire.ai"

    # OAuth/SSO — Entra ID (AIL-QUANTHIRE-NPD); secret via AKS only
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    azure_ad_client_id: Optional[str] = None
    azure_ad_client_secret: Optional[str] = None
    azure_ad_tenant_id: Optional[str] = None

    # Object Storage
    storage_type: str = "local"  # local, s3, azure_blob
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    s3_bucket: Optional[str] = None

    # Security
    jwt_secret_key: str = Field(default="your-jwt-secret-key-change-this")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8000",
            "http://0.0.0.0:3000",
            "http://0.0.0.0:8000",
        ]
    )
    rate_limit_per_minute: int = 60

    # Monitoring
    sentry_dsn: Optional[str] = None
    log_level: str = "INFO"
    structured_logging: bool = True
    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    # Feature Flags
    feature_video_interviews: bool = True
    feature_assessments: bool = True
    feature_proctoring: bool = True
    feature_arabic_support: bool = True

    # Performance
    max_workers: int = 4
    worker_timeout: int = 300
    request_timeout: int = 30

    @field_validator("auth_mode", mode="before")
    @classmethod
    def auth_mode_from_deployment(cls, v: Any) -> str:
        deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
        if deployment == "azure-nonprod":
            raw = os.getenv("AUTH_MODE")
            if raw and str(raw).strip():
                return str(raw).strip().lower()
            return "basic"
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return "none"

    @field_validator("deployment_target", mode="before")
    @classmethod
    def normalize_deployment_target(cls, v: Any) -> str:
        raw = os.getenv("DEPLOYMENT_TARGET")
        if raw and str(raw).strip():
            return str(raw).strip().lower()
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return "local"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def llm_provider_from_env(cls, v: Any) -> str:
        deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
        if deployment == "azure-nonprod":
            raw = os.getenv("LLM_PROVIDER")
            if raw and str(raw).strip():
                return str(raw).strip().lower()
            return "azure_openai"
        raw = os.getenv("LLM_PROVIDER")
        if raw and str(raw).strip():
            return str(raw).strip().lower()
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return "openai"

    @field_validator("vector_store_type", mode="before")
    @classmethod
    def vector_store_from_env(cls, v: Any) -> str:
        deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
        if deployment == "azure-nonprod":
            raw = os.getenv("VECTOR_STORE") or os.getenv("VECTOR_STORE_TYPE")
            if raw and str(raw).strip():
                return str(raw).strip().lower()
            return "pgvector"
        raw = os.getenv("VECTOR_STORE") or os.getenv("VECTOR_STORE_TYPE")
        if raw and str(raw).strip():
            return str(raw).strip().lower()
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return "pgvector"

    @field_validator("milvus_auto_load", mode="before")
    @classmethod
    def milvus_auto_load_for_azure(cls, v: Any) -> Any:
        if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
            return False
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return v

    @field_validator("milvus_enabled", mode="before")
    @classmethod
    def milvus_enabled_for_azure(cls, v: Any) -> Any:
        if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
            return os.getenv("MILVUS_ENABLED", "false").strip().lower() == "true"
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return v

    @field_validator("storage_type", mode="before")
    @classmethod
    def storage_type_for_azure(cls, v: Any) -> str:
        if os.getenv("DEPLOYMENT_TARGET", "").strip().lower() == "azure-nonprod":
            return "azure_blob"
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return "local"

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def openai_key_from_env(cls, v: Any) -> str:
        raw = os.getenv("OPENAI_API_KEY")
        if raw and str(raw).strip():
            return str(raw).strip()
        return str(v or "")

    @field_validator("azure_document_intelligence_api_key", mode="before")
    @classmethod
    def di_key_from_env(cls, v: Any) -> Optional[str]:
        for key in ("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", "AZURE_DOCUMENT_INTELLIGENCE_KEY"):
            raw = os.getenv(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("azure_openai_api_key", mode="before")
    @classmethod
    def aoai_key_from_env(cls, v: Any) -> Optional[str]:
        raw = os.getenv("AZURE_OPENAI_API_KEY")
        if raw and str(raw).strip():
            return str(raw).strip()
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("azure_storage_connection_string", mode="before")
    @classmethod
    def blob_connection_from_env(cls, v: Any) -> Optional[str]:
        raw = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if raw and str(raw).strip():
            return str(raw).strip()
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("openai_model", "gemini_model", mode="before")
    @classmethod
    def llm_model_from_env(cls, v: Any) -> str:
        """Keep API settings aligned with repo-standard LLM_MODEL / LLM_MODEL_NAME."""
        for key in ("LLM_MODEL_NAME", "LLM_MODEL", "OPENAI_MODEL", "GEMINI_MODEL"):
            raw = os.getenv(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        if isinstance(v, str) and v.strip():
            return v.strip()
        return "gpt-4o" if os.getenv("LLM_PROVIDER", "openai").strip().lower() == "openai" else "gemini-2.5-pro"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env in ("development", "dev", "local")

    @property
    def is_hardened(self) -> bool:
        """Non-local environments that must enforce security defaults."""
        return self.app_env not in ("development", "dev", "local", "test", "testing")

    @property
    def trust_proxy_headers(self) -> bool:
        raw = os.getenv("TRUST_PROXY_HEADERS", "false").strip().lower()
        return raw in ("1", "true", "yes")

    @property
    def is_azure_nonprod(self) -> bool:
        return self.deployment_target == "azure-nonprod"

    @property
    def entra_sso_enabled(self) -> bool:
        return bool(self.azure_ad_client_id and self.azure_ad_tenant_id)

    @field_validator("azure_ad_client_id", mode="before")
    @classmethod
    def entra_client_id_from_env(cls, v: Any) -> Optional[str]:
        for key in (
            "ENTRA_CLIENT_ID",
            "AZURE_AD_CLIENT_ID",
            "MICROSOFT_CLIENT_ID",
        ):
            raw = os.getenv(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        if isinstance(v, str) and v.strip():
            return v.strip()
        deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
        if deployment == "azure-nonprod":
            return "221c7e05-6581-4226-9a08-96a4011dd5ce"
        return None

    @field_validator("azure_ad_tenant_id", mode="before")
    @classmethod
    def entra_tenant_id_from_env(cls, v: Any) -> Optional[str]:
        for key in (
            "ENTRA_TENANT_ID",
            "AZURE_AD_TENANT_ID",
            "MICROSOFT_TENANT_ID",
        ):
            raw = os.getenv(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        if isinstance(v, str) and v.strip():
            return v.strip()
        deployment = os.getenv("DEPLOYMENT_TARGET", "").strip().lower()
        if deployment == "azure-nonprod":
            return "68bae048-c310-4ec2-934f-cbc2588f30fe"
        return None

    @field_validator("azure_ad_client_secret", mode="before")
    @classmethod
    def entra_client_secret_from_env(cls, v: Any) -> Optional[str]:
        for key in (
            "ENTRA_CLIENT_SECRET",
            "AZURE_AD_CLIENT_SECRET",
            "MICROSOFT_CLIENT_SECRET",
        ):
            raw = os.getenv(key)
            if raw and str(raw).strip():
                return str(raw).strip()
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    @property
    def postgres_required(self) -> bool:
        return self.is_azure_nonprod or bool(self.database_url)

    @property
    def milvus_required(self) -> bool:
        return self.milvus_enabled and self.vector_store_type == "milvus"

    @property
    def use_pgvector_pipeline(self) -> bool:
        """Azure, production, and explicit pgvector configs use Postgres RAG storage."""
        if self.is_azure_nonprod:
            return True
        return self.vector_store_type == "pgvector"

    @property
    def storage_backend(self) -> str:
        if self.is_azure_nonprod:
            return "azure_blob"
        return self.storage_type

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration."""
        if self.llm_provider == "groq":
            return {
                "provider": "groq",
                "api_key": self.groq_api_key,
                "model": self.groq_model,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
            }
        elif self.llm_provider in ("google", "vertexai"):
            # Vertex AI only - no standard Gemini API key
            import os
            return {
                "provider": "vertexai",
                "project": os.getenv("GCP_PROJECT_ID") or self.gcp_project_id,
                "location": os.getenv("GCP_LOCATION") or self.gcp_location,
                "model": self.gemini_model,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
            }
        elif self.llm_provider == "openai":
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
            }
        elif self.llm_provider == "azure_openai":
            return {
                "provider": "azure_openai",
                "endpoint": self.azure_openai_endpoint,
                "api_version": self.azure_openai_api_version,
                "api_key": self.azure_openai_api_key,
                "chat_deployment": self.azure_openai_chat_deployment,
                "embedding_deployment": self.azure_openai_embedding_deployment,
                "model": self.azure_openai_chat_deployment,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
            }
        elif self.llm_provider == "anthropic":
            return {
                "provider": "anthropic",
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
            }
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

