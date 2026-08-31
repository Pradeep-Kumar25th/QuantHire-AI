"""Assessment models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON as SA_JSON
from sqlmodel import Column, Field, SQLModel


class QuestionType(str, Enum):
    """Question types."""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    CODE = "code"
    VIDEO = "video"


class Assessment(SQLModel, table=True):
    """Assessment model."""

    __tablename__ = "assessments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="applications.id", index=True)
    
    # Assessment configuration
    config_json: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    # Fields in config_json:
    # - title: str
    # - description: str
    # - time_limit_minutes: int
    # - passing_score: float
    # - question_order: "fixed" | "random"
    # - allow_review: bool
    
    # Results
    results_json: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    # Fields in results_json:
    # - question_scores: List[{question_id, score, max_score}]
    # - time_taken_seconds: int
    # - completion_percentage: float
    
    score: Optional[float] = Field(default=None)  # 0-100
    max_score: float = Field(default=100.0)
    passed: Optional[bool] = None
    
    # Proctoring
    proctor_flags: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, sa_column=Column(SA_JSON)
    )
    # Example flags:
    # - {"type": "tab_switch", "timestamp": "..."}
    # - {"type": "face_not_detected", "timestamp": "..."}
    # - {"type": "multiple_faces", "timestamp": "..."}
    
    # Timestamps
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = Field(default=None, foreign_key="users.id")
    
    # Metadata - use sa_column with name to avoid SQLAlchemy reserved word conflict
    extra_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(SA_JSON, name="metadata")
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Assessment application={self.application_id}>"


class AssessmentQuestion(SQLModel, table=True):
    """Assessment question model."""

    __tablename__ = "assessment_questions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assessment_id: UUID = Field(foreign_key="assessments.id", index=True)
    
    question_type: QuestionType
    question_text: str
    question_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(SA_JSON)
    )
    # For multiple_choice: {options: List[str], correct_answer: int}
    # For code: {language: str, starter_code: str, test_cases: List}
    
    points: float = Field(default=1.0)
    order: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AssessmentQuestion {self.question_type}>"


class AssessmentResponse(SQLModel, table=True):
    """Assessment response model."""

    __tablename__ = "assessment_responses"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assessment_id: UUID = Field(foreign_key="assessments.id", index=True)
    question_id: UUID = Field(foreign_key="assessment_questions.id", index=True)
    
    response_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(SA_JSON)
    )
    # For multiple_choice: {selected_option: int}
    # For essay: {text: str}
    # For code: {code: str, language: str, execution_result: {}}
    
    score: Optional[float] = None
    max_score: float = Field(default=1.0)
    
    # Auto-grading
    auto_graded: bool = Field(default=False)
    auto_grade_confidence: Optional[float] = None
    auto_grade_rationale: Optional[str] = None
    
    # Manual review
    manually_reviewed: bool = Field(default=False)
    reviewed_by: Optional[UUID] = Field(default=None, foreign_key="users.id")
    reviewer_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AssessmentResponse question={self.question_id}>"

