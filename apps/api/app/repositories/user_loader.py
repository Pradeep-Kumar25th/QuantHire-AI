"""Load users without SQLAlchemy native PG enum processing.

Live Azure Non-Prod ``userrole`` enum labels (verified via API logs 2026-08-10):

| Entra / Hazim test user   | PG enum label   |
|---------------------------|-----------------|
| ADMIN (prakumar)          | ADMIN           |
| RECRUITER (xx1)           | RECRUITER       |
| HIRING_MANAGER (xx2)      | HIRING_MANAGER  |
| INTERVIEWER (xx3)         | INTERVIEWER     |
| VIEWER (xx4)              | viewer          |

Python ``UserRole`` uses lowercase values (admin, recruiter, …); JWT/UI use those values.
"""

from enum import Enum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.role_labels import (
    PG_ENUM_ADMIN,
    PG_ENUM_CANDIDATE,
    PG_ENUM_HIRING_MANAGER,
    PG_ENUM_INTERVIEWER,
    PG_ENUM_RECRUITER,
    PG_ENUM_VIEWER,
)
from app.models.users import User, UserRole

# Confirmed on Azure Non-Prod (Aug 2026): SQLAlchemy created ``userrole`` using Python
# enum member *names* (UPPERCASE). ``viewer`` was added later as lowercase only.
# Run scripts/verify_pg_userrole_enum.sql on the live DB to re-check after migrations.
PG_USERROLE_LABELS: dict[UserRole, str] = {
    UserRole.ADMIN: PG_ENUM_ADMIN,
    UserRole.RECRUITER: PG_ENUM_RECRUITER,
    UserRole.HIRING_MANAGER: PG_ENUM_HIRING_MANAGER,
    UserRole.INTERVIEWER: PG_ENUM_INTERVIEWER,
    UserRole.VIEWER: PG_ENUM_VIEWER,
    UserRole.CANDIDATE: PG_ENUM_CANDIDATE,
}

_USER_SELECT = """
    SELECT id, email, name, role::text AS role, org_id, hashed_password,
           is_active, is_verified, last_login_at
    FROM users
"""


def _coerce_models_user_role(role: UserRole | Enum | str) -> UserRole:
    """Accept models/rbac ``UserRole`` or raw string → ``models.users.UserRole``."""
    if isinstance(role, UserRole):
        return role
    if isinstance(role, Enum):
        return UserRole(str(role.value).strip().lower())
    normalized = str(role).strip().lower()
    return UserRole(normalized)


def role_to_pg_enum_label(role: UserRole | Enum | str) -> str:
    """Map Python UserRole to live PostgreSQL ``userrole`` enum labels."""
    member = _coerce_models_user_role(role)
    try:
        return PG_USERROLE_LABELS[member]
    except KeyError as exc:
        raise ValueError(f"No PostgreSQL userrole label configured for {member!r}") from exc


def role_from_pg_enum_label(raw: str) -> UserRole:
    """Read role text from PG (ADMIN, viewer, …) → UserRole."""
    label = (raw or "").strip()
    if not label:
        raise ValueError("empty role label from database")

    for member, pg_label in PG_USERROLE_LABELS.items():
        if pg_label == label or pg_label.lower() == label.lower():
            return member

    lowered = label.lower()
    for member in UserRole:
        if member.value == lowered or member.name.lower() == lowered:
            return member

    return UserRole(lowered)


def user_from_row(row) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        role=role_from_pg_enum_label(row.role),
        org_id=row.org_id,
        hashed_password=getattr(row, "hashed_password", None),
        is_active=row.is_active,
        is_verified=row.is_verified,
        last_login_at=getattr(row, "last_login_at", None),
    )


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(
        text(f"{_USER_SELECT} WHERE id = :id"),
        {"id": user_id},
    )
    row = result.one_or_none()
    return user_from_row(row) if row else None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        text(f"{_USER_SELECT} WHERE email = :email"),
        {"email": email.strip().lower()},
    )
    row = result.one_or_none()
    return user_from_row(row) if row else None
