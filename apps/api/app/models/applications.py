"""Application models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, Column


class ApplicationStatus(str, Enum):
    """Application status."""

    APPLIED = "applied"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Application(SQLModel, table=True):
    """Application model."""

    __tablename__ = "applications"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    candidate_id: UUID = Field(foreign_key="candidates.id", index=True)
    job_id: UUID = Field(foreign_key="jobs.id", index=True)
    
    status: ApplicationStatus = Field(default=ApplicationStatus.APPLIED, index=True)
    
    # Matching & scoring
    match_score: Optional[float] = Field(default=None)  # 0-100
    match_evidence: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # List of matching snippets
    
    # Stage tracking
    screening_score: Optional[float] = None
    screening_notes: Optional[str] = None
    assessment_score: Optional[float] = None
    interview_scores: Optional[Dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    overall_score: Optional[float] = None
    
    # Agent recommendations
    agent_recommendation: Optional[str] = Field(
        default=None, max_length=50
    )  # "hire", "reject", "review"
    agent_confidence: Optional[float] = None
    agent_rationale: Optional[str] = None
    
    # Human overrides
    final_decision: Optional[str] = Field(default=None, max_length=50)
    decision_by: Optional[UUID] = Field(default=None, foreign_key="users.id")
    decision_date: Optional[datetime] = None
    decision_notes: Optional[str] = None
    
    # Timeline
    applied_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    screening_completed_at: Optional[datetime] = None
    assessment_completed_at: Optional[datetime] = None
    interviews_completed_at: Optional[datetime] = None
    offer_sent_at: Optional[datetime] = None
    offer_accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    
    # Metadata
    source: Optional[str] = Field(
        default=None, max_length=100
    )  # How they applied
    referrer_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    # Use sa_column with name parameter to avoid SQLAlchemy reserved word conflict
    extra_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        sa_column=Column(JSON, name="metadata")  # Map to 'metadata' column in database
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Application candidate={self.candidate_id} job={self.job_id}>"

