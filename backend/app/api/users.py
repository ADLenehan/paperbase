"""
User Management API

Endpoints for managing users, including:
- Creating new users
- Listing and searching users
- Updating user profiles
- Deactivating users
- Managing user roles and permissions

All endpoints require appropriate permissions.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError
from app.models.permissions import PermissionAction
from app.models.settings import Organization, User
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


# ==================== Pydantic Models ====================

class UserCreate(BaseModel):
    """Request model for creating a new user"""
    email: EmailStr
    name: Optional[str] = None
    org_id: int
    password: Optional[str] = None  # Optional for now (MVP)
    is_admin: bool = False


class UserUpdate(BaseModel):
    """Request model for updating a user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class RoleAssignment(BaseModel):
    """Request model for assigning a role to a user"""
    role_id: int
    scope: str = "global"  # "global", "organization", or "folder"
    scope_org_id: Optional[int] = None
    scope_folder_path: Optional[str] = None
    expires_in_days: Optional[int] = None


class UserResponse(BaseModel):
    """Response model for user data"""
    id: int
    email: str
    name: Optional[str]
    org_id: int
    organization_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: str
    last_login: Optional[str]
    roles: List[dict] = []
    permissions: List[str] = []

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response model for list of users"""
    users: List[UserResponse]
    total: int
    page: int
    page_size: int


# ==================== Helper Functions ====================

async def require_permission(
    action: PermissionAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dependency to require a specific permission"""
    permission_service = PermissionService(db)
    permission_service.require_permission(current_user.id, action)


# ==================== Endpoints ====================

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user.

    Requires: WRITE_USERS permission
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.WRITE_USERS)

    # Verify organization exists
    org = db.query(Organization).filter(Organization.id == user_data.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {user_data.org_id} not found")

    # Check if email already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"User with email {user_data.email} already exists")

    # Hash password if provided
    hashed_password = None
    if user_data.password:
        from passlib.hash import bcrypt
        hashed_password = bcrypt.hash(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        name=user_data.name,
        org_id=user_data.org_id,
        hashed_password=hashed_password,
        is_admin=user_data.is_admin,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"User created: {user.email} (id={user.id}) by user {current_user.id}")

    # Return response
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        org_id=user.org_id,
        organization_name=org.name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        roles=[],
        permissions=[]
    )


@router.get("/", response_model=UserListResponse)
async def list_users(
    org_id: Optional[int] = Query(None, description="Filter by organization"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all users with optional filters.

    Requires: READ_USERS permission
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.READ_USERS)

    # Build query
    query = db.query(User)

    # Apply filters
    if org_id is not None:
        query = query.filter(User.org_id == org_id)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_term)) | (User.email.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()

    # Build response
    user_responses = []
    for user in users:
        org = db.query(Organization).filter(Organization.id == user.org_id).first()

        # Get user roles and permissions
        roles = permission_service.get_user_roles(user.id)
        permissions = permission_service.get_user_permissions(user.id)

        user_responses.append(UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            org_id=user.org_id,
            organization_name=org.name if org else None,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None,
            roles=roles,
            permissions=[p.value for p in permissions]
        ))

    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific user.

    Requires: READ_USERS permission
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.READ_USERS)

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get organization
    org = db.query(Organization).filter(Organization.id == user.org_id).first()

    # Get roles and permissions
    roles = permission_service.get_user_roles(user.id)
    permissions = permission_service.get_user_permissions(user.id)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        org_id=user.org_id,
        organization_name=org.name if org else None,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        roles=roles,
        permissions=[p.value for p in permissions]
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile information.

    Requires: WRITE_USERS permission

    Users can update their own profile without special permissions.
    """
    permission_service = PermissionService(db)

    # Check if updating self or need permission
    if current_user.id != user_id:
        permission_service.require_permission(current_user.id, PermissionAction.WRITE_USERS)

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Update fields
    if user_data.name is not None:
        user.name = user_data.name

    if user_data.email is not None:
        # Check if new email already exists
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Email {user_data.email} already in use")
        user.email = user_data.email

    if user_data.is_active is not None:
        # Only admins can change active status
        if current_user_id != user_id:
            permission_service.require_permission(current_user_id, PermissionAction.WRITE_USERS)
        user.is_active = user_data.is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    logger.info(f"User updated: {user.email} (id={user.id}) by user {current_user_id}")

    # Get organization
    org = db.query(Organization).filter(Organization.id == user.org_id).first()

    # Get roles and permissions
    roles = permission_service.get_user_roles(user.id)
    permissions = permission_service.get_user_permissions(user.id)

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        org_id=user.org_id,
        organization_name=org.name if org else None,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
        roles=roles,
        permissions=[p.value for p in permissions]
    )


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user (soft delete).

    Requires: DELETE_USERS permission

    Users are not actually deleted, just marked as inactive.
    This preserves audit trails and document ownership.
    """
    permission_service = PermissionService(db)

    # Check permission
    permission_service.require_permission(current_user.id, PermissionAction.DELETE_USERS)

    # Can't deactivate self
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is already inactive")

    # Deactivate
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User deactivated: {user.email} (id={user.id}) by user {current_user.id}")

    return {
        "success": True,
        "message": f"User {user.email} has been deactivated"
    }


