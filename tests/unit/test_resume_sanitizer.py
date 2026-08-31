"""Unit tests for enterprise resume sanitizer — any layout / LLM shape."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "apps" / "agents"
if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from agents.parsing.agent import ParsedResume, ParsingAgent  # noqa: E402
from agents.parsing.sanitizer import sanitize_parsed_resume  # noqa: E402


def test_sanitizer_handles_null_language_proficiency():
    data = sanitize_parsed_resume(
        {
            "languages": [
                {"language": "English", "proficiency": None},
                {"language": "French", "proficiency": None},
            ]
        }
    )
    resume = ParsedResume(**data)
    assert resume.languages[0]["proficiency"] == ""


def test_sanitizer_expands_comma_separated_languages():
    data = sanitize_parsed_resume(
        {"languages": [{"language": "English, Hindi, Arabic", "proficiency": None}]}
    )
    assert len(data["languages"]) == 3


def test_sanitizer_normalizes_skill_strings_and_aliases():
    data = sanitize_parsed_resume(
        {
            "skills": [
                "Python, Java, SQL",
                {"skill": "LangGraph", "type": "tool"},
                {"name": "Leadership", "category": "soft", "confidence": None},
            ]
        }
    )
    names = {item["name"] for item in data["skills"]}
    assert "Python" in names
    assert "LangGraph" in names
    assert "Leadership" in names


def test_sanitizer_normalizes_experience_field_aliases():
    data = sanitize_parsed_resume(
        {
            "experience": [
                {
                    "employer": "Acme Corp",
                    "job_title": "Engineer",
                    "date_from": "2019-01",
                    "date_to": "2022-06",
                    "highlights": ["Built APIs", "Led team"],
                }
            ]
        }
    )
    assert data["experience"][0]["company"] == "Acme Corp"
    assert data["experience"][0]["title"] == "Engineer"
    assert len(data["experience"][0]["bullets"]) == 2


def test_sanitizer_extracts_email_from_raw_text():
    raw = "Contact: jane.doe@company.com | +1 555 0100"
    data = sanitize_parsed_resume({"name": "Jane Doe"}, raw_text=raw)
    assert "jane.doe@company.com" in data["emails"]


def test_sanitizer_passes_messy_llm_payload_through_pydantic():
    messy = sanitize_parsed_resume(
        {
            "name": "Candidate",
            "emails": ["c@example.com"],
            "languages": [{"language": "Spanish", "proficiency": None}],
            "certificates": [{"name": "CKAD", "issuer": None, "date": None, "credential_id": None}],
            "awards": [{"title": "Top Performer"}],
            "skills": ["Docker, Kubernetes"],
            "custom_sections": [{"title": "Hobbies", "content": "Chess and mentoring"}],
            "confidence": None,
        }
    )
    resume = ParsingAgent._validate_parsed_resume(messy)
    assert resume.name == "Candidate"
    assert resume.certificates[0]["issuer"] == ""
    assert resume.awards[0] == "Top Performer"
