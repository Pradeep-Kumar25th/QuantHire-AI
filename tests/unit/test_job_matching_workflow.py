"""Unit tests for HSS-D job matching deployment workflow."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_job_matching_orchestrator_singleton_has_lock():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "job_matching.py"
    ).read_text(encoding="utf-8")
    assert "_orchestrator_lock" in source
    assert "JobMatchingOrchestrator singleton initialized" in source


def test_job_matching_weight_override_includes_projects():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "job_matching.py"
    ).read_text(encoding="utf-8")
    assert "projects: Optional[float]" in source
    assert '"projects"' in source


def test_job_matching_llm_preflight_and_timeout_mapping():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "job_matching.py"
    ).read_text(encoding="utf-8")
    assert "_ensure_llm_configured_for_matching" in source
    assert "_raise_match_http_error" in source
    assert "HTTP_504_GATEWAY_TIMEOUT" in source


def test_job_matching_health_reports_hss_d_pipeline():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "job_matching.py"
    ).read_text(encoding="utf-8")
    assert '"pipeline": "hss-d"' in source
    assert "match_stream" in source


def test_bff_long_timeout_includes_job_matching():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "v1/job-matching/match-stream" in source
    assert "v1/job-matching/match" in source
    assert "HSS-D job matching" in source


def test_match_launcher_includes_projects_weight():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "components" / "matching" / "match-launcher.tsx"
    ).read_text(encoding="utf-8")
    assert 'key: "projects"' in source
    assert "testJobMatchingReady" in source
    assert "projects: 0.12" in source


def test_api_health_includes_job_matching_ready():
    source = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-health.ts").read_text(
        encoding="utf-8"
    )
    assert "testJobMatchingReady" in source
    assert "/v1/job-matching/health" in source
