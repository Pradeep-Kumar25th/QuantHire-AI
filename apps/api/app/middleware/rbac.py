"""Role-Based Access Control (RBAC) middleware and dependencies."""

import logging
from enum import Enum
from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"
    VIEWER = "viewer"  # Read-only access


def coerce_user_role(role: UserRole | str | None) -> UserRole:
    """
    Normalize role from JWT (lowercase), Entra (UPPERCASE), or enum → UserRole.

    JWT stores ``recruiter``; Entra app roles use ``RECRUITER``; PostgreSQL enum
    label is ``RECRUITER`` — this helper accepts all spellings safely.
    """
    if isinstance(role, UserRole):
        return role
    if role is None or not str(role).strip():
        raise ValueError("User role is missing")

    raw = str(role).strip()
    lowered = raw.lower()
    try:
        return UserRole(lowered)
    except ValueError:
        pass

    canonical = raw.upper().replace("-", "_")
    canonical = "_".join(part for part in canonical.split() if part)
    for member in UserRole:
        if member.name == canonical or member.value == lowered:
            return member

    raise ValueError(f"Unsupported user role: {raw!r}")


# Role hierarchy (higher roles inherit lower role permissions)
ROLE_HIERARCHY = {
    UserRole.ADMIN: [UserRole.RECRUITER, UserRole.HIRING_MANAGER, UserRole.INTERVIEWER, UserRole.VIEWER],
    UserRole.RECRUITER: [UserRole.VIEWER],
    UserRole.HIRING_MANAGER: [UserRole.VIEWER],
    UserRole.INTERVIEWER: [UserRole.VIEWER],
    UserRole.CANDIDATE: [],
    UserRole.VIEWER: [],
}


# Permission definitions
class Permission(str, Enum):
    """System permissions."""
    # User management
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    VIEW_USER = "view_user"
    
    # Job management
    CREATE_JOB = "create_job"
    UPDATE_JOB = "update_job"
    DELETE_JOB = "delete_job"
    VIEW_JOB = "view_job"
    PUBLISH_JOB = "publish_job"
    
    # Candidate management
    CREATE_CANDIDATE = "create_candidate"
    UPDATE_CANDIDATE = "update_candidate"
    DELETE_CANDIDATE = "delete_candidate"
    VIEW_CANDIDATE = "view_candidate"
    VIEW_CANDIDATE_PII = "view_candidate_pii"
    EXPORT_CANDIDATE_DATA = "export_candidate_data"
    
    # Application management
    CREATE_APPLICATION = "create_application"
    UPDATE_APPLICATION = "update_application"
    VIEW_APPLICATION = "view_application"
    APPROVE_APPLICATION = "approve_application"
    REJECT_APPLICATION = "reject_application"
    
    # Assessment
    CREATE_ASSESSMENT = "create_assessment"
    GRADE_ASSESSMENT = "grade_assessment"
    VIEW_ASSESSMENT = "view_assessment"
    
    # Interview
    SCHEDULE_INTERVIEW = "schedule_interview"
    CONDUCT_INTERVIEW = "conduct_interview"
    VIEW_INTERVIEW = "view_interview"
    
    # Offer
    CREATE_OFFER = "create_offer"
    APPROVE_OFFER = "approve_offer"
    VIEW_OFFER = "view_offer"
    
    # System
    VIEW_ANALYTICS = "view_analytics"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SETTINGS = "manage_settings"
    RUN_AGENTS = "run_agents"


