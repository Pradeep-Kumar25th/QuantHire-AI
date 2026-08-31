"""End-to-end JD sync validation: job card preview, save pipeline, QuantChat, PDF wiring."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"
API_ROOT = REPO_ROOT / "apps" / "api"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_job_with_enterprise_jd.json"

for path in (str(APPS_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.jd_pipeline_service import (  # noqa: E402
    _department_display_from_jd,
    _job_level_from_jd,
)
from app.services.pgvector_ingestion import _structured_jd_full_content  # noqa: E402
from quantchat.ingestion.chunking import (  # noqa: E402
    JDChunker,
    format_jd_department_team,
    format_jd_job_title_block,
    jd_removed_section_ids,
)

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


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def is_enterprise_format(spec: object) -> bool:
    if not isinstance(spec, dict):
        return False
    return all(key in spec for key in _ENTERPRISE_KEYS)


def format_department_team(jd: dict) -> str:
    """Mirror of apps/web/src/types/enterprise-jd.ts formatDepartmentTeam()."""
    department = (jd.get("department") or "").strip()
    team = (jd.get("team") or "").strip()
    division = (jd.get("division") or "").strip()
    business_unit = (jd.get("business_unit") or "").strip()
    metadata = jd.get("metadata") or {}
    if not business_unit:
        business_unit = (metadata.get("business_unit") or "").strip()

    if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", department):
        parts = [department]
        if business_unit or division:
            parts.append(business_unit or division)
        return " / ".join(parts)

    parts = [part for part in (department, team, division or business_unit) if part]
    return " / ".join(parts)


def build_job_card_preview(job: dict) -> dict:
    """Mirror of apps/web/src/lib/job-card-preview.ts buildJobCardPreviewFromJob()."""
    spec = job.get("spec_json")
    if not is_enterprise_format(spec):
        return {
            "title": job.get("title") or "Untitled Role",
            "departmentDisplay": job.get("department") or "Not specified",
            "summary": (job.get("description") or "")[:180] or None,
            "skillTags": [],
            "customSectionCount": 0,
            "removedSectionCount": 0,
        }

    removed = spec.get("metadata", {}).get("removed_sections") or []
    summary = None
    if "position_summary" not in removed:
        ps = (spec.get("position_summary") or "").strip()
        if ps and ps.lower() != "position summary will be generated.":
            summary = ps[:180] or None
    elif "responsibilities" not in removed and spec.get("responsibilities"):
        summary = str(spec["responsibilities"][0]).strip()[:180]

    skill_tags = []
    seen = set()
    for bucket in (
        (spec.get("required_qualifications") or {}).get("technical_skills") or [],
        spec.get("tools_technologies") or [],
        spec.get("soft_skills") or [],
    ):
        for item in bucket:
            text = str(item).strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            skill_tags.append(text)
            if len(skill_tags) >= 4:
                break
        if len(skill_tags) >= 4:
            break

    location = spec.get("location") or {}
    location_parts = [part for part in (location.get("city"), location.get("country")) if part]
    location_label = ", ".join(location_parts)
    if location.get("work_model"):
        location_label = (
            f"{location_label} ({location['work_model']})"
            if location_label
            else str(location["work_model"])
        )

    return {
        "title": spec.get("job_title") or job.get("title") or "Untitled Role",
        "level": (spec.get("metadata") or {}).get("job_level") or "",
        "departmentDisplay": format_department_team(spec) or job.get("department") or "Not specified",
        "locationLabel": location_label or job.get("location") or "Not specified",
        "workModel": location.get("work_model"),
        "summary": summary,
        "skillTags": skill_tags,
        "customSectionCount": len(spec.get("custom_sections") or []),
        "removedSectionCount": len(removed),
    }


def resolve_save_job_title(jd_to_save: dict, form_data: dict) -> str:
    """Mirror of jd-generation-dialog handleSave() title priority."""
    return (
        jd_to_save.get("job_title")
        or form_data.get("job_title")
        or form_data.get("internal_title")
        or ""
    )


def test_edited_jd_title_wins_over_stale_hr_form():
    saved_title = resolve_save_job_title(
        {"job_title": "Senior Consultant L2"},
        {"job_title": "Solution Architect", "internal_title": "Old Internal"},
    )
    assert saved_title == "Senior Consultant L2"


def test_job_card_preview_reflects_saved_title():
    job = _load_fixture()
    job["spec_json"]["job_title"] = "Senior Consultant L2"
    preview = build_job_card_preview(job)
    assert preview["title"] == "Senior Consultant L2"


def test_job_card_preview_reflects_level_department_and_skills():
    job = _load_fixture()
    preview = build_job_card_preview(job)
    assert preview["level"] == "Senior"
    assert preview["departmentDisplay"] == "Application Development"
    assert "Azure" in preview["skillTags"]
    assert preview["customSectionCount"] == 1
    assert "Hybrid" in preview["locationLabel"]


def test_job_card_preview_department_includes_team_and_division():
    job = _load_fixture()
    job["spec_json"]["department"] = "Cybersecurity"
    job["spec_json"]["team"] = "Identity Team"
    job["spec_json"]["division"] = "CyberSecurity"
    preview = build_job_card_preview(job)
    assert preview["departmentDisplay"] == "Cybersecurity / Identity Team / CyberSecurity"


def test_job_card_preview_hides_removed_summary_and_uses_responsibility_fallback():
    job = _load_fixture()
    job["spec_json"]["metadata"]["removed_sections"] = ["position_summary"]
    preview = build_job_card_preview(job)
    assert preview["removedSectionCount"] == 1
    assert preview["summary"].startswith("Define solution architecture")


def test_pipeline_job_level_and_department_helpers():
    jd = {
        "metadata": {"job_level": "Mid-level"},
        "department": "Cybersecurity",
        "team": "Identity Team",
        "division": "CyberSecurity",
    }
    assert _job_level_from_jd(jd) == "Mid-level"
    assert _department_display_from_jd(jd) == "Cybersecurity / Identity Team / CyberSecurity"


def test_pipeline_job_level_empty_when_not_in_jd():
    assert _job_level_from_jd({}) == ""
    assert _department_display_from_jd({}) == ""


def test_quantchat_chunking_indexes_title_level_team_and_custom_sections():
    jd = {
        "id": "jd-sync-1",
        "job_title": "Senior Consultant L2",
        "department": "Cybersecurity",
        "team": "Identity Team",
        "division": "CyberSecurity",
        "metadata": {"job_level": "Mid-level", "removed_sections": ["about_company"]},
        "position_summary": (
            "Lead cybersecurity consulting engagements and deliver advisory services "
            "across enterprise clients in multiple regions."
        ),
        "custom_sections": [
            {
                "id": "custom-travel",
                "title": "Travel Policy",
                "content": "Up to fifty percent travel may be required for client delivery.",
            }
        ],
    }
    chunks = JDChunker().chunk_jd(jd)
    sections = {chunk["section"] for chunk in chunks}
    assert "About Company" not in sections
    assert "Custom: Travel Policy" in sections

    title_chunk = next(chunk for chunk in chunks if chunk["section"] == "Job Title")
    assert "Senior Consultant L2" in title_chunk["content"]
    assert "Mid-level" in title_chunk["content"]

    dept_chunk = next(chunk for chunk in chunks if chunk["section"] == "Department")
    assert "Cybersecurity" in dept_chunk["content"]
    assert "Identity Team" in dept_chunk["content"]


def test_quantchat_full_doc_header_uses_formatted_department():
    jd = {
        "job_title": "Senior Consultant L2",
        "department": "Cybersecurity",
        "team": "Identity Team",
        "metadata": {"job_level": "Mid-level"},
    }
    chunks = [
        {
            "section": "Job Title",
            "content": format_jd_job_title_block(jd),
        },
        {
            "section": "Department",
            "content": format_jd_department_team(jd),
        },
    ]
    full = _structured_jd_full_content(jd, chunks)
    assert "Job: Senior Consultant L2" in full
    assert "Identity Team" in full
    assert "Department:" in full


def test_removed_sections_excluded_from_quantchat_index():
    jd = {
        "id": "jd-sync-2",
        "job_title": "Engineer",
        "department": "Information Technology and Platform Engineering Division",
        "about_company": "Secret text that must never appear in vector retrieval output.",
        "position_summary": (
            "Build reliable systems and scalable services for enterprise customers "
            "across multiple regions."
        ),
        "metadata": {"removed_sections": ["about_company"]},
    }
    assert "about_company" in jd_removed_section_ids(jd)
    chunks = JDChunker().chunk_jd(jd)
    assert "About Company" not in {chunk["section"] for chunk in chunks}


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
    title_block = source.split("prepareEnterpriseJdForSave({", 1)[1].split("});", 1)[0]
    assert title_block.index("jdToSave.job_title") < title_block.index("formData.job_title")


def test_pipeline_updates_existing_job_level_on_save():
    source = _read(REPO_ROOT / "apps" / "api" / "app" / "services" / "jd_pipeline_service.py")
    assert "existing_job.level = job_level" in source
    assert "_job_level_from_jd" in source
    assert "_department_display_from_jd" in source


def test_jobs_page_builds_preview_from_spec_json():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "app" / "dashboard" / "jobs" / "page.tsx")
    assert "buildJobCardPreviewFromJob" in source
    assert "title: preview.title" in source
    assert "preview," in source


def test_jd_persist_syncs_dialog_inputs_on_save():
    source = _read(REPO_ROOT / "apps" / "web" / "src" / "lib" / "jd-persist.ts")
    assert "location: formatLocation(jd.location)" in source
    assert "internal_title: jd.metadata?.internal_title" in source
    assert "skills:" in source


def test_pdf_respects_removed_sections_and_dynamic_numbering():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "enterprise-jd-preview-card.tsx"
    )
    assert "isSectionVisible(" in source
    assert "getCustomSectionNumber" in source
    assert "pdfHeader(" in source
    assert 'pdfHeader("job_title"' in source
    assert "custom_sections" in source


def test_preview_on_update_syncs_full_hr_form():
    source = _read(
        REPO_ROOT / "apps" / "web" / "src" / "components" / "jobs" / "jd-generation-dialog.tsx"
    )
    assert "buildJdGenerationFormFromJob(" in source
    assert "onUpdate={(updatedJD)" in source
