"""Phase 1 HR-friendly JD editor copy (no pgvector in user-facing strings)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_jd_hr_copy_module_exports():
    source = _read(REPO_ROOT / "apps/web/src/lib/jd-hr-copy.ts")
    assert "Save job description" in source
    assert "Create job description with AI" in source
    assert "Edit job description" in source
    assert "pgvector" not in source


def test_enterprise_preview_uses_hr_save_not_pgvector():
    source = _read(
        REPO_ROOT / "apps/web/src/components/jobs/enterprise-jd-preview-card.tsx"
    )
    assert "JD_SAVE_BUTTON_LABEL" in source
    assert "Apply Changes" not in source
    assert "pgvector" not in source
    assert "formatJdSaveSuccessMessage" in source


def test_jd_dialog_uses_hr_titles_and_regenerate_confirm():
    source = _read(
        REPO_ROOT / "apps/web/src/components/jobs/jd-generation-dialog.tsx"
    )
    assert "JD_DIALOG_TITLE_EDIT" in source
    assert "JD_REGENERATE_CONFIRM" in source
    assert "View & Edit Job Description" not in source
    assert "Save to pgvector" not in source


def test_jd_save_success_message_copy():
    """Success banner is HR-facing — title + outcome, not raw job IDs."""
    source = _read(REPO_ROOT / "apps/web/src/lib/jd-hr-copy.ts")
    assert (
        "Your jobs list, QuantChat, and candidate matching now use this version"
        in source
    )
    return_line = next(
        line for line in source.splitlines() if "return `" in line and "✅" in line
    )
    assert "jobId" not in return_line
    assert "job_id" not in return_line
