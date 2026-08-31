"""Unit tests for JD human-in-the-loop chunking and persistence helpers."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"
API_ROOT = REPO_ROOT / "apps" / "api"
for path in (str(APPS_ROOT), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from quantchat.ingestion.chunking import JDChunker, jd_removed_section_ids


def test_jd_removed_section_ids_reads_metadata():
    jd = {"metadata": {"removed_sections": ["about_company", "soft_skills"]}}
    assert jd_removed_section_ids(jd) == {"about_company", "soft_skills"}


def test_jd_chunker_skips_removed_sections():
    jd = {
        "id": "jd-1",
        "job_title": "Engineer",
        "department": "Information Technology and Platform Engineering Division",
        "about_company": "Secret company paragraph that must not appear in vector retrieval.",
        "position_summary": (
            "Build reliable systems and scalable services for enterprise customers "
            "across multiple regions."
        ),
        "metadata": {"removed_sections": ["about_company"]},
    }
    chunks = JDChunker().chunk_jd(jd)
    sections = {chunk["section"] for chunk in chunks}
    assert "About Company" not in sections
    assert "Position Summary" in sections


def test_jd_chunker_keeps_department_when_other_sections_removed():
    jd = {
        "id": "jd-3",
        "job_title": "Consultant",
        "department": "Information Technology consulting and delivery organization",
        "position_summary": (
            "Support enterprise applications and deliver consulting outcomes "
            "for internal and external clients."
        ),
        "metadata": {"removed_sections": ["about_company", "soft_skills"]},
    }
    chunks = JDChunker().chunk_jd(jd)
    sections = {chunk["section"] for chunk in chunks}
    assert "Department" in sections
    assert "About Company" not in sections


def test_jd_chunker_formats_department_team_with_org_fields():
    jd = {
        "id": "jd-4",
        "job_title": "Senior Consultant L2",
        "department": "Cybersecurity",
        "team": "Identity Team",
        "division": "CyberSecurity",
        "metadata": {"job_level": "Mid-level"},
        "position_summary": (
            "Lead cybersecurity consulting engagements and deliver advisory services "
            "across enterprise clients in multiple regions."
        ),
    }
    chunks = JDChunker().chunk_jd(jd)
    dept = next(chunk for chunk in chunks if chunk["section"] == "Department")
    assert "Cybersecurity" in dept["content"]
    assert "Identity Team" in dept["content"]
    title = next(chunk for chunk in chunks if chunk["section"] == "Job Title")
    assert "Senior Consultant L2" in title["content"]
    assert "Mid-level" in title["content"]


def test_jd_chunker_indexes_short_custom_sections():
    jd = {
        "id": "jd-5",
        "job_title": "Security Analyst",
        "department": "Cybersecurity operations and governance organization",
        "position_summary": (
            "Monitor security events and support incident response activities "
            "for enterprise infrastructure and cloud platforms."
        ),
        "custom_sections": [
            {"id": "custom-visa", "title": "Visa", "content": "Qatar visa required."}
        ],
    }
    chunks = JDChunker().chunk_jd(jd)
    assert any(chunk["section"] == "Custom: Visa" for chunk in chunks)


def test_jd_chunker_indexes_custom_sections():
    jd = {
        "id": "jd-2",
        "job_title": "Analyst",
        "department": "Finance and corporate planning organization",
        "position_summary": (
            "Analyze financial reports and prepare recommendations for leadership "
            "and business stakeholders."
        ),
        "custom_sections": [
            {
                "id": "custom-1",
                "title": "Travel Policy",
                "content": (
                    "Employees may travel up to twenty percent of the time for client "
                    "engagements, workshops, and on-site delivery."
                ),
            }
        ],
    }
    chunks = JDChunker().chunk_jd(jd)
    assert any(chunk["section"] == "Custom: Travel Policy" for chunk in chunks)
    travel = next(chunk for chunk in chunks if chunk["section"] == "Custom: Travel Policy")
    assert "twenty percent" in travel["content"]
    assert travel["section"].startswith("Custom: ")
