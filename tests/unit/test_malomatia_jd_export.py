"""Unit tests for Malomatia JD Word export."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.services.malomatia_jd_export import (
    LEADER_YOE_THRESHOLD,
    build_download_filename,
    build_malomatia_docx,
    recommend_malomatia_template,
)
from app.services.malomatia_template_fill import (
    MalomatiaTemplateNotFoundError,
    resolve_template_path,
)

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "templates" / "malomatia"
HAS_TEMPLATES = (TEMPLATE_DIR / "leader_template.docx").is_file() and (
    TEMPLATE_DIR / "non_leader_template.docx"
).is_file()


def _sample_jd(**overrides):
    jd = {
        "job_title": "Data Center Manager",
        "department": "Cloud & Infrastructure Services (CIS)",
        "business_unit": "Cloud, Infrastructure & Security Services (CISS)",
        "team": "Cloud & Infrastructure Managed Services",
        "division": "Managed Infrastructure Services",
        "position_summary": (
            "The Data Center Manager is responsible for overseeing daily operations "
            "and reliability of data center facilities."
        ),
        "responsibilities": [
            "Manage overall data center operations including facilities, power, cooling, and physical security.",
            "Develop and maintain operational policies, procedures, and standards.",
            "Lead, coach, and manage data center staff and shift teams.",
        ],
        "required_qualifications": {
            "education": "Bachelor's degree in IT, Engineering, Computer Science, or related field.",
            "experience": "7–12 years of experience in data center or IT infrastructure operations.",
            "technical_skills": ["ITIL", "DCIM tools"],
        },
        "preferred_qualifications": ["Experience in project management"],
        "soft_skills": ["Leadership & Team Management", "Communication Skills"],
        "tools_technologies": ["Data Center Infrastructure Management", "Monitoring & DCIM Tools"],
        "work_environment": {
            "reports_to": "Delivery Leader – Managed Infrastructure Services",
            "collaborates_with": ["IT", "Cybersecurity", "Facilities"],
        },
        "metadata": {
            "years_of_experience": "7-12",
        },
    }
    jd.update(overrides)
    return jd


def test_recommend_ambiguous_when_range_crosses_leader_threshold():
    recommendation = recommend_malomatia_template(_sample_jd())
    assert recommendation.confidence == "ambiguous"
    assert recommendation.template_type == "leader"
    assert recommendation.yoe_minimum == 7
    assert recommendation.yoe_maximum == 12


def test_recommend_leader_for_ten_plus():
    jd = _sample_jd(
        required_qualifications={
            "education": "Bachelor's degree",
            "experience": "10+ years in infrastructure leadership",
            "technical_skills": [],
        },
        metadata={"years_of_experience": "10+"},
    )
    recommendation = recommend_malomatia_template(jd)
    assert recommendation.confidence == "high"
    assert recommendation.template_type == "leader"


def test_recommend_non_leader_for_low_yoe():
    jd = _sample_jd(
        required_qualifications={
            "education": "Bachelor's degree",
            "experience": "3-5 years in a similar role",
            "technical_skills": [],
        },
        metadata={"years_of_experience": "3-5"},
    )
    recommendation = recommend_malomatia_template(jd)
    assert recommendation.confidence == "high"
    assert recommendation.template_type == "non_leader"


def test_recommend_missing_when_no_yoe():
    jd = _sample_jd(
        metadata={},
        required_qualifications={"education": "Bachelor's", "experience": "", "technical_skills": []},
    )
    recommendation = recommend_malomatia_template(jd)
    assert recommendation.confidence == "missing"
    assert recommendation.template_type is None


def test_build_download_filename():
    filename = build_download_filename(_sample_jd(), "leader")
    assert filename.endswith("_Malomatia_Leader.docx")
    assert "Data_Center_Manager" in filename


def test_leader_threshold_constant():
    assert LEADER_YOE_THRESHOLD == 10


@pytest.mark.skipif(not HAS_TEMPLATES, reason="Official Malomatia templates not bundled")
def test_build_malomatia_docx_leader_uses_official_template():
    docx_bytes = build_malomatia_docx(_sample_jd(), "leader")
    assert docx_bytes.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "Data Center Manager" in xml
    assert "Delivery Leader" in xml


@pytest.mark.skipif(not HAS_TEMPLATES, reason="Official Malomatia templates not bundled")
def test_build_malomatia_docx_non_leader_uses_official_template():
    docx_bytes = build_malomatia_docx(_sample_jd(), "non_leader")
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "Data Center Manager" in xml
    assert "Other duties as assigned" in xml or "Operational" in xml


def test_resolve_template_path_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.malomatia_template_fill.TEMPLATE_ASSETS_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "app.services.malomatia_template_fill.DOWNLOADS_FALLBACK",
        {"leader": (), "non_leader": ()},
    )
    with pytest.raises(MalomatiaTemplateNotFoundError):
        resolve_template_path("leader")
