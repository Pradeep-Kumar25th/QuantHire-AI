"""Custom exceptions for QuantHireAI with proper error handling."""

from typing import Any, Dict, List, Optional


class QuantHireException(Exception):
    """Base exception for QuantHireAI."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationException(QuantHireException):
    """Validation error."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
            status_code=400,
        )


class AuthenticationException(QuantHireException):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=401,
        )


class AuthorizationException(QuantHireException):
    """Authorization error."""
    
    def __init__(self, message: str = "Insufficient permissions", required_role: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            details={"required_role": required_role} if required_role else {},
            status_code=403,
        )


class ResourceNotFoundException(QuantHireException):
    """Resource not found error."""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            error_code="NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=404,
        )


class RateLimitException(QuantHireException):
    """Rate limit exceeded error."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
            status_code=429,
        )


class ServiceUnavailableException(QuantHireException):
    """Service unavailable error."""
    
    def __init__(self, service_name: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Service temporarily unavailable: {service_name}",
            error_code="SERVICE_UNAVAILABLE",
            details={"service": service_name, "retry_after": retry_after},
            status_code=503,
        )


class DatabaseException(QuantHireException):
    """Database operation error."""
    
    def __init__(self, message: str, operation: str):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details={"operation": operation},
            status_code=500,
        )


class LLMException(QuantHireException):
    """LLM service error."""
    
    def __init__(self, message: str, provider: str, model: str):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            details={"provider": provider, "model": model},
            status_code=500,
        )


class AgentException(QuantHireException):
    """Agent execution error."""
    
    def __init__(self, message: str, agent_name: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="AGENT_ERROR",
            details={"agent": agent_name, **(details or {})},
            status_code=500,
        )


class BudgetExceededException(QuantHireException):
    """LLM budget exceeded error."""
    
    def __init__(self, daily_budget: float, spent: float):
        super().__init__(
            message="Daily LLM budget exceeded",
            error_code="BUDGET_EXCEEDED",
            details={"daily_budget_usd": daily_budget, "spent_usd": spent},
            status_code=429,
        )


class ComplianceException(QuantHireException):
    """Compliance violation error."""
    
    def __init__(self, message: str, violation_type: str):
        super().__init__(
            message=message,
            error_code="COMPLIANCE_VIOLATION",
            details={"violation_type": violation_type},
            status_code=400,
        )


class BiasCheckFailedException(QuantHireException):
    """Bias check failed error."""
    
    def __init__(self, concerns: List[str]):
        super().__init__(
            message="Decision failed bias check",
            error_code="BIAS_CHECK_FAILED",
            details={"concerns": concerns},
            status_code=400,
        )












