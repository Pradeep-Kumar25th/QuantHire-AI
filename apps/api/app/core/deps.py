"""Dependency injection for FastAPI with enterprise patterns."""

import logging
from typing import Optional

from fastapi import Depends, Header, Request

from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.session_cookie import SESSION_COOKIE_NAME
from app.middleware.rbac import UserRole, coerce_user_role

logger = logging.getLogger(__name__)


def _extract_access_token(
    request: Request,
    authorization: Optional[str],
) -> Optional[str]:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1)
    query_token = request.query_params.get("access_token")
    if query_token:
        return query_token
    return None


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Get current authenticated user with proper validation.

    Token is checked before opening a DB session so missing credentials return
    401 even when DATABASE_URL is unset (local pytest / static checks).
    """
    token = _extract_access_token(request, authorization)
    if not token:
        raise AuthenticationException("Missing or invalid authorization")

    from app.database import async_session_maker

    if not async_session_maker:
        raise AuthenticationException("Invalid or expired token")

    try:
        from app.core.security import verify_token

        async with async_session_maker() as db:
            user = await verify_token(token, db)
            request.state.user = user
            return user

    except AuthenticationException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise AuthenticationException("Invalid or expired token")


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Get current active user (not disabled/deleted).
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user dict
        
    Raises:
        AuthenticationException: If user is inactive
    """
    # User is_active is already checked in verify_token()
    # This is a double-check for extra safety
    is_active = current_user.get("is_active", True)
    
    if not is_active:
        raise AuthenticationException("User account is inactive")
    
    return current_user


async def get_current_admin_user(
    current_user: dict = Depends(get_current_active_user),
) -> dict:
    """
    Require admin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Admin user dict
        
    Raises:
        AuthorizationException: If user is not admin
    """
    try:
        user_role = coerce_user_role(current_user.get("role"))
    except ValueError:
        user_role = None

    if user_role != UserRole.ADMIN:
        logger.warning(
            f"Non-admin user attempted admin action: {current_user.get('id')}"
        )
        raise AuthorizationException(
            "Admin privileges required",
            required_role="admin",
        )
    
    return current_user


async def get_correlation_id(
    request: Request,
    x_correlation_id: Optional[str] = Header(None),
) -> str:
    """
    Get or generate correlation ID for request tracking.
    
    Args:
        request: FastAPI request
        x_correlation_id: Correlation ID from header (optional)
        
    Returns:
        Correlation ID string
    """
    from uuid import uuid4
    
    correlation_id = x_correlation_id or str(uuid4())
    
    # Store in request state
    request.state.correlation_id = correlation_id
    
    # Set in logging context
    from app.core.logging import set_correlation_id
    set_correlation_id(correlation_id)
    
    return correlation_id


class PaginationParams:
    """Pagination parameters with validation."""
    
    def __init__(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
    ):
        """
        Initialize pagination parameters.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
        """
        # Validate and constrain
        self.page = max(1, page)
        self.limit = max(1, min(limit, 100))  # Max 100 items per page
        self.sort_by = sort_by
        self.sort_order = sort_order if sort_order in ["asc", "desc"] else "desc"
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.limit
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "page": self.page,
            "limit": self.limit,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
        }


async def get_pagination_params(
    page: int = 1,
    limit: int = 20,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> PaginationParams:
    """
    Get validated pagination parameters.
    
    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends(get_pagination_params)):
            ...
    """
    return PaginationParams(page, limit, sort_by, sort_order)


class FilterParams:
    """Common filter parameters."""
    
    def __init__(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ):
        self.search = search
        self.status = status
        self.created_after = created_after
        self.created_before = created_before
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        return {
            k: v for k, v in {
                "search": self.search,
                "status": self.status,
                "created_after": self.created_after,
                "created_before": self.created_before,
            }.items() if v is not None
        }


# Service factory pattern
from sqlalchemy.ext.asyncio import AsyncSession


class ServiceFactory:
    """Factory for creating service instances with dependency injection."""
    
    @staticmethod
    def create_job_service(db: AsyncSession):
        """Create job service instance."""
        from app.services.jobs import JobService
        return JobService(db)
    
    @staticmethod
    def create_candidate_service(db: AsyncSession):
        """Create candidate service instance."""
        from app.services.candidates import CandidateService
        return CandidateService(db)












