"""End-to-end SSO flow tests (Entra token → upsert → JWT)."""

import pytest
from uuid import uuid4

pytest.importorskip("pgvector")

from app.api.v1.auth import EntraCallbackRequest, entra_callback  # noqa: E402
from app.api.v1 import auth as auth_module  # noqa: E402
from app.middleware.rbac import UserRole
from app.models.users import User
from starlette.responses import Response


@pytest.mark.parametrize(
    ("email", "name"),
    [
        ("vbhushan@malomatia.com", "Vaibhav Bharat Bhushan"),
        ("rcambell@malomatia.com", "Rohan Cambell"),
        ("kpole@malomatia.com", "Ketaki Pole"),
        ("rxavier@malomatia.com", "Romin Xavier"),
        ("nsahare@malomatia.com", "Nisha Sahare"),
        ("mvismonte@malomatia.com", "Melanie Carlos Vismonte"),
        ("pdudhnale@malomatia.com", "Pradeep Dudhnale"),
        ("rgirle@malomatia.com", "Richard Duncan Girle"),
    ],
)
def test_hr_recruiter_entra_role_matches_xx1(email, name):
    """Each HR recruiter must map to the same RECRUITER role as xx1@malomatia.com."""
    from app.integrations.entra_auth import _identity_from_id_token_claims
    from app.repositories.user_loader import role_to_pg_enum_label

    for entra_role in ("RECRUITER", "Recruiter"):
        identity = _identity_from_id_token_claims(
            {
                "oid": f"oid-{email.split('@')[0]}",
                "name": name,
                "preferred_username": email,
                "roles": [entra_role],
            }
        )
        assert identity["email"] == email
        assert identity["role"] == UserRole.RECRUITER
        assert role_to_pg_enum_label(identity["role"]) == "RECRUITER"


@pytest.mark.asyncio
async def test_entra_callback_full_flow_with_real_upsert(monkeypatch):
    """Regression: callback must use _upsert_entra_user (not stale ORM path)."""
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.settings,
        "jwt_secret_key",
        "unit-test-jwt-secret-key-32chars-min",
    )

    async def fake_authenticate(_token: str):
        return {
            "entra_id": "entra-xx4",
            "email": "xx4@malomatia.com",
            "name": "Viewer Four",
            "role": UserRole.VIEWER,
        }

    monkeypatch.setattr(auth_module, "authenticate_entra_id_token", fake_authenticate)

    stored_user = User(
        id=uuid4(),
        email="xx4@malomatia.com",
        name="Viewer Four",
        role=auth_module.UserRole.VIEWER,
        is_active=True,
        is_verified=True,
    )

    upsert_calls: list[dict] = []

    async def spy_upsert(_db, *, email, name, role):
        upsert_calls.append({"email": email, "name": name, "role": role})
        assert role == auth_module.UserRole.VIEWER
        return stored_user

    monkeypatch.setattr(auth_module, "_upsert_entra_user", spy_upsert)

    response = await entra_callback(
        EntraCallbackRequest(id_token="x" * 40),
        response=Response(),
        db=None,
    )

    assert len(upsert_calls) == 1
    assert response.email == "xx4@malomatia.com"
    assert response.role == "viewer"
    assert response.user_id == stored_user.id


@pytest.mark.asyncio
async def test_entra_callback_all_hazim_roles_map_before_upsert(monkeypatch):
    """Every Hazim test Entra role must reach upsert with correct models.UserRole."""
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.settings,
        "jwt_secret_key",
        "unit-test-jwt-secret-key-32chars-min",
    )

    cases = [
        ("xx1@malomatia.com", UserRole.RECRUITER, "recruiter"),
        ("xx2@malomatia.com", UserRole.HIRING_MANAGER, "hiring_manager"),
        ("xx3@malomatia.com", UserRole.INTERVIEWER, "interviewer"),
        ("xx4@malomatia.com", UserRole.VIEWER, "viewer"),
        ("prakumar@malomatia.com", UserRole.ADMIN, "admin"),
    ]

    for email, entra_role, jwt_role in cases:

        async def fake_authenticate(_token: str, role=entra_role, em=email):
            return {
                "entra_id": f"entra-{em}",
                "email": em,
                "name": em.split("@")[0],
                "role": role,
            }

        monkeypatch.setattr(auth_module, "authenticate_entra_id_token", fake_authenticate)

        stored_user = User(
            id=uuid4(),
            email=email,
            name=email.split("@")[0],
            role=auth_module.UserRole(jwt_role),
            is_active=True,
            is_verified=True,
        )

        async def fake_upsert(_db, *, email, name, role):
            assert role == auth_module.UserRole(jwt_role)
            return stored_user

        monkeypatch.setattr(auth_module, "_upsert_entra_user", fake_upsert)

        response = await entra_callback(
            EntraCallbackRequest(id_token="x" * 40),
            response=Response(),
            db=None,
        )
        assert response.role == jwt_role
