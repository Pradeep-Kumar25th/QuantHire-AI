"""Frontend API client paths must use /v1 prefix (BFF → FastAPI)."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TS = REPO_ROOT / "apps" / "web" / "src" / "lib" / "api.ts"


def test_api_ts_jobs_candidates_applications_use_v1():
    content = API_TS.read_text(encoding="utf-8")
    assert '/v1/jobs/${id}/publish' in content
    assert '/v1/jobs/${id}/match' in content
    assert '"/v1/candidates/upload"' in content
    assert '"/v1/applications"' in content
    assert 'apiClient.post(`/jobs/' not in content
    assert 'apiClient.post("/candidates/upload"' not in content
    assert 'apiClient.get("/applications"' not in content


def test_resume_upload_uses_v1_endpoint():
    resume_upload = (
        REPO_ROOT / "apps" / "web" / "src" / "components" / "ResumeUpload.tsx"
    ).read_text(encoding="utf-8")
    assert "/v1/resume-parsing/upload-resume" in resume_upload
    assert '"/upload-resume"' not in resume_upload


def test_api_health_uses_bff_health_route():
    api_health = (
        REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-health.ts"
    ).read_text(encoding="utf-8")
    assert "`${API_URL}/health`" in api_health
    assert "/healthz" not in api_health
