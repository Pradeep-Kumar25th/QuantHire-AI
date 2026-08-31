"""Tests for QuantHire sample resume (Aarav Mehta AI Engineer fixture)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "apps" / "agents"
API_ROOT = REPO_ROOT / "apps" / "api"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "aarav_mehta_sample_resume.txt"

for path in (AGENTS_ROOT, API_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def _fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_aarav_fixture_detects_key_sections():
    from app.services.resume_completeness import detect_section_headers

    headers = detect_section_headers(_fixture_text())
    joined = " ".join(headers).upper()
    assert "EXPERIENCE" in joined or "PROFESSIONAL EXPERIENCE" in _fixture_text().upper()
    assert "EDUCATION" in joined
    assert "CERTIFICATION" in joined or "CERTIFICATIONS" in _fixture_text().upper()


def test_aarav_fixture_supplements_languages_and_screening():
    from app.services.resume_completeness import enrich_parsed_for_enterprise

    parsed = {
        "name": "AARAV MEHTA",
        "emails": ["aarav.mehta.ai@example.com"],
        "experience": [
            {
                "company": "Nexora Digital Solutions",
                "title": "Principal AI Engineer",
                "start": "2023-04",
                "end": "present",
                "bullets": ["Built agent platform"],
            }
        ],
        "skills": [{"name": "Python", "category": "technical", "confidence": 0.9}],
        "education": [{"degree": "M.Tech", "institution": "NIDE", "year": "2018"}],
        "languages": [
            {"language": "English", "proficiency": None},
            {"language": "Hindi", "proficiency": None},
        ],
        "section_inventory": ["Summary", "Experience", "Education"],
        "ambiguous_fields": [],
    }
    enriched, completeness = enrich_parsed_for_enterprise(_fixture_text(), parsed)
    language_names = {
        str(item.get("language", "")).lower()
        for item in enriched.get("languages", [])
        if isinstance(item, dict)
    }
    assert "english" in language_names
    assert "hindi" in language_names
    assert "gujarati" in language_names
    screening = enriched.get("screening") or {}
    assert screening.get("work_authorization") == "India"
    assert screening.get("availability") == "30 days"
    assert completeness["completeness_grade"] in {"excellent", "good", "needs_review"}


def test_aarav_null_language_proficiency_passes_pydantic():
    from agents.parsing.agent import ParsedResume, ParsingAgent

    normalized = ParsingAgent._normalize_parsed_data(
        {
            "name": "AARAV MEHTA",
            "emails": ["aarav.mehta.ai@example.com"],
            "languages": [
                {"language": "English, Hindi, Gujarati", "proficiency": None},
            ],
            "confidence": 0.92,
        }
    )
    resume = ParsedResume(**normalized)
    assert len(resume.languages) == 3
    assert resume.languages[0]["language"] == "English"


def test_aarav_converter_produces_screening_report():
    from app.services.resume_completeness import enrich_parsed_for_enterprise
    from app.services.resume_profile_converter import parsing_agent_to_resume_format

    parsed = {
        "name": "AARAV MEHTA",
        "emails": ["aarav.mehta.ai@example.com"],
        "phones": ["+91 98765 43210"],
        "locations": ["Bengaluru, Karnataka, India"],
        "summary": "AI/ML engineer with 7+ years of experience.",
        "experience": [
            {
                "company": "Nexora Digital Solutions",
                "title": "Principal AI Engineer",
                "start": "2023-04",
                "end": "present",
                "bullets": ["Architected recruitment intelligence platform"],
            },
            {
                "company": "QuantEdge Systems",
                "title": "Senior Machine Learning Engineer",
                "start": "2020-07",
                "end": "2023-03",
                "bullets": ["Built hybrid semantic search platform"],
            },
        ],
        "skills": [
            {"name": "LangGraph", "category": "technical", "confidence": 0.95},
            {"name": "Python", "category": "technical", "confidence": 0.95},
        ],
        "education": [
            {"degree": "M.Tech", "institution": "National Institute of Digital Engineering", "year": "2018"},
        ],
        "certificates": [{"name": "Azure AI Engineer Associate", "issuer": "Microsoft", "date": "2025"}],
        "projects": [{"name": "Agentic Resume Intelligence", "description": "Resume parsing service"}],
        "awards": ["Engineering Excellence Award - 2025"],
        "languages": [{"language": "English", "proficiency": None}],
        "screening": {},
        "confidence": 0.91,
        "ambiguous_fields": [],
    }
    enriched, _ = enrich_parsed_for_enterprise(_fixture_text(), parsed)
    nested = parsing_agent_to_resume_format(
        enriched,
        resume_id="test-resume-id",
        resume_text=_fixture_text(),
    )
    report = nested["screening_report"]
    assert nested["personal_info"]["email"] == "aarav.mehta.ai@example.com"
    assert nested["experience"]["total_years"] >= 5.0
    assert report["experience_entries"] == 2
    assert report["work_authorization"] == "India"
    assert "gujarati" in {lang.lower() for lang in nested.get("languages", []) if isinstance(lang, str)}
