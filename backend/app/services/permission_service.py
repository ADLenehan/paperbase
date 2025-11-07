"""
Permission Service - Core RBAC Logic

Handles all permission validation and authorization checks for Paperbase.

Key Responsibilities:
- Check if a user has a specific permission
- Validate document/folder access
- Grant/revoke permissions
- Resolve permission inheritance
- Audit permission changes

Permission Resolution Order:
1. Admin users have all permissions (bypass checks)
2. Direct resource permissions (DocumentPermission, FolderPermission)
3. Role-based permissions (via UserRole)
4. Organization-level permissions
5. Public access (if resource is public)
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
import secrets

from app.models.permissions import (
    Role, Permission, UserRole, DocumentPermission, FolderPermission,
    ShareLink, PermissionAuditLog, PermissionAction, PermissionScope,
    RoleType, ShareLinkAccessLevel, DEFAULT_PERMISSIONS, DEFAULT_ROLES
)
from app.models.settings import User, Organization
from app.models.document import Document
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing permissions and access control"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Permission Checking ====================

    def check_permission(
        self,
        user_id: int,
        action: PermissionAction,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None
    ) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User to check
            action: Permission action (e.g., PermissionAction.READ_DOCUMENTS)
            resource_type: Optional resource type ("document", "template", etc.)
            resource_id: Optional specific resource ID

        Returns:
            True if user has permission, False otherwise
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return False

        # Admin bypass - admins have all permissions
        if user.is_admin:
            logger.debug(f"User {user_id} is admin - permission granted")
            return True

        # Check if user has ADMIN permission via role
        if self._has_permission_via_role(user_id, PermissionAction.ADMIN):
            logger.debug(f"User {user_id} has ADMIN permission - granted")
            return True

        # Check specific permission via roles
        has_permission = self._has_permission_via_role(user_id, action)

        logger.debug(f"Permission check: user={user_id}, action={action}, result={has_permission}")
        return has_permission

    def _has_permission_via_role(self, user_id: int, action: PermissionAction) -> bool:
        """Check if user has permission through their assigned roles"""
        # Get active user roles
        user_roles = self.db.query(UserRole).filter(
            and_(
                UserRole.user_id == user_id,
                UserRole.is_active == True,
                or_(
                    UserRole.expires_at == None,
                    UserRole.expires_at > datetime.utcnow()
                )
            )
        ).options(
            joinedload(UserRole.role).joinedload(Role.permissions)
        ).all()

        # Check each role's permissions
        for user_role in user_roles:
            role = user_role.role
            if not role or not role.is_active:
                continue

            # Check if role has the specific permission
            for permission in role.permissions:
                if permission.action == action or permission.action == PermissionAction.ADMIN:
                    return True

        return False

    def check_document_access(
        self,
        user_id: int,
        document_id: int,
        required_permission: str = "read"
    ) -> bool:
        """
        Check if user has access to a specific document.

        Checks in order:
        1. Document owner (full access)
        2. Public documents (read access for org members)
        3. Direct document permissions
        4. Folder permissions (inherited)
        5. Role-based permissions

        Args:
            user_id: User to check
            document_id: Document to access
            required_permission: "read", "write", "delete", or "share"

        Returns:
            True if user has access
        """
        # Get document
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False

        # Owner has full access
        if document.created_by_user_id == user_id:
            logger.debug(f"User {user_id} is owner of document {document_id}")
            return True

        # Admin has full access
        if self.check_permission(user_id, PermissionAction.ADMIN):
            return True

        # Check if public and user just needs read access
        if document.is_public and required_permission == "read":
            # Verify user is in same org
            user = self.db.query(User).filter(User.id == user_id).first()
            doc_owner = self.db.query(User).filter(
                User.id == document.created_by_user_id
            ).first()
            if user and doc_owner and user.org_id == doc_owner.org_id:
                logger.debug(f"Document {document_id} is public - read access granted")
                return True

        # Check direct document permissions
        doc_permission = self.db.query(DocumentPermission).filter(
            and_(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == user_id,
                DocumentPermission.is_active == True,
                or_(
                    DocumentPermission.expires_at == None,
                    DocumentPermission.expires_at > datetime.utcnow()
                )
            )
        ).first()

        if doc_permission:
            if required_permission == "read" and doc_permission.can_read:
                return True
            if required_permission == "write" and doc_permission.can_write:
                return True
            if required_permission == "delete" and doc_permission.can_delete:
                return True
            if required_permission == "share" and doc_permission.can_share:
                return True

        # Check folder permissions (if document has folder_path in extraction)
        # This would require looking up the document's folder from Extraction model
        # TODO: Implement folder permission checking

        # Check role-based permissions
        action_map = {
            "read": PermissionAction.READ_DOCUMENTS,
            "write": PermissionAction.WRITE_DOCUMENTS,
            "delete": PermissionAction.DELETE_DOCUMENTS,
            "share": PermissionAction.SHARE_DOCUMENTS
        }

        if required_permission in action_map:
            return self.check_permission(user_id, action_map[required_permission])

        return False

    def check_folder_access(
        self,
        user_id: int,
        folder_path: str,
        required_permission: str = "read"
    ) -> bool:
        """
        Check if user has access to a folder.

        Args:
            user_id: User to check
            folder_path: Folder path (e.g., "/contracts/2024")
            required_permission: "read", "write", "delete", or "share"

        Returns:
            True if user has access
        """
        # Admin has full access
        if self.check_permission(user_id, PermissionAction.ADMIN):
            return True

        # Check direct folder permissions
        folder_permission = self.db.query(FolderPermission).filter(
            and_(
                FolderPermission.folder_path == folder_path,
                FolderPermission.user_id == user_id,
                FolderPermission.is_active == True,
                or_(
                    FolderPermission.expires_at == None,
                    FolderPermission.expires_at > datetime.utcnow()
                )
            )
        ).first()

        if folder_permission:
            if required_permission == "read" and folder_permission.can_read:
                return True
            if required_permission == "write" and folder_permission.can_write:
                return True
            if required_permission == "delete" and folder_permission.can_delete:
                return True
            if required_permission == "share" and folder_permission.can_share:
                return True

        # Check parent folder permissions with inheritance
        if "/" in folder_path.rstrip("/"):
            parent_path = "/".join(folder_path.rstrip("/").split("/")[:-1]) or "/"
            parent_permissions = self.db.query(FolderPermission).filter(
                and_(
                    FolderPermission.folder_path == parent_path,
                    FolderPermission.user_id == user_id,
                    FolderPermission.inherit_to_subfolders == True,
                    FolderPermission.is_active == True
                )
            ).first()

            if parent_permissions:
                if required_permission == "read" and parent_permissions.can_read:
                    return True
                if required_permission == "write" and parent_permissions.can_write:
                    return True
                if required_permission == "delete" and parent_permissions.can_delete:
                    return True
                if required_permission == "share" and parent_permissions.can_share:
                    return True

        # Check role-based permissions
        action_map = {
            "read": PermissionAction.READ_DOCUMENTS,
            "write": PermissionAction.WRITE_DOCUMENTS,
            "delete": PermissionAction.DELETE_DOCUMENTS,
            "share": PermissionAction.SHARE_DOCUMENTS
        }

        if required_permission in action_map:
            return self.check_permission(user_id, action_map[required_permission])

        return False

    def require_permission(
        self,
        user_id: int,
        action: PermissionAction,
        error_message: Optional[str] = None
    ):
        """
        Require a permission or raise PermissionDeniedError.

        Use in API endpoints to enforce permissions.
        """
        if not self.check_permission(user_id, action):
            msg = error_message or f"Permission denied: {action.value}"
            logger.warning(f"Permission denied: user={user_id}, action={action}")
            raise PermissionDeniedError(msg)

    def require_document_access(
        self,
        user_id: int,
        document_id: int,
        required_permission: str = "read"
    ):
        """Require document access or raise PermissionDeniedError"""
        if not self.check_document_access(user_id, document_id, required_permission):
            logger.warning(
                f"Document access denied: user={user_id}, doc={document_id}, "
                f"permission={required_permission}"
            )
            raise PermissionDeniedError(
                f"You don't have {required_permission} access to this document"
            )

    # ==================== User Permissions Query ====================

    def get_user_permissions(
        self,
        user_id: int,
        scope: Optional[PermissionScope] = None
    ) -> List[PermissionAction]:
        """
        Get all permissions for a user.

        Args:
            user_id: User to query
            scope: Optional scope filter

        Returns:
            List of permission actions user has
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return []

        # Admin has all permissions
        if user.is_admin:
            return list(PermissionAction)

        permissions = set()

        # Get permissions from roles
        user_roles = self.db.query(UserRole).filter(
            and_(
                UserRole.user_id == user_id,
                UserRole.is_active == True,
                or_(
                    UserRole.expires_at == None,
                    UserRole.expires_at > datetime.utcnow()
                )
            )
        ).options(
            joinedload(UserRole.role).joinedload(Role.permissions)
        ).all()

        for user_role in user_roles:
            if scope and user_role.scope != scope:
                continue

            role = user_role.role
            if not role or not role.is_active:
                continue

            for permission in role.permissions:
                permissions.add(permission.action)

        return list(permissions)

    def get_user_roles(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all roles assigned to a user.

        Returns:
            List of role dictionaries with scope information
        """
        user_roles = self.db.query(UserRole).filter(
            and_(
                UserRole.user_id == user_id,
                UserRole.is_active == True
            )
        ).options(
            joinedload(UserRole.role),
            joinedload(UserRole.assigned_by)
        ).all()

        return [
            {
                "id": ur.id,
                "role": {
                    "id": ur.role.id,
                    "name": ur.role.name,
                    "slug": ur.role.slug,
                    "type": ur.role.role_type.value
                },
                "scope": ur.scope.value,
                "scope_org_id": ur.scope_org_id,
                "scope_folder_path": ur.scope_folder_path,
                "assigned_at": ur.assigned_at.isoformat() if ur.assigned_at else None,
                "assigned_by": {
                    "id": ur.assigned_by.id,
                    "email": ur.assigned_by.email,
                    "name": ur.assigned_by.name
                } if ur.assigned_by else None,
                "expires_at": ur.expires_at.isoformat() if ur.expires_at else None
            }
            for ur in user_roles
        ]

    # ==================== Permission Granting ====================

    def grant_document_access(
        self,
        document_id: int,
        target_user_id: int,
        granted_by_user_id: int,
        can_read: bool = True,
        can_write: bool = False,
        can_delete: bool = False,
        can_share: bool = False,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> DocumentPermission:
        """
        Grant a user access to a document.

        Args:
            document_id: Document to share
            target_user_id: User to grant access to
            granted_by_user_id: User granting the access
            can_read, can_write, can_delete, can_share: Permission levels
            expires_at: Optional expiration
            notes: Optional notes about why access was granted

        Returns:
            Created DocumentPermission

        Raises:
            PermissionDeniedError: If granter doesn't have share permission
            ResourceNotFoundError: If document or user doesn't exist
        """
        # Verify granter has permission to share
        if not self.check_document_access(granted_by_user_id, document_id, "share"):
            raise PermissionDeniedError("You don't have permission to share this document")

        # Verify document exists
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError(f"Document {document_id} not found")

        # Verify target user exists
        target_user = self.db.query(User).filter(User.id == target_user_id).first()
        if not target_user:
            raise ResourceNotFoundError(f"User {target_user_id} not found")

        # Check if permission already exists
        existing = self.db.query(DocumentPermission).filter(
            and_(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == target_user_id,
                DocumentPermission.is_active == True
            )
        ).first()

        if existing:
            # Update existing permission
            existing.can_read = can_read
            existing.can_write = can_write
            existing.can_delete = can_delete
            existing.can_share = can_share
            existing.expires_at = expires_at
            existing.notes = notes
            existing.shared_by_user_id = granted_by_user_id
            existing.shared_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)

            self._audit_log(
                user_id=granted_by_user_id,
                action="update_document_permission",
                resource_type="document",
                resource_id=document_id,
                target_user_id=target_user_id,
                details={
                    "can_read": can_read,
                    "can_write": can_write,
                    "can_delete": can_delete,
                    "can_share": can_share
                }
            )

            return existing

        # Create new permission
        permission = DocumentPermission(
            document_id=document_id,
            user_id=target_user_id,
            can_read=can_read,
            can_write=can_write,
            can_delete=can_delete,
            can_share=can_share,
            shared_by_user_id=granted_by_user_id,
            expires_at=expires_at,
            notes=notes
        )

        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)

        self._audit_log(
            user_id=granted_by_user_id,
            action="grant_document_permission",
            resource_type="document",
            resource_id=document_id,
            target_user_id=target_user_id,
            details={
                "can_read": can_read,
                "can_write": can_write,
                "can_delete": can_delete,
                "can_share": can_share
            }
        )

        logger.info(
            f"Granted document access: doc={document_id}, user={target_user_id}, "
            f"by={granted_by_user_id}"
        )

        return permission

    def revoke_document_access(
        self,
        document_id: int,
        target_user_id: int,
        revoked_by_user_id: int
    ) -> bool:
        """
        Revoke user's access to a document.

        Returns:
            True if access was revoked, False if no permission existed
        """
        # Verify revoker has permission
        if not self.check_document_access(revoked_by_user_id, document_id, "share"):
            raise PermissionDeniedError("You don't have permission to manage this document")

        permission = self.db.query(DocumentPermission).filter(
            and_(
                DocumentPermission.document_id == document_id,
                DocumentPermission.user_id == target_user_id,
                DocumentPermission.is_active == True
            )
        ).first()

        if not permission:
            return False

        permission.is_active = False
        self.db.commit()

        self._audit_log(
            user_id=revoked_by_user_id,
            action="revoke_document_permission",
            resource_type="document",
            resource_id=document_id,
            target_user_id=target_user_id
        )

        logger.info(
            f"Revoked document access: doc={document_id}, user={target_user_id}, "
            f"by={revoked_by_user_id}"
        )

        return True

    def assign_role(
        self,
        user_id: int,
        role_id: int,
        assigned_by_user_id: int,
        scope: PermissionScope = PermissionScope.GLOBAL,
        scope_org_id: Optional[int] = None,
        scope_folder_path: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> UserRole:
        """
        Assign a role to a user.

        Args:
            user_id: User to assign role to
            role_id: Role to assign
            assigned_by_user_id: User performing the assignment
            scope: Permission scope
            scope_org_id: Organization ID for org scope
            scope_folder_path: Folder path for folder scope
            expires_at: Optional expiration

        Returns:
            Created UserRole
        """
        # Verify assigner has manage_roles permission
        self.require_permission(assigned_by_user_id, PermissionAction.MANAGE_ROLES)

        # Verify user and role exist
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ResourceNotFoundError(f"User {user_id} not found")

        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise ResourceNotFoundError(f"Role {role_id} not found")

        # Check if assignment already exists
        existing = self.db.query(UserRole).filter(
            and_(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.scope == scope,
                UserRole.is_active == True
            )
        ).first()

        if existing:
            logger.info(f"Role assignment already exists: user={user_id}, role={role_id}")
            return existing

        # Create assignment
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            scope=scope,
            scope_org_id=scope_org_id,
            scope_folder_path=scope_folder_path,
            assigned_by_user_id=assigned_by_user_id,
            expires_at=expires_at
        )

        self.db.add(user_role)
        self.db.commit()
        self.db.refresh(user_role)

        self._audit_log(
            user_id=assigned_by_user_id,
            action="assign_role",
            resource_type="user",
            resource_id=user_id,
            target_user_id=user_id,
            details={
                "role_id": role_id,
                "role_name": role.name,
                "scope": scope.value
            }
        )

        logger.info(f"Assigned role: user={user_id}, role={role_id}, by={assigned_by_user_id}")

        return user_role

    def revoke_role(
        self,
        user_id: int,
        role_id: int,
        revoked_by_user_id: int
    ) -> bool:
        """
        Revoke a role from a user.

        Returns:
            True if role was revoked, False if assignment didn't exist
        """
        # Verify revoker has manage_roles permission
        self.require_permission(revoked_by_user_id, PermissionAction.MANAGE_ROLES)

        user_role = self.db.query(UserRole).filter(
            and_(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.is_active == True
            )
        ).first()

        if not user_role:
            return False

        user_role.is_active = False
        self.db.commit()

        self._audit_log(
            user_id=revoked_by_user_id,
            action="revoke_role",
            resource_type="user",
            resource_id=user_id,
            target_user_id=user_id,
            details={"role_id": role_id}
        )

        logger.info(f"Revoked role: user={user_id}, role={role_id}, by={revoked_by_user_id}")

        return True

    # ==================== Share Links ====================

    def create_share_link(
        self,
        document_id: int,
        created_by_user_id: int,
        access_level: ShareLinkAccessLevel = ShareLinkAccessLevel.READ,
        expires_in_days: Optional[int] = 7,
        max_accesses: Optional[int] = None,
        password: Optional[str] = None
    ) -> ShareLink:
        """
        Create a shareable link for a document.

        Args:
            document_id: Document to share
            created_by_user_id: User creating the link
            access_level: READ, COMMENT, or EDIT
            expires_in_days: Days until expiration (None = never)
            max_accesses: Maximum number of accesses (None = unlimited)
            password: Optional password protection

        Returns:
            Created ShareLink with token
        """
        # Verify creator has share permission
        self.require_document_access(created_by_user_id, document_id, "share")

        # Generate unique token
        token = secrets.token_urlsafe(32)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Hash password if provided
        password_hash = None
        if password:
            from passlib.hash import bcrypt
            password_hash = bcrypt.hash(password)

        share_link = ShareLink(
            document_id=document_id,
            token=token,
            access_level=access_level,
            password_hash=password_hash,
            max_accesses=max_accesses,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id
        )

        self.db.add(share_link)
        self.db.commit()
        self.db.refresh(share_link)

        self._audit_log(
            user_id=created_by_user_id,
            action="create_share_link",
            resource_type="document",
            resource_id=document_id,
            details={
                "token": token[:8] + "...",  # Don't log full token
                "access_level": access_level.value,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )

        logger.info(f"Created share link: doc={document_id}, by={created_by_user_id}")

        return share_link

    def revoke_share_link(
        self,
        share_link_id: int,
        revoked_by_user_id: int
    ) -> bool:
        """Revoke a share link"""
        share_link = self.db.query(ShareLink).filter(ShareLink.id == share_link_id).first()
        if not share_link:
            return False

        # Verify revoker has permission
        self.require_document_access(revoked_by_user_id, share_link.document_id, "share")

        share_link.is_active = False
        self.db.commit()

        self._audit_log(
            user_id=revoked_by_user_id,
            action="revoke_share_link",
            resource_type="document",
            resource_id=share_link.document_id,
            details={"share_link_id": share_link_id}
        )

        return True

    # ==================== Audit Logging ====================

    def _audit_log(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Internal method to log permission changes"""
        import json

        audit_entry = PermissionAuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            target_user_id=target_user_id,
            details=json.dumps(details) if details else None,
            success=success,
            error_message=error_message
        )

        self.db.add(audit_entry)
        self.db.commit()

    # ==================== Initialization ====================

    @staticmethod
    def initialize_default_permissions(db: Session):
        """Initialize default permissions and roles (run on first startup)"""
        # Create default permissions
        for perm_data in DEFAULT_PERMISSIONS:
            existing = db.query(Permission).filter(
                Permission.action == perm_data["action"]
            ).first()

            if not existing:
                permission = Permission(**perm_data)
                db.add(permission)
                logger.info(f"Created permission: {perm_data['action'].value}")

        db.commit()

        # Create default roles
        for role_slug, role_data in DEFAULT_ROLES.items():
            existing = db.query(Role).filter(Role.slug == role_slug).first()

            if not existing:
                role = Role(
                    name=role_data["name"],
                    slug=role_slug,
                    role_type=role_data["role_type"],
                    description=role_data["description"],
                    is_system_role=True
                )
                db.add(role)
                db.flush()  # Get role.id

                # Add permissions to role
                for action in role_data["permissions"]:
                    permission = db.query(Permission).filter(
                        Permission.action == action
                    ).first()
                    if permission:
                        role.permissions.append(permission)

                logger.info(f"Created role: {role_data['name']}")

        db.commit()
        logger.info("Default permissions and roles initialized")
