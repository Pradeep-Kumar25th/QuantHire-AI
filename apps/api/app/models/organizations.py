"""Organization model for multi-tenancy."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import JSON,  Field, SQLModel


class Organization(SQLModel, table=True):
    """Organization model for multi-tenant support."""

    __tablename__ = "organizations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=255, index=True)
    slug: str = Field(unique=True, max_length=100, index=True)
    
    # Contact
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=500)
    
    # Address
    address: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    
    # Branding
    logo_url: Optional[str] = Field(default=None, max_length=500)
    primary_color: Optional[str] = Field(default=None, max_length=7)  # Hex color
    
    # Settings
    settings: dict = Field(default_factory=dict, sa_type=JSON)
    # Settings can include:
    # - timezone, language, date_format
    # - hiring_workflow_config
    # - integration_config
    # - feature_flags
    
    # Subscription & limits
    subscription_tier: str = Field(default="free", max_length=50)
    subscription_status: str = Field(default="active", max_length=50)
    max_users: Optional[int] = Field(default=10)
    max_jobs: Optional[int] = Field(default=5)
    max_candidates: Optional[int] = None  # None = unlimited
    
    # Status
    is_active: bool = Field(default=True)
    onboarding_completed: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Organization {self.name}>"

