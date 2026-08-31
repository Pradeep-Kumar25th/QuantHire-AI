"""E2E wiring checks for job/JD and candidate/resume delete flows."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_resource_deletion_service_purges_vectors():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "services" / "resource_deletion_service.py")
    assert "class ResourceDeletionService" in source
    assert "purge_job_vectors" in source
    assert "purge_candidate_vectors" in source
    assert "delete_document" in source
    assert "CandidateEmbedding" in source
    assert "JobEmbedding" in source
    assert "candidate.is_active = False" in source
    assert "inspect.isawaitable" in source
    assert "self.session.delete(job)" in source
    assert "_job_document_ids" in source


def test_jobs_api_uses_resource_deletion_service():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jobs.py")
    assert "ResourceDeletionService" in source
    assert "await deletion.delete_job(job)" in source
    assert "HTTP_409_CONFLICT" in source


def test_candidates_api_soft_delete_and_list_active_default():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "candidates.py")
    assert "ResourceDeletionService" in source
    assert "await deletion.delete_candidate(candidate)" in source
    assert "is_active: bool = Query(True" in source
    assert "Candidate.is_active == is_active" in source


def test_delete_resource_helpers_call_api():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "delete-resource.ts")
    assert "export async function deleteJobWithConfirm" in source
    assert "export async function deleteCandidateWithConfirm" in source
    assert "api.jobs.delete" in source
    assert "api.candidates.delete" in source
    assert "indexed JD from QuantChat" in source


def test_jobs_page_wires_delete_on_cards():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "page.tsx")
    assert "ConfirmDeleteDialog" in source or "deleteJobWithConfirm" in source
    assert "handleDeleteJob" in source
    assert "onDelete={handleDeleteJob}" in source


def test_job_card_exposes_delete_action():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "job-card.tsx")
    assert "onDelete" in source
    assert "handleDeleteClick" in source
    assert "Trash2" in source
    assert 'aria-label="Delete job"' in source


def test_job_detail_has_delete_button():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "[id]" / "page.tsx")
    assert "ConfirmDeleteDialog" in source or "deleteJobWithConfirm" in source
    assert "handleDeleteJob" in source
    assert "Delete Job" in source
    assert 'router.push("/dashboard/jobs")' in source


def test_candidates_page_wires_delete_on_cards():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "candidates" / "page.tsx")
    assert "ConfirmDeleteDialog" in source or "deleteCandidateWithConfirm" in source
    assert "handleDeleteCandidate" in source
    assert "onDelete={handleDeleteCandidate}" in source


def test_candidate_profile_has_remove_action():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "candidates" / "candidate-profile-view.tsx"
    )
    assert "ConfirmDeleteDialog" in source or "deleteCandidateWithConfirm" in source
    assert "handleRemoveCandidate" in source
    assert "Remove from pool" in source
    assert 'router.push("/dashboard/candidates")' in source


def test_job_detail_delete_does_not_use_mock_application_guard():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "[id]" / "page.tsx")
    assert "ConfirmDeleteDialog" in source or "deleteJobWithConfirm" in source
    assert "applications: displayJob.applications" not in source


def test_api_client_filters_inactive_candidates_by_default():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "api.ts")
    assert "is_active: true" in source.split("candidates:", 1)[1].split("delete:", 1)[0]


def test_candidates_page_requests_active_only():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "candidates" / "page.tsx")
    assert "is_active=true" in source
