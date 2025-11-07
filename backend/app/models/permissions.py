"""
Permission and Role-Based Access Control (RBAC) Models

This module implements a comprehensive RBAC system for Paperbase:

Architecture:
- Roles: Named collections of permissions (Admin, Editor, Viewer, Custom)
- Permissions: Granular access rights (read:documents, write:templates, etc.)
- UserRoles: Assigns roles to users with optional scope (global/org/folder)
- DocumentPermissions: Document-level sharing and access control
- FolderPermissions: Folder-level access control

Permission Resolution Order:
1. Direct user permissions (DocumentPermission, FolderPermission)
2. Role-based permissions (via UserRole)
3. Organization-level permissions
4. Default permissions

Scope Levels:
- global: Applies to all resources
- organization: Applies to resources within an organization
- folder: Applies to resources within a specific folder
- document: Applies to a specific document
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Enum as SQLEnum, Table
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional
import enum
from app.core.database import Base


# Permission Enums
class PermissionScope(str, enum.Enum):
    """Scope of permission application"""
    GLOBAL = "global"
    ORGANIZATION = "organization"
    FOLDER = "folder"
    DOCUMENT = "document"


class PermissionAction(str, enum.Enum):
    """Available permission actions"""
    # Document permissions
    READ_DOCUMENTS = "read:documents"
    WRITE_DOCUMENTS = "write:documents"
    DELETE_DOCUMENTS = "delete:documents"
    SHARE_DOCUMENTS = "share:documents"

    # Template permissions
    READ_TEMPLATES = "read:templates"
    WRITE_TEMPLATES = "write:templates"
    DELETE_TEMPLATES = "delete:templates"

    # User management
    READ_USERS = "read:users"
    WRITE_USERS = "write:users"
    DELETE_USERS = "delete:users"
    MANAGE_ROLES = "manage:roles"

    # Organization management
    MANAGE_ORGANIZATION = "manage:organization"
    MANAGE_SETTINGS = "manage:settings"

    # Search and query
    SEARCH_ALL = "search:all"
    EXPORT_DATA = "export:data"

    # Audit and monitoring
    VIEW_AUDIT_LOG = "view:audit"

    # Special permissions
    ADMIN = "admin"  # Superuser - all permissions


class RoleType(str, enum.Enum):
    """Built-in role types"""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    CUSTOM = "custom"


class ShareLinkAccessLevel(str, enum.Enum):
    """Access levels for share links"""
    READ = "read"
    COMMENT = "comment"
    EDIT = "edit"


# Association table for Role-Permission many-to-many
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Role(Base):
    """
    Role definition with associated permissions.

    Built-in roles:
    - Admin: Full system access (all permissions)
    - Editor: Can create/edit documents and templates
    - Viewer: Read-only access

    Custom roles can be created with specific permission combinations.
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # Org-specific roles

    name = Column(String, nullable=False, index=True)  # e.g., "Admin", "Contract Reviewer"
    slug = Column(String, nullable=False, index=True)  # URL-friendly: "admin", "contract-reviewer"
    role_type = Column(SQLEnum(RoleType), default=RoleType.CUSTOM)
    description = Column(Text, nullable=True)

    # System roles cannot be deleted or modified
    is_system_role = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        UniqueConstraint('org_id', 'slug', name='uix_org_role_slug'),
    )


class Permission(Base):
    """
    Individual permission definition.

    Permissions are granular actions like:
    - read:documents
    - write:templates
    - manage:users

    Permissions are assigned to roles, which are then assigned to users.
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)

    action = Column(SQLEnum(PermissionAction), nullable=False, unique=True)
    name = Column(String, nullable=False)  # Human-readable: "Read Documents"
    description = Column(Text, nullable=True)

    # Permission metadata
    resource_type = Column(String, nullable=True)  # "document", "template", "user", etc.
    is_active = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class UserRole(Base):
    """
    Assigns roles to users with optional scope.

    Scope examples:
    - Global: User is Admin across entire system
    - Organization: User is Editor in Organization 1
    - Folder: User is Viewer for "/contracts/2024" folder

    Multiple UserRoles can be assigned to same user with different scopes.
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    # Scope configuration
    scope = Column(SQLEnum(PermissionScope), default=PermissionScope.GLOBAL)
    scope_org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)  # For org scope
    scope_folder_path = Column(String, nullable=True)  # For folder scope

    # Assignment metadata
    assigned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration

    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    scope_organization = relationship("Organization", foreign_keys=[scope_org_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', 'scope', 'scope_org_id', 'scope_folder_path',
                        name='uix_user_role_scope'),
    )


