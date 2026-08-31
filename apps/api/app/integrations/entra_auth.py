"""Entra ID SSO helpers — ID token validation and app-role mapping."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import jwt
from jwt import PyJWKClient, PyJWTError

from app.config import settings
from app.core.exceptions import AuthenticationException
from app.core.role_labels import (
    ENTRA_ROLE_ADMIN,
    ENTRA_ROLE_HIRING_MANAGER,
    ENTRA_ROLE_INTERVIEWER,
    ENTRA_ROLE_RECRUITER,
    ENTRA_ROLE_VIEWER,
)
from app.middleware.rbac import UserRole

logger = logging.getLogger(__name__)

# Entra app role *value* strings (AIL-QUANTHIRE-NPD) → QuantHire RBAC roles.
# Keys are canonical UPPERCASE labels after ``_canonical_entra_role_key`` (see below).
# Entra may emit mixed case in the token (e.g. "Recruiter", "RECruiter") — all normalize
# to RECRUITER, matching xx1@malomatia.com and Hazim test users.
ENTRA_ROLE_TO_QUANTHIRE: Dict[str, UserRole] = {
    ENTRA_ROLE_ADMIN: UserRole.ADMIN,
    ENTRA_ROLE_RECRUITER: UserRole.RECRUITER,
    ENTRA_ROLE_HIRING_MANAGER: UserRole.HIRING_MANAGER,
    "HIRINGMANAGER": UserRole.HIRING_MANAGER,
    ENTRA_ROLE_INTERVIEWER: UserRole.INTERVIEWER,
    ENTRA_ROLE_VIEWER: UserRole.VIEWER,
}

# When multiple app roles are assigned, pick the highest-privilege role.
_ROLE_PRIORITY: Tuple[UserRole, ...] = (
    UserRole.ADMIN,
    UserRole.RECRUITER,
    UserRole.HIRING_MANAGER,
    UserRole.INTERVIEWER,
    UserRole.VIEWER,
)

_JWKS_CLIENTS: Dict[str, PyJWKClient] = {}


def entra_sso_configured() -> bool:
    """True when Entra client id + tenant are available for SSO."""
    return bool(settings.azure_ad_client_id and settings.azure_ad_tenant_id)


def _require_entra_configured() -> None:
    if not entra_sso_configured():
        raise AuthenticationException("Entra SSO is not configured on this server")


def _jwks_client_for_tenant(tenant_id: str) -> PyJWKClient:
    client = _JWKS_CLIENTS.get(tenant_id)
    if client is None:
        jwks_uri = (
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )
        client = PyJWKClient(jwks_uri, cache_keys=True)
        _JWKS_CLIENTS[tenant_id] = client
    return client


def _valid_issuers(tenant_id: str) -> Tuple[str, ...]:
    return (
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        f"https://sts.windows.net/{tenant_id}/",
    )


def _normalize_roles_claim(roles_claim: object) -> List[str]:
    if isinstance(roles_claim, str):
        return [roles_claim] if roles_claim.strip() else []
    if isinstance(roles_claim, list):
        return [str(role).strip() for role in roles_claim if role]
    return []


def _canonical_entra_role_key(raw: str) -> str:
    """Normalize Entra ``roles`` claim values to a lookup key (UPPERCASE, underscores)."""
    key = raw.strip().upper().replace("-", "_")
    # "Recruiter Access" / "Hiring Manager" → RECRUITER_ACCESS / HIRING_MANAGER
    key = "_".join(part for part in key.split() if part)
    while "__" in key:
        key = key.replace("__", "_")
    return key


def _pick_quanthire_role(entra_role_names: List[str]) -> UserRole:
    mapped: List[UserRole] = []
    for name in entra_role_names:
        if not name:
            continue
        canonical = _canonical_entra_role_key(name)
        role = ENTRA_ROLE_TO_QUANTHIRE.get(canonical)
        if role is None and canonical.endswith("_ACCESS"):
            # e.g. RECRUITER_ACCESS from display name "Recruiter Access"
            role = ENTRA_ROLE_TO_QUANTHIRE.get(canonical.removesuffix("_ACCESS"))
        if role is not None:
            mapped.append(role)
    if not mapped:
        raise AuthenticationException(
            "No QuantHire application role assigned in Entra ID. "
            "Contact your administrator."
        )
    mapped_set = set(mapped)
    for candidate in _ROLE_PRIORITY:
        if candidate in mapped_set:
            return candidate
    return mapped[0]


def validate_entra_id_token(id_token: str) -> Dict:
    """
    Validate an Entra ID token (signature, audience, issuer, expiry).

    Returns decoded JWT claims.
    """
    _require_entra_configured()
    client_id = settings.azure_ad_client_id
    tenant_id = settings.azure_ad_tenant_id
    if not client_id or not tenant_id:
        raise AuthenticationException("Entra SSO is not configured on this server")

    try:
        jwks_client = _jwks_client_for_tenant(tenant_id)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_iss": False},
            leeway=60,
        )
    except PyJWTError as exc:
        logger.warning("Entra ID token validation failed: %s", exc)
        raise AuthenticationException("Invalid or expired Microsoft sign-in token") from exc

    issuer = payload.get("iss", "")
    if issuer not in _valid_issuers(tenant_id):
        raise AuthenticationException("Invalid Microsoft sign-in token issuer")

    token_tid = str(payload.get("tid") or "").strip()
    if token_tid and token_tid.lower() != tenant_id.lower():
        raise AuthenticationException("Microsoft sign-in token tenant mismatch")

    return payload


def _identity_from_id_token_claims(payload: Dict) -> Dict:
    entra_id = str(payload.get("oid") or payload.get("sub") or "").strip()
    if not entra_id:
        raise AuthenticationException("Microsoft account profile is incomplete")

    email = (
        payload.get("preferred_username")
        or payload.get("email")
        or payload.get("upn")
        or ""
    )
    email = str(email).strip().lower()
    if not email:
        raise AuthenticationException("Microsoft account has no email address")

    name = str(payload.get("name") or email.split("@")[0]).strip()
    role = _pick_quanthire_role(_normalize_roles_claim(payload.get("roles")))

    return {
        "entra_id": entra_id,
        "email": email,
        "name": name,
        "role": role,
    }


async def authenticate_entra_id_token(id_token: str) -> Dict:
    """
    Validate Entra ID token and return profile + mapped QuantHire role.

    Role is read from the token ``roles`` claim (Entra app role assignment).
    Returns dict with keys: entra_id, email, name, role (UserRole).
    """
    payload = validate_entra_id_token(id_token)
    return _identity_from_id_token_claims(payload)


def clear_jwks_cache() -> None:
    """Test helper — reset cached JWKS clients."""
    _JWKS_CLIENTS.clear()
