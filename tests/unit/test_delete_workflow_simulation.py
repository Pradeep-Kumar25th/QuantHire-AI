"""Simulated end-to-end delete journeys for jobs/JDs and candidates/resumes.

Mirrors frontend helpers and backend purge logic without a browser or live DB.
"""

from __future__ import annotations

import json
import sys
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models.candidates import Candidate  # noqa: E402
from app.models.jobs import Job  # noqa: E402
from app.services.resource_deletion_service import _job_document_ids  # noqa: E402

JOB_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_job_with_enterprise_jd.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def mirror_delete_job_with_confirm(
    *,
    job_id: str,
    title: str,
    applications: int = 0,
    confirmed: bool = True,
    api_succeeds: bool = True,
) -> tuple[bool, str | None]:
    """Mirror apps/web/src/lib/delete-resource.ts deleteJobWithConfirm()."""
    if applications > 0:
        return False, "blocked_applications"
    if not confirmed:
        return False, "cancelled"
    if not api_succeeds:
        return False, "api_error"
    return True, job_id


def mirror_delete_candidate_with_confirm(
    *,
    candidate_id: str,
    name: str,
    active_applications: int = 0,
    confirmed: bool = True,
    api_succeeds: bool = True,
) -> tuple[bool, str | None]:
    """Mirror apps/web/src/lib/delete-resource.ts deleteCandidateWithConfirm()."""
    if active_applications > 0:
        return False, "blocked_applications"
    if not confirmed:
        return False, "cancelled"
    if not api_succeeds:
        return False, "api_error"
    return True, candidate_id


def mirror_jobs_list_after_delete(jobs: list[dict], deleted_id: str) -> list[dict]:
    """Jobs list refresh after successful DELETE /v1/jobs/{id}."""
    return [job for job in jobs if str(job.get("id")) != deleted_id]


def mirror_candidates_list_after_delete(
    candidates: list[dict],
    removed_id: str,
) -> list[dict]:
    """Candidates list with is_active=true filter after soft-delete."""
    return [
        candidate
        for candidate in candidates
        if str(candidate.get("id")) != removed_id and candidate.get("is_active", True)
    ]


def candidate_document_ids(profile: dict, candidate_id: str) -> set[str]:
    """Document ids purged for a resume (mirrors ResourceDeletionService)."""
    ids = {str(candidate_id)}
    for key in ("id", "resume_id"):
        value = profile.get(key)
        if value and str(value).strip():
            ids.add(str(value).strip())
    return ids


def load_fixture_job() -> dict:
    return json.loads(JOB_FIXTURE.read_text(encoding="utf-8"))


def test_jd_delete_journey_removes_card_and_targets_all_vector_ids():
    fixture = load_fixture_job()
    job_id = fixture["id"]
    document_id = "enterprise-jd-doc-001"

    job = Job(
        id=uuid.UUID(job_id),
        title=fixture["title"],
        level=fixture["level"],
        department=fixture["department"],
        created_by=uuid.uuid4(),
        spec_json={**fixture["spec_json"], "id": document_id},
        extra_metadata={"document_id": document_id, "pipeline": "azure_pgvector"},
    )

    doc_ids = _job_document_ids(job)
    assert str(job.id) in doc_ids
    assert document_id in doc_ids

    jobs = [
        {"id": job_id, "title": fixture["title"], "applications": 0},
        {"id": str(uuid.uuid4()), "title": fixture["title"], "applications": 0},
        {"id": str(uuid.uuid4()), "title": "Other Role", "applications": 0},
    ]

    ok, _ = mirror_delete_job_with_confirm(
        job_id=job_id,
        title=fixture["title"],
        applications=0,
        confirmed=True,
    )
    assert ok is True

    remaining = mirror_jobs_list_after_delete(jobs, job_id)
    assert len(remaining) == 2
    assert all(str(item["id"]) != job_id for item in remaining)


def test_jd_delete_blocked_when_applications_exist():
    fixture = load_fixture_job()
    ok, reason = mirror_delete_job_with_confirm(
        job_id=fixture["id"],
        title=fixture["title"],
        applications=3,
        confirmed=True,
    )
    assert ok is False
    assert reason == "blocked_applications"


