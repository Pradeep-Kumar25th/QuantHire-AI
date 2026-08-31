"""Azure Non-Prod deployment invariants (BFF, UI copy, env sync)."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BFF_ROUTE = REPO / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
MATCH_LAUNCHER = REPO / "apps" / "web" / "src" / "components" / "matching" / "match-launcher.tsx"
QUANTCHAT = REPO / "apps" / "web" / "src" / "components" / "QuantChat.tsx"
AZURE_ENV = REPO / "apps" / "api" / "app" / "core" / "azure_env.py"
NEXT_CONFIG = REPO / "apps" / "web" / "next.config.js"
MANIFEST = REPO / "infra" / "kubernetes" / "nonprod" / "quanthire.yaml"


def test_bff_does_not_forward_content_encoding():
    content = BFF_ROUTE.read_text(encoding="utf-8")
    assert '"content-encoding"' not in content
    assert '"transfer-encoding"' not in content
    assert "text/event-stream" in content
    assert "backendResponse.body" in content


def test_match_launcher_uses_azure_pgvector_hint():
    content = MATCH_LAUNCHER.read_text(encoding="utf-8")
    assert "AZURE_MATCHING_DATA_HINT" in content
    assert "Make sure Milvus is running" not in content


def test_quantchat_settings_panel_azure_labels():
    content = QUANTCHAT.read_text(encoding="utf-8")
    assert "AZURE_VECTOR_STORE_LABEL" in content
    assert "Milvus Vector DB" not in content
    assert "Gemini AI Powered" not in content


def test_azure_env_syncs_milvus_and_database_url():
    content = AZURE_ENV.read_text(encoding="utf-8")
    assert '"MILVUS_ENABLED"' in content
    assert '"DATABASE_URL"' in content
    assert "settings.database_url" in content


def test_next_config_disables_compress_for_bff_safety():
    content = NEXT_CONFIG.read_text(encoding="utf-8")
    assert "compress: false" in content


def test_manifest_azure_vector_store_flags():
    content = MANIFEST.read_text(encoding="utf-8")
    assert 'VECTOR_STORE: "pgvector"' in content
    assert 'MILVUS_ENABLED: "false"' in content
    assert 'DEPLOYMENT_TARGET: "azure-nonprod"' in content
    assert "BFF_BACKEND_URL:" in content
