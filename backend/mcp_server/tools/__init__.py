"""
MCP Tools for Paperbase

Exposes document search, template management, analytics,
and audit functionality through MCP tool protocol.
"""

from .documents import (
    search_documents,
    get_document_details,
    get_document_by_filename
)
from .templates import (
    list_templates,
    get_template_details,
    get_template_stats
)
from .analytics import (
    get_extraction_stats,
    get_confidence_distribution,
    get_processing_timeline
)
from .audit import (
    get_audit_queue,
    get_low_confidence_fields
)

__all__ = [
    "search_documents",
    "get_document_details",
    "get_document_by_filename",
    "list_templates",
    "get_template_details",
    "get_template_stats",
    "get_extraction_stats",
    "get_confidence_distribution",
    "get_processing_timeline",
    "get_audit_queue",
    "get_low_confidence_fields"
]
