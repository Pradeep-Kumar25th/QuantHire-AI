"""Candidate management endpoints."""

import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth_policy import auth_enforced, require_authenticated_user
from app.database import get_session
from app.middleware.rbac import Permission, require_permission
from app.models.candidates import Candidate
from app.services.resource_deletion_service import ResourceDeletionService

router = APIRouter()


class CandidateCreate(BaseModel):
    """Candidate creation schema."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)
    resume_text: Optional[str] = Field(default=None, max_length=500_000)


class CandidateResponse(BaseModel):
    """Candidate response schema."""

    id: UUID
    name: str
    email: str
    phone: Optional[str]
    location: Optional[str]
    profile_json: dict
    parsing_confidence: Optional[float]
    missing_fields: List[str]
    source: Optional[str]
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ParseResponse(BaseModel):
    """Resume parse response schema."""

    candidate_id: UUID
    parsing_status: str
    parsing_confidence: Optional[float]
    missing_fields: List[str]
    profile: dict


async def get_candidate_actor(
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
    "/upload",
    response_model=ParseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission([Permission.CREATE_CANDIDATE]))],
)
async def upload_resume(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> ParseResponse:
    """Upload and parse a resume using AI.

    Azure Non-Prod: Blob → DI → ParsingAgent → Postgres + pgvector (same as /resume/upload).
    Legacy local dev: DocumentParser + CandidateService.
    """
    if settings.use_pgvector_pipeline:
        from app.api.v1.resume_parsing import upload_resume as azure_resume_upload

        result = await azure_resume_upload(file=file, current_user=None, session=session)
        parsed = result.get("parsed_data") or {}
        screening = parsed.get("screening_report") or {}
        confidence = (
            parsed.get("confidence")
            or screening.get("confidence")
            or (
                float(parsed["match_percentage"]) / 100.0
                if parsed.get("match_percentage") is not None
                else None
            )
        )
        missing_fields = (
            parsed.get("missing_fields")
            or screening.get("gaps_for_hr_review")
            or (parsed.get("completeness") or {}).get("gaps_for_hr_review")
            or []
        )
        return ParseResponse(
            candidate_id=UUID(result["candidate_id"]),
            parsing_status=result.get("storage_status", "success"),
            parsing_confidence=float(confidence) if confidence is not None else None,
            missing_fields=list(missing_fields),
            profile=parsed,
        )

    from app.services.candidate_service import CandidateService
    from app.utils.pdf_parser import DocumentParser
    
    # Read file content (legacy local path — enforce size limit)
    content = await file.read()
    max_bytes = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {max_bytes // (1024 * 1024)}MB",
        )
    
    # Extract text based on file type
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        resume_text = DocumentParser.extract_text(content, file.filename)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract text from file: {str(e)}"
        )
    
    # Use CandidateService to parse and create candidate
    candidate_service = CandidateService(session)
    result = await candidate_service.create_candidate_from_resume(
        resume_text=resume_text,
        source="upload"
    )
    
    return ParseResponse(
        candidate_id=UUID(result["candidate_id"]),
        parsing_status=result["parsing_status"],
        parsing_confidence=result["confidence"],
        missing_fields=result["missing_fields"],
        profile=result["profile"],
    )


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_candidate(
    candidate_data: CandidateCreate,
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> Candidate:
    """Create a new candidate manually."""
    candidate = Candidate(
        name=candidate_data.name,
        email=candidate_data.email,
        phone=candidate_data.phone,
        location=candidate_data.location,
        raw_resume_text=candidate_data.resume_text,
        source="manual",
        profile_json={},
    )
    
    # If resume text provided, queue parsing
    if candidate_data.resume_text:
        # TODO: Queue Celery task for parsing
        pass
    
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    
    return candidate


@router.get("", response_model=List[CandidateResponse])
@router.get("/", response_model=List[CandidateResponse], include_in_schema=False)
async def list_candidates(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool = Query(True, description="Return only active candidates by default"),
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> List[Candidate]:
    """List candidates. Defaults to active only (removed candidates are hidden)."""
    query = select(Candidate).where(Candidate.is_active == is_active)
    
    query = query.offset(skip).limit(limit).order_by(Candidate.created_at.desc())
    
    result = await session.execute(query)
    candidates = result.scalars().all()
    
    return list(candidates)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> Candidate:
    """Get candidate by ID."""
    result = await session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    if not candidate.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    
    return candidate


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    candidate_data: CandidateCreate,
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> Candidate:
    """Update candidate by ID."""
    result = await session.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    
    # Update fields
    for field, value in candidate_data.model_dump(exclude_unset=True).items():
        if field == "resume_text":
            candidate.raw_resume_text = value
        else:
            setattr(candidate, field, value)
    
    await session.commit()
    await session.refresh(candidate)
    
    return candidate


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission([Permission.UPDATE_CANDIDATE]))],
)
async def delete_candidate(
    candidate_id: str,
    session: AsyncSession = Depends(get_session),
    _actor: dict = Depends(get_candidate_actor),
) -> None:
    """Soft-delete candidate and purge resume vectors from QuantChat."""
    candidate: Optional[Candidate] = None
    try:
        parsed_uuid = UUID(candidate_id)
        result = await session.execute(select(Candidate).where(Candidate.id == parsed_uuid))
        candidate = result.scalar_one_or_none()
    except (ValueError, TypeError):
        pass
    
    if not candidate:
        # Purge any vector chunks by document_id in pgvector/Milvus anyway
        from app.services.pgvector_ingestion import PgVectorIngestionService
        ingestion = PgVectorIngestionService(session)
        await ingestion.delete_document(candidate_id)
        return

    if not candidate.is_active:
        return

    deletion = ResourceDeletionService(session)
    try:
        await deletion.delete_candidate(candidate)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

