"""
Settings model with hierarchical precedence: User > Organization > System Defaults

This design supports:
- System-wide defaults (org_id=None, user_id=None)
- Organization-level settings (org_id=X, user_id=None)
- User-level settings (org_id=X, user_id=Y)

Resolution order when retrieving settings:
1. Check user-level settings
2. Fall back to org-level settings
3. Fall back to system defaults
4. Fall back to hardcoded defaults in code
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from typing import Optional


class Organization(Base):
    """
    Organization/tenant model for multi-tenancy support.

    Users belong to organizations for data isolation.
    Each organization has its own documents, templates, and settings.
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True)  # URL-friendly identifier

    # Organization ownership
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for initial creation

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    settings = relationship("Settings", back_populates="organization", cascade="all, delete-orphan")
    users = relationship("User", back_populates="organization", foreign_keys="User.org_id", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_id], post_update=True)
    roles = relationship("Role", back_populates="organization", cascade="all, delete-orphan")
    invites = relationship("OrganizationInvite", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    """
    User model with support for password and OAuth authentication.

    Authentication Methods:
    - password: Traditional email/password
    - google: Google OAuth 2.0
    - microsoft: Microsoft/Azure AD OAuth 2.0

    Users can link multiple auth providers to the same account (via email).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # Nullable during onboarding
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=True)

    # Auth - Password
    hashed_password = Column(String, nullable=True)  # Null if OAuth-only user

    # Auth - OAuth
    auth_provider = Column(String, default="password")  # "password", "google", "microsoft"
    provider_user_id = Column(String, nullable=True, index=True)  # OAuth sub/id
    provider_metadata = Column(Text, nullable=True)  # Encrypted JSON: {tokens, profile, etc.}
    provider_linked_at = Column(DateTime, nullable=True)  # When OAuth was linked

    # Organization role within their org
    organization_role = Column(String, nullable=True)  # "owner", "admin", "member"

    # Status flags
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Global superadmin
    email_verified = Column(Boolean, default=False)

    # Onboarding state
    onboarding_completed = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="users", foreign_keys=[org_id])
    settings = relationship("Settings", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", foreign_keys="UserRole.user_id", back_populates="user", cascade="all, delete-orphan")
    document_permissions = relationship("DocumentPermission", foreign_keys="DocumentPermission.user_id", back_populates="user")
    folder_permissions = relationship("FolderPermission", foreign_keys="FolderPermission.user_id", back_populates="user")
    share_links = relationship("ShareLink", foreign_keys="ShareLink.created_by_user_id", back_populates="created_by")
    api_keys = relationship("APIKey", foreign_keys="APIKey.user_id", back_populates="user", cascade="all, delete-orphan")


class Settings(Base):
    """
    Settings model with hierarchical precedence.

    Examples:
    - System default: org_id=None, user_id=None, key="audit_confidence_threshold", value="0.6"
    - Org override: org_id=1, user_id=None, key="audit_confidence_threshold", value="0.7"
    - User override: org_id=1, user_id=42, key="audit_confidence_threshold", value="0.5"

    When user 42 in org 1 requests settings, we return value="0.5"
    """
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)

    # Hierarchy (nullable for system defaults)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Setting key-value
    key = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=False)  # JSON-serialized value
    value_type = Column(String, nullable=False)  # "float", "int", "bool", "string", "json"

    # Metadata
    description = Column(Text, nullable=True)  # Human-readable description
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="settings")
    user = relationship("User", back_populates="settings")

    # Constraints: unique (org_id, user_id, key)
    __table_args__ = (
        UniqueConstraint('org_id', 'user_id', 'key', name='uix_settings_scope_key'),
    )


class OrganizationInvite(Base):
    """
    Invitation system for users to join organizations.

    Features:
    - Unique invite codes for sharing
    - Optional expiration
    - Role assignment (admin, member)
    - Single-use or multi-use invites
    - Track usage and creation
    """
    __tablename__ = "organization_invites"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    # Invite details
    email = Column(String, nullable=True)  # Optional: restrict to specific email
    invite_code = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, default="member")  # "owner", "admin", "member"

    # Usage tracking
    max_uses = Column(Integer, default=1)  # 1 = single-use, None = unlimited
    current_uses = Column(Integer, default=0)

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Acceptance tracking
    accepted_by_user_ids = Column(String, nullable=True)  # JSON list of user IDs who used this
    last_used_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)

    # Relationships
    organization = relationship("Organization", back_populates="invites")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    @property
    def is_expired(self) -> bool:
        """Check if invite has expired"""
        if not self.is_active:
            return True
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_uses and self.current_uses >= self.max_uses:
            return True
        return False

    @property
    def remaining_uses(self) -> Optional[int]:
        """Get remaining uses (None if unlimited)"""
        if not self.max_uses:
            return None
        return max(0, self.max_uses - self.current_uses)


# Default settings configuration
DEFAULT_SETTINGS = {
    # Review Threshold (replaces audit_confidence_threshold)
    "review_threshold": {
        "value": 0.6,
        "type": "float",
        "description": "Fields with confidence below this threshold need human review. These will appear in the audit queue.",
        "min": 0.0,
        "max": 1.0,
        "category": "quality_control",
        "ui_label": "Review Threshold"
    },

    # Auto-Match Threshold (replaces template_matching_threshold)
    "auto_match_threshold": {
        "value": 0.70,
        "type": "float",
        "description": "Minimum confidence to automatically match templates. Below this threshold, Claude AI will be used as fallback for better accuracy.",
        "min": 0.0,
        "max": 1.0,
        "category": "template_matching",
        "ui_label": "Auto-Match Threshold"
    },

    # Claude Fallback
    "enable_claude_fallback": {
        "value": True,
        "type": "bool",
        "description": "Use Claude AI when Elasticsearch confidence is below auto-match threshold. Disabling this reduces costs but may reduce accuracy.",
        "category": "template_matching",
        "ui_label": "Enable AI Fallback"
    },

    # Processing
    "batch_size": {
        "value": 10,
        "type": "int",
        "description": "Number of documents to process in parallel during batch uploads.",
        "min": 1,
        "max": 50,
        "category": "processing",
        "ui_label": "Batch Size"
    },
}
