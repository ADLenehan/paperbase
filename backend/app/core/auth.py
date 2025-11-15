"""
Authentication and Authorization Module

Provides JWT token generation/validation, API key management,
and FastAPI dependency for getting the current authenticated user.

Supports two authentication methods:
1. JWT Bearer tokens (for web UI) - short-lived, 24 hours
2. API keys (for MCP/programmatic access) - long-lived, revokable
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.permissions import APIKey
from app.models.settings import User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer security scheme
security = HTTPBearer()


# ====================
# Password Hashing
# ====================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ====================
# JWT Token Management
# ====================

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token for a user

    Args:
        user_id: User ID to encode in token
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[int]:
    """
    Decode and validate a JWT access token

    Args:
        token: JWT token string

    Returns:
        User ID if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        return int(user_id)

    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.JWTError:
        # Invalid token
        return None


# ====================
# API Key Management
# ====================

def create_api_key(user_id: int, name: str = "Default") -> Tuple[str, str]:
    """
    Create a new API key for a user

    Args:
        user_id: User ID to create key for
        name: Friendly name for the key

    Returns:
        Tuple of (plain_key, hashed_key)
        The plain key should be shown to user only once
        The hashed key should be stored in database
    """
    # Generate secure random key with prefix
    plain_key = f"pb_{secrets.token_urlsafe(32)}"

    # Hash the key for storage
    hashed_key = hash_password(plain_key)

    return plain_key, hashed_key


def verify_api_key(db: Session, key: str) -> Optional[User]:
    """
    Verify an API key and return the associated user

    Args:
        db: Database session
        key: Plain API key to verify

    Returns:
        User object if valid, None if invalid
    """
    if not key.startswith("pb_"):
        return None

    # Get all active API keys (we need to check each hash)
    api_keys = db.query(APIKey).filter(
        APIKey.is_active == True
    ).all()

    # Check each key hash
    for api_key in api_keys:
        # Check if key matches
        if verify_password(key, api_key.key_hash):
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                continue

            # Update last used timestamp
            api_key.last_used_at = datetime.utcnow()
            db.commit()

            # Get and return user
            user = db.query(User).filter(
                User.id == api_key.user_id,
                User.is_active == True
            ).first()

            return user

    return None


# ====================
# Authentication Dependency
# ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user

    Supports two authentication methods:
    1. JWT Bearer token (from web UI)
    2. API key (from MCP/programmatic access)

    Args:
        credentials: HTTP Authorization header (Bearer token or API key)
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    # Try JWT token first
    user_id = decode_access_token(token)
    if user_id:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()

        if user:
            return user

    # Try API key
    user = verify_api_key(db, token)
    if user:
        return user

    # Authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency to get the current user and verify they are an admin

    Args:
        current_user: Current authenticated user

    Returns:
        User object (verified admin)

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# ====================
# Optional Dependency for Public Endpoints
# ====================

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication - returns None if no credentials provided

    Useful for endpoints that work differently for authenticated vs anonymous users

    Args:
        credentials: Optional HTTP Authorization header
        db: Database session

    Returns:
        User object if authenticated, None if not
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
