"""Security utilities for JWT token handling and password hashing."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthenticationException
from app.repositories.user_loader import get_user_by_id

logger = logging.getLogger(__name__)

_INSECURE_JWT_SECRETS = frozenset(
    {
        "your-jwt-secret-key-change-this",
        "changeme",
        "secret",
        "",
    }
)


def _validate_jwt_secret() -> None:
    """Refuse to sign or verify tokens with a known-weak secret in hardened envs."""
    secret = settings.jwt_secret_key
    if secret in _INSECURE_JWT_SECRETS or len(secret) < 32:
        if settings.is_hardened:
            raise AuthenticationException(
                "JWT_SECRET_KEY must be set to a strong value (32+ chars) in this environment"
            )
        logger.warning(
            "Using weak JWT secret — acceptable for local development only"
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(
    user_id: UUID,
    email: str,
    role: str,
    org_id: Optional[UUID] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User ID
        email: User email
        role: User role
        org_id: Organization ID (optional)
        expires_delta: Custom expiration time (optional)
        
    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)

    _validate_jwt_secret()

    to_encode = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    if org_id:
        to_encode["org_id"] = str(org_id)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return encoded_jwt


async def verify_token(
    token: str,
    db: AsyncSession,
) -> Dict:
    """
    Verify JWT token and return user information.
    
    Args:
        token: JWT token string
        db: Database session
        
    Returns:
        User dictionary with id, email, role, org_id, is_active
        
    Raises:
        AuthenticationException: If token is invalid or expired
    """
    try:
        _validate_jwt_secret()
        # Decode and verify token
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        # Extract user ID from token
        user_id_str: Optional[str] = payload.get("sub")
        if user_id_str is None:
            raise AuthenticationException("Token missing subject (user ID)")
        
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise AuthenticationException("Invalid user ID in token")
        
        # Get user from database (role::text — avoids PG enum / ORM mismatch on viewer)
        user = await get_user_by_id(db, user_id)
        
        if user is None:
            raise AuthenticationException("User not found")
        
        if not user.is_active:
            raise AuthenticationException("User account is inactive")
        
        # Return user information
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "org_id": str(user.org_id) if user.org_id else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        }
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise AuthenticationException("Invalid or expired token")
    except Exception as e:
        logger.error(f"Token verification error: {e}", exc_info=True)
        raise AuthenticationException("Token verification failed")
