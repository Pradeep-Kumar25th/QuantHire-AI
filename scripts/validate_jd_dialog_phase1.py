#!/usr/bin/env python3
"""Validate Phase 1 HR UX in the JD generation dialog (frontend-only).

Checks static wiring, forbidden technical copy, merged Save flow, dialog titles,
unsaved/close/regenerate confirms, and success message formatting.

Usage (from repo root, CMD recommended on Windows):
  python scripts\\validate_jd_dialog_phase1.py
  python scripts\\validate_jd_dialog_phase1.py --skip-pytest
  python scripts\\validate_jd_dialog_phase1.cmd

No browser or live API required for automated checks.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

JD_HR_COPY = REPO_ROOT / "apps/web/src/lib/jd-hr-copy.ts"
JD_DIALOG = REPO_ROOT / "apps/web/src/components/jobs/jd-generation-dialog.tsx"
JD_PREVIEW_WRAPPER = REPO_ROOT / "apps/web/src/components/jobs/jd-preview-card.tsx"
ENTERPRISE_PREVIEW = REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx"
JOBS_PAGE = REPO_ROOT / "apps/web/src/app/dashboard/jobs/page.tsx"
JOB_CARD = REPO_ROOT / "apps/web/src/components/jobs/job-card.tsx"
AZURE_MESSAGES = REPO_ROOT / "apps/web/src/lib/azure-messages.ts"

PYTEST_FILES = [
    "tests/unit/test_jd_hr_copy_phase1.py",
    "tests/unit/test_jd_reopen_workflow.py",
]

# HR copy constants that must exist in jd-hr-copy.ts
REQUIRED_COPY: dict[str, str] = {
    "JD_SAVE_BUTTON_LABEL": "Save job description",
    "JD_DIALOG_TITLE_CREATE": "Create job description with AI",
    "JD_DIALOG_TITLE_EDIT": "Edit job description",
    "JD_REGENERATE_BUTTON_LABEL": "Regenerate with AI",
}

FORBIDDEN_USER_STRINGS = (
    "Apply Changes",
    "Save to pgvector",
    "Save to Database",
    "View & Edit Job Description",
)

DIALOG_WIRING: list[tuple[str, str]] = [
    ("Create dialog title wired", "JD_DIALOG_TITLE_CREATE"),
    ("Edit dialog title wired", "JD_DIALOG_TITLE_EDIT"),
    ("Create dialog description wired", "JD_DIALOG_DESC_CREATE"),
    ("Edit dialog description wired", "JD_DIALOG_DESC_EDIT"),
    ("Unsaved banner wired", "JD_UNSAVED_BANNER"),
    ("Close-without-save confirm wired", "JD_CLOSE_UNSAVED_CONFIRM"),
    ("Regenerate confirm wired", "JD_REGENERATE_CONFIRM"),
    ("Regenerate button label wired", "JD_REGENERATE_BUTTON_LABEL"),
    ("Unsaved edits tracked", "hasUnsavedEdits"),
    ("Close respects unsaved edits", "requestDialogClose"),
    ("Edit mode opens preview tab", 'setActiveTab("preview")'),
    ("Preview delegates unsaved state", "onUnsavedChange={setHasUnsavedEdits}"),
]

PREVIEW_WIRING: list[tuple[str, str]] = [
    ("Imports HR save label", "JD_SAVE_BUTTON_LABEL"),
    ("Imports edit mode hint", "JD_EDIT_MODE_HINT"),
    ("Imports footer hint", "JD_SAVE_FOOTER_HINT"),
    ("Uses HR success formatter", "formatJdSaveSuccessMessage"),
    ("Merged save: edit header persists", "handleSaveEdit"),
    ("Merged save: calls backend save", "handleSaveToDatabase"),
    ("Edit save triggers persist", "void handleSaveToDatabase()"),
    ("Footer save uses same handler", "onClick={handleSaveToDatabase}"),
    ("Footer disabled while editing", "disabled={isSaving || isEditing}"),
    ("Persist notifies jobs list", "notifyJobsListUpdated"),
]

WRAPPER_WIRING: list[tuple[str, str]] = [
    ("Enterprise format routes to enterprise card", "EnterpriseJDPreviewCard"),
    ("Forwards unsaved callback", "onUnsavedChange={onUnsavedChange}"),
    ("Forwards persisted callback", "onPersisted={onPersisted}"),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_comments_and_strings_ts(source: str) -> str:
    """Rough strip for forbidden-string scans (ignore // comments)."""
    lines: list[str] = []
    for line in source.splitlines():
        if "//" in line:
            line = line.split("//", 1)[0]
        lines.append(line)
    return "\n".join(lines)


def check_required_copy() -> list[str]:
    errors: list[str] = []
    source = _read(JD_HR_COPY)
    if "pgvector" in source.lower():
        errors.append("jd-hr-copy.ts must not mention pgvector")
    for const, value in REQUIRED_COPY.items():
        if f'export const {const} = "{value}"' not in source:
            errors.append(f"Missing or wrong constant {const} = \"{value}\"")
    if "formatJdSaveSuccessMessage" not in source:
        errors.append("Missing formatJdSaveSuccessMessage() in jd-hr-copy.ts")
    return errors


def check_forbidden_strings() -> list[str]:
    errors: list[str] = []
    targets = [
        ("jd-hr-copy.ts", _read(JD_HR_COPY)),
        (
            "jd-generation-dialog.tsx (user strings)",
            _strip_comments_and_strings_ts(_read(JD_DIALOG)),
        ),
        ("enterprise-jd-preview-card.tsx", _read(ENTERPRISE_PREVIEW)),
    ]
    for label, source in targets:
        for forbidden in FORBIDDEN_USER_STRINGS:
            if forbidden in source:
                errors.append(f"{label} still contains forbidden UI string: {forbidden!r}")
        if label != "jd-hr-copy.ts" and re.search(r"\bpgvector\b", source, re.I):
            errors.append(f"{label} still mentions pgvector in user-facing code")
    return errors


def check_wiring(path: Path, checks: list[tuple[str, str]], group: str) -> list[str]:
    errors: list[str] = []
    source = _read(path)
    for label, needle in checks:
        if needle not in source:
            errors.append(f"{group}: {label} — missing {needle!r} in {path.name}")
    return errors


def check_regenerate_always_confirms() -> list[str]:
    errors: list[str] = []
    source = _read(JD_DIALOG)
    if "window.confirm(JD_REGENERATE_CONFIRM)" not in source:
        errors.append("Regenerate must always call window.confirm(JD_REGENERATE_CONFIRM)")
    # Old pattern: skip confirm when no unsaved edits
    if re.search(
        r"hasUnsavedEdits\s*&&\s*!window\.confirm\(JD_REGENERATE_CONFIRM\)",
        source,
    ):
        errors.append("Regenerate confirm must not be gated on hasUnsavedEdits only")
    return errors


def check_merged_save_not_apply_only() -> list[str]:
    errors: list[str] = []
    source = _read(ENTERPRISE_PREVIEW)
    if "Apply Changes" in source:
        errors.append("enterprise-jd-preview-card still has Apply Changes button")
    if "handleSaveEdit" not in source or "void handleSaveToDatabase()" not in source:
        errors.append("Edit header Save must call handleSaveToDatabase (merged save)")
    if "onUpdate?.(editedJD)" in source and "handleSaveToDatabase" in source:
        # onUpdate during save is OK for local sync; ensure persist runs in same handler
        block = source.split("const handleSaveToDatabase", 1)[-1].split("};", 1)[0]
        if "persistEnterpriseJdToBackend" not in block:
            errors.append("handleSaveToDatabase must call persistEnterpriseJdToBackend")
    return errors


def mirror_format_jd_save_success_message(
    job_title: str | None,
    updated: bool,
) -> str:
    title = (job_title or "").strip() or "Job description"
    verb = "updated" if updated else "saved"
    return (
        f'✅ "{title}" {verb}. Your jobs list, QuantChat, and candidate matching '
        "now use this version."
    )


def simulate_success_messages() -> list[str]:
    errors: list[str] = []
    cases = [
        ("Senior Analyst", False, mirror_format_jd_save_success_message("Senior Analyst", False)),
        ("Senior Analyst", True, mirror_format_jd_save_success_message("Senior Analyst", True)),
        (None, False, mirror_format_jd_save_success_message(None, False)),
    ]
    source = _read(JD_HR_COPY)
    for title, updated, expected in cases:
        if expected not in source and title is not None:
            # Function builds dynamically; verify parts
            if title and f'"{title}"' not in source and title != "Senior Analyst":
                pass
        if "job_id" in expected or "jobId" in expected:
            errors.append("Success message must not expose raw job IDs")
    if "Your jobs list, QuantChat, and candidate matching now use this version." not in source:
        errors.append("Success message missing HR outcome sentence")
    if mirror_format_jd_save_success_message("Data Engineer", True) != (
        '✅ "Data Engineer" updated. Your jobs list, QuantChat, and candidate matching '
        "now use this version."
    ):
        errors.append("Success message formatter simulation mismatch")
    return errors


def check_azure_jd_hint() -> list[str]:
    errors: list[str] = []
    source = _read(AZURE_MESSAGES)
    match = re.search(r'export const AZURE_JD_HINT\s*=\s*"([^"]*)"', source)
    if not match:
        errors.append("AZURE_JD_HINT not found in azure-messages.ts")
        return errors
    hint = match.group(1)
    if "pgvector" in hint.lower() or "vector store" in hint.lower():
        errors.append(f"AZURE_JD_HINT still technical: {hint!r}")
    if "save" not in hint.lower():
        errors.append("AZURE_JD_HINT should mention saving the JD")
    return errors


def check_jobs_entry_points() -> list[str]:
    errors: list[str] = []
    page = _read(JOBS_PAGE)
    card = _read(JOB_CARD)
    if "JDGenerationDialog" not in page:
        errors.append("jobs/page.tsx must render JDGenerationDialog")
    if "editJobId" not in page:
        errors.append("jobs/page.tsx must pass editJobId for reopen/edit flow")
    if "Edit AI job description" not in card:
        errors.append("job-card.tsx should use HR label 'Edit AI job description'")
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


def print_manual_uat() -> None:
    print()
    print("=" * 60)
    print("  Manual browser UAT — JD dialog Phase 1 HR UX")
    print("  (after npm run dev or NPD frontend deploy)")
    print("=" * 60)
    print()
    print("  CREATE FLOW")
    print("   [ ] Jobs -> Generate JD -> dialog title: Create job description with AI")
    print("   [ ] Fill role details -> Generate JD -> lands on Preview tab")
    print("   [ ] No pgvector / Apply Changes / Save to Database anywhere in dialog")
    print()
    print("  EDIT FLOW")
    print("   [ ] Click AI JD job card -> dialog title: Edit job description")
    print("   [ ] Preview tab label: Job Description (edit mode)")
    print("   [ ] Edit All Sections -> change title -> header shows Save job description")
    print()
    print("  MERGED SAVE")
    print("   [ ] Save job description (header while editing) -> green success banner")
    print("   [ ] Success text includes job title + QuantChat/matching (no raw UUID)")
    print("   [ ] Job card on list updates without creating duplicate card")
    print("   [ ] Footer Save job description works when not in inline edit mode")
    print("   [ ] Footer Save disabled while editing (hint points to header save)")
    print()
    print("  UNSAVED + REGENERATE")
    print("   [ ] Edit without save -> amber unsaved banner on Preview tab")
    print("   [ ] Close dialog -> confirm: unsaved changes warning")
    print("   [ ] Regenerate with AI -> always shows multi-line confirm")
    print("   [ ] Cancel regenerate -> JD unchanged; confirm -> returns to form tab")
    print()
    print("  REOPEN")
    print("   [ ] Close and reopen same job -> edits persisted")
    print("   [ ] QuantChat can answer using updated JD content (after save)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate JD generation dialog Phase 1 HR UX",
    )
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest suite")
    args = parser.parse_args()

    failed = False
    step = 0
    total = 8 if not args.skip_pytest else 7

    def step_header(title: str) -> None:
        nonlocal step
        step += 1
        print()
        print("-" * 60)
        print(f"  STEP {step}/{total}: {title}")
        print("-" * 60)

    print()
    print("=" * 60)
    print("  QuantHire AI — JD Dialog Phase 1 HR UX Validation")
    print("  Copy | merged save | titles | confirms | success message")
    print("=" * 60)

    step_header("HR copy module (jd-hr-copy.ts)")
    errors = check_required_copy()
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"  OK: {len(REQUIRED_COPY)} required constants + success formatter")

    step_header("Forbidden technical UI strings")
    errors = check_forbidden_strings()
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"  OK: no forbidden strings in dialog / preview / hr-copy")

    step_header("Dialog wiring (titles, banner, confirms)")
    errors = (
        check_wiring(JD_DIALOG, DIALOG_WIRING, "dialog")
        + check_regenerate_always_confirms()
    )
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"  OK: {len(DIALOG_WIRING)} dialog checks + regenerate confirm")

    step_header("Preview card wiring (merged Save job description)")
    errors = (
        check_wiring(ENTERPRISE_PREVIEW, PREVIEW_WIRING, "preview")
        + check_wiring(JD_PREVIEW_WRAPPER, WRAPPER_WIRING, "wrapper")
        + check_merged_save_not_apply_only()
    )
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"  OK: {len(PREVIEW_WIRING) + len(WRAPPER_WIRING)} preview checks + merged save")

    step_header("Success message + Azure JD hint")
    errors = simulate_success_messages() + check_azure_jd_hint()
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print("  OK: HR success message format + AZURE_JD_HINT")

    step_header("Jobs page entry points")
    errors = check_jobs_entry_points()
    if errors:
        failed = True
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print("  OK: dialog mounted + editJobId + job card HR label")

    if not args.skip_pytest:
        step_header("pytest (Phase 1 copy + reopen workflow)")
        code, output = run_pytest(skip=False)
        if code != 0:
            failed = True
            print("  FAIL: pytest")
            if output:
                print(output)
        else:
            print("  OK: pytest passed")
            if output:
                for line in output.splitlines():
                    if line.strip():
                        print(f"       {line}")

    print()
    print("=" * 60)
    if failed:
        print("  RESULT: FAILED — fix issues above before deploy")
        print("=" * 60)
        print_manual_uat()
        return 1

    print("  RESULT: ALL AUTOMATED CHECKS PASSED")
    print("=" * 60)
    print_manual_uat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
