"""Authentication endpoints."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthenticationException
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.session_cookie import (
    attach_session_cookies,
    clear_session_cookies,
    should_omit_token_from_body,
)
from app.database import get_db
from app.integrations.entra_auth import authenticate_entra_id_token, entra_sso_configured
from app.middleware.rbac import UserRole as RbacUserRole
from app.models.users import User, UserRole
from app.repositories.user_loader import get_user_by_email, get_user_by_id, role_to_pg_enum_label, user_from_row

logger = logging.getLogger(__name__)

router = APIRouter()

_DUMMY_PASSWORD_HASH: str | None = None

# MSAL delegated scopes — openid/profile/email for ID token; User.Read per Entra grant.
ENTRA_LOGIN_SCOPES = [
    "openid",
    "profile",
    "email",
    "User.Read",
]


def _dummy_password_hash() -> str:
    """Lazy init — avoids import-time bcrypt work and eases testing."""
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = get_password_hash("quanthire-timing-neutralizer")
    return _DUMMY_PASSWORD_HASH


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str


class EntraCallbackRequest(BaseModel):
    """Entra SSO callback — frontend sends Entra ID token (roles claim)."""

    id_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    email: str
    name: str
    role: str


class SsoConfigResponse(BaseModel):
    """Public SSO configuration for the frontend MSAL client."""

    enabled: bool
    client_id: Optional[str] = None
    tenant_id: Optional[str] = None
    scopes: list[str] = Field(default_factory=list)


def _role_to_str(role: UserRole | RbacUserRole | str) -> str:
    if hasattr(role, "value"):
        return str(role.value)
    return str(role)


def _coerce_model_user_role(role: UserRole | RbacUserRole | str) -> UserRole:
    """Map RBAC / Entra role to the SQLModel UserRole enum."""
    normalized = _role_to_str(role).strip().lower()
    try:
        return UserRole(normalized)
    except ValueError as exc:
        raise AuthenticationException(f"Unsupported QuantHire role: {normalized}") from exc


_ENTRA_USER_RETURNING = """
    RETURNING id, email, name, role::text AS role, org_id, hashed_password,
              is_active, is_verified
"""

_ENTRA_USER_UPSERT_ENUM = f"""
    INSERT INTO users (
        id, email, name, role, org_id, hashed_password,
        is_active, is_verified, metadata, created_at, updated_at, last_login_at
    )
    VALUES (
        :id, :email, :name, CAST(:role AS userrole), NULL, NULL,
        true, true, '{{}}'::jsonb, :now, :now, :now
    )
    ON CONFLICT (email) DO UPDATE SET
        name = EXCLUDED.name,
        role = EXCLUDED.role,
        is_active = true,
        is_verified = true,
        updated_at = EXCLUDED.updated_at,
        last_login_at = EXCLUDED.last_login_at
    {_ENTRA_USER_RETURNING.strip()}
"""

# Fallback when ``role`` is VARCHAR (legacy deploys) — same bind params as enum upsert.
_ENTRA_USER_UPSERT_VARCHAR = f"""
    INSERT INTO users (
        id, email, name, role, org_id, hashed_password,
        is_active, is_verified, metadata, created_at, updated_at, last_login_at
    )
    VALUES (
        :id, :email, :name, :role, NULL, NULL,
        true, true, '{{}}'::jsonb, :now, :now, :now
    )
    ON CONFLICT (email) DO UPDATE SET
        name = EXCLUDED.name,
        role = EXCLUDED.role,
        is_active = true,
        is_verified = true,
        updated_at = EXCLUDED.updated_at,
        last_login_at = EXCLUDED.last_login_at
    {_ENTRA_USER_RETURNING.strip()}
