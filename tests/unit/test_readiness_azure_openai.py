"""Azure OpenAI readiness uses settings (not fragile agents import)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.readiness import (
    _azure_openai_is_configured,
    build_readiness_report,
    check_azure_openai,
)


@pytest.mark.asyncio
async def test_azure_openai_healthy_when_settings_have_key_and_endpoint():
    with patch("app.core.readiness.settings") as mock_settings:
        mock_settings.llm_provider = "azure_openai"
        mock_settings.azure_openai_endpoint = "https://aif-ail-npd-we-01.openai.azure.com/"
        mock_settings.azure_openai_chat_deployment = "gpt-4o"
        mock_settings.azure_openai_api_key = "test-key"

        assert _azure_openai_is_configured() is True
        report = await check_azure_openai()
        assert report["status"] == "healthy"
        assert report["api_key_set"] is True


@pytest.mark.asyncio
async def test_azure_openai_not_configured_when_key_missing():
    with patch("app.core.readiness.settings") as mock_settings:
        mock_settings.llm_provider = "azure_openai"
        mock_settings.azure_openai_endpoint = "https://aif-ail-npd-we-01.openai.azure.com/"
        mock_settings.azure_openai_chat_deployment = "gpt-4o"
        mock_settings.azure_openai_api_key = None

        with patch("app.core.readiness._azure_openai_is_configured", return_value=False):
            report = await check_azure_openai()
        assert report["status"] == "not_configured"
        assert report["api_key_set"] is False


@pytest.mark.asyncio
async def test_build_readiness_report_ready_on_azure_nonprod_when_platform_checks_pass():
    """Simulates the user's AKS pod: secrets + configmap present, DB healthy."""
    with patch("app.core.readiness.settings") as mock_settings:
        mock_settings.deployment_target = "azure-nonprod"
        mock_settings.is_azure_nonprod = True
        mock_settings.auth_mode = "basic"
        mock_settings.vector_store_type = "pgvector"
        mock_settings.use_pgvector_pipeline = True
        mock_settings.llm_provider = "azure_openai"
        mock_settings.app_version = "1.0.0"
        mock_settings.app_env = "nonprod"
        mock_settings.postgres_required = True
        mock_settings.milvus_required = False
        mock_settings.azure_document_intelligence_enabled = True
        mock_settings.storage_backend = "azure_blob"
        mock_settings.azure_openai_endpoint = "https://aif-ail-npd-we-01.openai.azure.com/"
        mock_settings.azure_openai_chat_deployment = "gpt-4o"
        mock_settings.azure_openai_api_key = "pod-secret-key"
        mock_settings.azure_openai_embedding_deployment = "text-embedding-3-large"
        mock_settings.azure_storage_container = "quanthire-uploads"
        mock_settings.azure_document_intelligence_endpoint = (
            "https://di-ail-npd-we-01.cognitiveservices.azure.com/"
        )
        mock_settings.azure_document_intelligence_model = "prebuilt-layout"
        mock_settings.azure_document_intelligence_api_key = "di-key"
        mock_settings.azure_storage_connection_string = "DefaultEndpointsProtocol=https;..."
        mock_settings.milvus_enabled = False
        mock_settings.redis_url = "redis://localhost:6379/0"

        with (
            patch(
                "app.database.check_db_health",
                new_callable=AsyncMock,
                return_value={"status": "healthy"},
            ),
            patch("app.core.readiness.check_redis", new_callable=AsyncMock, return_value={"status": "not_configured"}),
            patch("app.core.readiness.check_llm_gateway", new_callable=AsyncMock, return_value={"status": "not_configured"}),
            patch("app.core.readiness.check_azure_openai", new_callable=AsyncMock, return_value={"status": "healthy"}),
            patch("app.core.readiness.check_azure_blob", return_value={"status": "healthy"}),
            patch("app.core.readiness.check_document_intelligence", return_value={"status": "healthy"}),
        ):
            report = await build_readiness_report()

    assert report["status"] == "ready"
    assert report["checks"]["azure_openai"] == "healthy"
    assert report["blocking"] == []


def test_azure_openai_is_configured_reads_settings_not_os_getenv(monkeypatch):
    """Regression: os.getenv can differ from settings; readiness must use settings."""
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)

    with patch("app.core.readiness.settings") as mock_settings:
        mock_settings.azure_openai_endpoint = "https://aif-ail-npd-we-01.openai.azure.com/"
        mock_settings.azure_openai_api_key = "from-settings-only"

        assert _azure_openai_is_configured() is True
