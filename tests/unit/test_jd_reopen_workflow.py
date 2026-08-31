"""Validation for JD reopen / view-edit workflow (frontend + save pipeline wiring)."""

from __future__ import annotations

import json
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
    """Mirror of apps/web/src/types/enterprise-jd.ts isEnterpriseFormat()."""
    if not isinstance(spec, dict):
        return False
    return all(key in spec for key in _ENTERPRISE_KEYS)


def job_has_enterprise_jd(job: dict) -> bool:
    return is_enterprise_format(job.get("spec_json"))


def hydrate_enterprise_jd_from_job(job: dict) -> dict | None:
    """Mirror of apps/web/src/lib/jd-persist.ts hydrateEnterpriseJdFromJob()."""
    spec = job.get("spec_json")
    if not is_enterprise_format(spec):
        return None
    job_id = str(job.get("id") or spec.get("job_id") or spec.get("id") or "")
    if not job_id:
        return None
    hydrated = {**spec}
    hydrated["job_id"] = job_id
    hydrated["id"] = job_id
    hydrated["milvus_id"] = spec.get("milvus_id") or job_id
    hydrated["job_title"] = spec.get("job_title") or job.get("title") or ""
    hydrated["department"] = spec.get("department") or job.get("department") or ""
    return hydrated


def build_jd_generation_form_from_job(job: dict, jd: dict) -> dict:
    """Mirror of apps/web/src/lib/jd-persist.ts buildJdGenerationFormFromJob()."""
    metadata = jd.get("metadata") or {}
    dialog_inputs = metadata.get("dialog_inputs") or {}
    hr_inputs = metadata.get("hr_inputs") or {}
    location = jd.get("location") or {}
    location_from_jd = ", ".join(
        part for part in (location.get("city"), location.get("country")) if part
    )
    skills_source = (
        dialog_inputs.get("skills")
        or metadata.get("skills")
        or hr_inputs.get("skills")
        or (jd.get("required_qualifications") or {}).get("technical_skills")
        or []
    )
    skills_text = (
        ", ".join(skills_source)
        if isinstance(skills_source, list)
        else str(skills_source or "")
    )
    return {
        "job_title": dialog_inputs.get("job_title")
        or jd.get("job_title")
        or job.get("title")
        or "",
        "job_level": dialog_inputs.get("job_level")
        or metadata.get("job_level")
        or job.get("level")
        or "",
        "department": dialog_inputs.get("department")
        or jd.get("department")
        or job.get("department")
        or "",
        "years_of_experience": dialog_inputs.get("years_of_experience")
        or metadata.get("years_of_experience")
        or hr_inputs.get("years_of_experience")
        or "",
        "internal_title": dialog_inputs.get("internal_title")
        or metadata.get("internal_title")
        or hr_inputs.get("internal_title")
        or "",
        "business_unit": dialog_inputs.get("business_unit")
        or metadata.get("business_unit")
        or hr_inputs.get("business_unit")
        or jd.get("business_unit")
        or "",
        "qualification": dialog_inputs.get("qualification")
        or metadata.get("qualification")
        or hr_inputs.get("qualification")
        or (jd.get("required_qualifications") or {}).get("education")
        or "",
        "skills": skills_text,
        "location": dialog_inputs.get("location") or location_from_jd or job.get("location") or "",
        "remote_allowed": dialog_inputs.get("remote_allowed")
        if dialog_inputs.get("remote_allowed") is not None
        else (
            location.get("work_model") == "Remote" or bool(job.get("remote_allowed"))
        ),
        "user_requirements": dialog_inputs.get("user_requirements") or "",
    }


def test_fixture_is_valid_enterprise_job():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert job_has_enterprise_jd(job)


def test_hydrate_preserves_job_id_for_save():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jd = hydrate_enterprise_jd_from_job(job)
    assert jd is not None
    assert jd["job_id"] == job["id"]
    assert jd["id"] == job["id"]
    assert jd["job_title"] == "Solution Architect"
    assert jd["department"] == "Application Development"


def test_hydrate_preserves_hitl_metadata_and_custom_sections():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    job["spec_json"]["metadata"]["removed_sections"] = ["compensation_benefits"]
    jd = hydrate_enterprise_jd_from_job(job)
    assert jd is not None
    assert jd["metadata"]["removed_sections"] == ["compensation_benefits"]
    assert jd["custom_sections"][0]["title"] == "Travel Policy"


