"""Job models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON,  Column
from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    """Job status."""

    DRAFT = "draft"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    FILLED = "filled"


class Job(SQLModel, table=True):
    """Job model."""

    __tablename__ = "jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str = Field(max_length=255, index=True)
    level: str = Field(max_length=100)  # e.g., Junior, Mid, Senior, Staff
    department: str = Field(max_length=100)
    location: Optional[str] = Field(default=None, max_length=255)
    remote_allowed: bool = Field(default=False)
    
    # Structured job specification (JSON)
    spec_json: dict = Field(default_factory=dict, sa_type=JSON)
    # Fields in spec_json:
    # - skills: List[{"name": str, "required": bool, "level": str}]
    # - responsibilities: List[str]
    # - screening_criteria: List[{"criterion": str, "weight": float}]
    # - kpis: List[str]
    # - compensation_range: {"min": int, "max": int, "currency": str}
    
    description: str = Field(default="")  # Raw job description text
    requirements: str = Field(default="")
    compensation_range: dict = Field(
        default_factory=dict, sa_type=JSON
    )
    
    status: JobStatus = Field(default=JobStatus.DRAFT, index=True)
    created_by: UUID = Field(foreign_key="users.id")
    hiring_manager_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    
    # Metadata
    openings_count: int = Field(default=1)
    filled_count: int = Field(default=0)
    extra_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    def __repr__(self) -> str:
        """String representation."""
        return f"<Job {self.title}>"


class JobEmbedding(SQLModel, table=True):
    """Job embedding for vector search."""

    __tablename__ = "job_embeddings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="jobs.id", index=True, unique=True)
    # Vector column for pgvector
    vector: Optional[list] = Field(
        default=None,
        sa_column=Column(Vector(768)),  # bge-base-en-v1.5 embedding dimension
    )
    model: str = Field(default="BAAI/bge-base-en-v1.5", max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<JobEmbedding job_id={self.job_id}>"

