"""Unit tests for azure_env sync."""

from app.core.azure_env import sync_azure_env_from_settings


class _SettingsStub:
    deployment_target = "azure-nonprod"
    llm_provider = "azure_openai"
    azure_openai_endpoint = "https://example.openai.azure.com/"
    azure_openai_api_version = "2024-08-01-preview"
    azure_openai_chat_deployment = "gpt-4o"
    azure_openai_embedding_deployment = "text-embedding-3-large"
    azure_openai_api_key = "test-key"
    azure_storage_connection_string = "UseDevelopmentStorage=true"
    azure_storage_account_name = "acct"
    azure_storage_container = "uploads"
    azure_storage_container_processed = "processed"
    azure_storage_blob_endpoint = "https://acct.blob.core.windows.net/"
    azure_document_intelligence_endpoint = "https://di.example.com/"
    azure_document_intelligence_model = "prebuilt-layout"
    azure_document_intelligence_api_key = "di-key"
    storage_backend = "azure_blob"
    vector_store_type = "pgvector"
    milvus_enabled = False
    milvus_auto_load = False
    database_url = "postgresql+asyncpg://u:p@host/db"
    is_azure_nonprod = True

    @property
    def azure_document_intelligence_enabled(self) -> bool:
        return True


def test_sync_azure_env_sets_milvus_disabled_and_database_url(monkeypatch):
    monkeypatch.delenv("MILVUS_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sync_azure_env_from_settings(_SettingsStub())
    assert __import__("os").environ.get("MILVUS_ENABLED") == "false"
    assert __import__("os").environ.get("VECTOR_STORE") == "pgvector"
    assert __import__("os").environ.get("DATABASE_URL") == "postgresql+asyncpg://u:p@host/db"
