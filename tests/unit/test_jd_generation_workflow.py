"""Unit tests for JD generation deployment workflow helpers."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "apps" / "agents"
if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))


def test_deployment_env_skips_local_storage_on_azure():
    from agents.deployment_env import should_skip_local_vector_storage

    with patch.dict(
        os.environ,
        {
            "DEPLOYMENT_TARGET": "azure-nonprod",
            "MILVUS_ENABLED": "true",
            "VECTOR_STORE": "milvus",
        },
        clear=False,
    ):
        assert should_skip_local_vector_storage() is True


def test_deployment_env_skips_local_storage_for_pgvector():
    from agents.deployment_env import should_skip_local_vector_storage

    with patch.dict(
        os.environ,
        {
            "DEPLOYMENT_TARGET": "local",
            "MILVUS_ENABLED": "false",
            "VECTOR_STORE": "pgvector",
        },
        clear=False,
    ):
        assert should_skip_local_vector_storage() is True


def test_langgraph_checkpointer_uses_memory_when_configured():
    from agents import langgraph_checkpointer as module

    module._checkpointer = None
    module._pg_pool = None

    with patch.dict(
        os.environ,
        {
            "LANGGRAPH_CHECKPOINT_BACKEND": "memory",
            "DEPLOYMENT_TARGET": "azure-nonprod",
            "DATABASE_URL": "postgresql://example",
        },
        clear=False,
    ):
        checkpointer = module.get_langgraph_checkpointer()
        assert type(checkpointer).__name__ in ("MemorySaver", "InMemorySaver")


def test_state_machine_routes_to_complete_on_azure():
    source = (
        REPO_ROOT / "apps" / "agents" / "agents" / "jd_generation" / "state_machine.py"
    ).read_text(encoding="utf-8")
    assert "_route_after_prepare" in source
    assert "should_skip_local_vector_storage" in source
    assert '"complete": "complete"' in source


def test_orchestrator_supports_preserve_hr_inputs():
    source = (
        REPO_ROOT / "apps" / "agents" / "agents" / "jd_generation" / "orchestrator.py"
    ).read_text(encoding="utf-8")
    assert "preserve_hr_inputs" in source
    assert "Skipping extra relevance LLM pass" in source


def test_api_passes_preserve_hr_inputs_to_orchestrator():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py"
    ).read_text(encoding="utf-8")
    assert "preserve_hr_inputs=True" in source
    assert "_jd_orchestrator" in source


def test_bff_proxy_has_jd_timeout():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "AbortController" in source


def test_bff_long_timeout_uses_shared_constant():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "LONG_RUNNING_PROXY_TIMEOUT_MS" in source


def test_api_health_checks_jd_test_endpoint():
    source = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-health.ts").read_text(
        encoding="utf-8"
    )
    assert "testJdGenerationReady" in source
    assert "/v1/jd-generation/test" in source


def test_jd_pipeline_import_does_not_require_worker_package():
    api_root = REPO_ROOT / "apps" / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))

    services_init = (api_root / "app" / "services" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "from app.services.candidate_service import CandidateService" not in services_init

    from app.services.jd_pipeline_service import JDPipelineService

    assert JDPipelineService.__name__ == "JDPipelineService"
