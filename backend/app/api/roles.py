"""
Role & Permission Management API

Endpoints for managing roles and permissions:
- List available permissions
- Create and manage custom roles
- Assign permissions to roles
- View role details and usage

System roles (Admin, Editor, Viewer) cannot be modified or deleted.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.auth import get_current_user, get_current_active_admin
from app.models.permissions import (
    Role, Permission, RoleType, PermissionAction,
    DEFAULT_PERMISSIONS, DEFAULT_ROLES
)
from app.models.settings import User
from app.services.permission_service import PermissionService
from app.core.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/roles", tags=["roles"])


# ==================== Pydantic Models ====================

class PermissionResponse(BaseModel):
    """Response model for permission"""
    id: int
    action: str
    name: str
    description: Optional[str]
    resource_type: Optional[str]

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """Request model for creating a custom role"""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None
    org_id: Optional[int] = None  # Org-specific role
    permission_ids: List[int] = []


class RoleUpdate(BaseModel):
    """Request model for updating a role"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    """Response model for role"""
    id: int
    name: str
    slug: str
    role_type: str
    description: Optional[str]
    is_system_role: bool
    is_active: bool
    created_at: str
    permissions: List[PermissionResponse] = []
    user_count: Optional[int] = 0
    org_id: Optional[int] = None

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Response model for list of roles"""
    roles: List[RoleResponse]
    total: int


class AddPermissionsRequest(BaseModel):
    """Request to add permissions to a role"""
    permission_ids: List[int]


# ==================== Endpoints ====================

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all available permissions.

    Permissions are predefined actions like:
    - read:documents
    - write:templates
    - manage:users

    These can be assigned to custom roles.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Query permissions
    query = db.query(Permission).filter(Permission.is_active == True)

    if resource_type:
        query = query.filter(Permission.resource_type == resource_type)

    permissions = query.order_by(Permission.resource_type, Permission.name).all()

    return [
        PermissionResponse(
            id=p.id,
            action=p.action.value,
            name=p.name,
            description=p.description,
            resource_type=p.resource_type
        )
        for p in permissions
    ]


@router.get("/", response_model=RoleListResponse)
async def list_roles(
    org_id: Optional[int] = Query(None, description="Filter by organization"),
    role_type: Optional[str] = Query(None, description="Filter by role type"),
    include_inactive: bool = Query(False, description="Include inactive roles"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all roles with their permissions.

    Returns both system roles (Admin, Editor, Viewer) and custom roles.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.READ_USERS)

    # Build query
    query = db.query(Role).options(joinedload(Role.permissions))

    # Apply filters
    if not include_inactive:
        query = query.filter(Role.is_active == True)

    if org_id is not None:
        query = query.filter(
            (Role.org_id == org_id) | (Role.org_id == None)  # Include global roles
        )

    if role_type:
        try:
            role_type_enum = RoleType(role_type)
            query = query.filter(Role.role_type == role_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role_type: {role_type}. Must be one of: admin, editor, viewer, custom"
            )

    roles = query.order_by(Role.is_system_role.desc(), Role.name).all()

    # Count users for each role
    from app.models.permissions import UserRole
    from sqlalchemy import func

    role_user_counts = dict(
        db.query(UserRole.role_id, func.count(UserRole.user_id))
        .filter(UserRole.is_active == True)
        .group_by(UserRole.role_id)
        .all()
    )

    # Build response
    role_responses = []
    for role in roles:
        role_responses.append(RoleResponse(
            id=role.id,
            name=role.name,
            slug=role.slug,
            role_type=role.role_type.value,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=role.is_active,
            created_at=role.created_at.isoformat(),
            permissions=[
                PermissionResponse(
                    id=p.id,
                    action=p.action.value,
                    name=p.name,
                    description=p.description,
                    resource_type=p.resource_type
                )
                for p in role.permissions
            ],
            user_count=role_user_counts.get(role.id, 0),
            org_id=role.org_id
        ))

    return RoleListResponse(
        roles=role_responses,
        total=len(role_responses)
    )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific role.

    Includes all permissions assigned to the role and count of users with this role.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.READ_USERS)

    # Get role
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    # Count users with this role
    from app.models.permissions import UserRole
    user_count = db.query(UserRole).filter(
        UserRole.role_id == role_id,
        UserRole.is_active == True
    ).count()

    return RoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        role_type=role.role_type.value,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at.isoformat(),
        permissions=[
            PermissionResponse(
                id=p.id,
                action=p.action.value,
                name=p.name,
                description=p.description,
                resource_type=p.resource_type
            )
            for p in role.permissions
        ],
        user_count=user_count,
        org_id=role.org_id
    )


