"""Auth API tests for Entra SSO endpoints."""

import pytest

pytest.importorskip("pgvector")

from app.api.v1.auth import (  # noqa: E402
    EntraCallbackRequest,
    entra_callback,
    get_sso_config,
)
from app.api.v1 import auth as auth_module  # noqa: E402
from app.middleware.rbac import UserRole
from app.models.users import User
from starlette.responses import Response


@pytest.mark.asyncio
async def test_sso_config_disabled_without_entra(monkeypatch):
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: False)

    result = await get_sso_config()

    assert result.enabled is False
    assert result.client_id is None
    assert result.scopes == []


@pytest.mark.asyncio
async def test_sso_config_enabled_on_azure_nonprod(monkeypatch):
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.settings,
        "azure_ad_client_id",
        "221c7e05-6581-4226-9a08-96a4011dd5ce",
    )
    monkeypatch.setattr(
        auth_module.settings,
        "azure_ad_tenant_id",
        "68bae048-c310-4ec2-934f-cbc2588f30fe",
    )

    result = await get_sso_config()

    assert result.enabled is True
    assert result.client_id == "221c7e05-6581-4226-9a08-96a4011dd5ce"
    assert "User.Read" in result.scopes
    assert "openid" in result.scopes


@pytest.mark.asyncio
async def test_entra_callback_issues_jwt(monkeypatch):
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.settings,
        "jwt_secret_key",
        "unit-test-jwt-secret-key-32chars-min",
    )

    async def fake_authenticate(_token: str):
        return {
            "entra_id": "entra-1",
            "email": "xx1@malomatia.com",
            "name": "Recruiter One",
            "role": UserRole.RECRUITER,
        }

    from uuid import uuid4

    stored_user = User(
        id=uuid4(),
        email="xx1@malomatia.com",
        name="Recruiter One",
        role=auth_module.UserRole.RECRUITER,
        is_active=True,
        is_verified=True,
    )

    async def fake_upsert(_db, *, email, name, role):
        assert email == "xx1@malomatia.com"
        assert role == auth_module.UserRole.RECRUITER
        return stored_user

    monkeypatch.setattr(auth_module, "authenticate_entra_id_token", fake_authenticate)
    monkeypatch.setattr(auth_module, "_upsert_entra_user", fake_upsert)

    response = await entra_callback(
        EntraCallbackRequest(id_token="x" * 30),
        response=Response(),
        db=None,
    )

    assert response.email == "xx1@malomatia.com"
    assert response.role == "recruiter"
    assert response.access_token


@pytest.mark.asyncio
async def test_entra_callback_viewer_role(monkeypatch):
    """Regression: xx4 VIEWER Entra login must not 500 on user upsert."""
    monkeypatch.setattr(auth_module, "entra_sso_configured", lambda: True)
    monkeypatch.setattr(
        auth_module.settings,
        "jwt_secret_key",
        "unit-test-jwt-secret-key-32chars-min",
    )

    async def fake_authenticate(_token: str):
        return {
            "entra_id": "entra-4",
            "email": "xx4@malomatia.com",
            "name": "Viewer Four",
            "role": UserRole.VIEWER,
        }

    from uuid import uuid4

    stored_user = User(
        id=uuid4(),
        email="xx4@malomatia.com",
        name="Viewer Four",
        role=auth_module.UserRole.VIEWER,
        is_active=True,
        is_verified=True,
    )

    captured: dict = {}

    async def fake_upsert(_db, *, email, name, role):
        captured["email"] = email
        captured["role"] = role
        return stored_user

    monkeypatch.setattr(auth_module, "authenticate_entra_id_token", fake_authenticate)
    monkeypatch.setattr(auth_module, "_upsert_entra_user", fake_upsert)

    response = await entra_callback(
        EntraCallbackRequest(id_token="x" * 30),
        response=Response(),
        db=None,
    )

    assert response.email == "xx4@malomatia.com"
    assert response.role == "viewer"
    assert captured["role"] == auth_module.UserRole.VIEWER


def test_coerce_model_user_role_normalizes_viewer():
    role = auth_module._coerce_model_user_role("VIEWER")
    assert role == auth_module.UserRole.VIEWER
    assert role.value == "viewer"


def test_role_to_pg_enum_label_matches_live_azure():
    from app.repositories.user_loader import (
        PG_USERROLE_LABELS,
        role_from_pg_enum_label,
        role_to_pg_enum_label,
    )

    for member, pg_label in PG_USERROLE_LABELS.items():
        assert role_to_pg_enum_label(member) == pg_label
        assert role_from_pg_enum_label(pg_label) == member


@pytest.mark.parametrize(
    ("email", "entra_role", "pg_label", "jwt_role", "ui_label"),
    [
        ("xx1@malomatia.com", "RECRUITER", "RECRUITER", "recruiter", "RECRUITER"),
        ("xx1@malomatia.com", "Recruiter", "RECRUITER", "recruiter", "RECRUITER"),
        ("xx1@malomatia.com", "RECruiter", "RECRUITER", "recruiter", "RECRUITER"),
        ("xx2@malomatia.com", "HIRING_MANAGER", "HIRING_MANAGER", "hiring_manager", "HIRING_MANAGER"),
        ("xx3@malomatia.com", "INTERVIEWER", "INTERVIEWER", "interviewer", "INTERVIEWER"),
        ("xx4@malomatia.com", "VIEWER", "viewer", "viewer", "VIEWER"),
        ("prakumar@malomatia.com", "ADMIN", "ADMIN", "admin", "ADMIN"),
    ],
)
def test_hazim_test_users_full_role_chain(email, entra_role, pg_label, jwt_role, ui_label):
    """Validate Entra → Python → PostgreSQL → JWT → UI for Hazim's test accounts."""
    from app.integrations.entra_auth import _pick_quanthire_role
    from app.repositories.user_loader import role_from_pg_enum_label, role_to_pg_enum_label

    rbac_role = _pick_quanthire_role([entra_role])

    model_role = auth_module._coerce_model_user_role(rbac_role)
    assert role_to_pg_enum_label(model_role) == pg_label
    assert role_from_pg_enum_label(pg_label) == model_role
    assert auth_module._role_to_str(model_role) == jwt_role

    role_labels = {
        "admin": "ADMIN",
        "recruiter": "RECRUITER",
        "hiring_manager": "HIRING_MANAGER",
        "interviewer": "INTERVIEWER",
        "viewer": "VIEWER",
    }
    assert role_labels[jwt_role] == ui_label
    assert email.endswith("@malomatia.com")
