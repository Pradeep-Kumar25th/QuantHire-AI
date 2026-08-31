"""Validation tests for UAT deployment fixes."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_intent_classifier_source_has_no_invalid_fstring():
    source = (
        REPO_ROOT / "apps" / "quantchat" / "core" / "intent_classifier.py"
    ).read_text(encoding="utf-8")
    assert "{f'" not in source
    assert "context_block" in source


def test_login_redirect_helpers_in_auth_storage():
    source = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "auth-storage.ts").read_text(
        encoding="utf-8"
    )
    assert "resolvePostLoginPath" in source
    assert "syncAuthCookieFromToken" in source
    assert 'startsWith("//")' in source


def test_login_form_redirects_when_authenticated():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "app" / "login" / "login-form.tsx"
    ).read_text(encoding="utf-8")
    assert "router.replace(resolvePostLoginPath(nextPath))" in source
    assert "Already signed in" not in source


def test_database_session_preserves_http_exceptions():
    source = (REPO_ROOT / "apps" / "api" / "app" / "database.py").read_text(
        encoding="utf-8"
    )
    assert "isinstance(e, HTTPException)" in source
    assert "isinstance(e, QuantHireException)" in source


def test_shared_query_router_lifecycle_module():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "core" / "query_router_lifecycle.py"
    ).read_text(encoding="utf-8")
    assert "def ensure_query_router" in source
    assert "QUERY_ROUTER_INIT_ERROR" in source
    assert not (
        REPO_ROOT / "apps" / "api" / "app" / "services" / "query_router_lifecycle.py"
    ).exists()


def test_quantchat_and_resume_use_shared_query_router_lifecycle():
    for rel in (
        "apps/api/app/api/v1/quantchat.py",
        "apps/api/app/api/v1/resume_parsing.py",
    ):
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "ensure_query_router" in source
        assert "app.core.query_router_lifecycle" in source


def test_langgraph_checkpointer_falls_back_to_memory():
    source = (
        REPO_ROOT / "apps" / "agents" / "agents" / "langgraph_checkpointer.py"
    ).read_text(encoding="utf-8")
    assert "_try_postgres_checkpointer" in source
    assert "Falling back to MemorySaver" in source
    assert "raise RuntimeError" not in source


def test_jd_orchestrator_is_cached():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py"
    ).read_text(encoding="utf-8")
    assert "_jd_orchestrator" in source
    assert "Initializing JD Generation Orchestrator" in source


def test_nonprod_langgraph_checkpoint_uses_memory():
    manifest = (
        REPO_ROOT / "infra" / "kubernetes" / "nonprod" / "quanthire.yaml"
    ).read_text(encoding="utf-8")
    assert 'LANGGRAPH_CHECKPOINT_BACKEND: "memory"' in manifest


def test_jd_workflow_unit_tests_exist():
    path = REPO_ROOT / "tests" / "unit" / "test_jd_generation_workflow.py"
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "should_skip_local_vector_storage" in source


def test_resume_parsing_workflow_tests_exist():
    path = REPO_ROOT / "tests" / "unit" / "test_resume_parsing_workflow.py"
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "document_intelligence_available" in source


def test_job_matching_workflow_tests_exist():
    path = REPO_ROOT / "tests" / "unit" / "test_job_matching_workflow.py"
    assert path.exists()
    source = path.read_text(encoding="utf-8")
    assert "testJobMatchingReady" in source


def test_manifest_image_tags_are_0_1_5():
    manifest = (
        REPO_ROOT / "infra" / "kubernetes" / "nonprod" / "quanthire.yaml"
    ).read_text(encoding="utf-8")
    assert "quanthire-backend:0.1.5" in manifest
    assert "quanthire-frontend:0.1.5" in manifest
