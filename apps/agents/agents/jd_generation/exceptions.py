"""
JD Generation Exceptions
========================
Enterprise-grade exception handling with proper error types.
"""

from typing import Any, Dict, Optional


class JDGenerationError(Exception):
    """Base exception for JD generation errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        """
        Initialize exception.
        
        Args:
            message: Error message
            error_code: Error code for categorization
            details: Additional error details
            retryable: Whether error is retryable
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "JD_GENERATION_ERROR"
        self.details = details or {}
        self.retryable = retryable


class ConfigurationError(JDGenerationError):
    """Configuration-related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details,
            retryable=False,
        )


class LLMError(JDGenerationError):
    """LLM-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            details=details,
            retryable=retryable,
        )


class WorkflowError(JDGenerationError):
    """Workflow-related errors."""
    
    def __init__(
        self,
        message: str,
        state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        details = details or {}
        if state:
            details["state"] = state
        
        super().__init__(
            message=message,
            error_code="WORKFLOW_ERROR",
            details=details,
            retryable=retryable,
        )


class AgentError(JDGenerationError):
    """Agent-related errors."""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        details = details or {}
        if agent_name:
            details["agent_name"] = agent_name
        
        super().__init__(
            message=message,
            error_code="AGENT_ERROR",
            details=details,
            retryable=retryable,
        )


class StorageError(JDGenerationError):
    """Storage-related errors."""
    
    def __init__(
        self,
        message: str,
        storage_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        details = details or {}
        if storage_type:
            details["storage_type"] = storage_type
        
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            details=details,
            retryable=retryable,
        )


class ValidationError(JDGenerationError):
    """Validation-related errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        details = details or {}
        if field:
            details["field"] = field
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details,
            retryable=retryable,
        )


class TimeoutError(JDGenerationError):
    """Timeout-related errors."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ):
        details = details or {}
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        
        super().__init__(
            message=message,
            error_code="TIMEOUT_ERROR",
            details=details,
            retryable=retryable,
        )

