from sqlalchemy import Column, JSON
"""User model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import JSON,  Field, SQLModel


class UserRole(str, Enum):
    """User roles."""

    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    INTERVIEWER = "interviewer"
    VIEWER = "viewer"
    CANDIDATE = "candidate"


class User(SQLModel, table=True):
    """User model."""

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    name: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.CANDIDATE)
    org_id: Optional[UUID] = Field(default=None, foreign_key="organizations.id")
    hashed_password: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    phone: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    extra_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    def __repr__(self) -> str:
        """String representation."""
        return f"<User {self.email}>"

