"""
Document Sharing API

Endpoints for sharing documents with users and managing access:
- Share documents with specific users or roles
- Create shareable links with optional expiration
- List who has access to documents
- Revoke access and delete share links
- Manage folder-level permissions

Enables collaboration and secure document distribution.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_active_admin
from app.models.document import Document
from app.models.permissions import (
    DocumentPermission, FolderPermission, ShareLink,
    ShareLinkAccessLevel, PermissionAction
)
from app.models.settings import User
from app.services.permission_service import PermissionService
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sharing", tags=["sharing"])


# ==================== Pydantic Models ====================

class ShareDocumentRequest(BaseModel):
    """Request to share a document with users"""
    user_ids: Optional[List[int]] = None
    role_ids: Optional[List[int]] = None
    can_read: bool = True
    can_write: bool = False
    can_delete: bool = False
    can_share: bool = False
    expires_in_days: Optional[int] = None
    notes: Optional[str] = None


class ShareLinkRequest(BaseModel):
    """Request to create a shareable link"""
    access_level: str = "read"  # "read", "comment", "edit"
    expires_in_days: Optional[int] = 7
    max_accesses: Optional[int] = None
    password: Optional[str] = None


class FolderShareRequest(BaseModel):
    """Request to share a folder"""
    user_ids: Optional[List[int]] = None
    role_ids: Optional[List[int]] = None
    can_read: bool = True
    can_write: bool = False
    can_delete: bool = False
    can_share: bool = False
    inherit_to_subfolders: bool = True
    expires_in_days: Optional[int] = None


class DocumentPermissionResponse(BaseModel):
    """Response for document permission"""
    id: int
    user: Optional[dict] = None
    role: Optional[dict] = None
    can_read: bool
    can_write: bool
    can_delete: bool
    can_share: bool
    shared_by: dict
    shared_at: str
    expires_at: Optional[str] = None
    notes: Optional[str] = None


class ShareLinkResponse(BaseModel):
    """Response for share link"""
    id: int
    token: str
    url: str
    access_level: str
    expires_at: Optional[str] = None
    max_accesses: Optional[int] = None
    current_accesses: int
    is_password_protected: bool
    created_by: dict
    created_at: str
    is_active: bool
    is_expired: bool


class DocumentAccessResponse(BaseModel):
    """Response showing all access to a document"""
    document_id: int
    filename: str
    owner: Optional[dict] = None
    is_public: bool
    direct_permissions: List[DocumentPermissionResponse]
    share_links: List[ShareLinkResponse]
    total_users_with_access: int


# ==================== Helper Functions ====================

def build_share_url(token: str) -> str:
    """Build public share link URL"""
    # TODO: Use actual frontend URL from config
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
    return f"{base_url}/share/{token}"


# ==================== Endpoints ====================

@router.post("/documents/{document_id}/share")
async def share_document(
    document_id: int,
    request: ShareDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Share a document with specific users or roles.

    Can grant different permission levels:
    - read: View document
    - write: Edit document fields
    - delete: Delete document
    - share: Share with others

    Optional expiration can be set.

    Example:
    ```json
    {
      "user_ids": [2, 3],
      "can_read": true,
      "can_write": true,
      "expires_in_days": 30,
      "notes": "Q1 report reviewers"
    }
    ```
    """
    permission_service = PermissionService(db)

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    results = {
        "success": True,
        "document_id": document_id,
        "filename": document.filename,
        "shared_with": []
    }

    # Share with users
    if request.user_ids:
        for user_id in request.user_ids:
            try:
                permission = permission_service.grant_document_access(
                    document_id=document_id,
                    target_user_id=user_id,
                    granted_by_user_id=current_user.id,
                    can_read=request.can_read,
                    can_write=request.can_write,
                    can_delete=request.can_delete,
                    can_share=request.can_share,
                    expires_at=expires_at,
                    notes=request.notes
                )

                user = db.query(User).filter(User.id == user_id).first()
                results["shared_with"].append({
                    "type": "user",
                    "user_id": user_id,
                    "email": user.email if user else None,
                    "permission_id": permission.id
                })
            except (PermissionDeniedError, ResourceNotFoundError) as e:
                results["shared_with"].append({
                    "type": "user",
                    "user_id": user_id,
                    "error": str(e)
                })

    # Share with roles
    if request.role_ids:
        for role_id in request.role_ids:
            # Create permission entry for role
            permission = DocumentPermission(
                document_id=document_id,
                role_id=role_id,
                can_read=request.can_read,
                can_write=request.can_write,
                can_delete=request.can_delete,
                can_share=request.can_share,
                shared_by_user_id=current_user.id,
                expires_at=expires_at,
                notes=request.notes
            )
            db.add(permission)
            db.commit()
            db.refresh(permission)

            from app.models.permissions import Role
            role = db.query(Role).filter(Role.id == role_id).first()
            results["shared_with"].append({
                "type": "role",
                "role_id": role_id,
                "role_name": role.name if role else None,
                "permission_id": permission.id
            })

    logger.info(
        f"Document {document_id} shared with {len(request.user_ids or [])} users "
        f"and {len(request.role_ids or [])} roles by user {current_user.id}"
    )

    return results


