"""Unit tests for Entra SSO user upsert and PostgreSQL role mapping."""

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import auth as auth_module
from app.middleware.rbac import UserRole as RbacUserRole
from app.models.users import UserRole
from app.repositories.user_loader import (
    PG_USERROLE_LABELS,
    role_from_pg_enum_label,
    role_to_pg_enum_label,
)


@pytest.mark.parametrize(
    ("role", "pg_label"),
    [
        (UserRole.ADMIN, "ADMIN"),
        (UserRole.RECRUITER, "RECRUITER"),
        (UserRole.HIRING_MANAGER, "HIRING_MANAGER"),
        (UserRole.INTERVIEWER, "INTERVIEWER"),
        (UserRole.VIEWER, "viewer"),
        (UserRole.CANDIDATE, "CANDIDATE"),
        (RbacUserRole.RECRUITER, "RECRUITER"),
        (RbacUserRole.VIEWER, "viewer"),
        ("recruiter", "RECRUITER"),
    ],
)
def test_role_to_pg_enum_label_accepts_rbac_and_strings(role, pg_label):
    assert role_to_pg_enum_label(role) == pg_label


def test_role_from_pg_enum_label_round_trip():
    for member, pg_label in PG_USERROLE_LABELS.items():
        assert role_from_pg_enum_label(pg_label) == member
        assert role_from_pg_enum_label(pg_label.lower()) == member


@pytest.mark.asyncio
async def test_upsert_entra_user_uses_uppercase_recruiter_label():
    captured: dict = {"sql": "", "params": {}}

    class FakeRow:
        id = "00000000-0000-0000-0000-000000000001"
        email = "xx1@malomatia.com"
        name = "Recruiter One"
        role = "RECRUITER"
        org_id = None
        hashed_password = None
        is_active = True
        is_verified = True

    class FakeResult:
        def one(self):
            return FakeRow()

    class FakeSession:
        async def execute(self, query, params=None):
            captured["sql"] = str(query)
            captured["params"] = params or {}
            return FakeResult()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    user = await auth_module._upsert_entra_user(
        FakeSession(),
        email="xx1@malomatia.com",
        name="Recruiter One",
        role=UserRole.RECRUITER,
    )

    assert user.email == "xx1@malomatia.com"
    assert user.role == UserRole.RECRUITER
    assert captured["params"]["role"] == "RECRUITER"
    assert "CAST" in captured["sql"] or "cast" in captured["sql"].lower()


@pytest.mark.asyncio
async def test_upsert_entra_user_viewer_uses_lowercase_pg_label():
    captured: dict = {"params": {}}

    class FakeRow:
        id = "00000000-0000-0000-0000-000000000004"
        email = "xx4@malomatia.com"
        name = "Viewer Four"
        role = "viewer"
        org_id = None
        hashed_password = None
        is_active = True
        is_verified = True

    class FakeResult:
        def one(self):
            return FakeRow()

    class FakeSession:
        async def execute(self, query, params=None):
            captured["params"] = params or {}
            return FakeResult()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    user = await auth_module._upsert_entra_user(
        FakeSession(),
        email="xx4@malomatia.com",
        name="Viewer Four",
        role=UserRole.VIEWER,
    )

    assert user.role == UserRole.VIEWER
    assert captured["params"]["role"] == "viewer"


@pytest.mark.asyncio
async def test_upsert_entra_user_falls_back_to_varchar_on_enum_error():
    calls: list[str] = []

    class FakeRow:
        id = "00000000-0000-0000-0000-000000000001"
        email = "xx1@malomatia.com"
        name = "Recruiter One"
        role = "RECRUITER"
        org_id = None
        hashed_password = None
        is_active = True
        is_verified = True

    class FakeResult:
        def one(self):
            return FakeRow()

    class FakeSession:
        async def execute(self, query, params=None):
            sql = str(query)
            calls.append(sql)
            if "CAST" in sql or "cast" in sql.lower():
                raise SQLAlchemyError("invalid input value for enum userrole")
            return FakeResult()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    user = await auth_module._upsert_entra_user(
        FakeSession(),
        email="xx1@malomatia.com",
        name="Recruiter One",
        role=UserRole.RECRUITER,
    )

    assert user.email == "xx1@malomatia.com"
    assert len(calls) == 2
