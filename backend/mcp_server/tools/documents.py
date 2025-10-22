"""
Document Tools for MCP Server

Tools for searching, retrieving, and managing documents.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from mcp_server.services.db_service import db_service
from mcp_server.services.es_service import es_mcp_service

logger = logging.getLogger(__name__)


async def search_documents(
    query: str,
    folder_path: Optional[str] = None,
    template_name: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search documents using natural language or keywords.

    Supports intelligent query understanding with field aliases,
    date ranges, numeric filters, and folder-based filtering.

    Args:
        query: Natural language search query (e.g., "invoices over $1000 from last week")
        folder_path: Optional folder path to restrict search (e.g., "invoices/acme-corp")
        template_name: Filter by template name
        status: Filter by document status (uploaded, processing, completed, etc.)
        min_confidence: Minimum average confidence score (0.0-1.0)
        limit: Maximum number of results (default: 20, max: 100)

    Returns:
        Search results with documents, total count, and query analysis

    Examples:
        >>> search_documents("contracts signed last month")
        >>> search_documents("invoices over $5000", folder_path="invoices")
        >>> search_documents("high priority", status="completed", min_confidence=0.8)
    """
    try:
        # Use Elasticsearch for semantic search with query optimization
        es_results = await es_mcp_service.search_with_context(
            query=query,
            folder_path=folder_path,
            limit=min(limit, 100),
            offset=0
        )

        # Get additional database context if needed
        if template_name or status or min_confidence:
            # Get template ID if template_name provided
            template_id = None
            if template_name:
                templates = await db_service.get_all_templates()
                matching_template = next(
                    (t for t in templates if t["name"].lower() == template_name.lower()),
                    None
                )
                if matching_template:
                    template_id = matching_template["id"]

            # Search in database with filters
            db_results, total = await db_service.search_documents(
                query=None,  # Already filtered by ES
                template_id=template_id,
                status=status,
                min_confidence=min_confidence,
                limit=limit,
                offset=0
            )

            return {
                "documents": db_results,
                "total": total,
                "query": query,
                "filters_applied": {
                    "folder_path": folder_path,
                    "template_name": template_name,
                    "status": status,
                    "min_confidence": min_confidence
                },
                "query_analysis": es_results.get("query_analysis", {})
            }

        return {
            "documents": es_results["results"],
            "total": es_results["total"],
            "query": query,
            "filters_applied": {
                "folder_path": folder_path
            },
            "query_analysis": es_results.get("query_analysis", {})
        }

    except Exception as e:
        logger.error(f"Error searching documents: {e}", exc_info=True)
        return {
            "error": str(e),
            "documents": [],
            "total": 0
        }


async def get_document_details(document_id: int) -> Dict[str, Any]:
    """
    Get complete details for a specific document.

    Retrieves document metadata, all extracted fields with confidence scores,
    verification status, and template information.

    Args:
        document_id: Document ID

    Returns:
        Complete document details including:
        - Metadata (filename, status, dates)
        - Template information
        - All extracted fields with confidence scores
        - Verification status for each field
        - Processing errors if any

    Examples:
        >>> get_document_details(123)
        {
            "id": 123,
            "filename": "invoice_2024.pdf",
            "status": "completed",
            "template": {"id": 5, "name": "Invoice"},
            "fields": [
                {"name": "total_amount", "value": "1250.00", "confidence": 0.95},
                ...
            ]
        }
    """
    try:
        # Get from database (includes all relationships)
        doc = await db_service.get_document(document_id)

        if not doc:
            return {
                "error": f"Document {document_id} not found",
                "id": document_id
            }

        # Enhance with Elasticsearch data if available
        es_doc = await es_mcp_service.get_document(document_id)
        if es_doc:
            doc["full_text_preview"] = es_doc.get("full_text", "")[:500]  # First 500 chars
            doc["elasticsearch_indexed"] = True
        else:
            doc["elasticsearch_indexed"] = False

        return doc

    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}", exc_info=True)
        return {
            "error": str(e),
            "id": document_id
        }


async def get_document_by_filename(
    filename: str,
    exact_match: bool = False
) -> Dict[str, Any]:
    """
    Find document(s) by filename.

    Supports both exact and partial filename matching.

    Args:
        filename: Filename to search for
        exact_match: If True, requires exact match; if False, uses partial matching

    Returns:
        List of matching documents with basic metadata

    Examples:
        >>> get_document_by_filename("invoice_2024.pdf", exact_match=True)
        >>> get_document_by_filename("contract", exact_match=False)  # Finds all contracts
    """
    try:
        # Search in database
        results, total = await db_service.search_documents(
            query=filename if not exact_match else None,
            limit=50,
            offset=0
        )

        # Filter for exact match if needed
        if exact_match:
            results = [doc for doc in results if doc["filename"] == filename]
            total = len(results)

        return {
            "matches": results,
            "total": total,
            "filename": filename,
            "exact_match": exact_match
        }

    except Exception as e:
        logger.error(f"Error searching by filename: {e}", exc_info=True)
        return {
            "error": str(e),
            "matches": [],
            "total": 0
        }


async def get_recent_documents(
    days: int = 7,
    limit: int = 20,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recently uploaded or processed documents.

    Args:
        days: Number of days to look back (default: 7)
        limit: Maximum number of results
        status: Optional status filter

    Returns:
        List of recent documents with metadata

    Examples:
        >>> get_recent_documents(days=1)  # Today's uploads
        >>> get_recent_documents(days=30, status="completed")
    """
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        results, total = await db_service.search_documents(
            query=None,
            status=status,
            date_from=cutoff_date,
            limit=limit,
            offset=0
        )

        return {
            "documents": results,
            "total": total,
            "period_days": days,
            "status_filter": status
        }

    except Exception as e:
        logger.error(f"Error getting recent documents: {e}", exc_info=True)
        return {
            "error": str(e),
            "documents": [],
            "total": 0
        }