@router.post("/", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a custom role with specific permissions.

    System roles (Admin, Editor, Viewer) cannot be created via API.
    Use this to create organization-specific or project-specific roles.

    Example:
    ```json
    {
      "name": "Contract Reviewer",
      "slug": "contract-reviewer",
      "description": "Can review and approve contracts",
      "permission_ids": [1, 2, 5]
    }
    ```
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Check if slug already exists
    existing = db.query(Role).filter(
        Role.slug == role_data.slug,
        Role.org_id == role_data.org_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Role with slug '{role_data.slug}' already exists"
        )

    # Validate permissions exist
    if role_data.permission_ids:
        permissions = db.query(Permission).filter(
            Permission.id.in_(role_data.permission_ids)
        ).all()
        if len(permissions) != len(role_data.permission_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more permission IDs are invalid"
            )
    else:
        permissions = []

    # Create role
    role = Role(
        name=role_data.name,
        slug=role_data.slug,
        description=role_data.description,
        org_id=role_data.org_id,
        role_type=RoleType.CUSTOM,
        is_system_role=False,
        created_by_user_id=current_user.id
    )

    # Add permissions
    role.permissions = permissions

    db.add(role)
    db.commit()
    db.refresh(role)

    logger.info(f"Custom role created: {role.name} (id={role.id}) by user {current_user.id}")

    return RoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        role_type=role.role_type.value,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at.isoformat(),
        permissions=[
            PermissionResponse(
                id=p.id,
                action=p.action.value,
                name=p.name,
                description=p.description,
                resource_type=p.resource_type
            )
            for p in role.permissions
        ],
        user_count=0,
        org_id=role.org_id
    )


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a custom role.

    System roles cannot be modified.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Get role
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    # Cannot modify system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles (Admin, Editor, Viewer) cannot be modified"
        )

    # Update fields
    if role_data.name is not None:
        role.name = role_data.name

    if role_data.description is not None:
        role.description = role_data.description

    if role_data.is_active is not None:
        role.is_active = role_data.is_active

    role.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(role)

    logger.info(f"Role updated: {role.name} (id={role.id}) by user {current_user.id}")

    # Count users
    from app.models.permissions import UserRole
    user_count = db.query(UserRole).filter(
        UserRole.role_id == role_id,
        UserRole.is_active == True
    ).count()

    return RoleResponse(
        id=role.id,
        name=role.name,
        slug=role.slug,
        role_type=role.role_type.value,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at.isoformat(),
        permissions=[
            PermissionResponse(
                id=p.id,
                action=p.action.value,
                name=p.name,
                description=p.description,
                resource_type=p.resource_type
            )
            for p in role.permissions
        ],
        user_count=user_count,
        org_id=role.org_id
    )


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a custom role.

    System roles cannot be deleted.
    If users are assigned this role, they will lose these permissions.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Get role
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    # Cannot delete system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles (Admin, Editor, Viewer) cannot be deleted"
        )

    # Check how many users have this role
    from app.models.permissions import UserRole
    user_count = db.query(UserRole).filter(
        UserRole.role_id == role_id,
        UserRole.is_active == True
    ).count()

    # Soft delete (mark inactive)
    role.is_active = False
    role.updated_at = datetime.utcnow()
    db.commit()

    logger.info(
        f"Role deleted: {role.name} (id={role.id}) by user {current_user.id}. "
        f"{user_count} users were affected."
    )

    return {
        "success": True,
        "message": f"Role '{role.name}' has been deleted",
        "affected_users": user_count
    }


@router.post("/{role_id}/permissions")
async def add_permissions_to_role(
    role_id: int,
    request: AddPermissionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add permissions to a role.

    System roles cannot be modified.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Get role
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    # Cannot modify system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles cannot be modified"
        )

    # Get permissions
    permissions = db.query(Permission).filter(
        Permission.id.in_(request.permission_ids)
    ).all()

    if len(permissions) != len(request.permission_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more permission IDs are invalid"
        )

    # Add new permissions (avoid duplicates)
    existing_permission_ids = {p.id for p in role.permissions}
    new_permissions = [p for p in permissions if p.id not in existing_permission_ids]

    role.permissions.extend(new_permissions)
    role.updated_at = datetime.utcnow()
    db.commit()

    logger.info(
        f"Added {len(new_permissions)} permissions to role {role.name} by user {current_user.id}"
    )

    return {
        "success": True,
        "message": f"Added {len(new_permissions)} permissions to role '{role.name}'",
        "added_count": len(new_permissions),
        "total_permissions": len(role.permissions)
    }


@router.delete("/{role_id}/permissions/{permission_id}")
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a permission from a role.

    System roles cannot be modified.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.MANAGE_ROLES)

    # Get role
    role = db.query(Role).options(joinedload(Role.permissions)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")

    # Cannot modify system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=400,
            detail="System roles cannot be modified"
        )

    # Find and remove permission
    permission_to_remove = None
    for p in role.permissions:
        if p.id == permission_id:
            permission_to_remove = p
            break

    if not permission_to_remove:
        raise HTTPException(
            status_code=404,
            detail=f"Permission {permission_id} not found in role {role.name}"
        )

    role.permissions.remove(permission_to_remove)
    role.updated_at = datetime.utcnow()
    db.commit()

    logger.info(
        f"Removed permission {permission_id} from role {role.name} by user {current_user.id}"
    )

    return {
        "success": True,
        "message": f"Removed permission from role '{role.name}'",
        "remaining_permissions": len(role.permissions)
    }


@router.post("/initialize")
async def initialize_default_roles_and_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialize default permissions and roles.

    This should be run once on system setup.
    Creates:
    - All default permissions (read:documents, write:templates, etc.)
    - System roles (Admin, Editor, Viewer) with their permissions

    Safe to run multiple times - will skip existing permissions/roles.
    """
    current_user.id = get_current_user.id()

    # Only admins can initialize
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can initialize system permissions"
        )

    try:
        PermissionService.initialize_default_permissions(db)
        logger.info(f"Default permissions and roles initialized by user {current_user.id}")

        return {
            "success": True,
            "message": "Default permissions and roles have been initialized"
        }
    except Exception as e:
        logger.error(f"Error initializing permissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error initializing permissions: {str(e)}"
        )
