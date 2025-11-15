"""
Organization Management API Endpoints

Handles:
- Organization CRUD operations
- Member management
- Invitation system
- Role assignment
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.settings import User, Organization, OrganizationInvite
from app.services.organization_service import get_organization_service, OrganizationService

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


# ====================
# Request/Response Models
# ====================

class CreateOrganizationRequest(BaseModel):
    """Create organization request"""
    name: str
    slug: Optional[str] = None


class OrganizationResponse(BaseModel):
    """Organization details"""
    id: int
    name: str
    slug: str
    owner_id: int
    is_active: bool
    created_at: datetime
    member_count: Optional[int] = None


class CreateInviteRequest(BaseModel):
    """Create invitation request"""
    role: str = "member"  # "owner", "admin", "member"
    email: Optional[EmailStr] = None
    expires_in_days: Optional[int] = 7
    max_uses: int = 1


class InviteResponse(BaseModel):
    """Invitation details"""
    id: int
    invite_code: str
    role: str
    email: Optional[str]
    max_uses: int
    current_uses: int
    remaining_uses: Optional[int]
    expires_at: Optional[datetime]
    is_expired: bool
    created_at: datetime


class AcceptInviteRequest(BaseModel):
    """Accept invitation request"""
    invite_code: str


class MemberResponse(BaseModel):
    """Organization member details"""
    id: int
    email: str
    name: Optional[str]
    organization_role: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]


class UpdateMemberRoleRequest(BaseModel):
    """Update member role request"""
    role: str  # "owner", "admin", "member"


class TransferOwnershipRequest(BaseModel):
    """Transfer ownership request"""
    new_owner_id: int


# ====================
# Organization CRUD
# ====================

@router.post("/", response_model=OrganizationResponse)
def create_organization(
    org_request: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Create a new organization.

    The current user becomes the organization owner.
    Users can only create one organization unless they're a superadmin.

    Args:
        org_request: Organization name and optional slug

    Returns:
        Created organization

    Example:
        POST /api/organizations/
        {
            "name": "Acme Corporation",
            "slug": "acme"
        }
    """
    # Check if user already has an organization
    if current_user.org_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization"
        )

    try:
        organization = org_service.create_organization(
            db=db,
            name=org_request.name,
            owner=current_user,
            slug=org_request.slug
        )

        # Get member count
        members = org_service.get_organization_members(db, organization)

        return OrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            owner_id=organization.owner_id,
            is_active=organization.is_active,
            created_at=organization.created_at,
            member_count=len(members)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/my", response_model=OrganizationResponse)
def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Get current user's organization.

    Returns:
        Organization details with member count

    Example:
        GET /api/organizations/my
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to an organization"
        )

    organization = db.query(Organization).filter(
        Organization.id == current_user.org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Get member count
    members = org_service.get_organization_members(db, organization)

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        owner_id=organization.owner_id,
        is_active=organization.is_active,
        created_at=organization.created_at,
        member_count=len(members)
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
def get_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Get organization details.

    Only members of the organization can view it (or superadmins).

    Args:
        org_id: Organization ID

    Returns:
        Organization details
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check access (member or superadmin)
    if current_user.org_id != org_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get member count
    members = org_service.get_organization_members(db, organization)

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        owner_id=organization.owner_id,
        is_active=organization.is_active,
        created_at=organization.created_at,
        member_count=len(members)
    )


@router.put("/{org_id}", response_model=OrganizationResponse)
def update_organization(
    org_id: int,
    org_request: CreateOrganizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Update organization details.

    Only organization owner or admins can update.

    Args:
        org_id: Organization ID
        org_request: Updated name and slug

    Returns:
        Updated organization
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update organization"
        )

    # Update fields
    if org_request.name:
        organization.name = org_request.name
    if org_request.slug:
        organization.slug = org_request.slug

    organization.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(organization)

    # Get member count
    members = org_service.get_organization_members(db, organization)

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        owner_id=organization.owner_id,
        is_active=organization.is_active,
        created_at=organization.created_at,
        member_count=len(members)
    )


@router.delete("/{org_id}")
def delete_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Delete organization (soft delete).

    Only organization owner can delete.

    Args:
        org_id: Organization ID

    Returns:
        Success message
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.organization_role != 'owner' or current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can delete the organization"
        )

    org_service.delete_organization(db, organization, current_user)

    return {"message": "Organization deleted successfully"}


# ====================
# Member Management
# ====================

