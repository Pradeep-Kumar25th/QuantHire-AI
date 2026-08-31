"""Feedback model for capturing hiring outcomes and AI performance data."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class Feedback(SQLModel, table=True):
    """
    Feedback from recruiters on hiring outcomes and AI performance.
    
    Used to continuously improve AI models through real-world hiring data.
    """

    __tablename__ = "feedback"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # References
    job_id: UUID = Field(foreign_key="jobs.id", index=True)
    candidate_id: UUID = Field(foreign_key="candidates.id", index=True)
    application_id: UUID = Field(foreign_key="applications.id", index=True, unique=True)
    recruiter_id: UUID = Field(foreign_key="users.id", index=True)
    
    # Outcome data
    hire_decision: str = Field(max_length=50, index=True)  # hired, rejected, withdrawn
    hire_date: Optional[datetime] = None
    rejection_reason: Optional[str] = Field(default=None, max_length=500)
    rejection_stage: Optional[str] = Field(default=None, max_length=100)  # resume_review, interview, final
    
    # AI performance metrics
    ai_match_score: float = Field(ge=0.0, le=1.0)
    ai_match_accurate: bool = Field(default=False, index=True)
    ai_ranking_position: int = Field(default=0)  # Where AI ranked this candidate
    actual_recruiter_rating: float = Field(ge=0.0, le=10.0)  # Recruiter's true rating
    rating_delta: float = Field(default=0.0)  # Difference between AI and recruiter
    
    # Quality metrics
    time_to_hire_days: Optional[int] = Field(default=None)
    interview_stages_completed: int = Field(default=0)
    recruiter_satisfaction: float = Field(default=5.0, ge=1.0, le=10.0)
    candidate_quality_rating: float = Field(default=5.0, ge=1.0, le=10.0)
    candidate_fit_rating: float = Field(default=5.0, ge=1.0, le=10.0)
    
    # Detailed qualitative feedback
    what_worked_well: Optional[str] = None  # TEXT field
    areas_for_improvement: Optional[str] = None  # TEXT field
    ai_missed_factors: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    unexpected_strengths: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    
    # Performance tracking
    source_channel: Optional[str] = Field(default=None, max_length=100)
    job_category: str = Field(max_length=100, index=True)
    seniority_level: str = Field(max_length=50, index=True)
    location: Optional[str] = Field(default=None, max_length=200)
    
    # Interview performance (if hired)
    interview_performance_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    technical_assessment_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    cultural_fit_score: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    
    # Post-hire performance (if applicable)
    employee_performance_30d: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    employee_performance_90d: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    retained_after_probation: Optional[bool] = None
    
    # Metadata
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Soft delete
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = None

    def __repr__(self) -> str:
        """String representation."""
        return f"<Feedback {self.id} - {self.hire_decision} - Accurate: {self.ai_match_accurate}>"


class FeedbackSummary(SQLModel, table=True):
    """
    Aggregated feedback statistics for model drift detection.
    
    Periodically computed summary statistics for efficient drift detection.
    """

    __tablename__ = "feedback_summaries"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Time period
    period_start: datetime = Field(index=True)
    period_end: datetime = Field(index=True)
    period_days: int = Field(default=30)
    
    # Aggregated metrics
    total_feedback_count: int = Field(default=0)
    hired_count: int = Field(default=0)
    rejected_count: int = Field(default=0)
    
    # Accuracy metrics
    overall_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    false_positive_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    false_negative_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Performance metrics
    average_time_to_hire: float = Field(default=0.0)
    average_recruiter_satisfaction: float = Field(default=5.0)
    average_candidate_quality: float = Field(default=5.0)
    
    # Drift detection
    drift_detected: bool = Field(default=False, index=True)
    drift_severity: str = Field(default="none", max_length=20)  # none, low, medium, high
    drift_reasons: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    
    # Recommendations
    retraining_recommended: bool = Field(default=False, index=True)
    retraining_priority: str = Field(default="low", max_length=20)  # low, medium, high, critical
    recommended_actions: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    
    # Bias metrics
    bias_detected: bool = Field(default=False)
    bias_categories: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    fairness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Metadata
    extra_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<FeedbackSummary {self.period_start} to {self.period_end} - Drift: {self.drift_detected}>"












