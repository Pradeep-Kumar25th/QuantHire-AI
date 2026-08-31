"""QuantChat pgvector retrieval parity tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
APPS_ROOT = ROOT / "apps"
for path in (str(API_ROOT), str(APPS_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_name_match_score_prefers_exact_title():
    from quantchat.retrieval.entity_match import name_match_score

    assert name_match_score("Senior AI Engineer", "Senior AI Engineer") == 100.0
    assert name_match_score("UI/UX Designer", "Junior UI/UX Designer") >= 90.0
    assert name_match_score("Engineer", "Senior AI Engineer") > 0.0
    assert name_match_score("Totally Different", "Senior AI Engineer") == 0.0


def test_document_type_clause_normalizes_jd():
    from app.services.pgvector_ingestion import _document_type_clause

    clause, params = _document_type_clause("jd")
    assert "job_description" in clause
    assert "jd" in clause
    assert params == {}

    clause, params = _document_type_clause("resume")
    assert clause == "document_type = :document_type"
    assert params == {"document_type": "resume"}


def test_entity_filter_clause_supports_multiple_names():
    from app.services.pgvector_ingestion import _entity_filter_clause

    clauses, params = _entity_filter_clause(
        entity_names=["Alice Smith", "Bob Jones"],
    )
    assert len(clauses) == 1
    assert " OR " in clauses[0]
    assert "entity_name_0" in params
    assert "entity_name_1" in params


def test_section_filter_clause_uses_ilike():
    from app.services.pgvector_ingestion import _section_filter_clause

    clause, params = _section_filter_clause("Skills")
    assert "ILIKE" in clause
    assert params["section_type"] == "%Skills%"


def test_use_pgvector_pipeline_when_vector_store_pgvector(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TARGET", "local")
    monkeypatch.setenv("VECTOR_STORE_TYPE", "pgvector")
    monkeypatch.setenv("MILVUS_ENABLED", "true")

    from app.config import Settings

    settings = Settings()
    assert settings.use_pgvector_pipeline is True


def test_use_pgvector_retrieval_production_target(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TARGET", "production")
    monkeypatch.delenv("VECTOR_STORE", raising=False)

    from quantchat.retrieval.retrieval_backend import use_pgvector_retrieval

    assert use_pgvector_retrieval() is True


def test_intent_fallback_full_jd_uses_jd_domain():
    from quantchat.core.intent_classifier import Domain, Intent, IntentClassifier

    classifier = IntentClassifier()
    result = classifier._fallback_classify("Show me the full JD for Senior AI Engineer")
    assert result.intent == Intent.FULL_DOCUMENT
    assert result.domain == Domain.JD