def test_hydrate_returns_none_for_non_enterprise_job():
    job = {"id": "x", "title": "Manual", "spec_json": {"job_title": "Only title"}}
    assert hydrate_enterprise_jd_from_job(job) is None


def test_build_form_restores_hr_inputs():
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))
    jd = hydrate_enterprise_jd_from_job(job)
    assert jd is not None
    form = build_jd_generation_form_from_job(job, jd)
    assert form["job_title"] == "Solution Architect"
    assert form["department"] == "Application Development"
    assert form["internal_title"] == "Senior Consultant L2"
    assert "Azure" in form["skills"]
    assert form["location"] == "Doha, Qatar"


def test_jd_generation_dialog_supports_edit_job_id():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx")
    assert "editJobId" in source
    assert "hydrateEnterpriseJdFromJob" in source
    assert "buildJdGenerationFormFromJob" in source
    assert "JD_DIALOG_TITLE_EDIT" in source
    assert "loadingExisting" in source


def test_jobs_page_wires_card_to_editor():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "page.tsx")
    assert "jobHasEnterpriseJd" in source
    assert "handleOpenSavedJd" in source
    assert "onOpenJd={handleOpenSavedJd}" in source
    assert "editJobId={editJobId}" in source


def test_job_card_opens_ai_jd_when_flagged():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "job-card.tsx")
    assert "hasEnterpriseJd" in source
    assert "onOpenJd" in source
    assert "AI JD" in source


def test_job_detail_has_edit_ai_jd_button():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "[id]" / "page.tsx")
    assert "Edit AI JD" in source
    assert "JDGenerationDialog" in source
    assert "editJobId={jobId}" in source


def test_jd_persist_exports_reopen_helpers():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "jd-persist.ts")
    assert "export function hydrateEnterpriseJdFromJob" in source
    assert "export function buildJdGenerationFormFromJob" in source
    assert "export function jobHasEnterpriseJd" in source


def test_generate_endpoint_accepts_job_id_for_updates():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py")
    assert "job_id: Optional[str]" in source.split("class JDGenerationRequest", 1)[1].split("class JDGenerationResponse", 1)[0]
    assert "job_id = request.job_id or str(uuid.uuid4())" in source
    assert "job_row_id=job_row_id" in source


def test_jd_generation_dialog_passes_job_id_when_regenerating():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "replaceJobId" in source
    assert "existingJobId ? { job_id: String(existingJobId) }" in source
    assert "resolveReplaceJobId" in source


def test_save_endpoint_accepts_job_id_for_updates():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "jd_generation.py")
    assert '@router.post("/save"' in source
    assert "job_id" in source


def test_pipeline_updates_existing_job_row():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "services" / "jd_pipeline_service.py")
    assert "_find_job_for_document" in source
    assert "Updating existing job row" in source
    assert "store_jd" in source


def test_jd_persist_preserves_removed_sections():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "jd-persist.ts")
    assert "removed_sections: [...(jd.metadata?.removed_sections || [])]" in source
    assert "dialog_inputs:" in source
    assert "job_title: jd.job_title" in source
    assert "location: formatLocation(jd.location)" in source


def test_job_card_preview_reads_enterprise_spec():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "job-card-preview.ts")
    assert "buildJobCardPreviewFromJob" in source
    assert "formatDepartmentTeam(spec)" in source
    assert "getRemovedSectionIds(spec)" in source


def test_job_card_ui_uses_preview_data():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "job-card.tsx")
    assert "preview?.title" in source
    assert "preview?.summary" in source
    assert "preview.skillTags" in source


def test_preview_save_does_not_double_persist_with_stale_form():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "enterprise-jd-preview-card.tsx"
    )
    assert "onPersisted?.(savedJd)" in source
    assert "onSave?.(savedJd)" not in source


def test_handle_save_prefers_edited_jd_title_over_form():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "jdToSave.job_title ||" in source
    assert "formData.job_title ||" in source
    title_block = source.split("prepareEnterpriseJdForSave({", 1)[1].split("});", 1)[0]
    assert title_block.index("jdToSave.job_title") < title_block.index("formData.job_title")


def test_chunking_honors_removed_sections_for_quantchat():
    source = _read(REPO_ROOT / "apps" / "quantchat" / "ingestion" / "chunking.py")
    assert "jd_removed_section_ids" in source
    assert "custom_sections" in source
