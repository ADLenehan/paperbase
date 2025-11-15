"""
OAuth 2.0 Service for Google and Microsoft authentication

Supports:
- Google OAuth 2.0 (Sign in with Google)
- Microsoft OAuth 2.0 / Azure AD (Sign in with Microsoft)
- PKCE flow for security
- Token refresh
- Profile retrieval

Security Features:
- CSRF protection via state parameter
- PKCE (Proof Key for Code Exchange)
- Encrypted token storage
- Scope minimal permissions
"""

import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from starlette.config import Config

from app.models.settings import User
from app.utils.encryption import decrypt_oauth_tokens, encrypt_oauth_tokens

logger = logging.getLogger(__name__)


# OAuth Configuration
class OAuthConfig:
    """OAuth provider configurations"""

    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback/google")

    # Microsoft OAuth
    MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common")  # 'common' allows any Microsoft account
    MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5173/auth/callback/microsoft")

    # Scopes
    GOOGLE_SCOPES = ["openid", "email", "profile"]
    MICROSOFT_SCOPES = ["openid", "email", "profile", "User.Read"]


# Initialize OAuth
config = Config(environ=os.environ)
oauth = OAuth(config)

# Register Google (only if credentials are configured)
if OAuthConfig.GOOGLE_CLIENT_ID and OAuthConfig.GOOGLE_CLIENT_SECRET:
    try:
        oauth.register(
            name='google',
            client_id=OAuthConfig.GOOGLE_CLIENT_ID,
            client_secret=OAuthConfig.GOOGLE_CLIENT_SECRET,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': ' '.join(OAuthConfig.GOOGLE_SCOPES)},
        )
        logger.info("Google OAuth configured successfully")
    except Exception as e:
        logger.warning(f"Failed to configure Google OAuth: {e}")
else:
    logger.info("Google OAuth not configured (missing credentials)")

# Register Microsoft (only if credentials are configured)
if OAuthConfig.MICROSOFT_CLIENT_ID and OAuthConfig.MICROSOFT_CLIENT_SECRET:
    try:
        oauth.register(
            name='microsoft',
            client_id=OAuthConfig.MICROSOFT_CLIENT_ID,
            client_secret=OAuthConfig.MICROSOFT_CLIENT_SECRET,
            server_metadata_url=f'https://login.microsoftonline.com/{OAuthConfig.MICROSOFT_TENANT_ID}/v2.0/.well-known/openid-configuration',
            client_kwargs={'scope': ' '.join(OAuthConfig.MICROSOFT_SCOPES)},
        )
        logger.info("Microsoft OAuth configured successfully")
    except Exception as e:
        logger.warning(f"Failed to configure Microsoft OAuth: {e}")
else:
    logger.info("Microsoft OAuth not configured (missing credentials)")