class DocumentPermission(Base):
    """
    Document-level access control and sharing.

    Allows granular control over who can access specific documents.
    Used for:
    - Sharing documents with specific users
    - Restricting access to sensitive documents
    - Collaboration on specific files
    """
    __tablename__ = "document_permissions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # Null = public
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)  # Share with role

    # Permission level
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_share = Column(Boolean, default=False)

    # Sharing metadata
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Notes/reason for sharing
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)

    # Relationships
    document = relationship("Document", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role", foreign_keys=[role_id])
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])


class FolderPermission(Base):
    """
    Folder-level access control.

    Permissions cascade to all documents within the folder.
    Useful for:
    - Departmental access (Finance folder → Finance team)
    - Project-based access
    - Hierarchical security
    """
    __tablename__ = "folder_permissions"

    id = Column(Integer, primary_key=True, index=True)
    folder_path = Column(String, nullable=False, index=True)  # e.g., "/contracts/2024"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)

    # Permission level
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_share = Column(Boolean, default=False)

    # Inheritance
    inherit_to_subfolders = Column(Boolean, default=True)  # Apply to child folders

    # Metadata
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role", foreign_keys=[role_id])
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])

    __table_args__ = (
        UniqueConstraint('folder_path', 'user_id', 'role_id', name='uix_folder_user_role'),
    )


class ShareLink(Base):
    """
    Shareable links for documents with optional expiration and access control.

    Enables:
    - Public sharing via unique token
    - Time-limited access
    - Trackable sharing
    - Revokable access
    """
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    # Unique share token (used in URL)
    token = Column(String, nullable=False, unique=True, index=True)

    # Access configuration
    access_level = Column(SQLEnum(ShareLinkAccessLevel), default=ShareLinkAccessLevel.READ)
    password_hash = Column(String, nullable=True)  # Optional password protection
    max_accesses = Column(Integer, nullable=True)  # Limit number of accesses
    current_accesses = Column(Integer, default=0)

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Metadata
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True)

    # Relationships
    document = relationship("Document", back_populates="share_links")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    access_logs = relationship("ShareLinkAccessLog", back_populates="share_link", cascade="all, delete-orphan")

    @property
    def is_expired(self) -> bool:
        """Check if share link has expired"""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        if self.max_accesses and self.current_accesses >= self.max_accesses:
            return True
        return False


class ShareLinkAccessLog(Base):
    """
    Tracks access to share links for security and analytics.
    """
    __tablename__ = "share_link_access_logs"

    id = Column(Integer, primary_key=True, index=True)
    share_link_id = Column(Integer, ForeignKey("share_links.id", ondelete="CASCADE"), nullable=False)

    # Access details
    accessed_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    access_granted = Column(Boolean, default=True)  # False if denied (expired, wrong password)
    denial_reason = Column(String, nullable=True)

    # Relationships
    share_link = relationship("ShareLink", back_populates="access_logs")


