"""
Custom Exceptions for Resume Parsing Agent
===========================================

Enterprise-level exception hierarchy for better error handling.
"""

from typing import Optional


class ResumeParsingError(Exception):
    """Base exception for resume parsing errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        """Initialize resume parsing error.
        
        Args:
            message: Error message
            error_code: Optional error code
            details: Optional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class AgentInitializationError(ResumeParsingError):
    """Raised when agent initialization fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="AGENT_INIT_ERROR",
            details=details
        )


class MilvusConnectionError(ResumeParsingError):
    """Raised when Milvus connection fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="MILVUS_CONNECTION_ERROR",
            details=details
        )


class LLMServiceError(ResumeParsingError):
    """Raised when LLM service call fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="LLM_SERVICE_ERROR",
            details=details
        )


class EmbeddingModelError(ResumeParsingError):
    """Raised when embedding model fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="EMBEDDING_MODEL_ERROR",
            details=details
        )


class ToolExecutionError(ResumeParsingError):
    """Raised when agent tool execution fails."""
    
    def __init__(self, tool_name: str, message: str, details: Optional[dict] = None):
        tool_details = details.copy() if details else {}
        tool_details["tool_name"] = tool_name
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {message}",
            error_code="TOOL_EXECUTION_ERROR",
            details=tool_details
        )


class ValidationError(ResumeParsingError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )


