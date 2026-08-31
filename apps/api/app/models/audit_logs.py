"""Audit log models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    """Audit log for tracking all actions."""

    __tablename__ = "audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Actor (who performed the action)
    actor_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    actor_type: str = Field(default="user", max_length=50)  # user, agent, system
    
    # Action
    action: str = Field(max_length=100, index=True)  # e.g., "create_job", "parse_resume"
    action_category: str = Field(
        default="other", max_length=50
    )  # job, candidate, application, etc.
    
    # Target (what was acted upon)
    target_type: str = Field(max_length=50, index=True)  # job, candidate, application, etc.
    target_id: UUID = Field(index=True)
    
    # Details
    details_json: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, name="details_json")
    )
    # Contains action-specific details
    
    # Context
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    request_id: Optional[str] = Field(default=None, max_length=100)
    
    # Status
    success: bool = Field(default=True)
    error_message: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AuditLog {self.action} on {self.target_type}:{self.target_id}>"


class AgentAction(SQLModel, table=True):
    """Agent action tracking for AI agent decisions."""

    __tablename__ = "agent_actions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Agent identification
    agent_name: str = Field(max_length=100, index=True)  # e.g., "ParsingAgent", "DecisionAgent"
    action_type: str = Field(max_length=100)  # e.g., "parse_resume", "score_candidate"
    
    # Input/Output
    input_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, name="input_data")
    )
    output_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, name="output_data")
    )
    
    # Confidence & evidence
    confidence: Optional[float] = Field(default=None)  # 0-1
    evidence: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        sa_column=Column(JSON, name="evidence")
    )  # Retrieved context/evidence
    
    # LLM metadata
    llm_provider: Optional[str] = Field(default=None, max_length=50)
    llm_model: Optional[str] = Field(default=None, max_length=100)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None
    
    # Status
    success: bool = Field(default=True)
    error_message: Optional[str] = None
    
    # Context
    application_id: Optional[UUID] = Field(default=None, foreign_key="applications.id", index=True)
    candidate_id: Optional[UUID] = Field(default=None, foreign_key="candidates.id", index=True)
    job_id: Optional[UUID] = Field(default=None, foreign_key="jobs.id", index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<AgentAction {self.agent_name}.{self.action_type}>"


class Override(SQLModel, table=True):
    """Human override of agent decisions."""

    __tablename__ = "overrides"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Who overrode
    actor_id: UUID = Field(foreign_key="users.id", index=True)
    
    # What was overridden
    agent_action_id: UUID = Field(foreign_key="agent_actions.id", index=True)
    
    # Original vs override
    original_decision: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, name="original_decision")
    )
    override_decision: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON, name="override_decision")
    )
    
    # Reason
    reason: str  # Required explanation
    reason_category: Optional[str] = Field(
        default=None, max_length=100
    )  # e.g., "agent_error", "business_rule", "edge_case"
    
    # Impact
    impact_assessment: Optional[str] = None  # How critical is this override
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<Override by user:{self.actor_id} on action:{self.agent_action_id}>"

