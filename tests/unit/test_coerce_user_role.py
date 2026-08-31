"""Unit tests for RBAC role coercion across JWT / Entra / PostgreSQL spellings."""

import pytest

from app.middleware.rbac import UserRole, coerce_user_role


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("recruiter", UserRole.RECRUITER),
        ("RECRUITER", UserRole.RECRUITER),
        ("Recruiter", UserRole.RECRUITER),
        ("RECruiter", UserRole.RECRUITER),
        (UserRole.RECRUITER, UserRole.RECRUITER),
        ("admin", UserRole.ADMIN),
        ("ADMIN", UserRole.ADMIN),
        ("viewer", UserRole.VIEWER),
        ("VIEWER", UserRole.VIEWER),
        ("hiring_manager", UserRole.HIRING_MANAGER),
        ("HIRING_MANAGER", UserRole.HIRING_MANAGER),
    ],
)
def test_coerce_user_role_accepts_all_canonical_spellings(raw, expected):
    assert coerce_user_role(raw) == expected


def test_coerce_user_role_rejects_unknown():
    with pytest.raises(ValueError):
        coerce_user_role("RecruiterAccess")
