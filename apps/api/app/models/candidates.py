"""Candidate models."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON,  Column
from sqlmodel import Field, SQLModel


class Candidate(SQLModel, table=True):
    """Candidate model."""

    __tablename__ = "candidates"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    
    # Basic info
    name: str = Field(max_length=255, index=True)
    email: str = Field(max_length=255, index=True)
    phone: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)
    
    # Resume/Profile data
    raw_resume_ref: Optional[str] = Field(
        default=None, max_length=500
    )  # S3/blob reference
    raw_resume_text: Optional[str] = Field(default=None)  # Extracted text
    
    # Structured profile (parsed from resume)
    profile_json: dict = Field(default_factory=dict, sa_type=JSON)
    # Fields in profile_json:
    # - emails: List[str]
    # - phones: List[str]
    # - locations: List[str]
    # - education: List[{degree, institution, year, field}]
    # - experience: List[{company, title, start, end, bullets, location}]
    # - skills: List[{name, confidence}]
    # - certificates: List[{name, issuer, date}]
    # - links: List[{type, url}] (LinkedIn, GitHub, etc.)
    # - languages: List[{language, proficiency}]
    
    # Parsing metadata
    parsing_confidence: Optional[float] = Field(default=None)
    missing_fields: list = Field(
        default_factory=list, sa_type=JSON
    )
    
    # Enrichment data
    enrichment_score: Optional[float] = Field(default=None)
    enrichment_data: dict = Field(
        default_factory=dict, sa_type=JSON
    )
    # Fields in enrichment_data:
    # - github_profile: {username, repos_count, contributions, languages}
    # - linkedin_profile: {headline, connections, endorsements}
    # - public_signals: List[{source, data}]
    
    # Consent & privacy
    consent_given: bool = Field(default=False)
    consent_date: Optional[datetime] = None
    gdpr_export_requested: bool = Field(default=False)
    deletion_requested: bool = Field(default=False)
    
    # Source
    source: Optional[str] = Field(
        default=None, max_length=100
    )  # e.g., "upload", "linkedin", "referral"
    source_metadata: dict = Field(
        default_factory=dict, sa_type=JSON
    )
    
    # Status
    is_active: bool = Field(default=True)
    is_blacklisted: bool = Field(default=False)
    blacklist_reason: Optional[str] = None
    
    # Metadata
    tags: list = Field(default_factory=list, sa_type=JSON)
    extra_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_contacted_at: Optional[datetime] = None

    def __repr__(self) -> str:
        """String representation."""
        return f"<Candidate {self.name} <{self.email}>>"


class CandidateEmbedding(SQLModel, table=True):
    """Candidate embedding for vector search."""

    __tablename__ = "candidate_embeddings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    candidate_id: UUID = Field(foreign_key="candidates.id", index=True, unique=True)
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
        return f"<CandidateEmbedding candidate_id={self.candidate_id}>"

