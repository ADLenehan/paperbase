"""
Audit Helper Utilities

Provides helper functions for retrieving low-confidence fields and generating
audit URLs for use in AI answer citations and MCP responses.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.document import Document, ExtractedField
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


async def get_low_confidence_fields_for_documents(
    document_ids: List[int],
    db: Session,
    confidence_threshold: Optional[float] = None,
    include_verified: bool = False,
    field_names: Optional[List[str]] = None
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Get low-confidence fields for a list of documents, grouped by document_id.

    This is the primary helper for enriching AI answers and MCP responses with
    audit metadata. Returns fields that need human review based on confidence
    score threshold.

    Args:
        document_ids: List of document IDs to get fields for
        db: Database session
        confidence_threshold: Override threshold (uses settings default if None)
        include_verified: If True, include already-verified fields (default: False)
        field_names: Optional list of field names to filter by (only return these fields)

    Returns:
        Dictionary mapping document_id to list of low-confidence field metadata:
        {
            123: [
                {
                    "field_id": 456,
                    "document_id": 123,
                    "filename": "invoice.pdf",
                    "field_name": "invoice_total",
                    "field_value": "$2,100.00",
                    "confidence": 0.58,
                    "verified": False,
                    "source_page": 1,
                    "source_bbox": [100, 200, 50, 20],
                    "audit_url": "/audit?field_id=456&document_id=123&highlight=true&source=ai_answer"
                },
                ...
            ],
            ...
        }

    Example:
        >>> fields = await get_low_confidence_fields_for_documents([123, 456], db)
        >>> if 123 in fields:
        >>>     print(f"Document 123 has {len(fields[123])} fields needing review")
    """

    if not document_ids:
        return {}

    # Get confidence threshold from settings if not provided
    if confidence_threshold is None:
        settings_service = SettingsService(db)
        org = settings_service.get_or_create_default_org()
        user = settings_service.get_or_create_default_user(org.id)
        confidence_threshold = settings_service.get_setting(
            key="review_threshold",
            user_id=user.id,
            org_id=org.id,
            default=0.6
        )

    # Build query for low-confidence fields
    query = db.query(ExtractedField).join(Document).filter(
        and_(
            ExtractedField.document_id.in_(document_ids),
            ExtractedField.confidence_score < confidence_threshold
        )
    )

    # Filter out verified fields unless explicitly requested
    if not include_verified:
        query = query.filter(ExtractedField.verified == False)

    # Filter by specific field names if provided (OPTIMIZATION: filter in SQL, not Python)
    if field_names:
        query = query.filter(ExtractedField.field_name.in_(field_names))
        logger.info(f"Filtering audit fields to {len(field_names)} query-relevant fields: {field_names}")

    # Execute query
    low_confidence_fields = query.all()

    logger.info(
        f"Found {len(low_confidence_fields)} low-confidence fields "
        f"across {len(document_ids)} documents (threshold: {confidence_threshold})"
    )

    # Group by document_id
    grouped_fields: Dict[int, List[Dict[str, Any]]] = {}

    for field in low_confidence_fields:
        doc_id = field.document_id

        if doc_id not in grouped_fields:
            grouped_fields[doc_id] = []

        # Build audit URL
        audit_url = (
            f"/audit?"
            f"field_id={field.id}&"
            f"document_id={doc_id}&"
            f"highlight=true&"
            f"source=ai_answer"
        )

        # Create field metadata
        field_data = {
            "field_id": field.id,
            "document_id": doc_id,
            "filename": field.document.filename,
            "file_path": field.document.actual_file_path,  # For PDF viewer
            "field_name": field.field_name,
            "field_value": field.field_value,
            "field_value_json": field.field_value_json,  # For complex types (arrays, tables)
            "field_type": field.field_type,  # Field type (text, date, array, table, etc.)
            "confidence": round(field.confidence_score, 3) if field.confidence_score else 0.0,
            "verified": field.verified,
            "verified_at": field.verified_at.isoformat() if field.verified_at else None,
            "source_page": field.source_page,
            "source_bbox": field.source_bbox,
            "audit_url": audit_url
        }

        grouped_fields[doc_id].append(field_data)

    return grouped_fields


