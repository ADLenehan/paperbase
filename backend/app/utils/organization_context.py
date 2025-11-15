"""
Organization Context Utilities for Multi-Tenancy

CRITICAL: All queries for Document, Schema, PhysicalFile MUST filter by organization_id
to prevent cross-organization data leaks.

This module provides utilities to enforce organization-scoped queries.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.physical_file import PhysicalFile
from app.models.schema import Schema
from app.models.settings import Organization, User


class OrganizationContext:
    """
    Organization context for enforcing multi-tenancy.

    Usage:
        @router.get("/documents")
        def get_documents(org_ctx: OrganizationContext = Depends()):
            # Automatically filtered by organization
            documents = org_ctx.query(Document).all()
    """

    def __init__(
        self,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        self.user = current_user
        self.db = db
        self.organization_id = current_user.org_id

        if not self.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization"
            )

    @property
    def organization(self) -> Optional[Organization]:
        """Get the current organization"""
        if not hasattr(self, '_organization'):
            self._organization = self.db.query(Organization).filter(
                Organization.id == self.organization_id
            ).first()
        return self._organization

    def query(self, model) -> Query:
        """
        Create an organization-scoped query.

        Automatically filters by organization_id for multi-tenant models.

        Args:
            model: SQLAlchemy model class

        Returns:
            Query filtered by organization_id

        Example:
            >>> documents = org_ctx.query(Document).filter(Document.status == "completed").all()
        """
        query = self.db.query(model)

        # Apply organization filter for multi-tenant models
        if model in [Document, Schema, PhysicalFile]:
            query = query.filter(model.organization_id == self.organization_id)

        return query

    def get_document(self, document_id: int) -> Optional[Document]:
        """
        Get a document by ID (organization-scoped).

        Args:
            document_id: Document ID

        Returns:
            Document if found and belongs to user's organization, None otherwise
        """
        return self.query(Document).filter(Document.id == document_id).first()

    def get_schema(self, schema_id: int) -> Optional[Schema]:
        """
        Get a schema/template by ID (organization-scoped).

        Args:
            schema_id: Schema ID

        Returns:
            Schema if found and belongs to user's organization, None otherwise
        """
        return self.query(Schema).filter(Schema.id == schema_id).first()

    def get_physical_file(self, file_id: int) -> Optional[PhysicalFile]:
        """
        Get a physical file by ID (organization-scoped).

        Args:
            file_id: File ID

        Returns:
            PhysicalFile if found and belongs to user's organization, None otherwise
        """
        return self.query(PhysicalFile).filter(PhysicalFile.id == file_id).first()

    def check_document_access(self, document_id: int) -> Document:
        """
        Check if user has access to a document, raise 404 if not.

        Args:
            document_id: Document ID

        Returns:
            Document object

        Raises:
            HTTPException: 404 if document not found or not in user's organization
        """
        document = self.get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        return document

    def check_schema_access(self, schema_id: int) -> Schema:
        """
        Check if user has access to a schema, raise 404 if not.

        Args:
            schema_id: Schema ID

        Returns:
            Schema object

        Raises:
            HTTPException: 404 if schema not found or not in user's organization
        """
        schema = self.get_schema(schema_id)
        if not schema:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema/template not found"
            )
        return schema


def get_organization_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> OrganizationContext:
    """
    FastAPI dependency to get organization context.

    Returns:
        OrganizationContext instance

    Example:
        @router.get("/documents")
        def get_documents(org_ctx: OrganizationContext = Depends(get_organization_context)):
            return org_ctx.query(Document).all()
    """
    return OrganizationContext(current_user, db)


# Convenience helper functions

def ensure_org_id(obj, organization_id: int):
    """
    Ensure an object has organization_id set.

    Use when creating new objects to ensure they belong to the user's organization.

    Args:
        obj: SQLAlchemy model instance
        organization_id: Organization ID to set

    Example:
        >>> doc = Document(filename="test.pdf")
        >>> ensure_org_id(doc, org_ctx.organization_id)
    """
    if hasattr(obj, 'organization_id'):
        obj.organization_id = organization_id


def validate_org_access(obj, organization_id: int):
    """
    Validate that an object belongs to the given organization.

    Args:
        obj: SQLAlchemy model instance
        organization_id: Expected organization ID

    Raises:
        HTTPException: 403 if object belongs to different organization

    Example:
        >>> validate_org_access(document, org_ctx.organization_id)
    """
    if hasattr(obj, 'organization_id') and obj.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Resource belongs to different organization"
        )
