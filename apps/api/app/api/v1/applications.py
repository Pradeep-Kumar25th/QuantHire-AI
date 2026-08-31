"""Application management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.applications import Application, ApplicationStatus

router = APIRouter()


class ApplicationCreate(BaseModel):
    """Application creation schema."""

    candidate_id: UUID
    job_id: UUID
    source: Optional[str] = None


class ApplicationResponse(BaseModel):
    """Application response schema."""

    id: UUID
    candidate_id: UUID
    job_id: UUID
    status: ApplicationStatus
    match_score: Optional[float]
    agent_recommendation: Optional[str]
    agent_confidence: Optional[float]
    agent_rationale: Optional[str]

    class Config:
        from_attributes = True


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: ApplicationCreate,
    session: AsyncSession = Depends(get_session),
) -> Application:
    """Create a new application."""
    # TODO: Validate candidate and job exist
    # TODO: Trigger MatchingAgent to calculate match score
    
    application = Application(
        candidate_id=application_data.candidate_id,
        job_id=application_data.job_id,
        source=application_data.source,
        status=ApplicationStatus.APPLIED,
    )
    
    session.add(application)
    await session.commit()
    await session.refresh(application)
    
    # TODO: Queue background task to generate embeddings and calculate match
    
    return application


@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    job_id: Optional[UUID] = None,
    candidate_id: Optional[UUID] = None,
    status: Optional[ApplicationStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> List[Application]:
    """List applications with optional filtering."""
    query = select(Application)
    
    if job_id:
        query = query.where(Application.job_id == job_id)
    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
    if status:
        query = query.where(Application.status == status)
    
    query = query.offset(skip).limit(limit).order_by(Application.applied_at.desc())
    
    result = await session.execute(query)
    applications = result.scalars().all()
    
    return list(applications)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Application:
    """Get application by ID."""
    result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    
    return application


@router.patch("/{application_id}/status")
async def update_application_status(
    application_id: UUID,
    status: ApplicationStatus,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update application status."""
    result = await session.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    
    application.status = status
    await session.commit()
    
    return {"message": "Status updated successfully", "new_status": status}