# Role-Permission mapping
ROLE_PERMISSIONS = {
    UserRole.ADMIN: [p for p in Permission],  # All permissions
    
    UserRole.RECRUITER: [
        Permission.CREATE_JOB,
        Permission.UPDATE_JOB,
        Permission.VIEW_JOB,
        Permission.PUBLISH_JOB,
        Permission.CREATE_CANDIDATE,
        Permission.UPDATE_CANDIDATE,
        Permission.VIEW_CANDIDATE,
        Permission.VIEW_CANDIDATE_PII,
        Permission.CREATE_APPLICATION,
        Permission.UPDATE_APPLICATION,
        Permission.VIEW_APPLICATION,
        Permission.SCHEDULE_INTERVIEW,
        Permission.VIEW_INTERVIEW,
        Permission.CREATE_OFFER,
        Permission.VIEW_OFFER,
        Permission.VIEW_ANALYTICS,
        Permission.RUN_AGENTS,
    ],
    
    UserRole.HIRING_MANAGER: [
        Permission.VIEW_JOB,
        Permission.VIEW_CANDIDATE,
        Permission.VIEW_APPLICATION,
        Permission.APPROVE_APPLICATION,
        Permission.REJECT_APPLICATION,
        Permission.SCHEDULE_INTERVIEW,
        Permission.VIEW_INTERVIEW,
        Permission.APPROVE_OFFER,
        Permission.VIEW_OFFER,
        Permission.VIEW_ANALYTICS,
    ],
    
    UserRole.INTERVIEWER: [
        Permission.VIEW_JOB,
        Permission.VIEW_CANDIDATE,
        Permission.VIEW_APPLICATION,
        Permission.CONDUCT_INTERVIEW,
        Permission.VIEW_INTERVIEW,
        Permission.GRADE_ASSESSMENT,
    ],
    
    UserRole.CANDIDATE: [
        Permission.VIEW_JOB,
        Permission.CREATE_APPLICATION,
        Permission.UPDATE_APPLICATION,  # Own applications only
        Permission.VIEW_APPLICATION,     # Own applications only
        Permission.VIEW_INTERVIEW,       # Own interviews only
        Permission.EXPORT_CANDIDATE_DATA,  # Own data only
    ],
    
    UserRole.VIEWER: [
        Permission.VIEW_JOB,
        Permission.VIEW_CANDIDATE,
        Permission.VIEW_APPLICATION,
        Permission.VIEW_INTERVIEW,
        Permission.VIEW_ANALYTICS,
    ],
}


