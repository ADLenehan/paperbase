"""
MCP Resources for Paperbase

Provides read-only access to templates, statistics, and document data
through MCP resource URIs.
"""

from .templates import (
    get_all_templates_resource,
    get_template_resource
)
from .stats import (
    get_daily_stats_resource,
    get_system_health_resource
)
from .documents import (
    get_document_fields_resource
)

__all__ = [
    "get_all_templates_resource",
    "get_template_resource",
    "get_daily_stats_resource",
    "get_system_health_resource",
    "get_document_fields_resource"
]
