"""Unit tests for Entra SSO ID token role mapping."""

import pytest

from app.core.exceptions import AuthenticationException
from app.integrations import entra_auth
from app.integrations.entra_auth import (
    ENTRA_ROLE_TO_QUANTHIRE,
    _identity_from_id_token_claims,
    _normalize_roles_claim,
    _pick_quanthire_role,
    authenticate_entra_id_token,
    clear_jwks_cache,
    validate_entra_id_token,
)
from app.middleware.rbac import UserRole


def test_entra_role_mapping_includes_viewer():
    assert ENTRA_ROLE_TO_QUANTHIRE["VIEWER"] == UserRole.VIEWER
    assert ENTRA_ROLE_TO_QUANTHIRE["RECRUITER"] == UserRole.RECRUITER


@pytest.mark.parametrize(
    "entra_role",
    [
        "RECRUITER",
        "Recruiter",
        "RECruiter",
        "recruiter",
        "Recruiter Access",
    ],
)
def test_pick_quanthire_role_accepts_recruiter_spelling_variants(entra_role):
    role = _pick_quanthire_role([entra_role])
    assert role == UserRole.RECRUITER


def test_canonical_entra_role_key_normalizes_spaces_and_hyphens():
    from app.integrations.entra_auth import _canonical_entra_role_key

    assert _canonical_entra_role_key("RECruiter") == "RECRUITER"
    assert _canonical_entra_role_key("Hiring Manager") == "HIRING_MANAGER"
    assert _canonical_entra_role_key(" hiring-manager ") == "HIRING_MANAGER"


def test_pick_highest_priority_role():
    role = _pick_quanthire_role(["VIEWER", "RECRUITER"])
    assert role == UserRole.RECRUITER


def test_pick_role_raises_when_unassigned():
    with pytest.raises(AuthenticationException):
        _pick_quanthire_role(["UNKNOWN_ROLE"])


def test_normalize_roles_claim_accepts_string_or_list():
    assert _normalize_roles_claim("RECRUITER") == ["RECRUITER"]
    assert _normalize_roles_claim(["VIEWER", "ADMIN"]) == ["VIEWER", "ADMIN"]


def test_identity_from_id_token_claims():
    payload = {
        "oid": "entra-user-1",
        "name": "Test Recruiter",
        "preferred_username": "xx1@malomatia.com",
        "roles": ["RECRUITER"],
    }
    identity = _identity_from_id_token_claims(payload)
    assert identity["email"] == "xx1@malomatia.com"
    assert identity["role"] == UserRole.RECRUITER
    assert identity["name"] == "Test Recruiter"


@pytest.mark.asyncio
async def test_authenticate_entra_id_token_success(monkeypatch):
    clear_jwks_cache()

    def fake_validate(_token: str):
        return {
            "oid": "entra-user-1",
            "name": "Test Recruiter",
            "preferred_username": "xx1@malomatia.com",
            "roles": ["RECRUITER"],
        }

    monkeypatch.setattr(entra_auth, "validate_entra_id_token", fake_validate)
    monkeypatch.setattr(entra_auth.settings, "azure_ad_client_id", "client-id")
    monkeypatch.setattr(entra_auth.settings, "azure_ad_tenant_id", "tenant-id")

    identity = await authenticate_entra_id_token("fake-token")
    assert identity["email"] == "xx1@malomatia.com"
    assert identity["role"] == UserRole.RECRUITER
    assert identity["name"] == "Test Recruiter"


def test_validate_entra_id_token_rejects_invalid_signature(monkeypatch):
    clear_jwks_cache()

    class FakeSigningKey:
        key = "fake"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
            return FakeSigningKey()

    def fake_decode(*_args, **_kwargs):
        raise entra_auth.PyJWTError("bad signature")

    monkeypatch.setattr(entra_auth, "_jwks_client_for_tenant", lambda _tenant: FakeJwksClient())
    monkeypatch.setattr(entra_auth.jwt, "decode", fake_decode)
    monkeypatch.setattr(entra_auth.settings, "azure_ad_client_id", "client-id")
    monkeypatch.setattr(entra_auth.settings, "azure_ad_tenant_id", "tenant-id")

    with pytest.raises(AuthenticationException):
        validate_entra_id_token("bad-token")


def test_validate_entra_id_token_rejects_tenant_mismatch(monkeypatch):
    clear_jwks_cache()

    class FakeSigningKey:
        key = "fake"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
            return FakeSigningKey()

    def fake_decode(*_args, **_kwargs):
        return {
            "iss": "https://login.microsoftonline.com/expected-tenant/v2.0",
            "tid": "wrong-tenant-id",
        }

    monkeypatch.setattr(entra_auth, "_jwks_client_for_tenant", lambda _tenant: FakeJwksClient())
    monkeypatch.setattr(entra_auth.jwt, "decode", fake_decode)
    monkeypatch.setattr(entra_auth.settings, "azure_ad_client_id", "client-id")
    monkeypatch.setattr(entra_auth.settings, "azure_ad_tenant_id", "expected-tenant")

    with pytest.raises(AuthenticationException, match="tenant mismatch"):
        validate_entra_id_token("token-with-wrong-tid")


def test_validate_entra_id_token_accepts_matching_tenant(monkeypatch):
    clear_jwks_cache()

    class FakeSigningKey:
        key = "fake"

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token: str) -> FakeSigningKey:
            return FakeSigningKey()

    tenant = "68bae048-c310-4ec2-934f-cbc2588f30fe"

    def fake_decode(*_args, **_kwargs):
        return {
            "iss": f"https://login.microsoftonline.com/{tenant}/v2.0",
            "tid": tenant,
            "oid": "user-1",
        }

    monkeypatch.setattr(entra_auth, "_jwks_client_for_tenant", lambda _tenant: FakeJwksClient())
    monkeypatch.setattr(entra_auth.jwt, "decode", fake_decode)
    monkeypatch.setattr(entra_auth.settings, "azure_ad_client_id", "221c7e05-6581-4226-9a08-96a4011dd5ce")
    monkeypatch.setattr(entra_auth.settings, "azure_ad_tenant_id", tenant)

    payload = validate_entra_id_token("valid-token")
    assert payload["tid"] == tenant
