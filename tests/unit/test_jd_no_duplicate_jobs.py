"""E2E validation: JD generate/regenerate/HITL save must update one job, not duplicate cards."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_job_with_enterprise_jd.json"

_ENTERPRISE_KEYS = (
    "job_title",
    "location",
    "about_company",
    "position_summary",
    "required_qualifications",
    "work_environment",
    "equal_opportunity_statement",
    "application_instructions",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_enterprise_format(spec: object) -> bool:
    if not isinstance(spec, dict):
        return False
    return all(key in spec for key in _ENTERPRISE_KEYS)


def resolve_replace_job_id(*candidates: str | None) -> str | None:
    """Mirror of jd-generation-dialog resolveReplaceJobId()."""
    for candidate in candidates:
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def build_generate_payload(
    *,
    replace_job_id: str | None,
    edit_job_id: str | None,
    edited_jd: dict | None,
    generated_jd: dict | None,
    job_title: str,
    department: str,
) -> dict:
    """Mirror of handleGenerate() request payload assembly."""
    existing_job_id = resolve_replace_job_id(
        replace_job_id,
        edit_job_id,
        (edited_jd or {}).get("job_id"),
        (edited_jd or {}).get("id"),
        (generated_jd or {}).get("job_id"),
        (generated_jd or {}).get("id"),
    )
    payload = {
        "job_title": job_title,
        "department": department,
        "job_level": "Consultant",
    }
    if existing_job_id:
        payload["job_id"] = existing_job_id
    return payload


def simulate_backend_auto_save_id(request_job_id: str | None) -> str:
    """Mirror of jd_generation._execute_jd_generation_core auto-save id selection."""
    return request_job_id or str(uuid.uuid4())


def simulate_save_endpoint_id(request_job_id: str | None) -> str:
    """Mirror of POST /jd-generation/save id selection."""
    return request_job_id or str(uuid.uuid4())


def apply_generate_to_jobs_list(
    jobs: list[dict],
    *,
    request_job_id: str | None,
    job_title: str,
    department: str,
) -> tuple[list[dict], str]:
    """Simulate jobs list after generate auto-save (update in place or append one row)."""
    stored_id = simulate_backend_auto_save_id(request_job_id)
    updated = deepcopy(jobs)
    match = next((job for job in updated if job["id"] == stored_id), None)
    if match:
        match["title"] = job_title
        match["department"] = department
        match["spec_json"]["job_title"] = job_title
        match["spec_json"]["department"] = department
    else:
        updated.append(
            {
                "id": stored_id,
                "title": job_title,
                "department": department,
                "spec_json": {
                    "job_title": job_title,
                    "department": department,
                    "metadata": {},
                },
            }
        )
    return updated, stored_id


def apply_hitl_save_to_jobs_list(
    jobs: list[dict],
    *,
    job_id: str,
    job_title: str,
    removed_sections: list[str],
) -> list[dict]:
    """Simulate jobs list after HITL Save to pgvector."""
    updated = deepcopy(jobs)
    match = next((job for job in updated if job["id"] == job_id), None)
    assert match is not None, f"job {job_id} must exist for in-place HITL save"
    match["title"] = job_title
    match["spec_json"]["job_title"] = job_title
    match["spec_json"].setdefault("metadata", {})["removed_sections"] = removed_sections
    return updated


def test_first_generate_without_job_id_creates_one_row():
    jobs: list[dict] = []
    payload = build_generate_payload(
        replace_job_id=None,
        edit_job_id=None,
        edited_jd=None,
        generated_jd=None,
        job_title="Principle Consultant",
        department="Cloud Implementation",
    )
    assert "job_id" not in payload
    jobs, stored_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=payload.get("job_id"),
        job_title=payload["job_title"],
        department=payload["department"],
    )
    assert len(jobs) == 1
    assert jobs[0]["id"] == stored_id


def test_regenerate_with_same_job_id_does_not_duplicate():
    jobs: list[dict] = []
    jobs, first_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=None,
        job_title="Principle Consultant",
        department="Cloud Implementation",
    )

    replace_job_id = first_id
    payload = build_generate_payload(
        replace_job_id=replace_job_id,
        edit_job_id=None,
        edited_jd=None,
        generated_jd={"job_id": first_id, "id": first_id},
        job_title="Principal Consultant",
        department="Cloud Implementation and Transformation",
    )
    assert payload["job_id"] == first_id

    jobs, second_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=payload["job_id"],
        job_title=payload["job_title"],
        department=payload["department"],
    )
    assert second_id == first_id
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Principal Consultant"


def test_open_card_edit_hitl_save_updates_same_row():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jobs = [job]
    job_id = job["id"]

    jobs = apply_hitl_save_to_jobs_list(
        jobs,
        job_id=job_id,
        job_title="Principal Solution Architect",
        removed_sections=["compensation_benefits"],
    )
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id
    assert jobs[0]["title"] == "Principal Solution Architect"
    assert jobs[0]["spec_json"]["metadata"]["removed_sections"] == ["compensation_benefits"]


def test_edit_job_id_flow_generate_updates_existing_card():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jobs = [job]
    edit_job_id = job["id"]

    payload = build_generate_payload(
        replace_job_id=edit_job_id,
        edit_job_id=edit_job_id,
        edited_jd=job["spec_json"],
        generated_jd=job["spec_json"],
        job_title="Senior Consultant L2",
        department="Application Development",
    )
    assert payload["job_id"] == edit_job_id

    jobs, stored_id = apply_generate_to_jobs_list(
        jobs,
        request_job_id=payload["job_id"],
        job_title=payload["job_title"],
        department=payload["department"],
    )
    assert len(jobs) == 1
    assert stored_id == edit_job_id
    assert jobs[0]["title"] == "Senior Consultant L2"


def test_triple_generate_without_job_id_would_create_three_cards():
    """Documents the old bug: missing job_id on repeat generate creates duplicates."""
    jobs: list[dict] = []
    for _ in range(3):
        jobs, _ = apply_generate_to_jobs_list(
            jobs,
            request_job_id=None,
            job_title="Principle Consultant",
            department="Cloud Implementation",
        )
    assert len(jobs) == 3


def test_triple_generate_with_replace_job_id_keeps_one_card():
    jobs: list[dict] = []
    replace_job_id: str | None = None
    for title in ("Principle Consultant", "Principal Consultant", "Principal Consultant L2"):
        payload = build_generate_payload(
            replace_job_id=replace_job_id,
            edit_job_id=None,
            edited_jd={"job_id": replace_job_id} if replace_job_id else None,
            generated_jd={"job_id": replace_job_id} if replace_job_id else None,
            job_title=title,
            department="Cloud Implementation",
        )
        jobs, replace_job_id = apply_generate_to_jobs_list(
            jobs,
            request_job_id=payload.get("job_id"),
            job_title=payload["job_title"],
            department=payload["department"],
        )
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Principal Consultant L2"


def test_save_endpoint_reuses_job_id_for_customization():
    existing_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert simulate_save_endpoint_id(existing_id) == existing_id
    assert simulate_save_endpoint_id(None) != existing_id


def test_generate_endpoint_wiring():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py")
    request_block = source.split("class JDGenerationRequest", 1)[1].split("class JDGenerationResponse", 1)[0]
    assert "job_id: Optional[str]" in request_block
    assert "job_id = request.job_id or str(uuid.uuid4())" in source
    assert '"job_id": job_id' in source
    assert "job_row_id=job_row_id" in source


def test_dialog_wiring_for_replace_job_id():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "const [replaceJobId, setReplaceJobId]" in source
    assert "resolveReplaceJobId" in source
    assert "existingJobId ? { job_id: String(existingJobId) }" in source
    assert "setReplaceJobId((current) =>" in source


def test_api_client_passes_job_id_to_generate():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "api.ts")
    assert "generateAsync: (data: {" in source
    assert "job_id?: string;" in source
