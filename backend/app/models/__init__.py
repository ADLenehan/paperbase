# Export all models for easy imports
# NOTE: Import permissions BEFORE document to resolve DocumentPermission relationship
from app.models.background_job import BackgroundJob
from app.models.batch import Batch
from app.models.canonical_mapping import CanonicalAlias, CanonicalFieldMapping
from app.models.document import Document, ExtractedField
from app.models.extraction import Extraction
from app.models.permissions import (
    APIKey,
    DocumentPermission,
    FolderPermission,
    Permission,
    Role,
    ShareLink,
    UserRole,
)
from app.models.physical_file import PhysicalFile
from app.models.query_pattern import QueryPattern
from app.models.schema import Schema
from app.models.settings import Organization, Settings, User
from app.models.template import SchemaTemplate
from app.models.verification import Verification, VerificationSession

# PostgreSQL-only models (conditionally import for SQLite compatibility)
try:
    from app.models.search_index import DocumentSearchIndex, TemplateSignature
    HAS_POSTGRES_MODELS = True
except Exception:
    DocumentSearchIndex = None
    TemplateSignature = None
    HAS_POSTGRES_MODELS = False

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
    "BackgroundJob",
    "DocumentSearchIndex",
    "TemplateSignature",
    "CanonicalFieldMapping",
    "CanonicalAlias",
]
