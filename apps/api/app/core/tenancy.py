"""Multi-tenant scoping helpers for API queries."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.sql import Select

from app.middleware.rbac import UserRole


def _user_id(user: dict[str, Any]) -> Optional[UUID]:
    raw = user.get("id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def is_admin(user: dict[str, Any]) -> bool:
    role = user.get("role")
    if isinstance(role, UserRole):
        return role == UserRole.ADMIN
    return str(role) == UserRole.ADMIN.value


def scope_jobs_query(query: Select, user: dict[str, Any], job_model: Any) -> Select:
    """Restrict job queries to the authenticated user unless admin."""
    if is_admin(user):
        return query
    user_id = _user_id(user)
    if user_id is not None and hasattr(job_model, "created_by"):
        return query.where(job_model.created_by == user_id)
    return query


def assert_job_access(job: Any, user: dict[str, Any]) -> None:
    """Raise HTTP 403 if user cannot access this job."""
    from fastapi import HTTPException, status

    if is_admin(user):
        return
    user_id = _user_id(user)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if getattr(job, "created_by", None) != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
