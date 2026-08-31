from sqlalchemy import Column, JSON
"""Offer models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import JSON,  Field, SQLModel


class OfferStatus(str, Enum):
    """Offer status."""

    DRAFT = "draft"
    SENT = "sent"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class Offer(SQLModel, table=True):
    """Offer model."""

    __tablename__ = "offers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    application_id: UUID = Field(foreign_key="applications.id", index=True, unique=True)
    
    status: OfferStatus = Field(default=OfferStatus.DRAFT, index=True)
    
    # Package details
    package_json: dict = Field(default_factory=dict, sa_type=JSON)
    # Fields in package_json:
    # - base_salary: {"amount": int, "currency": str}
    # - bonus: {"amount": int, "currency": str, "type": "annual|signing"}
    # - equity: {"shares": int, "type": "RSU|options", "vesting_schedule": str}
    # - benefits: List[str]
    # - start_date: str
    # - relocation: {"amount": int, "currency": str}
    # - other_perks: List[{name: str, value: str}]
    
    # Generation metadata (from OfferAgent)
    agent_rationale: Optional[str] = None
    market_data_ref: dict = Field(
        default_factory=dict, sa_type=JSON
    )  # Market compensation data used
    
    # Negotiation history
    negotiation_history: list = Field(
        default_factory=list, sa_type=JSON
    )
    # List of negotiation rounds:
    # [{
    #   "timestamp": "...",
    #   "actor": "candidate|company",
    #   "proposed_changes": {},
    #   "notes": str
    # }]
    
    # Offer letter
    offer_letter_ref: Optional[str] = Field(
        default=None, max_length=500
    )  # S3/blob reference
    offer_letter_template: Optional[str] = Field(default=None, max_length=100)
    
    # Validity
    valid_until: Optional[datetime] = None
    
    # Response
    candidate_response: Optional[str] = None  # Acceptance/decline message
    candidate_response_date: Optional[datetime] = None
    
    # Approval workflow
    approved_by: Optional[UUID] = Field(default=None, foreign_key="users.id")
    approval_date: Optional[datetime] = None
    approval_notes: Optional[str] = None
    
    # Timestamps
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    withdrawal_reason: Optional[str] = None
    
    # Metadata
    extra_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, name="metadata"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Offer application={self.application_id} status={self.status}>"