class PermissionAuditLog(Base):
    """
    Comprehensive audit trail for all permission changes.

    Tracks:
    - Role assignments/removals
    - Permission grants/revokes
    - Document sharing
    - Access attempts
    """
    __tablename__ = "permission_audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Who did what
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Actor
    action = Column(String, nullable=False)  # "grant_role", "revoke_access", "share_document"

    # What was affected
    resource_type = Column(String, nullable=False)  # "document", "folder", "role", "user"
    resource_id = Column(Integer, nullable=True)

    # Details
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Affected user
    details = Column(Text, nullable=True)  # JSON with full context

    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Success/failure
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class APIKey(Base):
    """
    API Keys for programmatic access (MCP, scripts, integrations)

    API keys provide long-lived authentication for non-interactive access.
    Unlike JWT tokens which expire after 24 hours, API keys remain valid
    until explicitly revoked.

    Security:
    - Keys are hashed using bcrypt before storage
    - Plain key shown only once at creation
    - Keys have 'pb_' prefix for identification
    - Can be scoped to specific permissions
    - Track last usage for security auditing
    """
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)  # Friendly name: "MCP Server", "Python Script"
    key_hash = Column(String, nullable=False, unique=True)  # bcrypt hash of the key

    # Permissions & expiration
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    is_active = Column(Boolean, default=True)

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="api_keys")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    revoked_by = relationship("User", foreign_keys=[revoked_by_user_id])

    def __repr__(self):
        return f"<APIKey(id={self.id}, user_id={self.user_id}, name='{self.name}', active={self.is_active})>"


# Default permission sets
DEFAULT_PERMISSIONS = [
    # Document permissions
    {"action": PermissionAction.READ_DOCUMENTS, "name": "Read Documents", "resource_type": "document"},
    {"action": PermissionAction.WRITE_DOCUMENTS, "name": "Write Documents", "resource_type": "document"},
    {"action": PermissionAction.DELETE_DOCUMENTS, "name": "Delete Documents", "resource_type": "document"},
    {"action": PermissionAction.SHARE_DOCUMENTS, "name": "Share Documents", "resource_type": "document"},

    # Template permissions
    {"action": PermissionAction.READ_TEMPLATES, "name": "Read Templates", "resource_type": "template"},
    {"action": PermissionAction.WRITE_TEMPLATES, "name": "Write Templates", "resource_type": "template"},
    {"action": PermissionAction.DELETE_TEMPLATES, "name": "Delete Templates", "resource_type": "template"},

    # User management
    {"action": PermissionAction.READ_USERS, "name": "Read Users", "resource_type": "user"},
    {"action": PermissionAction.WRITE_USERS, "name": "Write Users", "resource_type": "user"},
    {"action": PermissionAction.DELETE_USERS, "name": "Delete Users", "resource_type": "user"},
    {"action": PermissionAction.MANAGE_ROLES, "name": "Manage Roles", "resource_type": "role"},

    # Organization
    {"action": PermissionAction.MANAGE_ORGANIZATION, "name": "Manage Organization", "resource_type": "organization"},
    {"action": PermissionAction.MANAGE_SETTINGS, "name": "Manage Settings", "resource_type": "settings"},

    # Search & export
    {"action": PermissionAction.SEARCH_ALL, "name": "Search All Documents", "resource_type": "search"},
    {"action": PermissionAction.EXPORT_DATA, "name": "Export Data", "resource_type": "export"},

    # Audit
    {"action": PermissionAction.VIEW_AUDIT_LOG, "name": "View Audit Log", "resource_type": "audit"},

    # Admin
    {"action": PermissionAction.ADMIN, "name": "System Administrator", "resource_type": "system"},
]

# Default role configurations
DEFAULT_ROLES = {
    "admin": {
        "name": "Administrator",
        "role_type": RoleType.ADMIN,
        "description": "Full system access with all permissions",
        "permissions": [PermissionAction.ADMIN]  # Admin gets all permissions
    },
    "editor": {
        "name": "Editor",
        "role_type": RoleType.EDITOR,
        "description": "Can create, edit, and share documents and templates",
        "permissions": [
            PermissionAction.READ_DOCUMENTS,
            PermissionAction.WRITE_DOCUMENTS,
            PermissionAction.SHARE_DOCUMENTS,
            PermissionAction.READ_TEMPLATES,
            PermissionAction.WRITE_TEMPLATES,
            PermissionAction.SEARCH_ALL,
            PermissionAction.EXPORT_DATA,
        ]
    },
    "viewer": {
        "name": "Viewer",
        "role_type": RoleType.VIEWER,
        "description": "Read-only access to documents and templates",
        "permissions": [
            PermissionAction.READ_DOCUMENTS,
            PermissionAction.READ_TEMPLATES,
            PermissionAction.SEARCH_ALL,
        ]
    }
}
