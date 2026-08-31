"""Unit tests for enterprise resume completeness helpers."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.resume_completeness import (  # noqa: E402
    compute_completeness,
    detect_section_headers,
    enrich_parsed_for_enterprise,
)


SAMPLE_RESUME = """
Jane Smith
jane@example.com | +1-555-0100

PROFESSIONAL SUMMARY
Senior engineer with 8 years building cloud systems.

EXPERIENCE
Lead Engineer | Acme Corp | 2020 - Present
- Led team of 6 delivering Azure microservices
- Reduced latency 40%

Software Engineer | Beta Inc | 2016 - 2020
- Built APIs in Python and Java

EDUCATION
B.Sc. Computer Science | State University | 2016

SKILLS
Python, Java, Azure, Kubernetes, Leadership

CERTIFICATIONS
AWS Solutions Architect

VOLUNTEER WORK
Mentor at Code for Good | 2019 - Present
"""


def test_detect_section_headers():
    headers = detect_section_headers(SAMPLE_RESUME)
    assert any("EXPERIENCE" in h.upper() for h in headers)
    assert any("SKILLS" in h.upper() for h in headers)


def test_enrich_adds_custom_sections_from_raw_text():
    parsed = {
        "name": "Jane Smith",
        "emails": ["jane@example.com"],
        "experience": [{"company": "Acme", "title": "Lead", "start": "2020-01", "end": "present", "bullets": []}],
        "skills": [{"name": "Python", "category": "technical", "confidence": 0.9}],
        "section_inventory": ["Experience", "Skills"],
        "ambiguous_fields": [],
    }
    enriched, completeness = enrich_parsed_for_enterprise(SAMPLE_RESUME, parsed)
    assert "completeness" in enriched
    assert completeness["raw_text_characters"] > 100
    titles = [s.get("title", "").upper() for s in enriched.get("custom_sections", []) if isinstance(s, dict)]
    assert any("VOLUNTEER" in t for t in titles)


def test_completeness_grade_for_populated_resume():
    parsed = {
        "name": "Jane Smith",
        "summary": "Senior engineer",
        "experience": [{"company": "Acme", "title": "Lead", "start": "2020-01", "end": "present", "bullets": ["Built systems"]}],
        "skills": [{"name": "Python", "category": "technical", "confidence": 0.9}],
        "education": [{"degree": "BSc", "institution": "State U", "year": "2016"}],
        "section_inventory": ["Summary", "Experience", "Education", "Skills"],
    }
    enriched, completeness = enrich_parsed_for_enterprise(SAMPLE_RESUME, parsed)
    assert completeness["completeness_grade"] in {"excellent", "good", "needs_review"}
