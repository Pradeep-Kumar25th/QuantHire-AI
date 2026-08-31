"""Agent result model with full explainability."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """
    Agent execution result with full explainability and auditability.
    
    Includes all required fields for:
    - Explainable AI (explanation, confidence, evidence)
    - Cost tracking (token usage, cost)
    - Model versioning (model_version, provider)
    - Auditability (timestamp, execution_id)
    - Human oversight (human_override_flag, review_required)
    """

    # Core result
    agent_name: str
    output: Any
    success: bool = Field(default=True, description="Whether execution was successful")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Explainability (REQUIRED for compliance)
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    explanation: str = Field(
        default="", description="Natural language explanation of the decision"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Supporting evidence for the output"
    )
    
    # Model versioning (REQUIRED for auditability)
    model_version: str = Field(
        default="1.0.0", description="Version of model/prompt used"
    )
    model_name: str = Field(
        default="gpt-4o", description="LLM model name"
    )
    model_provider: str = Field(
        default="openai", description="LLM provider"
    )
    
    # Cost tracking (REQUIRED for budget control)
    prompt_tokens: int = Field(default=0, description="Number of prompt tokens")
    completion_tokens: int = Field(default=0, description="Number of completion tokens")
    total_tokens: int = Field(default=0, description="Total tokens used")
    cost_usd: float = Field(default=0.0, description="Cost in USD")
    
    # Execution metadata
    execution_id: str = Field(default="", description="Unique execution ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    
    # Human oversight
    human_override_flag: bool = Field(
        default=False, description="Whether human override occurred"
    )
    review_required: bool = Field(
        default=False, description="Whether human review is required"
    )
    reviewer_notes: Optional[str] = Field(
        default=None, description="Notes from human reviewer"
    )
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    
    # Input context (for audit trail)
    input_context: Dict[str, Any] = Field(
        default_factory=dict, description="Input data (for audit)"
    )

    def __repr__(self) -> str:
        """String representation."""
        status = "Success" if self.success else "Failed"
        conf_str = f" (confidence: {self.confidence:.2f})" if self.confidence else ""
        cost_str = f" (${self.cost_usd:.4f})" if self.cost_usd > 0 else ""
        return f"<AgentResult {self.agent_name}: {status}{conf_str}{cost_str}>"
    
    def to_audit_log(self) -> Dict[str, Any]:
        """Convert to audit log format with PII redaction."""
        from app.utils.pii_redaction import PIIRedactor
        
        return {
            "agent_name": self.agent_name,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "model_name": self.model_name,
            "cost_usd": self.cost_usd,
            "total_tokens": self.total_tokens,
            "human_override": self.human_override_flag,
            "review_required": self.review_required,
            # Redact PII from input/output
            "input_context": PIIRedactor.redact_dict(self.input_context),
            "output_summary": PIIRedactor.redact_dict(
                {"keys": list(self.output.keys() if isinstance(self.output, dict) else [])}
            ),
        }