@router.get("/{org_id}/members", response_model=List[MemberResponse])
def get_organization_members(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Get all members of an organization.

    Args:
        org_id: Organization ID

    Returns:
        List of organization members
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check access
    if current_user.org_id != org_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    members = org_service.get_organization_members(db, organization)

    return [
        MemberResponse(
            id=member.id,
            email=member.email,
            name=member.name,
            organization_role=member.organization_role,
            is_active=member.is_active,
            created_at=member.created_at,
            last_login=member.last_login
        )
        for member in members
    ]


@router.delete("/{org_id}/members/{user_id}")
def remove_member(
    org_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Remove a member from the organization.

    Only owners and admins can remove members.
    Cannot remove the organization owner.

    Args:
        org_id: Organization ID
        user_id: User ID to remove

    Returns:
        Success message
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id or current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can remove members"
        )

    user_to_remove = db.query(User).filter(User.id == user_id).first()

    if not user_to_remove:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        org_service.remove_member(db, organization, user_to_remove, current_user)
        return {"message": "Member removed successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{org_id}/members/{user_id}/role")
def update_member_role(
    org_id: int,
    user_id: int,
    role_request: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Update a member's role in the organization.

    Only owners and admins can change roles.
    Only owners can assign owner role.

    Args:
        org_id: Organization ID
        user_id: User ID to update
        role_request: New role

    Returns:
        Success message
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id or current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can change roles"
        )

    user_to_update = db.query(User).filter(User.id == user_id).first()

    if not user_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        org_service.update_member_role(
            db, organization, user_to_update,
            role_request.role, current_user
        )
        return {"message": "Member role updated successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{org_id}/transfer-ownership")
def transfer_ownership(
    org_id: int,
    transfer_request: TransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Transfer organization ownership to another member.

    Only current owner can transfer ownership.
    New owner must be an existing member.

    Args:
        org_id: Organization ID
        transfer_request: New owner user ID

    Returns:
        Success message
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.organization_role != 'owner' or current_user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can transfer ownership"
        )

    new_owner = db.query(User).filter(
        User.id == transfer_request.new_owner_id
    ).first()

    if not new_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New owner not found"
        )

    try:
        org_service.transfer_ownership(db, organization, new_owner, current_user)
        return {"message": "Ownership transferred successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ====================
# Invitation System
# ====================

@router.post("/{org_id}/invites", response_model=InviteResponse)
def create_invite(
    org_id: int,
    invite_request: CreateInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Create an invitation to join the organization.

    Only owners and admins can create invites.

    Args:
        org_id: Organization ID
        invite_request: Invitation parameters

    Returns:
        Created invitation with invite code
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id or current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create invites"
        )

    invite = org_service.create_invite(
        db=db,
        organization=organization,
        created_by=current_user,
        role=invite_request.role,
        email=invite_request.email,
        expires_in_days=invite_request.expires_in_days,
        max_uses=invite_request.max_uses
    )

    return InviteResponse(
        id=invite.id,
        invite_code=invite.invite_code,
        role=invite.role,
        email=invite.email,
        max_uses=invite.max_uses,
        current_uses=invite.current_uses,
        remaining_uses=invite.remaining_uses,
        expires_at=invite.expires_at,
        is_expired=invite.is_expired,
        created_at=invite.created_at
    )


@router.get("/{org_id}/invites", response_model=List[InviteResponse])
def list_invites(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all invitations for the organization.

    Args:
        org_id: Organization ID

    Returns:
        List of invitations
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id or current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can view invites"
        )

    invites = db.query(OrganizationInvite).filter(
        OrganizationInvite.organization_id == org_id
    ).all()

    return [
        InviteResponse(
            id=invite.id,
            invite_code=invite.invite_code,
            role=invite.role,
            email=invite.email,
            max_uses=invite.max_uses,
            current_uses=invite.current_uses,
            remaining_uses=invite.remaining_uses,
            expires_at=invite.expires_at,
            is_expired=invite.is_expired,
            created_at=invite.created_at
        )
        for invite in invites
    ]


@router.post("/join", response_model=OrganizationResponse)
def accept_invite(
    invite_request: AcceptInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    org_service: OrganizationService = Depends(get_organization_service)
):
    """
    Accept an invitation and join the organization.

    User must not already belong to an organization.

    Args:
        invite_request: Invite code

    Returns:
        Organization details
    """
    try:
        organization = org_service.accept_invite(
            db=db,
            invite_code=invite_request.invite_code,
            user=current_user
        )

        # Get member count
        members = org_service.get_organization_members(db, organization)

        return OrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            owner_id=organization.owner_id,
            is_active=organization.is_active,
            created_at=organization.created_at,
            member_count=len(members)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{org_id}/invites/{invite_id}")
def revoke_invite(
    org_id: int,
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke an invitation.

    Only owners and admins can revoke invites.

    Args:
        org_id: Organization ID
        invite_id: Invitation ID

    Returns:
        Success message
    """
    organization = db.query(Organization).filter(
        Organization.id == org_id
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check permissions
    if current_user.org_id != org_id or current_user.organization_role not in ['owner', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can revoke invites"
        )

    invite = db.query(OrganizationInvite).filter(
        OrganizationInvite.id == invite_id,
        OrganizationInvite.organization_id == org_id
    ).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    invite.is_active = False
    db.commit()

    return {"message": "Invitation revoked successfully"}