async def get_confidence_summary(
    document_ids: List[int],
    db: Session,
    high_threshold: float = 0.8,
    medium_threshold: float = 0.6
) -> Dict[str, Any]:
    """
    Get confidence score summary statistics for a list of documents.

    Useful for displaying overall data quality in AI answer responses.

    Args:
        document_ids: List of document IDs
        db: Database session
        high_threshold: Threshold for high confidence (default: 0.8)
        medium_threshold: Threshold for medium confidence (default: 0.6)

    Returns:
        Dictionary with confidence distribution:
        {
            "high_confidence_count": 5,
            "medium_confidence_count": 2,
            "low_confidence_count": 1,
            "total_fields": 8,
            "avg_confidence": 0.75,
            "audit_recommended": True  # If any low-confidence fields exist
        }
    """

    if not document_ids:
        return {
            "high_confidence_count": 0,
            "medium_confidence_count": 0,
            "low_confidence_count": 0,
            "total_fields": 0,
            "avg_confidence": 0.0,
            "audit_recommended": False
        }

    # Get all fields for these documents
    fields = db.query(ExtractedField).filter(
        ExtractedField.document_id.in_(document_ids)
    ).all()

    if not fields:
        return {
            "high_confidence_count": 0,
            "medium_confidence_count": 0,
            "low_confidence_count": 0,
            "total_fields": 0,
            "avg_confidence": 0.0,
            "audit_recommended": False
        }

    # Calculate statistics
    high_count = sum(1 for f in fields if f.confidence_score >= high_threshold)
    medium_count = sum(
        1 for f in fields
        if medium_threshold <= f.confidence_score < high_threshold
    )
    low_count = sum(1 for f in fields if f.confidence_score < medium_threshold)

    total = len(fields)
    avg_confidence = sum(f.confidence_score or 0.0 for f in fields) / total if total > 0 else 0.0

    return {
        "high_confidence_count": high_count,
        "medium_confidence_count": medium_count,
        "low_confidence_count": low_count,
        "total_fields": total,
        "avg_confidence": round(avg_confidence, 3),
        "audit_recommended": low_count > 0
    }


def build_audit_url(
    field_id: int,
    document_id: int,
    source: str = "ai_answer",
    highlight: bool = True,
    query_id: Optional[str] = None
) -> str:
    """
    Build a properly formatted audit URL for a specific field.

    Args:
        field_id: ExtractedField ID
        document_id: Document ID for context
        source: Source of audit link (ai_answer, mcp_rag, search_result)
        highlight: Whether to auto-highlight bbox in PDF viewer
        query_id: Optional query ID for analytics tracking

    Returns:
        Formatted audit URL string

    Example:
        >>> url = build_audit_url(123, 45, source="mcp_rag")
        >>> print(url)
        "/audit?field_id=123&document_id=45&highlight=true&source=mcp_rag"
    """

    params = [
        f"field_id={field_id}",
        f"document_id={document_id}",
    ]

    if highlight:
        params.append("highlight=true")

    if source:
        params.append(f"source={source}")

    if query_id:
        params.append(f"query_id={query_id}")

    return f"/audit?{'&'.join(params)}"


async def prepare_citation_metadata(
    document_id: int,
    extracted_fields: Dict[str, Any],
    confidence_scores: Dict[str, float],
    db: Session,
    confidence_threshold: Optional[float] = None,
    query_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prepare citation metadata for Elasticsearch indexing.

    This enriches documents with audit URLs and confidence flags for
    trustworthy AI answer generation. Used during document indexing to
    pre-compute citation data that will be returned with search results.

    Args:
        document_id: Document ID
        extracted_fields: Field values being indexed
        confidence_scores: Confidence scores for each field
        db: Database session
        confidence_threshold: Threshold for low-confidence detection (default: 0.6)
        query_id: Optional query ID for tracking

    Returns:
        Dictionary with citation metadata ready for ES indexing:
        {
            "has_low_confidence_fields": True,
            "low_confidence_field_names": ["invoice_total", "vendor_name"],
            "audit_urls": {
                "invoice_total": "/audit?field_id=123&document_id=45...",
                "vendor_name": "/audit?field_id=124&document_id=45..."
            }
        }

    Example:
        >>> metadata = await prepare_citation_metadata(
        ...     document_id=45,
        ...     extracted_fields={"invoice_total": "$2,100"},
        ...     confidence_scores={"invoice_total": 0.58},
        ...     db=db
        ... )
        >>> print(metadata["has_low_confidence_fields"])  # True
    """

    # Get threshold from settings if not provided
    if confidence_threshold is None:
        settings_service = SettingsService(db)
        org = settings_service.get_or_create_default_org()
        user = settings_service.get_or_create_default_user(org.id)
        confidence_threshold = settings_service.get_setting(
            key="review_threshold",
            user_id=user.id,
            org_id=org.id,
            default=0.6
        )

    # Identify low-confidence fields
    low_confidence_fields = [
        field_name for field_name, conf in confidence_scores.items()
        if conf < confidence_threshold
    ]

    # Get field IDs from database to build audit URLs
    audit_urls = {}
    if low_confidence_fields:
        # Query extracted fields for this document
        fields = db.query(ExtractedField).filter(
            and_(
                ExtractedField.document_id == document_id,
                ExtractedField.field_name.in_(low_confidence_fields)
            )
        ).all()

        # Build audit URL for each low-confidence field
        for field in fields:
            audit_urls[field.field_name] = build_audit_url(
                field_id=field.id,
                document_id=document_id,
                source="search_result",
                highlight=True,
                query_id=query_id
            )

    return {
        "has_low_confidence_fields": len(low_confidence_fields) > 0,
        "low_confidence_field_names": low_confidence_fields,
        "audit_urls": audit_urls
    }