"""


async def _upsert_entra_user(db: AsyncSession, *, email: str, name: str, role: UserRole) -> User:
    """Create or update a user record synced from Entra SSO."""
    normalized_email = email.strip().lower()
    display_name = (name or normalized_email.split("@")[0]).strip() or normalized_email
    role_value = role_to_pg_enum_label(role)
    now = datetime.utcnow()
    params = {
        "id": uuid4(),
        "email": normalized_email,
        "name": display_name,
        "role": role_value,
        "now": now,
    }

    last_exc: SQLAlchemyError | None = None
    for sql in (_ENTRA_USER_UPSERT_ENUM, _ENTRA_USER_UPSERT_VARCHAR):
        try:
            row = await db.execute(text(sql), params)
            record = row.one()
            await db.commit()
            try:
                return user_from_row(record)
            except ValueError as exc:
                await db.rollback()
                logger.error(
                    "Entra user row parse failed for %s (role=%s): %s",
                    normalized_email,
                    role_value,
                    exc,
                )
                raise ValueError(
                    f"User saved but role could not be read back: {exc}"
                ) from exc
        except SQLAlchemyError as exc:
            await db.rollback()
            last_exc = exc
            err = str(exc).lower()
            if sql is _ENTRA_USER_UPSERT_ENUM and (
                "userrole" in err or "type" in err or "cast" in err or "enum" in err
            ):
                logger.warning(
                    "Entra user enum upsert failed for %s (role=%s), retrying varchar: %s",
                    normalized_email,
                    role_value,
                    exc,
                )
                continue
            logger.error(
                "Entra user upsert failed for %s (role=%s): %s",
                normalized_email,
                role_value,
                exc,
                exc_info=True,
            )
            raise

    assert last_exc is not None
    logger.error(
        "Entra user upsert failed for %s (role=%s): %s",
        normalized_email,
        role_value,
        last_exc,
        exc_info=True,
    )
    raise last_exc


def _token_response_for_user(user: User, *, include_access_token: bool = True) -> TokenResponse:
    role = _role_to_str(user.role)
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=role,
        org_id=user.org_id,
    )
    return TokenResponse(
        access_token=access_token if include_access_token else "",
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=role,
    )


def _finalize_auth_response(response: Response, user: User) -> TokenResponse:
    """Issue JWT in HttpOnly cookie; omit token from JSON body in hardened envs."""
    role = _role_to_str(user.role)
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=role,
        org_id=user.org_id,
    )
    attach_session_cookies(response, access_token)
    return TokenResponse(
        access_token=access_token if not should_omit_token_from_body() else "",
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=role,
    )


@router.get("/sso-config", response_model=SsoConfigResponse)
async def get_sso_config() -> SsoConfigResponse:
    """Return Entra SSO settings for the frontend (no secrets)."""
    enabled = entra_sso_configured()
    return SsoConfigResponse(
        enabled=enabled,
        client_id=settings.azure_ad_client_id if enabled else None,
        tenant_id=settings.azure_ad_tenant_id if enabled else None,
        scopes=list(ENTRA_LOGIN_SCOPES) if enabled else [],
    )


@router.post("/entra/callback", response_model=TokenResponse)
async def entra_callback(
    request: EntraCallbackRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange an Entra ID token for a QuantHire JWT.

    Validates the ID token, reads the ``roles`` claim, maps Entra role → QuantHire RBAC,
    upserts the user, and returns JWT.
    """
    if not entra_sso_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra SSO is not configured",
        )

    identity: dict | None = None
    try:
        identity = await authenticate_entra_id_token(request.id_token)
        quanthire_role = _coerce_model_user_role(identity["role"])
        pg_role_label = role_to_pg_enum_label(quanthire_role)

        logger.info(
            "Entra SSO callback upserting user email=%s role=%s pg_role=%s",
            identity["email"],
            _role_to_str(quanthire_role),
            pg_role_label,
        )

        user = await _upsert_entra_user(
            db,
            email=identity["email"],
            name=identity["name"],
            role=quanthire_role,
        )
        return _finalize_auth_response(response, user)

    except AuthenticationException:
        raise
    except (SQLAlchemyError, ValueError) as exc:
        logger.error(
            "Entra SSO callback database error (email=%s): %s",
            (identity or {}).get("email", "unknown"),
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Microsoft sign-in failed while saving your account. "
                "Please contact your administrator."
            ),
        ) from exc
    except Exception as e:
        logger.error(
            "Entra SSO callback failed (email=%s): %s",
            (identity or {}).get("email", "unknown"),
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Microsoft sign-in failed. Please try again.",
        ) from e


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Login endpoint with JWT token generation.
    
    Authenticates user with email and password, returns JWT token.
    In production, this can integrate with SSO providers.
    """
    try:
        # Find user by email
        user = await get_user_by_email(db, request.email)
        
        if user is None:
            verify_password(request.password, _dummy_password_hash())
            raise AuthenticationException("Invalid email or password")
        
        if not user.is_active:
            raise AuthenticationException("User account is inactive")
        
        # Verify password
        if not user.hashed_password:
            # User doesn't have a password set (SSO-only user)
            raise AuthenticationException(
                "Password authentication not available. Please use SSO."
            )
        
        if not verify_password(request.password, user.hashed_password):
            raise AuthenticationException("Invalid email or password")
        
        now = datetime.utcnow()
        await db.execute(
            text("UPDATE users SET last_login_at = :now WHERE id = :id"),
            {"now": now, "id": user.id},
        )
        await db.commit()
        user.last_login_at = now

        return _finalize_auth_response(response, user)
        
    except AuthenticationException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Login database error: {e}", exc_info=True)
        raise AuthenticationException("Invalid email or password") from e
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Logout endpoint — clears HttpOnly session cookies."""
    clear_session_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get current user information from JWT token.
    
    Requires authentication via Bearer token in Authorization header.
    """
    from app.core.deps import get_current_user
    
    # Use the dependency to get authenticated user
    user = await get_current_user(request, authorization)
    
    # Get full user details from database (for name, etc.)
    db_user = await get_user_by_id(db, UUID(user["id"]))
    
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "name": db_user.name if db_user else user.get("name", ""),
        "role": user.get("role"),
        "org_id": user.get("org_id"),
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
    }
