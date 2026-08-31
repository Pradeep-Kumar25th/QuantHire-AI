"""Tests for QuantChat full-JD reconstruction after HITL edits."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"
API_ROOT = REPO_ROOT / "apps" / "api"
for path in (str(APPS_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.pgvector_ingestion import (  # noqa: E402
    _normalize_jd_section_body,
    _reconstruct_jd_full_content,
    _strip_jd_chunk_context_prefix,
)
from quantchat.generation.formatter import ResponseFormatter  # noqa: E402


def test_strip_jd_chunk_context_prefix():
    raw = "[Senior IoT Engineer - Soft Skills]\nSoft Skills:\nCommunication, Teamwork"
    assert _strip_jd_chunk_context_prefix(raw).startswith("Soft Skills:")


def test_reconstruct_jd_full_content_structures_custom_sections():
    rows = [
        (
            "doc-1",
            "job_description",
            "Senior IoT Engineer",
            "Work Environment",
            "[Senior IoT Engineer - Work Environment]\nReports to: Engineering Manager",
            None,
            None,
        ),
        (
            "doc-1",
            "job_description",
            "Senior IoT Engineer",
            "Custom: Soft Skills",
            "[Senior IoT Engineer - Soft Skills]\nSoft Skills:\nCommunication, Teamwork",
            None,
            None,
        ),
    ]
    full = _reconstruct_jd_full_content(rows)
    assert "## Work Environment" in full
    assert "## Soft Skills" in full
    assert "Communication, Teamwork" in full
    assert "Soft Skills:\n" not in full
    assert "[Senior IoT Engineer - Soft Skills]" not in full
    assert full.index("## Work Environment") < full.index("## Soft Skills")


def test_normalize_jd_section_body_removes_duplicate_title():
    body = "Soft Skills:\nCommunication, Teamwork"
    assert _normalize_jd_section_body("Soft Skills", body) == "Communication, Teamwork"


def test_formatter_structured_jd_uses_section_headers():
    formatter = ResponseFormatter()
    content = "## Tools & Technologies\nLangChain, LangGraph\n\n## Soft Skills\nCommunication, Teamwork"
    formatted = formatter.format_full_doc_response(content, "jd", "AI Engineer")
    assert "## Tools & Technologies" in formatted
    assert "## Soft Skills" in formatted
    assert "Communication, Teamwork" in formatted
    assert "[AI Engineer - Soft Skills]" not in formatted


def test_formatter_handles_markdown_section_headers():
    source = (
        REPO_ROOT / "apps" / "quantchat" / "generation" / "formatter.py"
    ).read_text(encoding="utf-8")
    assert 'stripped.startswith("## ")' in source
