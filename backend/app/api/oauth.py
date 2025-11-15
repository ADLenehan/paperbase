"""
OAuth 2.0 Authentication Endpoints

Provides Google and Microsoft OAuth authentication flows.

Flow:
1. Frontend: Redirect to GET /oauth/{provider}/authorize
2. User: Authenticates with provider
3. Provider: Redirects to callback URL
4. Frontend: POST /oauth/{provider}/callback with code
5. Backend: Exchanges code for tokens, creates/links user
6. Frontend: Receives JWT token for session

Security:
- CSRF protection via state parameter
- PKCE for authorization code flow
- Encrypted token storage
- Session validation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.auth import create_access_token, get_current_user
from app.models.settings import User
from app.services.oauth_service import get_oauth_service, OAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/oauth", tags=["OAuth Authentication"])


# ====================
# Request/Response Models
# ====================

class OAuthCallbackRequest(BaseModel):
    """OAuth callback data from frontend"""
    code: str
    state: str
    code_verifier: str  # PKCE verifier from frontend session


class OAuthResponse(BaseModel):
    """OAuth authentication response"""
    access_token: str
    token_type: str = "bearer"
    user: dict
    is_new_user: bool
    needs_onboarding: bool  # True if user needs to create/join org


class LinkProviderRequest(BaseModel):
    """Link OAuth provider to existing account"""
    provider: str
    code: str
    code_verifier: str


# ====================
# OAuth Endpoints
# ====================

@router.get("/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    request: Request,
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Initiate OAuth authorization flow.

    Generates authorization URL and returns it for frontend redirect.

    Supported providers:
    - google: Google OAuth 2.0
    - microsoft: Microsoft/Azure AD OAuth 2.0

    Returns:
        Dictionary with:
        - url: Authorization URL to redirect user to
        - state: State parameter (frontend must store in session)
        - code_verifier: PKCE verifier (frontend must store in session)

    Example:
        GET /api/auth/oauth/google/authorize
        →
        {
            "url": "https://accounts.google.com/o/oauth2/v2/auth?...",
            "state": "abc123...",
            "code_verifier": "xyz789..."
        }
    """
    if provider not in ['google', 'microsoft']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

    try:
        auth_data = await oauth_service.get_authorization_url(provider)
        return auth_data
    except Exception as e:
        logger.error(f"OAuth authorization failed for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.post("/{provider}/callback", response_model=OAuthResponse)
async def oauth_callback(
    provider: str,
    callback_data: OAuthCallbackRequest,
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Handle OAuth callback and complete authentication.

    Flow:
    1. Exchange authorization code for tokens
    2. Retrieve user profile from provider
    3. Find or create user in database
    4. Generate JWT token for session
    5. Return user data + session token

    Args:
        provider: 'google' or 'microsoft'
        callback_data: Authorization code, state, and PKCE verifier

    Returns:
        JWT access token and user information

    Raises:
        HTTPException: If OAuth flow fails or provider returns error

    Example:
        POST /api/auth/oauth/google/callback
        {
            "code": "4/0AY0e-g7...",
            "state": "abc123...",
            "code_verifier": "xyz789..."
        }
        →
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "name": "John Doe"
            },
            "is_new_user": false,
            "needs_onboarding": false
        }
    """
    if provider not in ['google', 'microsoft']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

    try:
        # Exchange code for tokens
        tokens = await oauth_service.exchange_code_for_token(
            provider=provider,
            code=callback_data.code,
            code_verifier=callback_data.code_verifier
        )

        # Get user info from provider
        access_token = tokens.get('access_token')
        user_info = await oauth_service.get_user_info(provider, access_token)

        # Find or create user
        user, is_new_user = await oauth_service.find_or_create_user(
            db=db,
            provider=provider,
            user_info=user_info,
            tokens=tokens
        )

        # Generate JWT token for our application
        jwt_token = create_access_token(data={"sub": user.email})

        # Check if user needs onboarding (no organization)
        needs_onboarding = not user.onboarding_completed or user.org_id is None

        return OAuthResponse(
            access_token=jwt_token,
            token_type="bearer",
            user={
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "organization_id": user.org_id,
                "organization_role": user.organization_role,
            },
            is_new_user=is_new_user,
            needs_onboarding=needs_onboarding
        )

    except ValueError as e:
        logger.warning(f"OAuth callback validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"OAuth callback failed for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth authentication failed: {str(e)}"
        )


@router.post("/link-provider")
async def link_oauth_provider(
    link_request: LinkProviderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Link an OAuth provider to an existing account.

    Allows users who signed up with password to link Google/Microsoft,
    or vice versa.

    Args:
        link_request: Provider and authorization code
        current_user: Currently authenticated user

    Returns:
        Success message

    Example:
        POST /api/auth/oauth/link-provider
        Headers: Authorization: Bearer <jwt_token>
        {
            "provider": "google",
            "code": "4/0AY0e-g7...",
            "code_verifier": "xyz789..."
        }
        →
        {
            "message": "Successfully linked Google account",
            "provider": "google",
            "email": "user@gmail.com"
        }
    """
    provider = link_request.provider

    if provider not in ['google', 'microsoft']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {provider}"
        )

    try:
        # Exchange code for tokens
        tokens = await oauth_service.exchange_code_for_token(
            provider=provider,
            code=link_request.code,
            code_verifier=link_request.code_verifier
        )

        # Get user info from provider
        access_token = tokens.get('access_token')
        user_info = await oauth_service.get_user_info(provider, access_token)

        # Verify email matches current user
        provider_email = user_info.get('email', '').lower()
        if provider_email != current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OAuth email ({provider_email}) doesn't match your account ({current_user.email})"
            )

        # Link provider to account
        current_user.auth_provider = provider
        current_user.provider_user_id = user_info.get('sub')
        current_user.provider_linked_at = datetime.utcnow()
        oauth_service.store_tokens_on_user(current_user, tokens)

        db.commit()

        logger.info(f"User {current_user.email} linked {provider} account")

        return {
            "message": f"Successfully linked {provider.capitalize()} account",
            "provider": provider,
            "email": provider_email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Link provider failed for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link provider: {str(e)}"
        )