@router.get("/documents/{document_id}/permissions", response_model=DocumentAccessResponse)
async def get_document_permissions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all users and roles with access to a document.

    Shows:
    - Direct user permissions
    - Role-based permissions
    - Active share links
    - Document owner

    Useful for managing access and auditing who can see the document.
    """
    permission_service = PermissionService(db)

    # Check if user can view permissions (need share permission or be owner)
    if not permission_service.check_document_access(current_user.id, document_id, "share"):
        # Allow document owner to view
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document or document.created_by_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Permission denied")
    else:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    # Get owner info
    owner_info = None
    if document.created_by_user_id:
        owner = db.query(User).filter(User.id == document.created_by_user_id).first()
        if owner:
            owner_info = {
                "id": owner.id,
                "email": owner.email,
                "name": owner.name
            }

    # Get direct permissions
    permissions = db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document_id,
        DocumentPermission.is_active == True
    ).options(
        joinedload(DocumentPermission.user),
        joinedload(DocumentPermission.role),
        joinedload(DocumentPermission.shared_by)
    ).all()

    permission_responses = []
    unique_users = set()

    for perm in permissions:
        user_info = None
        role_info = None

        if perm.user:
            user_info = {
                "id": perm.user.id,
                "email": perm.user.email,
                "name": perm.user.name
            }
            unique_users.add(perm.user.id)

        if perm.role:
            role_info = {
                "id": perm.role.id,
                "name": perm.role.name,
                "slug": perm.role.slug
            }

        permission_responses.append(DocumentPermissionResponse(
            id=perm.id,
            user=user_info,
            role=role_info,
            can_read=perm.can_read,
            can_write=perm.can_write,
            can_delete=perm.can_delete,
            can_share=perm.can_share,
            shared_by={
                "id": perm.shared_by.id,
                "email": perm.shared_by.email,
                "name": perm.shared_by.name
            } if perm.shared_by else None,
            shared_at=perm.shared_at.isoformat(),
            expires_at=perm.expires_at.isoformat() if perm.expires_at else None,
            notes=perm.notes
        ))

    # Get share links
    share_links = db.query(ShareLink).filter(
        ShareLink.document_id == document_id,
        ShareLink.is_active == True
    ).options(
        joinedload(ShareLink.created_by)
    ).all()

    share_link_responses = []
    for link in share_links:
        share_link_responses.append(ShareLinkResponse(
            id=link.id,
            token=link.token,
            url=build_share_url(link.token),
            access_level=link.access_level.value,
            expires_at=link.expires_at.isoformat() if link.expires_at else None,
            max_accesses=link.max_accesses,
            current_accesses=link.current_accesses,
            is_password_protected=bool(link.password_hash),
            created_by={
                "id": link.created_by.id,
                "email": link.created_by.email,
                "name": link.created_by.name
            } if link.created_by else None,
            created_at=link.created_at.isoformat(),
            is_active=link.is_active,
            is_expired=link.is_expired
        ))

    # Add owner to unique users count
    if document.created_by_user_id:
        unique_users.add(document.created_by_user_id)

    return DocumentAccessResponse(
        document_id=document_id,
        filename=document.filename,
        owner=owner_info,
        is_public=document.is_public,
        direct_permissions=permission_responses,
        share_links=share_link_responses,
        total_users_with_access=len(unique_users)
    )


@router.delete("/documents/{document_id}/permissions/{user_id}")
async def revoke_document_access(
    document_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a user's access to a document.

    Requires share permission on the document.
    """
    permission_service = PermissionService(db)

    try:
        success = permission_service.revoke_document_access(
            document_id=document_id,
            target_user_id=user_id,
            revoked_by_user_id=current_user.id
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No active permission found for user {user_id} on document {document_id}"
        )

    return {
        "success": True,
        "message": f"Access revoked for user {user_id}"
    }


