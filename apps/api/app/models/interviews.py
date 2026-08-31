from sqlalchemy import Column, JSON
"""Interview models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import JSON,  Field, SQLModel


class InterviewType(str, Enum):
    """Interview types."""

    PHONE_SCREEN = "phone_screen"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    PANEL = "panel"
    ASYNC_VIDEO = "async_video"


class InterviewStatus(str, Enum):
    """Interview status."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Interview(SQLModel, table=True):
    """Interview model."""

    __tablename__ = "interviews"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="applications.id", index=True)
    
    interview_type: InterviewType
    status: InterviewStatus = Field(default=InterviewStatus.SCHEDULED)
    
    # Scheduling
    scheduled_at: Optional[datetime] = Field(default=None, index=True)
    duration_minutes: int = Field(default=60)
    timezone: str = Field(default="UTC", max_length=50)
    
    # Participants
    interviewer_ids: list = Field(
        default_factory=list, sa_type=JSON
    )  # List[UUID] of interviewer user IDs
    candidate_id: UUID = Field(foreign_key="candidates.id", index=True)
    
    # Meeting details
    meeting_link: Optional[str] = Field(default=None, max_length=500)
    meeting_id: Optional[str] = Field(default=None, max_length=255)
    calendar_event_id: Optional[str] = Field(default=None, max_length=255)
    
    # Recording & transcript (for async video or recorded interviews)
    recording_ref: Optional[str] = Field(
        default=None, max_length=500
    )  # S3/blob reference
    transcript: Optional[str] = None
    transcript_language: Optional[str] = Field(default="en", max_length=10)
    
    # Analysis
    analysis_json: dict = Field(
        default_factory=dict, sa_type=JSON
    )
    # Fields in analysis_json:
    # - summary: str
    # - sentiment: {"score": float, "label": str}
    # - clarity_score: float
    # - communication_score: float
    # - technical_score: float (if applicable)
    # - red_flags: List[str]
    # - highlights: List[str]
    # - key_points: List[str]
    
    # Scoring
    overall_score: Optional[float] = Field(default=None)  # 0-100
    interviewer_ratings: dict = Field(
        default_factory=dict, sa_type=JSON
    )
    # {interviewer_id: {score, notes, recommendation}}
    
    # Notes
    notes: Optional[str] = None
    internal_notes: Optional[str] = None  # Not visible to candidate
    
    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    
    # Metadata
    extra_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Interview {self.interview_type} application={self.application_id}>"