class OAuthService:
    """
    OAuth authentication service supporting Google and Microsoft.

    Features:
    - Generate authorization URLs with PKCE
    - Exchange authorization codes for tokens
    - Refresh access tokens
    - Retrieve user profile information
    - Link OAuth providers to existing accounts
    """

    def __init__(self):
        self.oauth = oauth

    def is_provider_configured(self, provider: str) -> bool:
        """
        Check if an OAuth provider is configured.

        Args:
            provider: 'google' or 'microsoft'

        Returns:
            True if provider is configured, False otherwise
        """
        try:
            self.oauth.create_client(provider)
            return True
        except Exception:
            return False

    @staticmethod
    def generate_state() -> str:
        """
        Generate a random state parameter for CSRF protection.

        Returns:
            32-character random string
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_pkce_pair() -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate code verifier (43-128 characters)
        code_verifier = secrets.token_urlsafe(64)

        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip('=')

        return code_verifier, code_challenge

    async def get_authorization_url(
        self,
        provider: str,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate OAuth authorization URL.

        Args:
            provider: 'google' or 'microsoft'
            redirect_uri: Optional custom redirect URI

        Returns:
            Dictionary with:
            - url: Authorization URL to redirect user to
            - state: State parameter (store in session for validation)
            - code_verifier: PKCE code verifier (store in session)

        Example:
            >>> service = OAuthService()
            >>> result = await service.get_authorization_url('google')
            >>> # Redirect user to result['url']
            >>> # Store result['state'] and result['code_verifier'] in session
        """
        if provider not in ['google', 'microsoft']:
            raise ValueError(f"Unsupported provider: {provider}")

        # Generate security parameters
        state = self.generate_state()
        code_verifier, code_challenge = self.generate_pkce_pair()

        # Set redirect URI
        if not redirect_uri:
            redirect_uri = (
                OAuthConfig.GOOGLE_REDIRECT_URI if provider == 'google'
                else OAuthConfig.MICROSOFT_REDIRECT_URI
            )

        # Build authorization URL
        client = self.oauth.create_client(provider)
        authorization_url = await client.create_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method='S256',
        )

        return {
            'url': authorization_url['url'],
            'state': state,
            'code_verifier': code_verifier,
        }

    async def exchange_code_for_token(
        self,
        provider: str,
        code: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            provider: 'google' or 'microsoft'
            code: Authorization code from OAuth callback
            code_verifier: PKCE code verifier from session
            redirect_uri: Same redirect URI used in authorization request

        Returns:
            Dictionary with tokens and metadata:
            - access_token: OAuth access token
            - refresh_token: OAuth refresh token (if available)
            - id_token: OpenID Connect ID token
            - expires_at: Token expiration timestamp
            - token_type: Usually "Bearer"

        Raises:
            Exception: If token exchange fails
        """
        if provider not in ['google', 'microsoft']:
            raise ValueError(f"Unsupported provider: {provider}")

        # Set redirect URI
        if not redirect_uri:
            redirect_uri = (
                OAuthConfig.GOOGLE_REDIRECT_URI if provider == 'google'
                else OAuthConfig.MICROSOFT_REDIRECT_URI
            )

        # Exchange code for token
        client = self.oauth.create_client(provider)
        token = await client.fetch_token(
            redirect_uri=redirect_uri,
            code=code,
            code_verifier=code_verifier,
        )

        return token

    async def get_user_info(self, provider: str, access_token: str) -> Dict[str, Any]:
        """
        Retrieve user profile information from OAuth provider.

        Args:
            provider: 'google' or 'microsoft'
            access_token: Valid OAuth access token

        Returns:
            Dictionary with user information:
            - email: User's email address
            - name: User's full name
            - picture: URL to profile picture
            - sub: Provider's unique user ID

        Example:
            >>> user_info = await service.get_user_info('google', 'ya29.a0...')
            >>> print(user_info['email'])  # "user@example.com"
        """
        if provider not in ['google', 'microsoft']:
            raise ValueError(f"Unsupported provider: {provider}")

        client = self.oauth.create_client(provider)

        if provider == 'google':
            # Google userinfo endpoint
            resp = await client.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                token={'access_token': access_token, 'token_type': 'Bearer'}
            )
            user_info = resp.json()

        else:  # microsoft
            # Microsoft Graph API
            resp = await client.get(
                'https://graph.microsoft.com/v1.0/me',
                token={'access_token': access_token, 'token_type': 'Bearer'}
            )
            user_info = resp.json()

            # Normalize Microsoft response to match Google format
            user_info = {
                'sub': user_info.get('id'),
                'email': user_info.get('mail') or user_info.get('userPrincipalName'),
                'name': user_info.get('displayName'),
                'picture': None,  # Microsoft doesn't provide picture URL in basic profile
            }

        return user_info

    async def refresh_access_token(
        self,
        provider: str,
        refresh_token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh an expired access token using refresh token.

        Args:
            provider: 'google' or 'microsoft'
            refresh_token: OAuth refresh token

        Returns:
            New token dictionary, or None if refresh failed

        Example:
            >>> new_tokens = await service.refresh_access_token('google', '1//0g...')
            >>> if new_tokens:
            ...     access_token = new_tokens['access_token']
        """
        if provider not in ['google', 'microsoft']:
            return None

        try:
            client = self.oauth.create_client(provider)
            token = await client.fetch_token(
                grant_type='refresh_token',
                refresh_token=refresh_token,
            )
            return token
        except Exception as e:
            logger.error(f"Token refresh failed for {provider}: {e}")
            return None

    def store_tokens_on_user(self, user: User, tokens: Dict[str, Any]) -> None:
        """
        Encrypt and store OAuth tokens on user model.

        Args:
            user: User model instance
            tokens: Token dictionary from OAuth provider

        Example:
            >>> service.store_tokens_on_user(user, tokens)
            >>> # user.provider_metadata now contains encrypted tokens
        """
        # Add expiration timestamp if not present
        if 'expires_in' in tokens and 'expires_at' not in tokens:
            tokens['expires_at'] = int(
                (datetime.utcnow() + timedelta(seconds=tokens['expires_in'])).timestamp()
            )

        # Encrypt and store
        encrypted = encrypt_oauth_tokens(tokens)
        user.provider_metadata = encrypted

    def get_tokens_from_user(self, user: User) -> Optional[Dict[str, Any]]:
        """
        Decrypt and retrieve OAuth tokens from user model.

        Args:
            user: User model instance

        Returns:
            Decrypted token dictionary, or None if not available

        Example:
            >>> tokens = service.get_tokens_from_user(user)
            >>> if tokens:
            ...     access_token = tokens['access_token']
        """
        if not user.provider_metadata:
            return None

        return decrypt_oauth_tokens(user.provider_metadata)

    async def find_or_create_user(
        self,
        db: Session,
        provider: str,
        user_info: Dict[str, Any],
        tokens: Dict[str, Any]
    ) -> Tuple[User, bool]:
        """
        Find existing user by email or create new user from OAuth data.

        Args:
            db: Database session
            provider: 'google' or 'microsoft'
            user_info: User profile from OAuth provider
            tokens: OAuth tokens

        Returns:
            Tuple of (user, is_new_user)

        Logic:
        - If user with email exists: Link OAuth provider to existing account
        - If user doesn't exist: Create new user with OAuth data
        """
        email = user_info.get('email')
        if not email:
            raise ValueError("Email not provided by OAuth provider")

        email = email.lower()  # Normalize email

        # Check if user exists
        user = db.query(User).filter(User.email == email).first()

        if user:
            # Link OAuth provider to existing account
            user.auth_provider = provider
            user.provider_user_id = user_info.get('sub')
            user.provider_linked_at = datetime.utcnow()
            self.store_tokens_on_user(user, tokens)
            user.last_login = datetime.utcnow()

            # Update name if not set
            if not user.name and user_info.get('name'):
                user.name = user_info.get('name')

            db.commit()
            db.refresh(user)

            return user, False

        else:
            # Create new user
            user = User(
                email=email,
                name=user_info.get('name'),
                auth_provider=provider,
                provider_user_id=user_info.get('sub'),
                provider_linked_at=datetime.utcnow(),
                email_verified=True,  # OAuth providers verify email
                is_active=True,
                last_login=datetime.utcnow(),
                onboarding_completed=False,  # Will need to create/join org
            )

            self.store_tokens_on_user(user, tokens)

            db.add(user)
            db.commit()
            db.refresh(user)

            return user, True


# Singleton instance
_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    """
    Get the singleton OAuth service instance.

    Returns:
        OAuthService instance
    """
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service
