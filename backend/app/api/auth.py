"""
Authentication API Endpoints

Provides login, logout, and API key management endpoints.

Authentication Methods:
1. JWT Tokens (for web UI) - POST /auth/login returns token
2. API Keys (for MCP/scripts) - POST /auth/api-keys creates key

Both methods use the same get_current_user() dependency for authorization.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import (
    create_access_token,
    create_api_key,
    hash_password,
    verify_password,
    get_current_user,
    get_current_active_admin
)
from app.models.settings import User
from app.models.permissions import APIKey

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ====================
# Request/Response Models
# ====================

class LoginRequest(BaseModel):
    """Login credentials"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT token"""
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str


class CreateAPIKeyRequest(BaseModel):
    """Create API key request"""
    name: str
    expires_in_days: Optional[int] = None  # None = never expires


class APIKeyResponse(BaseModel):
    """API key response (includes plain key only once)"""
    id: int
    name: str
    key: str  # Plain key - show only once!
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyListItem(BaseModel):
    """API key list item (no plain key)"""
    id: int
    name: str
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    is_active: bool


# ====================
# Authentication Endpoints
# ====================

@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password

    Returns JWT access token for web UI authentication.
    Token expires after 24 hours (configurable in settings).
    """
    # Find user by email
    user = db.query(User).filter(
        User.email == credentials.email,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Check password
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password not set. Please contact administrator."
        )

    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create access token
    access_token = create_access_token(user.id)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin,
            "org_id": user.org_id
        }
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user

    Note: JWT tokens cannot be truly invalidated server-side.
    Client should discard the token. For true logout, implement
    a token blacklist or use short-lived tokens.
    """
    return {"message": "Logged out successfully"}


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "is_admin": current_user.is_admin,
        "org_id": current_user.org_id,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at
    }


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""

    # Verify current password
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password not set"
        )

    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    # Update password
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


# ====================
# API Key Management
# ====================

@router.post("/api-keys", response_model=APIKeyResponse)
def create_user_api_key(
    request: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for the current user

    IMPORTANT: The plain key is returned only once. Store it securely!

    Use cases:
    - MCP server authentication
    - Script/CLI access
    - Third-party integrations
    """
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Generate API key
    plain_key, hashed_key = create_api_key(current_user.id, request.name)

    # Create database record
    api_key = APIKey(
        user_id=current_user.id,
        name=request.name,
        key_hash=hashed_key,
        expires_at=expires_at,
        created_by_user_id=current_user.id
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only time this is returned!
        expires_at=api_key.expires_at,
        created_at=api_key.created_at
    )


@router.get("/api-keys", response_model=List[APIKeyListItem])
def list_user_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys for the current user"""
    api_keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id
    ).order_by(APIKey.created_at.desc()).all()

    return [
        APIKeyListItem(
            id=key.id,
            name=key.name,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            is_active=key.is_active
        )
        for key in api_keys
    ]


@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke (deactivate) an API key

    The key is soft-deleted (is_active=False) to preserve audit trail.
    """
    # Find key
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Revoke key
    api_key.is_active = False
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_by_user_id = current_user.id
    db.commit()

    return {"message": "API key revoked successfully"}


# ====================
# Admin-Only Endpoints
# ====================

@router.post("/users/{user_id}/api-keys", response_model=APIKeyResponse)
def create_api_key_for_user(
    user_id: int,
    request: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: Create an API key for any user

    This is useful for setting up service accounts or helping users
    who need API keys created on their behalf.
    """
    # Find target user
    target_user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Generate API key
    plain_key, hashed_key = create_api_key(target_user.id, request.name)

    # Create database record
    api_key = APIKey(
        user_id=target_user.id,
        name=request.name,
        key_hash=hashed_key,
        expires_at=expires_at,
        created_by_user_id=current_user.id  # Admin who created it
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at
    )


@router.get("/users/{user_id}/api-keys", response_model=List[APIKeyListItem])
def list_user_api_keys_admin(
    user_id: int,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Admin: List API keys for any user"""
    api_keys = db.query(APIKey).filter(
        APIKey.user_id == user_id
    ).order_by(APIKey.created_at.desc()).all()

    return [
        APIKeyListItem(
            id=key.id,
            name=key.name,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            is_active=key.is_active
        )
        for key in api_keys
    ]
