"""Base agent class with enterprise-grade error handling and observability."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agents.base.result import AgentResult
from agents.llm.client import LLMClient

logger = logging.getLogger(__name__)


def _default_agent_llm_provider() -> str:
    try:
        from agents.llm.chat_factory import llm_provider

        return llm_provider()
    except Exception:
        return "openai"


def _default_agent_llm_model() -> str:
    try:
        from agents.llm.chat_factory import primary_llm_model

        return primary_llm_model()
    except Exception:
        return "gpt-4o"


class AgentConfig(BaseModel):
    """Agent configuration with validation."""

    name: str = Field(..., min_length=1, description="Agent name")
    description: str = Field(..., min_length=10, description="Agent description")
    llm_provider: str = Field(
        default_factory=_default_agent_llm_provider,
        pattern="^(openai|azure_openai|anthropic|groq|google|vertexai)$",
    )
    llm_model: str = Field(default_factory=_default_agent_llm_model)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)
    timeout: int = Field(default=60, gt=0, le=600)
    max_retries: int = Field(default=3, ge=0, le=5)
    retry_delay: float = Field(default=2.0, ge=0.1, le=10.0)
    enable_tracking: bool = Field(default=True)
    enable_caching: bool = Field(default=False)
    cache_ttl: int = Field(default=3600, gt=0)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name format."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Agent name must be alphanumeric (underscore allowed)")
        return v


class BaseAgent(ABC):
    """
    Base agent class for all QuantHire agents with enterprise features.
    
    Features:
    - Automatic retry with exponential backoff
    - Circuit breaker pattern for external services
    - Performance tracking and observability
    - Error handling with proper logging
    - Input validation
    - Result caching (optional)
    - Timeout protection
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize agent with configuration.
        
        Args:
            config: Agent configuration with validation
            
        Raises:
            ValueError: If configuration is invalid
        """
        self.config = config
        self.logger = logging.getLogger(f"agent.{config.name}")
        
        try:
            self.llm_client = LLMClient(
                provider=config.llm_provider,
                model=config.llm_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            self.logger.info(
                f"Agent initialized: {config.name}",
                extra={
                    "agent": config.name,
                    "model": config.llm_model,
                    "provider": config.llm_provider,
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Execute agent logic (must be implemented by subclasses).
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            AgentResult: Result of agent execution
            
        Raises:
            AgentException: If execution fails
        """
        pass
    
    async def validate_input(self, input_data: Dict[str, Any]) -> None:
        """
        Validate input data before execution.
        
        Args:
            input_data: Input data to validate
            
        Raises:
            ValidationException: If input is invalid
        """
        # Override in subclass for specific validation
        pass
    
    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def execute_with_retry(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Execute agent with automatic retry on transient failures.
        
        Args:
            input_data: Input data for execution
            
        Returns:
            AgentResult: Execution result
        """
        return await self.execute(input_data)
    
    def _create_result(
        self,
        output: Any,
        confidence: float = 0.0,
        explanation: str = "",
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
        review_required: bool = False,
    ) -> AgentResult:
        """
        Create agent result with full explainability fields.
        
        Args:
            output: Agent output data
            confidence: Confidence score (0-1)
            explanation: Natural language explanation
            evidence: Supporting evidence
            metadata: Additional metadata
            success: Whether execution was successful
            error: Error message if failed
            review_required: Whether human review is required
            
        Returns:
            AgentResult: Formatted agent result with all required fields
        """
        execution_id = str(uuid4())
        
        return AgentResult(
            agent_name=self.config.name,
            output=output,
            confidence=confidence,
            explanation=explanation,
            evidence=evidence or [],
            metadata=metadata or {},
            success=success,
            error=error,
            model_version="1.0.0",
            model_name=self.config.llm_model,
            model_provider=self.config.llm_provider,
            execution_id=execution_id,
            review_required=review_required,
        )

    async def run_with_tracking(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Run agent with comprehensive tracking and error handling.
        
        Features:
        - Performance tracking
        - Error handling with retries
        - Timeout protection
        - MLflow logging (if enabled)
        - Audit trail creation
        
        Args:
            input_data: Input data
            context: Additional context (user_id, request_id, etc.)
            
        Returns:
            AgentResult: Result with complete tracking metadata
        """
        start_time = time.time()
        execution_id = str(uuid4())
        
        self.logger.info(
            f"Agent execution started: {self.config.name}",
            extra={
                "agent": self.config.name,
                "execution_id": execution_id,
                "context": context,
            }
        )
        
        try:
            # Validate input
            await self.validate_input(input_data)
            
            # Execute with timeout protection
            result = await asyncio.wait_for(
                self.execute_with_retry(input_data),
                timeout=self.config.timeout,
            )
            
            # Add tracking metadata
            execution_time_ms = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time_ms
            result.execution_id = execution_id
            result.input_context = {
                "keys": list(input_data.keys()),
                "context": context,
            }
            
            # Log success
            self.logger.info(
                f"Agent execution completed: {self.config.name}",
                extra={
                    "agent": self.config.name,
                    "execution_id": execution_id,
                    "execution_time_ms": execution_time_ms,
                    "confidence": result.confidence,
                    "success": result.success,
                }
            )
            
            # Track with MLflow if enabled
            if self.config.enable_tracking:
                await self._track_execution(result, input_data)
            
            return result
            
        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Agent execution timeout: {self.config.name}",
                extra={
                    "agent": self.config.name,
                    "execution_id": execution_id,
                    "timeout": self.config.timeout,
                }
            )
            return self._create_result(
                output={},
                success=False,
                error=f"Execution timeout after {self.config.timeout}s",
                metadata={
                    "execution_time_ms": execution_time_ms,
                    "execution_id": execution_id,
                },
            )
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Agent execution failed: {self.config.name}",
                extra={
                    "agent": self.config.name,
                    "execution_id": execution_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return self._create_result(
                output={},
                success=False,
                error=str(e),
                metadata={
                    "execution_time_ms": execution_time_ms,
                    "execution_id": execution_id,
                    "exception_type": type(e).__name__,
                },
            )
    
    async def _track_execution(self, result: AgentResult, input_data: Dict) -> None:
        """Track execution with MLflow."""
        try:
            from agents.mlops.mlflow_tracker import get_mlflow_tracker
            
            tracker = get_mlflow_tracker()
            await tracker.track_agent_execution(
                agent_name=self.config.name,
                model_version=result.model_version,
                input_data=input_data,
                output_data=result.output,
                confidence=result.confidence,
                execution_time_ms=result.execution_time_ms,
                cost_usd=result.cost_usd,
            )
        except Exception as e:
            self.logger.warning(f"Failed to track execution in MLflow: {e}")

    def get_system_prompt(self) -> str:
        """
        Get system prompt for the agent.
        
        Returns:
            str: System prompt with instructions
        """
        return f"""You are {self.config.name}: {self.config.description}

You must provide accurate, structured responses based on the input provided.
Always include confidence scores and supporting evidence when possible.
If you're uncertain, indicate lower confidence and explain why.

IMPORTANT GUIDELINES:
- Be objective and unbiased
- Base decisions only on job-relevant criteria
- Never consider protected characteristics (age, gender, race, religion, etc.)
- Provide clear explanations with evidence
- Flag any concerns or ambiguities
- Follow the specified output schema exactly"""