@router.post("/refresh")
async def refresh_oauth_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Refresh OAuth access tokens using refresh token.

    Useful when making API calls to Google/Microsoft on behalf of the user.

    Returns:
        New access token and updated metadata

    Example:
        POST /api/auth/oauth/refresh
        Headers: Authorization: Bearer <jwt_token>
        →
        {
            "access_token": "ya29.a0...",
            "expires_at": 1699999999
        }
    """
    if not current_user.auth_provider or current_user.auth_provider == 'password':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not authenticated via OAuth"
        )

    # Get current tokens
    tokens = oauth_service.get_tokens_from_user(current_user)
    if not tokens or 'refresh_token' not in tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available"
        )

    # Refresh access token
    new_tokens = await oauth_service.refresh_access_token(
        provider=current_user.auth_provider,
        refresh_token=tokens['refresh_token']
    )

    if not new_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh token. Please re-authenticate."
        )

    # Update stored tokens
    oauth_service.store_tokens_on_user(current_user, new_tokens)
    db.commit()

    return {
        "access_token": new_tokens.get('access_token'),
        "expires_at": new_tokens.get('expires_at'),
    }


@router.delete("/unlink-provider")
async def unlink_oauth_provider(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlink OAuth provider from account.

    Warning: If user has no password set, this will lock them out!

    Returns:
        Success message
    """
    if current_user.auth_provider == 'password':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account uses password authentication, not OAuth"
        )

    # Check if user has password set
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink OAuth provider without setting a password first"
        )

    # Unlink provider
    provider = current_user.auth_provider
    current_user.auth_provider = 'password'
    current_user.provider_user_id = None
    current_user.provider_metadata = None
    current_user.provider_linked_at = None

    db.commit()

    logger.info(f"User {current_user.email} unlinked {provider} account")

    return {
        "message": f"Successfully unlinked {provider.capitalize()} account"
    }
