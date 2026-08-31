"""Feedback API endpoints for continuous learning and model optimization."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.feedback import Feedback, FeedbackSummary
from app.models.users import User

router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ==================== Schemas ====================

class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""

    job_id: UUID
    candidate_id: UUID
    application_id: UUID
    hire_decision: str = Field(..., pattern="^(hired|rejected|withdrawn)$")
    hire_date: Optional[datetime] = None
    rejection_reason: Optional[str] = Field(None, max_length=500)
    rejection_stage: Optional[str] = None
    
    ai_match_score: float = Field(..., ge=0.0, le=1.0)
    ai_match_accurate: bool
    ai_ranking_position: int = Field(..., ge=0)
    actual_recruiter_rating: float = Field(..., ge=0.0, le=10.0)
    
    time_to_hire_days: Optional[int] = None
    interview_stages_completed: int = Field(default=0)
    recruiter_satisfaction: float = Field(default=5.0, ge=1.0, le=10.0)
    candidate_quality_rating: float = Field(default=5.0, ge=1.0, le=10.0)
    candidate_fit_rating: float = Field(default=5.0, ge=1.0, le=10.0)
    
    what_worked_well: Optional[str] = None
    areas_for_improvement: Optional[str] = None
    ai_missed_factors: Optional[List[str]] = None
    unexpected_strengths: Optional[List[str]] = None
    
    source_channel: Optional[str] = None
    job_category: str
    seniority_level: str
    location: Optional[str] = None
    
    interview_performance_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    technical_assessment_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    cultural_fit_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackUpdate(BaseModel):
    """Schema for updating feedback (e.g., adding post-hire performance)."""

    employee_performance_30d: Optional[float] = Field(None, ge=0.0, le=10.0)
    employee_performance_90d: Optional[float] = Field(None, ge=0.0, le=10.0)
    retained_after_probation: Optional[bool] = None
    
    recruiter_satisfaction: Optional[float] = Field(None, ge=1.0, le=10.0)
    candidate_quality_rating: Optional[float] = Field(None, ge=1.0, le=10.0)
    
    what_worked_well: Optional[str] = None
    areas_for_improvement: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""

    id: UUID
    job_id: UUID
    candidate_id: UUID
    application_id: UUID
    recruiter_id: UUID
    hire_decision: str
    hire_date: Optional[datetime]
    ai_match_score: float
    ai_match_accurate: bool
    ai_ranking_position: int
    actual_recruiter_rating: float
    rating_delta: float
    recruiter_satisfaction: float
    candidate_quality_rating: float
    time_to_hire_days: Optional[int]
    created_at: datetime
    updated_at: datetime


class FeedbackAnalyticsRequest(BaseModel):
    """Request schema for feedback analytics."""

    analysis_period_days: int = Field(default=30, ge=1, le=365)
    min_samples_for_drift: int = Field(default=20, ge=5, le=100)
    drift_threshold: float = Field(default=0.15, ge=0.01, le=0.5)
    job_category: Optional[str] = None
    seniority_level: Optional[str] = None


class FeedbackAnalyticsResponse(BaseModel):
    """Response schema for feedback analytics."""

    total_feedback_count: int
    time_period_days: int
    overall_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    average_time_to_hire: float
    recruiter_satisfaction_avg: float
    candidate_quality_avg: float
    drift_detected: bool
    drift_severity: str
    drift_reasons: List[str]
    retraining_recommended: bool
    retraining_priority: str
    recommended_actions: List[str]
    bias_detected: bool
    bias_categories: List[str]
    fairness_score: float
    prompt_optimization_suggestions: List[str]
    feature_importance_changes: Dict[str, float]


from app.core.auth_policy import auth_enforced, require_authenticated_user
from app.config import settings

# ==================== Dependency ====================


async def get_current_user(
    auth_user: dict | None = Depends(require_authenticated_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve authenticated user from JWT and load full User row."""
    from uuid import UUID

    if auth_user is None:
        if auth_enforced() or settings.is_hardened:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No users in database",
            )
        return user

    try:
        user_id = UUID(str(auth_user["id"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from exc

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# ==================== Endpoints ====================

@router.post(
    "/",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit hiring feedback",
    description="Submit feedback on a hiring decision to improve AI models",
)
async def create_feedback(
    feedback_data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Feedback:
    """Create new feedback record."""
    
    # Calculate rating delta
    rating_delta = abs(feedback_data.ai_match_score * 10 - feedback_data.actual_recruiter_rating)
    
    feedback = Feedback(
        **feedback_data.model_dump(),
        recruiter_id=current_user.id,
        rating_delta=rating_delta,
    )
    
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    
    return feedback


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Get feedback by ID",
)
async def get_feedback(
    feedback_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Feedback:
    """Retrieve a specific feedback record."""
    result = await session.execute(
        select(Feedback).where(
            Feedback.id == feedback_id,
            Feedback.is_deleted == False,
        )
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    return feedback


@router.get(
    "/job/{job_id}",
    response_model=List[FeedbackResponse],
    summary="Get feedback for a job",
)
async def get_feedback_by_job(
    job_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> List[Feedback]:
    """Retrieve all feedback for a specific job."""
    result = await session.execute(
        select(Feedback)
        .where(
            Feedback.job_id == job_id,
            Feedback.is_deleted == False,
        )
        .order_by(Feedback.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/candidate/{candidate_id}",
    response_model=List[FeedbackResponse],
    summary="Get feedback for a candidate",
)
async def get_feedback_by_candidate(
    candidate_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> List[Feedback]:
    """Retrieve all feedback for a specific candidate."""
    result = await session.execute(
        select(Feedback)
        .where(
            Feedback.candidate_id == candidate_id,
            Feedback.is_deleted == False,
        )
        .order_by(Feedback.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Update feedback",
)
async def update_feedback(
    feedback_id: UUID,
    update_data: FeedbackUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Feedback:
    """Update feedback record (e.g., add post-hire performance data)."""
    result = await session.execute(
        select(Feedback).where(
            Feedback.id == feedback_id,
            Feedback.is_deleted == False,
        )
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    # Update fields
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(feedback, field, value)
    
    feedback.updated_at = datetime.utcnow()
    
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    
    return feedback


@router.delete(
    "/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete feedback",
)
async def delete_feedback(
    feedback_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Soft delete a feedback record."""
    result = await session.execute(
        select(Feedback).where(
            Feedback.id == feedback_id,
            Feedback.is_deleted == False,
        )
    )
    feedback = result.scalar_one_or_none()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    
    feedback.is_deleted = True
    feedback.deleted_at = datetime.utcnow()
    
    session.add(feedback)
    await session.commit()


@router.post(
    "/analytics",
    response_model=FeedbackAnalyticsResponse,
    summary="Analyze feedback data",
    description="Generate analytics and detect model drift from feedback data",
)
async def analyze_feedback(
    analytics_request: FeedbackAnalyticsRequest = FeedbackAnalyticsRequest(),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Analyze feedback data to detect drift and generate recommendations.
    
    This endpoint triggers the FeedbackAgent to analyze recent feedback
    and provide insights for model optimization.
    """
    # Fetch feedback records
    cutoff_date = datetime.utcnow() - timedelta(days=analytics_request.analysis_period_days)
    
    query = select(Feedback).where(
        Feedback.created_at >= cutoff_date,
        Feedback.is_deleted == False,
    )
    
    # Apply filters
    if analytics_request.job_category:
        query = query.where(Feedback.job_category == analytics_request.job_category)
    if analytics_request.seniority_level:
        query = query.where(Feedback.seniority_level == analytics_request.seniority_level)
    
    result = await session.execute(query)
    feedback_records = list(result.scalars().all())
    
    if len(feedback_records) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient feedback data. Found {len(feedback_records)} records, need at least 5.",
        )
    
    # Use FeedbackAgent for analysis
    from agents.feedback.agent import FeedbackAgent
    
    agent = FeedbackAgent()
    
    # Convert SQLModel objects to dicts
    feedback_dicts = [
        {
            "job_id": str(f.job_id),
            "candidate_id": str(f.candidate_id),
            "application_id": str(f.application_id),
            "recruiter_id": str(f.recruiter_id),
            "hire_decision": f.hire_decision,
            "hire_date": f.hire_date,
            "rejection_reason": f.rejection_reason,
            "ai_match_score": f.ai_match_score,
            "ai_match_accurate": f.ai_match_accurate,
            "ai_ranking_position": f.ai_ranking_position,
            "actual_recruiter_rating": f.actual_recruiter_rating,
            "time_to_hire_days": f.time_to_hire_days,
            "interview_stages_completed": f.interview_stages_completed,
            "recruiter_satisfaction": f.recruiter_satisfaction,
            "candidate_quality_rating": f.candidate_quality_rating,
            "what_worked_well": f.what_worked_well,
            "areas_for_improvement": f.areas_for_improvement,
            "ai_missed_factors": f.ai_missed_factors or [],
            "source_channel": f.source_channel,
            "job_category": f.job_category,
            "seniority_level": f.seniority_level,
            "feedback_timestamp": f.created_at,
            "metadata": f.metadata,
        }
        for f in feedback_records
    ]
    
    analysis_result = await agent.run_with_tracking(
        input_data={
            "feedback_records": feedback_dicts,
            "analysis_period_days": analytics_request.analysis_period_days,
            "min_samples_for_drift": analytics_request.min_samples_for_drift,
            "drift_threshold": analytics_request.drift_threshold,
        }
    )
    
    if not analysis_result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feedback analysis failed: {analysis_result.error}",
        )
    
    # Store summary in database
    analysis_output = analysis_result.output
    summary = FeedbackSummary(
        period_start=cutoff_date,
        period_end=datetime.utcnow(),
        period_days=analytics_request.analysis_period_days,
        total_feedback_count=analysis_output["total_feedback_count"],
        overall_accuracy=analysis_output["overall_accuracy"],
        false_positive_rate=analysis_output["false_positive_rate"],
        false_negative_rate=analysis_output["false_negative_rate"],
        average_time_to_hire=analysis_output["average_time_to_hire"],
        average_recruiter_satisfaction=analysis_output["recruiter_satisfaction_avg"],
        average_candidate_quality=analysis_output["candidate_quality_avg"],
        drift_detected=analysis_output["drift_detected"],
        drift_severity=analysis_output["drift_severity"],
        drift_reasons=analysis_output["drift_reasons"],
        retraining_recommended=analysis_output["retraining_recommended"],
        retraining_priority=analysis_output["retraining_priority"],
        recommended_actions=analysis_output["recommended_actions"],
        bias_detected=analysis_output["bias_detected"],
        bias_categories=analysis_output["bias_categories"],
        fairness_score=analysis_output["fairness_score"],
    )
    
    session.add(summary)
    await session.commit()
    
    return analysis_output


@router.get(
    "/summaries/recent",
    response_model=List[Dict[str, Any]],
    summary="Get recent feedback summaries",
)
async def get_recent_summaries(
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> List[FeedbackSummary]:
    """Retrieve recent feedback analysis summaries."""
    result = await session.execute(
        select(FeedbackSummary)
        .order_by(FeedbackSummary.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get(
    "/metrics/overview",
    summary="Get feedback metrics overview",
)
async def get_metrics_overview(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Get a quick overview of feedback metrics."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await session.execute(
        select(Feedback).where(
            Feedback.created_at >= cutoff_date,
            Feedback.is_deleted == False,
        )
    )
    feedback_records = list(result.scalars().all())
    
    if not feedback_records:
        return {
            "total_feedback": 0,
            "message": "No feedback data available for this period",
        }
    
    total_count = len(feedback_records)
    accurate_count = sum(1 for f in feedback_records if f.ai_match_accurate)
    hired_count = sum(1 for f in feedback_records if f.hire_decision == "hired")
    
    avg_satisfaction = sum(f.recruiter_satisfaction for f in feedback_records) / total_count
    avg_quality = sum(f.candidate_quality_rating for f in feedback_records) / total_count
    
    avg_time_to_hire = 0
    hire_times = [f.time_to_hire_days for f in feedback_records if f.time_to_hire_days]
    if hire_times:
        avg_time_to_hire = sum(hire_times) / len(hire_times)
    
    return {
        "total_feedback": total_count,
        "period_days": days,
        "overall_accuracy": accurate_count / total_count if total_count > 0 else 0,
        "hired_count": hired_count,
        "rejected_count": total_count - hired_count,
        "average_recruiter_satisfaction": round(avg_satisfaction, 2),
        "average_candidate_quality": round(avg_quality, 2),
        "average_time_to_hire_days": round(avg_time_to_hire, 1),
    }