@router.post("/documents/{document_id}/links", response_model=ShareLinkResponse)
async def create_share_link(
    document_id: int,
    request: ShareLinkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a shareable link for a document.

    Share links allow anyone with the URL to access the document.
    Optional features:
    - Expiration date
    - Access limit (max number of uses)
    - Password protection

    Example:
    ```json
    {
      "access_level": "read",
      "expires_in_days": 7,
      "max_accesses": 100,
      "password": "secret123"
    }
    ```
    """
    permission_service = PermissionService(db)

    # Parse access level
    try:
        access_level = ShareLinkAccessLevel(request.access_level)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid access_level: {request.access_level}. Must be one of: read, comment, edit"
        )

    # Create share link
    try:
        share_link = permission_service.create_share_link(
            document_id=document_id,
            created_by_user_id=current_user.id,
            access_level=access_level,
            expires_in_days=request.expires_in_days,
            max_accesses=request.max_accesses,
            password=request.password
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    creator = db.query(User).filter(User.id == current_user.id).first()

    return ShareLinkResponse(
        id=share_link.id,
        token=share_link.token,
        url=build_share_url(share_link.token),
        access_level=share_link.access_level.value,
        expires_at=share_link.expires_at.isoformat() if share_link.expires_at else None,
        max_accesses=share_link.max_accesses,
        current_accesses=share_link.current_accesses,
        is_password_protected=bool(share_link.password_hash),
        created_by={
            "id": creator.id,
            "email": creator.email,
            "name": creator.name
        } if creator else None,
        created_at=share_link.created_at.isoformat(),
        is_active=share_link.is_active,
        is_expired=share_link.is_expired
    )


@router.delete("/links/{link_id}")
async def revoke_share_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke/delete a share link.

    The link will no longer provide access to the document.
    """
    permission_service = PermissionService(db)

    try:
        success = permission_service.revoke_share_link(
            share_link_id=link_id,
            revoked_by_user_id=current_user.id
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not success:
        raise HTTPException(status_code=404, detail=f"Share link {link_id} not found")

    return {
        "success": True,
        "message": "Share link has been revoked"
    }


@router.post("/folders/{folder_path:path}/share")
async def share_folder(
    folder_path: str,
    request: FolderShareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Share an entire folder with users or roles.

    Folder permissions cascade to all documents within the folder.
    Optionally inherit to subfolders.

    Example:
    ```json
    {
      "user_ids": [2, 3],
      "can_read": true,
      "inherit_to_subfolders": true
    }
    ```
    """
    permission_service = PermissionService(db)

    # Verify user has permission to share folder
    # (For now, require admin or document write permission)
    permission_service.require_permission(current_user.id, PermissionAction.SHARE_DOCUMENTS)

    # Normalize folder path
    if not folder_path.startswith("/"):
        folder_path = "/" + folder_path
    folder_path = folder_path.rstrip("/")

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    results = {
        "success": True,
        "folder_path": folder_path,
        "shared_with": []
    }

    # Share with users
    if request.user_ids:
        for user_id in request.user_ids:
            # Check if permission already exists
            existing = db.query(FolderPermission).filter(
                FolderPermission.folder_path == folder_path,
                FolderPermission.user_id == user_id,
                FolderPermission.is_active == True
            ).first()

            if existing:
                # Update existing
                existing.can_read = request.can_read
                existing.can_write = request.can_write
                existing.can_delete = request.can_delete
                existing.can_share = request.can_share
                existing.inherit_to_subfolders = request.inherit_to_subfolders
                existing.expires_at = expires_at
                permission = existing
            else:
                # Create new
                permission = FolderPermission(
                    folder_path=folder_path,
                    user_id=user_id,
                    can_read=request.can_read,
                    can_write=request.can_write,
                    can_delete=request.can_delete,
                    can_share=request.can_share,
                    inherit_to_subfolders=request.inherit_to_subfolders,
                    granted_by_user_id=current_user.id,
                    expires_at=expires_at
                )
                db.add(permission)

            db.commit()
            db.refresh(permission)

            user = db.query(User).filter(User.id == user_id).first()
            results["shared_with"].append({
                "type": "user",
                "user_id": user_id,
                "email": user.email if user else None,
                "permission_id": permission.id
            })

    # Share with roles
    if request.role_ids:
        for role_id in request.role_ids:
            existing = db.query(FolderPermission).filter(
                FolderPermission.folder_path == folder_path,
                FolderPermission.role_id == role_id,
                FolderPermission.is_active == True
            ).first()

            if existing:
                existing.can_read = request.can_read
                existing.can_write = request.can_write
                existing.can_delete = request.can_delete
                existing.can_share = request.can_share
                existing.inherit_to_subfolders = request.inherit_to_subfolders
                existing.expires_at = expires_at
                permission = existing
            else:
                permission = FolderPermission(
                    folder_path=folder_path,
                    role_id=role_id,
                    can_read=request.can_read,
                    can_write=request.can_write,
                    can_delete=request.can_delete,
                    can_share=request.can_share,
                    inherit_to_subfolders=request.inherit_to_subfolders,
                    granted_by_user_id=current_user.id,
                    expires_at=expires_at
                )
                db.add(permission)

            db.commit()
            db.refresh(permission)

            from app.models.permissions import Role
            role = db.query(Role).filter(Role.id == role_id).first()
            results["shared_with"].append({
                "type": "role",
                "role_id": role_id,
                "role_name": role.name if role else None,
                "permission_id": permission.id
            })

    logger.info(
        f"Folder {folder_path} shared with {len(request.user_ids or [])} users "
        f"and {len(request.role_ids or [])} roles by user {current_user.id}"
    )

    return results


@router.get("/folders/{folder_path:path}/permissions")
async def get_folder_permissions(
    folder_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all users and roles with access to a folder.
    """
    permission_service = PermissionService(db)

    # Require admin or share permission
    permission_service.require_permission(current_user.id, PermissionAction.READ_DOCUMENTS)

    # Normalize folder path
    if not folder_path.startswith("/"):
        folder_path = "/" + folder_path
    folder_path = folder_path.rstrip("/")

    # Get folder permissions
    permissions = db.query(FolderPermission).filter(
        FolderPermission.folder_path == folder_path,
        FolderPermission.is_active == True
    ).options(
        joinedload(FolderPermission.user),
        joinedload(FolderPermission.role),
        joinedload(FolderPermission.granted_by)
    ).all()

    permission_list = []
    for perm in permissions:
        user_info = None
        role_info = None

        if perm.user:
            user_info = {
                "id": perm.user.id,
                "email": perm.user.email,
                "name": perm.user.name
            }

        if perm.role:
            role_info = {
                "id": perm.role.id,
                "name": perm.role.name,
                "slug": perm.role.slug
            }

        permission_list.append({
            "id": perm.id,
            "user": user_info,
            "role": role_info,
            "can_read": perm.can_read,
            "can_write": perm.can_write,
            "can_delete": perm.can_delete,
            "can_share": perm.can_share,
            "inherit_to_subfolders": perm.inherit_to_subfolders,
            "granted_by": {
                "id": perm.granted_by.id,
                "email": perm.granted_by.email,
                "name": perm.granted_by.name
            } if perm.granted_by else None,
            "granted_at": perm.granted_at.isoformat(),
            "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
        })

    return {
        "folder_path": folder_path,
        "permissions": permission_list,
        "total": len(permission_list)
    }