@router.post("/{user_id}/roles")
async def assign_role_to_user(
    user_id: int,
    assignment: RoleAssignment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign a role to a user.

    Requires: MANAGE_ROLES permission

    Roles can be assigned with different scopes:
    - global: User has role permissions everywhere
    - organization: User has role permissions in specific org
    - folder: User has role permissions in specific folder
    """
    permission_service = PermissionService(db)

    # Parse scope
    from app.models.permissions import PermissionScope
    try:
        scope = PermissionScope(assignment.scope)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope: {assignment.scope}. Must be one of: global, organization, folder, document"
        )

    # Calculate expiration
    expires_at = None
    if assignment.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=assignment.expires_in_days)

    # Assign role
    try:
        user_role = permission_service.assign_role(
            user_id=user_id,
            role_id=assignment.role_id,
            assigned_by_user_id=current_user.id,
            scope=scope,
            scope_org_id=assignment.scope_org_id,
            scope_folder_path=assignment.scope_folder_path,
            expires_at=expires_at
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "success": True,
        "message": "Role assigned successfully",
        "user_role_id": user_role.id,
        "role_id": user_role.role_id,
        "scope": user_role.scope.value
    }


@router.delete("/{user_id}/roles/{role_id}")
async def revoke_role_from_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a role from a user.

    Requires: MANAGE_ROLES permission
    """
    permission_service = PermissionService(db)

    # Revoke role
    try:
        success = permission_service.revoke_role(
            user_id=user_id,
            role_id=role_id,
            revoked_by_user_id=current_user.id
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Role assignment not found for user {user_id} and role {role_id}"
        )

    return {
        "success": True,
        "message": "Role revoked successfully"
    }


@router.get("/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all permissions for a user.

    Requires: READ_USERS permission

    Returns a comprehensive list of all permissions the user has,
    including those from roles and direct assignments.
    """
    permission_service = PermissionService(db)

    # Check permission (users can view their own permissions)
    if current_user.id != user_id:
        permission_service.require_permission(current_user.id, PermissionAction.READ_USERS)

    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Get permissions
    permissions = permission_service.get_user_permissions(user_id)
    roles = permission_service.get_user_roles(user_id)

    return {
        "user_id": user_id,
        "email": user.email,
        "is_admin": user.is_admin,
        "permissions": [
            {
                "action": p.value,
                "name": p.name if hasattr(p, 'name') else p.value.replace(':', ' ').title()
            }
            for p in permissions
        ],
        "roles": roles,
        "total_permissions": len(permissions)
    }
