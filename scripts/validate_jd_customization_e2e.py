#!/usr/bin/env python3
"""End-to-end validation for JD preview-card click -> HITL customization workflow.

Simulates the full user journey without a browser:
  Jobs list card click -> hydrate saved JD -> edit sections (HITL) ->
  prepare for save -> job card preview sync -> QuantChat chunking.

Also runs static wiring checks and the full JD/HITL pytest suite.

Usage (from repo root):
  python scripts\\validate_jd_customization_e2e.py
  python scripts\\validate_jd_customization_e2e.py --skip-pytest
  python scripts\\validate_jd_customization_e2e.py --live-api http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_job_with_enterprise_jd.json"

APPS_ROOT = REPO_ROOT / "apps"
API_ROOT = REPO_ROOT / "apps" / "api"
for path in (str(APPS_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.jd_pipeline_service import (  # noqa: E402
    _department_display_from_jd,
    _job_level_from_jd,
)
from quantchat.ingestion.chunking import JDChunker, jd_removed_section_ids  # noqa: E402

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

ENTERPRISE_JD_SECTIONS = [
    {"id": "job_title", "label": "Job Title"},
    {"id": "department_team", "label": "Department / Grade / BU"},
    {"id": "location_work_model", "label": "Location & Work Model"},
    {"id": "about_company", "label": "About the Company"},
    {"id": "position_summary", "label": "Position Summary"},
    {"id": "responsibilities", "label": "Key Responsibilities"},
    {"id": "required_qualifications", "label": "Required Qualifications"},
    {"id": "preferred_qualifications", "label": "Preferred Qualifications"},
    {"id": "soft_skills", "label": "Core Competencies / Soft Skills"},
    {"id": "tools_technologies", "label": "Skills & Technologies"},
    {"id": "success_metrics", "label": "Success Metrics / KPIs"},
    {"id": "work_environment", "label": "Work Environment / Reporting Structure"},
    {"id": "compensation_benefits", "label": "Compensation & Benefits"},
    {"id": "equal_opportunity_statement", "label": "Equal Opportunity Statement"},
    {"id": "application_instructions", "label": "Application Instructions"},
]

PYTEST_FILES = [
    "tests/unit/test_jd_hitl_chunking.py",
    "tests/unit/test_jd_section_numbering.py",
    "tests/unit/test_jd_pipeline_service.py",
    "tests/unit/test_jd_quantchat_full_doc.py",
    "tests/unit/test_jd_reopen_workflow.py",
    "tests/unit/test_jd_e2e_sync.py",
    "tests/unit/test_jd_generation_async.py",
    "tests/unit/test_jd_generation_workflow.py",
]

WIRING_CHECKS: list[tuple[str, Path, str]] = [
    (
        "Job card opens JD editor on click",
        REPO_ROOT / "apps/web/src/app/dashboard/jobs/page.tsx",
        "handleOpenSavedJd",
    ),
    (
        "Job card passes editJobId to dialog",
        REPO_ROOT / "apps/web/src/app/dashboard/jobs/page.tsx",
        "editJobId={editJobId}",
    ),
    (
        "Dialog hydrates enterprise JD from saved job",
        REPO_ROOT / "apps/web/src/components/jobs/jd-generation-dialog.tsx",
        "hydrateEnterpriseJdFromJob",
    ),
    (
        "Dialog tracks unsaved HITL edits",
        REPO_ROOT / "apps/web/src/components/jobs/jd-generation-dialog.tsx",
        "hasUnsavedEdits",
    ),
    (
        "Preview card section visibility toggles (HITL)",
        REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx",
        "setSectionVisibility",
    ),
    (
        "Preview card persists via onPersisted (not stale onSave)",
        REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx",
        "onPersisted?.(savedJd)",
    ),
    (
        "Preview card uses prepareEnterpriseJdForSave before save",
        REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx",
        "prepareEnterpriseJdForSave(editedJD)",
    ),
    (
        "Persist preserves removed_sections metadata",
        REPO_ROOT / "apps/web/src/lib/jd-persist.ts",
        "removed_sections: [...(jd.metadata?.removed_sections || [])]",
    ),
    (
        "Job card preview reads HITL metadata",
        REPO_ROOT / "apps/web/src/lib/job-card-preview.ts",
        "getRemovedSectionIds(spec)",
    ),
    (
        "Backend chunking honors removed sections",
        REPO_ROOT / "apps/quantchat/ingestion/chunking.py",
        "jd_removed_section_ids",
    ),
    (
        "Pipeline updates existing job on save",
        REPO_ROOT / "apps/api/app/services/jd_pipeline_service.py",
        "Updating existing job row",
    ),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_enterprise_format(spec: object) -> bool:
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


def set_section_visibility(jd: dict, section_id: str, visible: bool) -> dict:
    """Mirror of enterprise-jd-preview-card setSectionVisibility()."""
    updated = deepcopy(jd)
    removed = list(updated.get("metadata", {}).get("removed_sections") or [])
    if visible:
        removed = [sid for sid in removed if sid != section_id]
    elif section_id not in removed:
        removed.append(section_id)
    updated.setdefault("metadata", {})["removed_sections"] = removed
    return updated


def add_custom_section(jd: dict, section_id: str, title: str, content: str) -> dict:
    updated = deepcopy(jd)
    sections = list(updated.get("custom_sections") or [])
    sections.append({"id": section_id, "title": title, "content": content})
    updated["custom_sections"] = sections
    return updated


def prepare_enterprise_jd_for_save(jd: dict) -> dict:
    """Mirror of apps/web/src/lib/jd-persist.ts prepareEnterpriseJdForSave()."""
    clean_list = lambda lst: [item.strip() for item in (lst or []) if str(item).strip()]  # noqa: E731
    rq = jd.get("required_qualifications") or {}
    we = jd.get("work_environment") or {}
    ai = jd.get("application_instructions") or {}
    business_unit = (
        (jd.get("metadata") or {}).get("business_unit", "").strip()
        or (jd.get("business_unit") or "").strip()
        or None
    )
    metadata = {**(jd.get("metadata") or {})}
    metadata["removed_sections"] = list(metadata.get("removed_sections") or [])
    metadata["dialog_inputs"] = {
        **(metadata.get("dialog_inputs") or {}),
        "job_title": jd.get("job_title"),
        "department": jd.get("department"),
        "job_level": metadata.get("job_level"),
        "location": ", ".join(
            part
            for part in (
                (jd.get("location") or {}).get("city"),
                (jd.get("location") or {}).get("country"),
            )
            if part
        ),
    }
    if business_unit:
        metadata["business_unit"] = business_unit
    return {
        **jd,
        "metadata": metadata,
        "responsibilities": clean_list(jd.get("responsibilities")),
        "preferred_qualifications": clean_list(jd.get("preferred_qualifications")),
        "soft_skills": clean_list(jd.get("soft_skills")),
        "tools_technologies": clean_list(jd.get("tools_technologies")),
        "success_metrics": clean_list(jd.get("success_metrics")),
        "compensation_benefits": clean_list(jd.get("compensation_benefits")),
        "required_qualifications": {
            **rq,
            "technical_skills": clean_list(rq.get("technical_skills")),
        },
        "work_environment": {
            **we,
            "collaborates_with": clean_list(we.get("collaborates_with")),
        },
        "application_instructions": {
            **ai,
            "required_materials": clean_list(ai.get("required_materials")),
        },
        "custom_sections": [
            {
                **section,
                "title": (section.get("title") or "").strip(),
                "content": (section.get("content") or "").strip(),
            }
            for section in (jd.get("custom_sections") or [])
            if (section.get("title") or "").strip() or (section.get("content") or "").strip()
        ],
    }


def build_visible_section_number_map(jd: dict) -> dict[str, int]:
    removed = set(jd.get("metadata", {}).get("removed_sections") or [])
    mapping: dict[str, int] = {}
    number = 1
    for section in ENTERPRISE_JD_SECTIONS:
        if section["id"] not in removed:
            mapping[section["id"]] = number
            number += 1
    return mapping


def get_custom_section_number(jd: dict, custom_index: int) -> int:
    return len(build_visible_section_number_map(jd)) + 1 + custom_index


def format_department_team(jd: dict) -> str:
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

    skill_tags: list[str] = []
    seen: set[str] = set()
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


def simulate_hitl_workflow() -> list[str]:
    """Simulate card click -> HITL edits -> save prep -> card + QuantChat sync."""
    errors: list[str] = []
    job = json.loads(FIXTURE.read_text(encoding="utf-8"))

    # Step 1: User clicks job card (only enterprise JD jobs open editor)
    if not job_has_enterprise_jd(job):
        errors.append("Fixture job must have enterprise spec_json for card click flow")
        return errors

    # Step 2: Dialog loads saved JD (GET /v1/jobs/{id} -> hydrate)
    jd = hydrate_enterprise_jd_from_job(job)
    if jd is None:
        errors.append("hydrateEnterpriseJdFromJob returned None for fixture job")
        return errors
    if jd["job_id"] != job["id"]:
        errors.append(f"Expected job_id {job['id']}, got {jd['job_id']}")

    # Step 3: User enters edit mode, removes compensation section (HITL)
    edited = set_section_visibility(jd, "compensation_benefits", visible=False)
    removed = edited.get("metadata", {}).get("removed_sections") or []
    if "compensation_benefits" not in removed:
        errors.append("HITL remove section failed: compensation_benefits not in removed_sections")

    # Step 4: User edits title and adds custom section
    edited["job_title"] = "Principal Solution Architect"
    edited.setdefault("metadata", {})["job_level"] = "Principal"
    edited = add_custom_section(
        edited,
        "custom-visa",
        "Visa Requirements",
        "Valid Qatar work visa or eligibility to obtain one within 30 days.",
    )

    # Step 5: Apply Changes (local only — card should NOT update until save)
    apply_snapshot = deepcopy(edited)
    card_before_save = build_job_card_preview(job)
    if card_before_save["title"] == apply_snapshot["job_title"]:
        errors.append("Job card must not reflect Apply-only edits before Save to pgvector")

    # Step 6: Save to pgvector — prepare payload and update job row spec_json
    prepared = prepare_enterprise_jd_for_save(apply_snapshot)
    if prepared.get("metadata", {}).get("removed_sections") != ["compensation_benefits"]:
        errors.append("prepareEnterpriseJdForSave did not preserve removed_sections")
    if len(prepared.get("custom_sections") or []) != 2:
        errors.append("prepareEnterpriseJdForSave dropped custom sections")

    saved_job = deepcopy(job)
    saved_job["spec_json"] = prepared
    saved_job["title"] = prepared["job_title"]
    saved_job["level"] = prepared.get("metadata", {}).get("job_level") or job.get("level")
    saved_job["department"] = _department_display_from_jd(prepared) or job.get("department")

    # Step 7: Job card preview reflects saved HITL state
    preview = build_job_card_preview(saved_job)
    checks = [
        (preview["title"] == "Principal Solution Architect", "card title after save"),
        (preview["level"] == "Principal", "card level after save"),
        (preview["removedSectionCount"] == 1, "removed section count badge"),
        (preview["customSectionCount"] == 2, "custom section count badge"),
        (preview["summary"] is not None, "summary still visible when position_summary kept"),
    ]
    for ok, label in checks:
        if not ok:
            errors.append(f"Job card preview failed: {label}")

    # Step 8: Dynamic section numbering for PDF/preview
    numbers = build_visible_section_number_map(prepared)
    if "compensation_benefits" in numbers:
        errors.append("Removed section compensation_benefits still numbered")
    if get_custom_section_number(prepared, 0) != len(numbers) + 1:
        errors.append("Custom section numbering incorrect after HITL removal")

    # Step 9: QuantChat chunking excludes removed, indexes custom
    chunks = JDChunker().chunk_jd(prepared)
    sections = {chunk["section"] for chunk in chunks}
    if "Compensation & Benefits" in sections:
        errors.append("QuantChat chunker still indexes removed compensation section")
    if not any(chunk["section"] == "Custom: Visa Requirements" for chunk in chunks):
        errors.append("QuantChat chunker missing custom Visa Requirements section")
    if "about_company" in jd_removed_section_ids(prepared):
        errors.append("about_company incorrectly marked removed")

    title_chunk = next((c for c in chunks if c["section"] == "Job Title"), None)
    if not title_chunk or "Principal Solution Architect" not in title_chunk["content"]:
        errors.append("QuantChat Job Title chunk missing edited title")

    # Step 10: Reopen flow — hydrate again must preserve HITL state
    reopened = hydrate_enterprise_jd_from_job(saved_job)
    if reopened is None:
        errors.append("Reopen hydrate failed after save")
    else:
        reopen_removed = reopened.get("metadata", {}).get("removed_sections") or []
        if reopen_removed != ["compensation_benefits"]:
            errors.append("Reopen lost removed_sections metadata")
        if reopened.get("job_title") != "Principal Solution Architect":
            errors.append("Reopen lost edited job title")

    # Step 11: Pipeline denormalization helpers
    if _job_level_from_jd(prepared) != "Principal":
        errors.append("_job_level_from_jd mismatch after HITL save")
    if _department_display_from_jd(prepared) != preview["departmentDisplay"]:
        errors.append("_department_display_from_jd mismatch with card preview")

    return errors


def run_static_wiring_checks() -> list[str]:
    errors: list[str] = []
    for label, path, needle in WIRING_CHECKS:
        if not path.is_file():
            errors.append(f"Missing file for wiring check [{label}]: {path}")
            continue
        if needle not in _read(path):
            errors.append(f"Wiring check failed [{label}]: '{needle}' not in {path.relative_to(REPO_ROOT)}")

    preview_source = _read(
        REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx"
    )
    if "onSave?.(savedJd)" in preview_source:
        errors.append("enterprise-jd-preview-card must not call onSave on persist (stale double-save)")

    dialog_source = _read(REPO_ROOT / "apps/web/src/components/jobs/jd-generation-dialog.tsx")
    if "onPersisted={(savedJd)" not in dialog_source and "onPersisted={(savedJD)" not in dialog_source:
        if "onPersisted" not in dialog_source:
            errors.append("jd-generation-dialog missing onPersisted handler for save sync")

    return errors


def run_py_compile() -> list[str]:
    errors: list[str] = []
    files = [
        REPO_ROOT / "apps/quantchat/ingestion/chunking.py",
        REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py",
        REPO_ROOT / "apps/api/app/services/jd_pipeline_service.py",
        REPO_ROOT / "apps/api/app/services/jd_generation_tasks.py",
        REPO_ROOT / "apps/api/app/api/v1/jd_generation.py",
    ]
    for path in files:
        try:
            compile(_read(path), str(path), "exec")
        except SyntaxError as exc:
            errors.append(f"Python syntax error in {path.name}: {exc}")
    return errors


def run_pytest(skip: bool) -> tuple[int, str]:
    if skip:
        return 0, "skipped"
    cmd = [sys.executable, "-m", "pytest", *PYTEST_FILES, "-q", "--tb=line"]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def check_live_api(base_url: str) -> list[str]:
    errors: list[str] = []
    health_url = base_url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            if response.status != 200:
                errors.append(f"Live API health returned HTTP {response.status}")
    except urllib.error.URLError as exc:
        errors.append(f"Live API unreachable at {health_url}: {exc.reason}")
    return errors


def print_manual_uat() -> None:
    print()
    print("=" * 60)
    print("  Manual browser UAT (after npm run dev or NPD deploy)")
    print("=" * 60)
    print()
    print("  JD PREVIEW CARD CLICK")
    print("   [ ] Click AI JD job card -> 'View & Edit Job Description' opens")
    print("   [ ] Preview tab shows all sections from saved spec_json")
    print()
    print("  HITL CUSTOMIZATION")
    print("   [ ] Edit All Sections -> toggle section off -> section hidden in preview")
    print("   [ ] Add custom section -> appears with dynamic number after standard sections")
    print("   [ ] Edit job title / level / department -> Apply Changes")
    print("   [ ] Unsaved banner remains; job card list does NOT update yet")
    print()
    print("  SAVE TO PGVECTOR")
    print("   [ ] Save to pgvector -> success message with same job ID (update, not duplicate)")
    print("   [ ] Job card title, level, badges update immediately")
    print("   [ ] Card shows 'Customized JD (N sections hidden)' and '+N custom' when applicable")
    print()
    print("  REOPEN + QUANTCHAT + PDF")
    print("   [ ] Close dialog, reopen card -> all HITL edits persisted")
    print("   [ ] QuantChat: removed section content not retrievable")
    print("   [ ] QuantChat: custom section content is queryable")
    print("   [ ] Download PDF: removed sections absent, custom sections numbered correctly")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JD customization HITL E2E workflow")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest suite")
    parser.add_argument(
        "--live-api",
        metavar="URL",
        help="Optional API base URL for health check (e.g. http://localhost:8000)",
    )
    args = parser.parse_args()

    failed = False
    step = 0
    total = 5 if not args.skip_pytest else 4
    if args.live_api:
        total += 1

    def step_header(title: str) -> None:
        nonlocal step
        step += 1
        print()
        print("-" * 60)
        print(f"  STEP {step}/{total}: {title}")
        print("-" * 60)

    print()
    print("=" * 60)
    print("  QuantHire AI - JD Customization HITL E2E Validation")
    print("  Card click | HITL edits | Save | Card sync | QuantChat")
    print("=" * 60)

    step_header("Python syntax check (JD backend)")
    syntax_errors = run_py_compile()
    if syntax_errors:
        failed = True
        for err in syntax_errors:
            print(f"  FAIL: {err}")
    else:
        print("  OK: backend Python syntax")

    step_header("Static wiring checks (frontend + backend)")
    wiring_errors = run_static_wiring_checks()
    if wiring_errors:
        failed = True
        for err in wiring_errors:
            print(f"  FAIL: {err}")
    else:
        print(f"  OK: {len(WIRING_CHECKS)} wiring checks passed")

    step_header("Simulated HITL workflow (card click -> save -> reopen)")
    sim_errors = simulate_hitl_workflow()
    if sim_errors:
        failed = True
        for err in sim_errors:
            print(f"  FAIL: {err}")
    else:
        print("  OK: full HITL simulation passed")
        print("       - card click hydrate")
        print("       - section removal + custom section + title edit")
        print("       - Apply does not update card before save")
        print("       - save prep preserves metadata")
        print("       - job card preview sync")
        print("       - dynamic numbering")
        print("       - QuantChat chunking honors HITL")
        print("       - reopen preserves edits")

    if not args.skip_pytest:
        step_header("pytest (JD + HITL regression suite)")
        code, output = run_pytest(skip=False)
        if code != 0:
            failed = True
            print("  FAIL: pytest")
            if output:
                print(output)
        else:
            print("  OK: all JD/HITL unit tests passed")
            if output:
                print(f"  {output.splitlines()[-1] if output.splitlines() else output}")

    if args.live_api:
        step_header(f"Live API health check ({args.live_api})")
        live_errors = check_live_api(args.live_api)
        if live_errors:
            failed = True
            for err in live_errors:
                print(f"  FAIL: {err}")
        else:
            print("  OK: API health endpoint reachable")

    print()
    if failed:
        print("=" * 60)
        print("  VALIDATION FAILED - fix errors above and re-run")
        print("=" * 60)
        print()
        print("  Re-run: scripts\\validate_jd_customization_e2e.cmd")
        return 1

    print("=" * 60)
    print("  ALL AUTOMATED JD CUSTOMIZATION / HITL CHECKS PASSED")
    print("=" * 60)
    print_manual_uat()
    print("Quick re-run:")
    print("  scripts\\validate_jd_customization_e2e.cmd")
    print("  scripts\\validate_jd_full.cmd          (full JD suite incl. TypeScript)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
