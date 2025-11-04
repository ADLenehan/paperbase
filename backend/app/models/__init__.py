# Export all models for easy imports
# NOTE: Import permissions BEFORE document to resolve DocumentPermission relationship
from app.models.permissions import (
    Role, Permission, UserRole, DocumentPermission,
    FolderPermission, ShareLink, APIKey
)
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.template import SchemaTemplate
from app.models.verification import Verification, VerificationSession
from app.models.physical_file import PhysicalFile
from app.models.extraction import Extraction
from app.models.batch import Batch
from app.models.query_pattern import QueryPattern
from app.models.settings import Settings, Organization, User

__all__ = [
    # Permissions (must be first to resolve relationships)
    "Role",
    "Permission",
    "UserRole",
    "DocumentPermission",
    "FolderPermission",
    "ShareLink",
    "APIKey",
    # Core models
    "Document",
    "ExtractedField",
    "Schema",
    "SchemaTemplate",
    "Verification",
    "VerificationSession",
    "PhysicalFile",
    "Extraction",
    "Batch",
    "QueryPattern",
    "Settings",
    "Organization",
    "User",
]
