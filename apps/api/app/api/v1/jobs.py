"""Job management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_policy import auth_enforced, require_authenticated_user
from app.config import settings
from app.core.tenancy import assert_job_access, scope_jobs_query
from app.database import get_session
from app.middleware.rbac import Permission, require_permission
from app.models.jobs import Job, JobStatus
from app.services.resource_deletion_service import ResourceDeletionService

router = APIRouter()


class JobCreate(BaseModel):
    """Job creation schema."""

    model_config = ConfigDict(extra="forbid")

    title: str
    level: str
    department: str
    location: Optional[str] = None
    remote_allowed: bool = False
    description: str = ""
    requirements: str = ""
    compensation_range: dict = {}


class JobUpdate(BaseModel):
    """Mutable job fields only — status changes use dedicated endpoints."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    level: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    remote_allowed: Optional[bool] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    compensation_range: Optional[dict] = None


class JobResponse(BaseModel):
    """Job response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    level: str
    department: str
    location: Optional[str]
    remote_allowed: bool
    status: JobStatus
    description: str
    requirements: str
    compensation_range: dict
    spec_json: dict
    openings_count: int
    filled_count: int


class MatchedCandidate(BaseModel):
    """Matched candidate schema."""

    candidate_id: UUID
    name: str
    email: str
    match_score: float
    rationale: str
    evidence: List[str]


async def get_job_actor(
    user: Optional[dict] = Depends(require_authenticated_user),
) -> dict:
    if user is not None:
        return user
    if auth_enforced() or settings.is_hardened:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return {"id": "00000000-0000-0000-0000-000000000000", "role": "admin"}


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission([Permission.CREATE_JOB]))],
)
@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
    dependencies=[Depends(require_permission([Permission.CREATE_JOB]))],
)
async def create_job(
    job_data: JobCreate,
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> Job:
    """Create a new job posting with AI-powered spec generation."""
    from app.services.job_service import JobService

    job_service = JobService(session)
    job = await job_service.create_job_with_ai(
        title=job_data.title,
        description=job_data.description,
        level=job_data.level,
        department=job_data.department,
        location=job_data.location,
        remote_allowed=job_data.remote_allowed,
        created_by=UUID(actor["id"]),
    )
    return job


@router.get("", response_model=List[JobResponse])
@router.get("/", response_model=List[JobResponse], include_in_schema=False)
async def list_jobs(
    status: Optional[JobStatus] = None,
    department: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> List[Job]:
    """List jobs visible to the authenticated user."""
    query = select(Job)
    query = scope_jobs_query(query, actor, Job)

    if status:
        query = query.where(Job.status == status)
    if department:
        query = query.where(Job.department == department)

    query = query.offset(skip).limit(limit).order_by(Job.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> Job:
    """Get job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    assert_job_access(job, actor)
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    job_data: JobUpdate,
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> Job:
    """Update mutable job fields."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    assert_job_access(job, actor)

    for field, value in job_data.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    await session.commit()
    await session.refresh(job)
    return job


@router.post("/{job_id}/publish")
async def publish_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> dict:
    """Publish a job (change status to OPEN)."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    assert_job_access(job, actor)
    job.status = JobStatus.OPEN
    await session.commit()
    return {"message": "Job published successfully", "job_id": job_id}


@router.post("/{job_id}/match", response_model=List[MatchedCandidate])
async def match_candidates(
    job_id: UUID,
    top: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> List[MatchedCandidate]:
    """Find and rank candidates for a job using vector search."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    assert_job_access(job, actor)

    from app.services.job_service import JobService

    job_service = JobService(session)
    matches = await job_service.match_candidates(job_id, top_k=top)

    return [
        MatchedCandidate(
            candidate_id=UUID(match["candidate_id"]),
            name=match["name"],
            email=match["email"],
            match_score=match["match_score"],
            rationale="Strong match based on skills and experience",
            evidence=[
                f"{len(match['skills'])} relevant skills",
                f"{match['experience']} years experience",
            ],
        )
        for match in matches
    ]


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission([Permission.UPDATE_JOB]))],
)
async def delete_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    actor: dict = Depends(get_job_actor),
) -> None:
    """Delete job and purge indexed JD chunks from QuantChat."""
    job: Optional[Job] = None
    try:
        parsed_uuid = UUID(job_id)
        result = await session.execute(select(Job).where(Job.id == parsed_uuid))
        job = result.scalar_one_or_none()
    except (ValueError, TypeError):
        pass

    if not job:
        # Purge any vector chunks by document_id in pgvector/Milvus anyway
        from app.services.pgvector_ingestion import PgVectorIngestionService
        ingestion = PgVectorIngestionService(session)
        await ingestion.delete_document(job_id)
        return

    assert_job_access(job, actor)

    deletion = ResourceDeletionService(session)
    try:
        await deletion.delete_job(job)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
