"""Unit tests for enterprise JD visible section numbering helpers (mirrors TS logic)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"
for path in (str(APPS_ROOT),):
    if path not in sys.path:
        sys.path.insert(0, path)

# Mirror of apps/web/src/types/enterprise-jd.ts numbering helpers for regression coverage.
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


def test_contiguous_numbering_when_sections_removed():
    jd = {
        "metadata": {
            "removed_sections": [
                "about_company",
                "preferred_qualifications",
                "compensation_benefits",
            ]
        }
    }
    numbers = build_visible_section_number_map(jd)
    assert numbers["job_title"] == 1
    assert numbers["position_summary"] == 4
    assert numbers["work_environment"] == 10
    assert numbers["application_instructions"] == 12
    assert "about_company" not in numbers


def test_custom_sections_follow_visible_standard_sections():
    jd = {
        "metadata": {"removed_sections": ["success_metrics", "compensation_benefits"]},
        "custom_sections": [{"id": "c1", "title": "Soft Skills", "content": "Teamwork"}],
    }
    assert get_custom_section_number(jd, 0) == 14
    assert get_custom_section_number(jd, 1) == 15


def _set_section_visibility(jd: dict, section_id: str, visible: bool) -> dict:
    """Mirror of enterprise-jd-preview-card setSectionVisibility()."""
    removed = list(jd.get("metadata", {}).get("removed_sections") or [])
    if visible:
        removed = [sid for sid in removed if sid != section_id]
    elif section_id not in removed:
        removed.append(section_id)
    return {
        **jd,
        "metadata": {**(jd.get("metadata") or {}), "removed_sections": removed},
    }


def test_custom_sections_persist_when_standard_sections_rechecked():
    """HITL: toggling standard sections must not remove or hide custom sections."""
    jd = {
        "metadata": {"removed_sections": []},
        "custom_sections": [
            {"id": "custom-travel", "title": "Travel Policy", "content": "Up to 20% travel."},
            {"id": "custom-visa", "title": "Visa", "content": "Qatar visa required."},
        ],
    }
    jd = _set_section_visibility(jd, "compensation_benefits", visible=False)
    jd = _set_section_visibility(jd, "about_company", visible=False)
    assert len(jd["custom_sections"]) == 2
    assert get_custom_section_number(jd, 0) == 14  # 13 visible standard + 1

    jd = _set_section_visibility(jd, "compensation_benefits", visible=True)
    assert len(jd["custom_sections"]) == 2
    assert jd["custom_sections"][0]["title"] == "Travel Policy"
    assert get_custom_section_number(jd, 0) == 15  # 14 visible standard + 1
    assert get_custom_section_number(jd, 1) == 16


def test_set_section_visibility_does_not_touch_custom_sections_array():
    source = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "web"
        / "src"
        / "components"
        / "jobs"
        / "enterprise-jd-preview-card.tsx"
    ).read_text(encoding="utf-8")
    block = source.split("const setSectionVisibility", 1)[1].split("};", 1)[0]
    assert "custom_sections" not in block


def test_preview_card_uses_conditional_section_dividers():
    source = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "web"
        / "src"
        / "components"
        / "jobs"
        / "enterprise-jd-preview-card.tsx"
    ).read_text(encoding="utf-8")
    assert "contentSectionClass" in source
    assert "customSectionClass" in source
    assert "border-t my-2" not in source


def test_preview_card_uses_dynamic_section_numbering():
    source = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "web"
        / "src"
        / "components"
        / "jobs"
        / "enterprise-jd-preview-card.tsx"
    ).read_text(encoding="utf-8")
    assert "buildVisibleSectionNumberMap" in source
    assert "formatNumberedSectionLabel" in source
    assert "getCustomSectionNumber" in source
    assert "STANDARD_SECTION_OPTIONS" not in source
    assert 'addHeader(16 +' not in source


def test_pgvector_retriever_does_not_broaden_entity_filters():
    source = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "quantchat"
        / "retrieval"
        / "pgvector_retriever.py"
    ).read_text(encoding="utf-8")
    assert "retrying broader search" not in source
    assert "Do not broaden entity filters" in source


def test_fetch_full_document_prefers_latest_indexed_jd():
    source = (
        Path(__file__).resolve().parents[2]
        / "apps"
        / "api"
        / "app"
        / "services"
        / "pgvector_ingestion.py"
    ).read_text(encoding="utf-8")
    assert "MAX(created_at) AS latest_at" in source
    assert "_reconstruct_jd_full_content" in source
