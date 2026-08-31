"""Unit tests for ResourceDeletionService (job/JD and candidate/resume purge)."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models.candidates import Candidate  # noqa: E402
from app.models.jobs import Job  # noqa: E402
from app.services.resource_deletion_service import (  # noqa: E402
    ResourceDeletionService,
    _candidate_document_ids,
    _job_document_ids,
)


def _scalar_result(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _rowcount_result(count: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = count
    return result


@pytest.fixture
def session() -> AsyncMock:
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.delete = MagicMock(return_value=None)
    mock.flush = AsyncMock()
    mock.commit = AsyncMock()
    return mock


def test_job_document_ids_collects_metadata_and_spec():
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        title="Consultant",
        level="Senior",
        department="Cyber",
        extra_metadata={"document_id": "doc-abc"},
        spec_json={"id": "spec-xyz", "job_title": "Consultant", "milvus_id": "mv-1"},
    )
    ids = _job_document_ids(job)
    assert str(job_id) in ids
    assert "doc-abc" in ids
    assert "spec-xyz" in ids
    assert "mv-1" in ids


def test_candidate_document_ids_collects_profile_and_source_metadata():
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        name="Jane",
        email="jane@example.com",
        profile_json={"id": str(candidate_id), "resume_id": "legacy-resume-id"},
        source_metadata={"resume_id": "upload-resume-id", "document_id": "doc-meta"},
    )
    ids = _candidate_document_ids(candidate)
    assert str(candidate_id) in ids
    assert "legacy-resume-id" in ids
    assert "upload-resume-id" in ids
    assert "doc-meta" in ids


@pytest.mark.asyncio
async def test_delete_job_blocks_when_applications_exist(session: AsyncMock) -> None:
    job_id = uuid.uuid4()
    job = Job(id=job_id, title="Engineer", level="Senior", department="Eng")
    session.execute.return_value = _scalar_result(2)

    service = ResourceDeletionService(session)
    with pytest.raises(ValueError, match="2 active application"):
        await service.delete_job(job)

    session.delete.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_job_purges_vectors_and_hard_deletes(session: AsyncMock) -> None:
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        title="Consultant",
        level="Senior",
        department="Cyber",
        extra_metadata={"document_id": "doc-123"},
    )
    session.execute.side_effect = [
        _scalar_result(0),
        _rowcount_result(3),
        _rowcount_result(1),
    ]

    with patch.object(
        ResourceDeletionService,
        "__init__",
        lambda self, s: None,
    ):
        service = ResourceDeletionService(session)
        service.session = session
        service.ingestion = AsyncMock()
        service.ingestion.delete_document = AsyncMock(return_value=2)

        result = await service.delete_job(job)

    assert result["job_id"] == str(job_id)
    assert result["chunks_removed"] >= 2
    session.delete.assert_called_once_with(job)
    session.commit.assert_called_once()
    assert service.ingestion.delete_document.await_count >= 1


@pytest.mark.asyncio
async def test_delete_candidate_soft_deletes_and_purges_vectors(session: AsyncMock) -> None:
    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        name="Jane Doe",
        email="jane@example.com",
        is_active=True,
        profile_json={"id": "resume-abc"},
    )
    session.execute.side_effect = [
        _scalar_result(0),
        _rowcount_result(4),
        _rowcount_result(1),
    ]

    with patch.object(
        ResourceDeletionService,
        "__init__",
        lambda self, s: None,
    ):
        service = ResourceDeletionService(session)
        service.session = session
        service.ingestion = AsyncMock()
        service.ingestion.delete_document = AsyncMock(return_value=2)
        service.ingestion._dedupe_by_candidate = AsyncMock()

        result = await service.delete_candidate(candidate)

    assert result["candidate_id"] == str(candidate_id)
    assert candidate.is_active is False
    assert candidate.deletion_requested is True
    session.commit.assert_called_once()
    service.ingestion._dedupe_by_candidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_candidate_blocks_when_applications_exist(session: AsyncMock) -> None:
    candidate = Candidate(
        id=uuid.uuid4(),
        name="John",
        email="john@example.com",
    )
    session.execute.return_value = _scalar_result(1)

    service = ResourceDeletionService(session)
    with pytest.raises(ValueError, match="1 application"):
        await service.delete_candidate(candidate)

    session.commit.assert_not_called()
