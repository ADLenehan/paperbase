"""
Organization Management Service

Handles:
- Organization creation and management
- User invitations and membership
- Organization settings
- Multi-tenant data isolation
"""

import secrets
import string
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging
import re

from app.models.settings import Organization, User, OrganizationInvite

logger = logging.getLogger(__name__)


class OrganizationService:
    """
    Service for managing organizations and memberships.

    Features:
    - Create organizations with unique slugs
    - Generate and manage invite codes
    - Handle user membership
    - Validate organization access
    """

    @staticmethod
    def generate_slug(name: str) -> str:
        """
        Generate URL-friendly slug from organization name.

        Args:
            name: Organization name

        Returns:
            URL-safe slug (lowercase, hyphens, alphanumeric)

        Example:
            >>> OrganizationService.generate_slug("Acme Corporation")
            "acme-corporation"
        """
        # Convert to lowercase
        slug = name.lower()

        # Replace spaces and special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)

        # Remove leading/trailing hyphens
        slug = slug.strip('-')

        return slug

    @staticmethod
    def generate_invite_code(length: int = 8) -> str:
        """
        Generate a random invite code.

        Args:
            length: Length of invite code (default: 8)

        Returns:
            Random alphanumeric code (uppercase)

        Example:
            >>> code = OrganizationService.generate_invite_code()
            >>> print(code)  # "ABC123XY"
        """
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))

    def create_organization(
        self,
        db: Session,
        name: str,
        owner: User,
        slug: Optional[str] = None
    ) -> Organization:
        """
        Create a new organization with the user as owner.

        Args:
            db: Database session
            name: Organization name
            owner: User who will own the organization
            slug: Optional custom slug (auto-generated if not provided)

        Returns:
            Created organization

        Raises:
            ValueError: If organization name or slug already exists

        Example:
            >>> org = service.create_organization(db, "Acme Corp", user)
            >>> print(org.slug)  # "acme-corp"
        """
        # Generate slug if not provided
        if not slug:
            slug = self.generate_slug(name)

        # Ensure uniqueness
        existing_org = db.query(Organization).filter(
            or_(
                Organization.name == name,
                Organization.slug == slug
            )
        ).first()

        if existing_org:
            if existing_org.name == name:
                raise ValueError(f"Organization with name '{name}' already exists")
            else:
                # Add random suffix to slug
                slug = f"{slug}-{secrets.token_hex(4)}"

        # Create organization
        org = Organization(
            name=name,
            slug=slug,
            is_active=True,
        )

        db.add(org)
        db.flush()  # Get org.id before setting owner

        # Set owner
        org.owner_id = owner.id
        owner.org_id = org.id
        owner.organization_role = "owner"
        owner.onboarding_completed = True

        db.commit()
        db.refresh(org)

        logger.info(f"Created organization '{name}' (id={org.id}) with owner {owner.email}")

        return org

    def create_invite(
        self,
        db: Session,
        organization: Organization,
        created_by: User,
        role: str = "member",
        email: Optional[str] = None,
        expires_in_days: Optional[int] = 7,
        max_uses: int = 1
    ) -> OrganizationInvite:
        """
        Create an invitation to join the organization.

        Args:
            db: Database session
            organization: Organization to invite to
            created_by: User creating the invite
            role: Role to assign ("owner", "admin", "member")
            email: Optional specific email to restrict invite to
            expires_in_days: Days until expiration (None = no expiration)
            max_uses: Maximum number of uses (1 = single-use)

        Returns:
            Created invite

        Example:
            >>> invite = service.create_invite(db, org, admin_user, role="member")
            >>> print(invite.invite_code)  # "ABC123XY"
        """
        # Generate unique invite code
        invite_code = self.generate_invite_code()
        while db.query(OrganizationInvite).filter(
            OrganizationInvite.invite_code == invite_code
        ).first():
            invite_code = self.generate_invite_code()

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create invite
        invite = OrganizationInvite(
            organization_id=organization.id,
            invite_code=invite_code,
            email=email.lower() if email else None,
            role=role,
            max_uses=max_uses,
            expires_at=expires_at,
            created_by_user_id=created_by.id,
            is_active=True,
        )

        db.add(invite)
        db.commit()
        db.refresh(invite)

        logger.info(
            f"Created invite {invite_code} for org {organization.name} "
            f"(role={role}, max_uses={max_uses})"
        )

        return invite

    def accept_invite(
        self,
        db: Session,
        invite_code: str,
        user: User
    ) -> Organization:
        """
        Accept an invitation and add user to organization.

        Args:
            db: Database session
            invite_code: Invite code
            user: User accepting the invite

        Returns:
            Organization user was added to

        Raises:
            ValueError: If invite is invalid, expired, or email doesn't match

        Example:
            >>> org = service.accept_invite(db, "ABC123XY", user)
            >>> print(user.org_id == org.id)  # True
        """
        # Find invite
        invite = db.query(OrganizationInvite).filter(
            OrganizationInvite.invite_code == invite_code
        ).first()

        if not invite:
            raise ValueError("Invalid invite code")

        if invite.is_expired:
            raise ValueError("Invite has expired or reached max uses")

        # Check email restriction
        if invite.email and invite.email.lower() != user.email.lower():
            raise ValueError(f"This invite is only for {invite.email}")

        # Check if user already belongs to an organization
        if user.org_id:
            raise ValueError("User already belongs to an organization")

        # Get organization
        organization = db.query(Organization).filter(
            Organization.id == invite.organization_id
        ).first()

        if not organization or not organization.is_active:
            raise ValueError("Organization not found or inactive")

        # Add user to organization
        user.org_id = organization.id
        user.organization_role = invite.role
        user.onboarding_completed = True

        # Update invite usage
        invite.current_uses += 1
        invite.last_used_at = datetime.utcnow()

        # Track accepted users (store as JSON list)
        import json
        accepted_ids = []
        if invite.accepted_by_user_ids:
            try:
                accepted_ids = json.loads(invite.accepted_by_user_ids)
            except:
                accepted_ids = []
        accepted_ids.append(user.id)
        invite.accepted_by_user_ids = json.dumps(accepted_ids)

        db.commit()
        db.refresh(user)
        db.refresh(organization)

        logger.info(
            f"User {user.email} accepted invite {invite_code} "
            f"and joined {organization.name} as {invite.role}"
        )

        return organization

    def get_organization_members(
        self,
        db: Session,
        organization: Organization
    ) -> List[User]:
        """
        Get all members of an organization.

        Args:
            db: Database session
            organization: Organization

        Returns:
            List of users in the organization

        Example:
            >>> members = service.get_organization_members(db, org)
            >>> for user in members:
            ...     print(f"{user.name} - {user.organization_role}")
        """
        return db.query(User).filter(
            and_(
                User.org_id == organization.id,
                User.is_active == True
            )
        ).all()

    def remove_member(
        self,
        db: Session,
        organization: Organization,
        user_to_remove: User,
        removed_by: User
    ) -> None:
        """
        Remove a member from an organization.

        Args:
            db: Database session
            organization: Organization
            user_to_remove: User to remove
            removed_by: User performing the removal

        Raises:
            ValueError: If trying to remove owner or without permission

        Example:
            >>> service.remove_member(db, org, member_user, admin_user)
        """
        # Can't remove owner
        if user_to_remove.id == organization.owner_id:
            raise ValueError("Cannot remove organization owner")

        # Check permissions (owner or admin can remove members)
        if removed_by.organization_role not in ['owner', 'admin']:
            raise ValueError("Only owners and admins can remove members")

        # Remove from organization
        user_to_remove.org_id = None
        user_to_remove.organization_role = None

        db.commit()

        logger.info(
            f"User {user_to_remove.email} removed from {organization.name} "
            f"by {removed_by.email}"
        )

    def update_member_role(
        self,
        db: Session,
        organization: Organization,
        user_to_update: User,
        new_role: str,
        updated_by: User
    ) -> None:
        """
        Update a member's role in the organization.

        Args:
            db: Database session
            organization: Organization
            user_to_update: User to update
            new_role: New role ("owner", "admin", "member")
            updated_by: User performing the update

        Raises:
            ValueError: If trying to change owner role or without permission

        Example:
            >>> service.update_member_role(db, org, user, "admin", owner_user)
        """
        # Validate role
        if new_role not in ['owner', 'admin', 'member']:
            raise ValueError(f"Invalid role: {new_role}")

        # Can't change owner role via this method
        if user_to_update.id == organization.owner_id and new_role != 'owner':
            raise ValueError("Cannot change owner role. Transfer ownership first.")

        # Only owner can assign owner role
        if new_role == 'owner' and updated_by.organization_role != 'owner':
            raise ValueError("Only owner can assign owner role")

        # Owner or admin can change roles
        if updated_by.organization_role not in ['owner', 'admin']:
            raise ValueError("Only owners and admins can change roles")

        # Update role
        user_to_update.organization_role = new_role

        db.commit()

        logger.info(
            f"User {user_to_update.email} role changed to {new_role} "
            f"in {organization.name} by {updated_by.email}"
        )

    def transfer_ownership(
        self,
        db: Session,
        organization: Organization,
        new_owner: User,
        current_owner: User
    ) -> None:
        """
        Transfer organization ownership to another member.

        Args:
            db: Database session
            organization: Organization
            new_owner: User to become new owner
            current_owner: Current owner (must match org.owner_id)

        Raises:
            ValueError: If not current owner or new owner not in org

        Example:
            >>> service.transfer_ownership(db, org, new_owner_user, current_owner_user)
        """
        # Verify current owner
        if current_owner.id != organization.owner_id:
            raise ValueError("Only current owner can transfer ownership")

        # Verify new owner is in organization
        if new_owner.org_id != organization.id:
            raise ValueError("New owner must be a member of the organization")

        # Transfer ownership
        organization.owner_id = new_owner.id
        new_owner.organization_role = "owner"
        current_owner.organization_role = "admin"  # Demote to admin

        db.commit()

        logger.info(
            f"Ownership of {organization.name} transferred from "
            f"{current_owner.email} to {new_owner.email}"
        )

    def delete_organization(
        self,
        db: Session,
        organization: Organization,
        deleted_by: User
    ) -> None:
        """
        Soft delete an organization.

        Args:
            db: Database session
            organization: Organization to delete
            deleted_by: User performing deletion (must be owner)

        Raises:
            ValueError: If not owner

        Example:
            >>> service.delete_organization(db, org, owner_user)
        """
        # Only owner can delete
        if deleted_by.id != organization.owner_id:
            raise ValueError("Only organization owner can delete the organization")

        # Soft delete
        organization.is_active = False

        db.commit()

        logger.warning(
            f"Organization {organization.name} (id={organization.id}) "
            f"deleted by {deleted_by.email}"
        )


# Singleton instance
_organization_service: Optional[OrganizationService] = None


def get_organization_service() -> OrganizationService:
    """
    Get the singleton organization service instance.

    Returns:
        OrganizationService instance
    """
    global _organization_service
    if _organization_service is None:
        _organization_service = OrganizationService()
    return _organization_service