class RBACMiddleware:
    """RBAC enforcement middleware."""
    
    @staticmethod
    def has_permission(user_role: UserRole, permission: Permission) -> bool:
        """
        Check if a role has a specific permission.
        
        Includes inherited permissions from role hierarchy.
        """
        # Check direct permissions
        if permission in ROLE_PERMISSIONS.get(user_role, []):
            return True
        
        # Check inherited permissions from subordinate roles
        for inherited_role in ROLE_HIERARCHY.get(user_role, []):
            if permission in ROLE_PERMISSIONS.get(inherited_role, []):
                return True
        
        return False
    
    @staticmethod
    def has_any_permission(user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if role has any of the specified permissions."""
        return any(RBACMiddleware.has_permission(user_role, p) for p in permissions)
    
    @staticmethod
    def has_all_permissions(user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if role has all specified permissions."""
        return all(RBACMiddleware.has_permission(user_role, p) for p in permissions)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve authenticated user from JWT — never returns a mock user."""
    from app.core.deps import get_current_user as resolve_user

    authorization = request.headers.get("Authorization")
    return await resolve_user(request, authorization, db)


def require_role(allowed_roles: List[UserRole]):
    """
    Dependency to require specific roles.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_role([UserRole.ADMIN]))])
    """
    async def check_role(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            user_role = coerce_user_role(current_user.get("role"))
        except ValueError:
            user_role = None

        if user_role is None or user_role not in allowed_roles:
            logger.warning(
                f"Access denied: user {current_user.get('id')} "
                f"with role {user_role} attempted to access {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}",
            )
        
        # Log access for audit
        await log_access(
            user_id=current_user.get("id"),
            role=user_role,
            action="access",
            resource=request.url.path,
            ip_address=request.client.host if request.client else None,
            db=db,
        )
        
        return current_user
    
    return check_role


def require_permission(required_permissions: List[Permission]):
    """
    Dependency to require specific permissions.
    
    Usage:
        @app.post("/jobs", dependencies=[Depends(require_permission([Permission.CREATE_JOB]))])
    """
    async def check_permission(
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            user_role = coerce_user_role(current_user.get("role"))
        except ValueError:
            user_role = None

        has_permissions = bool(user_role) and RBACMiddleware.has_all_permissions(
            user_role, required_permissions
        )
        
        if not has_permissions:
            logger.warning(
                f"Permission denied: user {current_user.get('id')} "
                f"with role {user_role} lacks permissions: {[p.value for p in required_permissions]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[p.value for p in required_permissions]}",
            )
        
        # Log access for audit
        await log_access(
            user_id=current_user.get("id"),
            role=user_role,
            action="access",
            resource=request.url.path,
            permissions=required_permissions,
            ip_address=request.client.host if request.client else None,
            db=db,
        )
        
        return current_user
    
    return check_permission


def require_owner_or_role(resource_type: str, allowed_roles: List[UserRole]):
    """
    Require user to be resource owner OR have specified role.
    
    For candidate-specific operations.
    """
    async def check_owner_or_role(
        resource_id: str,
        request: Request,
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        user_role = current_user.get("role")
        try:
            coerced_role = coerce_user_role(user_role)
        except ValueError:
            coerced_role = None
        user_id = current_user.get("id")
        
        # Check if user has required role
        if coerced_role is not None and coerced_role in allowed_roles:
            return current_user
        
        # Check if user is resource owner
        is_owner = await check_resource_ownership(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            db=db,
        )
        
        if not is_owner:
            logger.warning(
                f"Access denied: user {user_id} is not owner of {resource_type}:{resource_id} "
                f"and lacks required role"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )
        
        return current_user
    
    return check_owner_or_role


async def check_resource_ownership(
    user_id: str,
    resource_type: str,
    resource_id: str,
    db: AsyncSession,
) -> bool:
    """Check if user owns a specific resource."""
    from uuid import UUID

    from sqlalchemy import select

    from app.models.candidates import Candidate
    from app.models.jobs import Job

    try:
        uid = UUID(user_id)
        rid = UUID(resource_id)
    except ValueError:
        return False

    if resource_type == "job":
        result = await db.execute(select(Job).where(Job.id == rid))
        job = result.scalar_one_or_none()
        return job is not None and job.created_by == uid

    if resource_type == "candidate":
        result = await db.execute(select(Candidate).where(Candidate.id == rid))
        candidate = result.scalar_one_or_none()
        if candidate is None:
            return False
        owner = getattr(candidate, "created_by", None) or getattr(
            candidate, "uploaded_by", None
        )
        return owner == uid

    return False


async def log_access(
    user_id: str,
    role: UserRole,
    action: str,
    resource: str,
    permissions: Optional[List[Permission]] = None,
    ip_address: Optional[str] = None,
    result: str = "success",
    db: Optional[AsyncSession] = None,
):
    """Log access attempt to audit_logs for compliance."""
    from datetime import datetime, timezone
    from uuid import UUID

    from app.models.audit_logs import AuditLog

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "role": role.value if isinstance(role, UserRole) else str(role),
        "action": action,
        "resource": resource,
        "permissions": [p.value for p in permissions] if permissions else [],
        "ip_address": ip_address,
        "result": result,
    }
    logger.info("Access log: %s", log_entry)

    if db is None:
        return

    try:
        target_type = resource.split(":")[0] if ":" in resource else "api"
        target_id_raw = resource.split(":")[1] if ":" in resource else None
        try:
            target_id = UUID(target_id_raw) if target_id_raw else UUID(int=0)
        except ValueError:
            target_id = UUID(int=0)

        db.add(
            AuditLog(
                actor_id=UUID(user_id),
                actor_type="user",
                action=action,
                action_category=target_type,
                target_type=target_type,
                target_id=target_id,
                details_json=log_entry,
                ip_address=ip_address,
                success=result == "success",
            )
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist audit log: %s", exc)
        await db.rollback()


async def log_sensitive_operation(
    user_id: str,
    operation: str,
    resource_type: str,
    resource_id: str,
    details: dict,
    db: AsyncSession,
):
    """Log sensitive operations to audit_logs."""
    from datetime import datetime, timezone
    from uuid import UUID

    from app.models.audit_logs import AuditLog

    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "operation": operation,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "severity": "high",
    }
    logger.warning("Sensitive operation: %s", audit_entry)

    try:
        db.add(
            AuditLog(
                actor_id=UUID(user_id),
                actor_type="user",
                action=operation,
                action_category=resource_type,
                target_type=resource_type,
                target_id=UUID(resource_id),
                details_json=audit_entry,
                success=True,
            )
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist sensitive audit log: %s", exc)
        await db.rollback()












