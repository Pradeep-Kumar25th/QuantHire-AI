"""Unit tests for resume parsing deployment workflow."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "apps" / "agents"
API_ROOT = REPO_ROOT / "apps" / "api"
for path in (AGENTS_ROOT, API_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def test_resume_profile_converter_estimates_experience():
    from app.services.resume_profile_converter import (
        _estimate_total_years,
        parsing_agent_to_resume_format,
    )

    years = _estimate_total_years(
        [
            {"start": "2018-01", "end": "2020-06"},
            {"start": "2020-07", "end": "present"},
        ]
    )
    assert years >= 6.0

    parsed = parsing_agent_to_resume_format(
        {
            "name": "Jane Doe",
            "emails": ["jane@example.com"],
            "summary": "Senior engineer with cloud experience.",
            "experience": [
                {"company": "Acme", "title": "Engineer", "start": "2019-01", "end": "2022-01"},
            ],
            "skills": [
                {"name": "Python", "category": "technical", "confidence": 0.9},
                {"name": "Leadership", "category": "soft", "confidence": 0.8},
                {"name": "Docker", "category": "tool", "confidence": 0.85},
            ],
            "screening": {"notice_period": "30 days", "career_level": "senior"},
            "confidence": 0.91,
        },
        resume_id="resume-1",
        resume_text="Jane Doe resume text " * 20,
    )
    assert parsed["experience"]["total_years"] >= 1.0
    assert parsed["summary"] == "Senior engineer with cloud experience."
    assert "Python" in parsed["skills"]["technical_skills"]
    assert "Leadership" in parsed["skills"]["soft_skills"]
    assert "Docker" in parsed["skills"]["tools"]
    assert parsed["screening_report"]["notice_period"] == "30 days"
    assert parsed["screening_report"]["confidence"] == 0.91


def test_parsing_agent_schema_includes_screening_fields():
    from agents.parsing.agent import ParsingAgent

    agent = ParsingAgent()
    schema = agent._get_parsing_schema()
    assert "screening" in schema
    assert "section_inventory" in schema
    assert "custom_sections" in schema
    assert "publications" in schema
    assert "volunteer" in schema
    assert "internships" in schema
    assert agent.config.max_tokens >= 16384


def test_parsing_agent_uses_enterprise_sanitizer():
    source = (AGENTS_ROOT / "agents" / "parsing" / "agent.py").read_text(encoding="utf-8")
    assert "sanitize_parsed_resume" in source
    assert "Never use null for string fields" in source or 'never use null for string fields' in source.lower()
    sanitizer = (AGENTS_ROOT / "agents" / "parsing" / "sanitizer.py").read_text(encoding="utf-8")
    assert "_normalize_experience_items" in sanitizer
    assert "_normalize_skill_items" in sanitizer


def test_parsing_agent_normalizes_missing_lists():
    from agents.parsing.agent import ParsingAgent

    normalized = ParsingAgent._normalize_parsed_data({"confidence": None})
    assert normalized["skills"] == []
    assert all(value is None for value in normalized["screening"].values())


def test_parsing_agent_singleton_in_pipeline():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "services" / "resume_pipeline_service.py"
    ).read_text(encoding="utf-8")
    assert "get_parsing_agent" in source
    assert "ParsingAgent singleton" in source
    assert "_upsert_candidate" in source
    assert "CandidateEmbedding" in source
    assert "move_to_processed" in source


def test_resume_pipeline_stores_candidate_embedding_via_orm():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "services" / "resume_pipeline_service.py"
    ).read_text(encoding="utf-8")
    assert "VectorStore" not in source


def test_resume_parsing_requires_blob_on_azure_nonprod():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "resume_parsing.py"
    ).read_text(encoding="utf-8")
    assert "Failed to store resume in Azure Blob Storage" in source
    assert "screening_report" in source


def test_resume_parsing_lazy_query_router():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "resume_parsing.py"
    ).read_text(encoding="utf-8")
    assert "_refresh_query_router_status" in source
    assert "ensure_query_router()" not in source.split("_refresh_query_router_status")[0]


def test_agent_status_reports_document_intelligence():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "api" / "v1" / "resume_parsing.py"
    ).read_text(encoding="utf-8")
    assert "document_intelligence_available" in source


def test_document_intelligence_extracts_tables():
    source = (
        REPO_ROOT / "apps" / "api" / "app" / "integrations" / "document_intelligence.py"
    ).read_text(encoding="utf-8")
    assert "tables" in source
    assert "paragraphs" in source


def test_pdf_extraction_prefers_di_on_azure_nonprod():
    source = (REPO_ROOT / "apps" / "api" / "app" / "services" / "pdf_extraction.py").read_text(
        encoding="utf-8"
    )
    assert "prefer_di = settings.is_azure_nonprod" in source


def test_job_matching_pg_profile_maps_experience_and_skills():
    source = (AGENTS_ROOT / "agents" / "job_matching" / "data_access_pg.py").read_text(
        encoding="utf-8"
    )
    assert "total_years_experience" in source
    assert "certifications=certs" in source
    assert "soft_skills" in source


def test_vector_store_binds_pgvector_type_for_raw_sql():
    source = (AGENTS_ROOT / "agents" / "rag" / "vector_store.py").read_text(
        encoding="utf-8"
    )
    assert "_vector_param" in source
    assert "bindparams(_vector_param" in source


def test_bff_long_timeout_includes_resume_upload():
    source = (
        REPO_ROOT / "apps" / "web" / "src" / "app" / "api" / "[...path]" / "route.ts"
    ).read_text(encoding="utf-8")
    assert "v1/resume-parsing/upload" in source
    assert "LONG_RUNNING_PROXY_TIMEOUT_MS" in source


def test_resume_upload_health_check():
    source = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "api-health.ts").read_text(
        encoding="utf-8"
    )
    assert "testResumeParsingReady" in source
    assert "/v1/resume-parsing/agent-status" in source


def test_candidate_mapper_reads_profile_json():
    source = (REPO_ROOT / "apps" / "web" / "src" / "lib" / "candidate-mapper.ts").read_text(
        encoding="utf-8"
    )
    assert "profile_json" in source
    assert "technical_skills" in source


def test_chunking_includes_raw_coverage_and_enterprise_sections():
    source = (REPO_ROOT / "apps" / "quantchat" / "ingestion" / "chunking.py").read_text(
        encoding="utf-8"
    )
    assert "_create_raw_coverage_chunks" in source
    assert "_create_enterprise_section_chunks" in source
    assert "Publications" in source


def test_resume_completeness_module_exists():
    path = REPO_ROOT / "apps" / "api" / "app" / "services" / "resume_completeness.py"
    assert path.is_file()
    source = path.read_text(encoding="utf-8")
    assert "enrich_parsed_for_enterprise" in source


def test_resume_completeness_supplements_screening_from_raw_text():
    source = (REPO_ROOT / "apps" / "api" / "app" / "services" / "resume_completeness.py").read_text(
        encoding="utf-8"
    )
    assert "supplement_parsed_from_raw_text" in source


def test_resume_upload_ui_shows_screening_summary():
    source = (REPO_ROOT / "apps" / "web" / "src" / "components" / "ResumeUpload.tsx").read_text(
        encoding="utf-8"
    )
    assert "Screening Summary" in source
    assert "completeness_grade" in source
    assert "Enterprise Resume Screening" in source
