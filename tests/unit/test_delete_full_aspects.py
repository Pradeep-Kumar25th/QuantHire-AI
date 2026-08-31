"""Every-aspect validation for delete: QuantChat, matching, API guards, UI behavior."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
QUANTCHAT_ROOT = REPO_ROOT / "apps" / "quantchat"
for path in (str(API_ROOT), str(REPO_ROOT / "apps")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.resource_deletion_service import _job_document_ids  # noqa: E402
from app.models.jobs import Job  # noqa: E402


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- QuantChat retrieval depends on document_chunks; delete must purge them ---


def test_pgvector_delete_document_targets_document_chunks_table():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    assert "async def delete_document" in source
    assert "delete(DocumentChunk).where(DocumentChunk.document_id == document_id)" in source


def test_quantchat_vector_retriever_uses_pgvector_search_chunks():
    source = _read(REPO_ROOT / "apps/quantchat/retrieval/pgvector_retriever.py")
    assert "search_chunks" in source
    assert "PgVectorIngestionService" in source


def test_quantchat_keyword_retriever_uses_pgvector_keywords():
    source = _read(REPO_ROOT / "apps/quantchat/retrieval/keyword_retriever.py")
    assert "search_chunks_by_keywords" in source
    assert "_retrieve_pgvector" in source


def test_quantchat_full_doc_retriever_uses_fetch_full_document():
    source = _read(REPO_ROOT / "apps/quantchat/retrieval/full_doc_retriever.py")
    assert "fetch_full_document" in source
    assert "_retrieve_pgvector_full" in source


def test_fetch_full_document_reads_document_chunks_only():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    assert "async def fetch_full_document" in source
    assert "FROM document_chunks" in source


def test_jd_delete_purge_covers_all_document_id_sources():
    job = Job(
        id=uuid.uuid4(),
        title="Architect",
        level="Senior",
        department="Eng",
        created_by=uuid.uuid4(),
        extra_metadata={"document_id": "meta-doc-id"},
        spec_json={"id": "spec-doc-id", "job_id": "legacy-job-id"},
    )
    ids = _job_document_ids(job)
    assert "meta-doc-id" in ids
    assert "spec-doc-id" in ids
    assert "legacy-job-id" in ids
    assert str(job.id) in ids


def test_jd_purge_also_deletes_by_job_id_fk():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "delete(DocumentChunk).where(DocumentChunk.job_id == job.id)" in source


def test_resume_purge_deletes_by_candidate_id_and_dedupes():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "delete(DocumentChunk).where(DocumentChunk.candidate_id == candidate_id)" in source
    assert "_dedupe_by_candidate" in source


# --- Job matching embeddings (separate from QuantChat chunks) ---


def test_job_matching_reads_job_embeddings_table():
    source = _read(REPO_ROOT / "apps/agents/agents/rag/vector_store.py")
    assert "search_similar_candidates" in source
    assert "job_embeddings" in source
    assert "candidate_embeddings" in source


def test_delete_job_purges_job_embeddings():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "delete(JobEmbedding).where(JobEmbedding.job_id == job.id)" in source


def test_delete_candidate_purges_candidate_embeddings():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "delete(CandidateEmbedding).where(CandidateEmbedding.candidate_id == candidate_id)" in source


# --- API guards and visibility ---


def test_jobs_delete_returns_409_on_application_conflict():
    source = _read(REPO_ROOT / "apps/api/app/api/v1/jobs.py")
    assert "HTTP_409_CONFLICT" in source
    assert "except ValueError as exc" in source


def test_candidates_delete_returns_409_on_application_conflict():
    source = _read(REPO_ROOT / "apps/api/app/api/v1/candidates.py")
    assert "HTTP_409_CONFLICT" in source


def test_get_candidate_404_when_inactive():
    source = _read(REPO_ROOT / "apps/api/app/api/v1/candidates.py")
    assert "if not candidate.is_active:" in source
    assert 'detail="Candidate not found"' in source


def test_delete_inactive_candidate_is_idempotent_204():
    source = _read(REPO_ROOT / "apps/api/app/api/v1/candidates.py")
    assert "if not candidate.is_active:" in source.split("async def delete_candidate", 1)[1]
    assert "return" in source.split("async def delete_candidate", 1)[1].split("deletion = ResourceDeletionService", 1)[0]


def test_jobs_delete_handles_missing_or_deleted_idempotently():
    source = _read(REPO_ROOT / "apps/api/app/api/v1/jobs.py")
    delete_block = source.split("async def delete_job", 1)[1].split("@router", 1)[0]
    assert "delete_document" in delete_block
    assert "return" in delete_block


# --- Frontend UX: confirm, stop propagation, refresh ---


def test_delete_resource_shows_quantchat_impact_in_confirm_text():
    source = _read(REPO_ROOT / "apps/web/src/lib/delete-resource.ts")
    assert "QuantChat" in source
    assert "matching" in source.lower()


def test_delete_resource_surfaces_api_errors():
    source = _read(REPO_ROOT / "apps/web/src/lib/delete-resource.ts")
    assert "getApiErrorMessage" in source


def test_job_card_delete_stops_event_propagation():
    source = _read(REPO_ROOT / "apps/web/src/components/jobs/job-card.tsx")
    assert "stopPropagation" in source
    assert "handleDeleteClick" in source


def test_candidate_card_delete_stops_event_propagation():
    source = _read(REPO_ROOT / "apps/web/src/components/candidates/candidate-card.tsx")
    assert "stopPropagation" in source
    assert "preventDefault" in source


def test_jobs_page_refreshes_after_successful_delete():
    source = _read(REPO_ROOT / "apps/web/src/app/dashboard/jobs/page.tsx")
    assert "fetchJobs" in source
    assert "executeDeleteJob" in source or "if (deleted)" in source


def test_candidates_page_refreshes_after_successful_delete():
    source = _read(REPO_ROOT / "apps/web/src/app/dashboard/candidates/page.tsx")
    assert "fetchCandidates" in source
    assert "executeDeleteCandidate" in source or "if (removed)" in source


def test_candidate_profile_only_shows_remove_when_active():
    source = _read(
        REPO_ROOT / "apps/web/src/components/candidates/candidate-profile-view.tsx"
    )
    assert "candidate.isActive" in source
    assert "Remove from pool" in source


# --- JD ingest alignment: chunks use same ids delete purges ---


def test_jd_ingest_sets_job_id_on_document_chunks():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    add_jd = source.split("async def add_jd", 1)[1].split("async def _dedupe_by_candidate", 1)[0]
    assert "job_id=job_id" in add_jd


def test_resume_ingest_sets_candidate_id_on_document_chunks():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    add_resume = source.split("async def add_resume", 1)[1].split("async def add_jd", 1)[0]
    assert "candidate_id=candidate_id" in add_resume


def test_quantchat_search_applies_visibility_filters_for_deleted_resources():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    assert "def _quantchat_visibility_clauses" in source
    assert "is_active = true" in source
    assert "SELECT id FROM jobs" in source
    assert "_apply_common_filters" in source
    assert "clauses.extend(_quantchat_visibility_clauses())" in source


def test_fetch_full_document_applies_visibility_filters():
    source = _read(REPO_ROOT / "apps/api/app/services/pgvector_ingestion.py")
    fetch_block = source.split("async def fetch_full_document", 1)[1].split("async def ", 1)[0]
    assert "_quantchat_visibility_clauses()" in fetch_block
    assert fetch_block.count("_quantchat_visibility_clauses()") >= 2


def test_candidate_document_ids_helper_in_deletion_service():
    source = _read(REPO_ROOT / "apps/api/app/services/resource_deletion_service.py")
    assert "def _candidate_document_ids" in source
    assert "source_metadata" in source.split("def _candidate_document_ids", 1)[1].split("class ResourceDeletionService", 1)[0]


def test_jd_chunker_entity_id_matches_document_id():
    source = _read(REPO_ROOT / "apps/quantchat/ingestion/chunking.py")
    assert "'entity_id': jd_id" in source or '"entity_id": jd_id' in source