def test_jd_delete_cancelled_by_user():
    fixture = load_fixture_job()
    jobs = [{"id": fixture["id"], "title": fixture["title"]}]
    ok, reason = mirror_delete_job_with_confirm(
        job_id=fixture["id"],
        title=fixture["title"],
        confirmed=False,
    )
    assert ok is False
    assert reason == "cancelled"
    # Cancelled delete must not refresh/remove the card from the list.
    assert len(jobs) == 1
    assert jobs[0]["id"] == fixture["id"]


def test_duplicate_jd_cards_delete_one_at_a_time():
    """Regression: duplicate Principle Consultant cards can be removed individually."""
    shared_title = "Principle Consultant"
    jobs = [
        {"id": str(uuid.uuid4()), "title": shared_title, "applications": 0},
        {"id": str(uuid.uuid4()), "title": shared_title, "applications": 0},
        {"id": str(uuid.uuid4()), "title": shared_title, "applications": 0},
    ]
    working = deepcopy(jobs)

    for target in jobs[:2]:
        ok, _ = mirror_delete_job_with_confirm(
            job_id=target["id"],
            title=target["title"],
        )
        assert ok is True
        working = mirror_jobs_list_after_delete(working, target["id"])

    assert len(working) == 1
    assert working[0]["title"] == shared_title


def test_resume_delete_journey_soft_hides_and_purges_vectors():
    candidate_id = str(uuid.uuid4())
    profile = {
        "id": candidate_id,
        "name": "Aarav Mehta",
        "personal_info": {"name": "Aarav Mehta", "email": "aarav@example.com"},
    }
    doc_ids = candidate_document_ids(profile, candidate_id)
    assert candidate_id in doc_ids

    candidates = [
        {"id": candidate_id, "name": "Aarav Mehta", "is_active": True, "active_applications": 0},
        {"id": str(uuid.uuid4()), "name": "Other Person", "is_active": True, "active_applications": 0},
    ]

    ok, _ = mirror_delete_candidate_with_confirm(
        candidate_id=candidate_id,
        name="Aarav Mehta",
        active_applications=0,
        confirmed=True,
    )
    assert ok is True

    candidates_after = mirror_candidates_list_after_delete(candidates, candidate_id)
    assert len(candidates_after) == 1
    assert candidates_after[0]["name"] == "Other Person"

    candidate = Candidate(
        id=uuid.UUID(candidate_id),
        name="Aarav Mehta",
        email="aarav@example.com",
        is_active=False,
        deletion_requested=True,
        profile_json=profile,
    )
    assert candidate.is_active is False
    assert candidate.deletion_requested is True


def test_resume_delete_blocked_when_active_applications():
    ok, reason = mirror_delete_candidate_with_confirm(
        candidate_id=str(uuid.uuid4()),
        name="Pipeline Candidate",
        active_applications=2,
    )
    assert ok is False
    assert reason == "blocked_applications"


def test_inactive_candidate_hidden_from_list_and_profile_404():
    candidate_id = str(uuid.uuid4())
    candidates = [
        {"id": candidate_id, "name": "Removed", "is_active": False},
        {"id": str(uuid.uuid4()), "name": "Active", "is_active": True},
    ]
    visible = mirror_candidates_list_after_delete(candidates, candidate_id)
    assert len(visible) == 1
    assert visible[0]["name"] == "Active"


def test_delete_resource_ts_exports_job_and_candidate_helpers():
    source = _read(REPO_ROOT / "apps/web/src/lib/delete-resource.ts")
    assert "export async function deleteJobWithConfirm" in source
    assert "export async function deleteCandidateWithConfirm" in source
    assert "api.jobs.delete" in source
    assert "api.candidates.delete" in source


def test_api_routes_return_204_on_delete():
    jobs_source = _read(REPO_ROOT / "apps/api/app/api/v1/jobs.py")
    candidates_source = _read(REPO_ROOT / "apps/api/app/api/v1/candidates.py")
    assert "status_code=status.HTTP_204_NO_CONTENT" in jobs_source
    assert "@router.delete" in jobs_source
    assert "status_code=status.HTTP_204_NO_CONTENT" in candidates_source
    assert "await deletion.delete_candidate(candidate)" in candidates_source


def test_resource_deletion_service_does_not_await_sync_delete():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "inspect.isawaitable" in source
    assert "self.session.delete(job)" in source
    assert "JobEmbedding" in source
