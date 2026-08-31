"""Unit tests for JD pipeline Postgres field normalization."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.jd_pipeline_service import (  # noqa: E402
    _department_display_from_jd,
    _job_level_from_jd,
    _location_to_str,
    _remote_allowed_from_jd,
    _requirements_to_str,
)


def test_location_to_str_from_structured_dict():
    location = {
        "city": "Pune",
        "country": "Maharashtra",
        "work_model": "On-site",
    }
    assert _location_to_str(location) == "Pune, Maharashtra (On-site)"


def test_requirements_to_str_from_structured_dict():
    jd_data = {
        "required_qualifications": {
            "education": "B.Tech/MCA",
            "experience": "1-3 years of relevant experience",
            "technical_skills": ["Java", ".NET", "SpringBoot"],
        }
    }
    text = _requirements_to_str(jd_data)
    assert "Education: B.Tech/MCA" in text
    assert "Experience: 1-3 years of relevant experience" in text
    assert "Technical Skills: Java, .NET, SpringBoot" in text


def test_remote_allowed_from_work_model():
    assert _remote_allowed_from_jd({"location": {"work_model": "Remote"}}) is True
    assert _remote_allowed_from_jd({"location": {"work_model": "On-site"}}) is False


def test_job_level_from_jd_metadata():
    jd = {"metadata": {"job_level": "Senior"}}
    assert _job_level_from_jd(jd) == "Senior"


def test_department_display_from_jd_includes_team_and_division():
    jd = {
        "department": "Cybersecurity",
        "team": "Identity Team",
        "division": "CyberSecurity",
    }
    assert _department_display_from_jd(jd) == "Cybersecurity / Identity Team / CyberSecurity"
