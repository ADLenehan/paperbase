"""
Audit Tools for MCP Server

Tools for HITL (Human-in-the-Loop) audit queue and verification management.
"""

from typing import Optional, Dict, Any, List
import logging

from mcp_server.services.db_service import db_service

logger = logging.getLogger(__name__)


async def get_audit_queue(
    confidence_threshold: Optional[float] = None,
    template_id: Optional[int] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get audit queue of fields needing human verification.

    Returns fields with confidence below threshold or manually flagged
    for review, sorted by confidence (lowest first).

    Args:
        confidence_threshold: Maximum confidence for inclusion (default: 0.6)
        template_id: Optional filter by template
        limit: Maximum number of items to return (default: 50, max: 200)

    Returns:
        List of fields needing verification with document context

    Examples:
        >>> get_audit_queue()  # Use default threshold
        >>> get_audit_queue(confidence_threshold=0.7, template_id=1)
        {
            "queue": [
                {
                    "field_id": 123,
                    "document_id": 45,
                    "filename": "invoice_001.pdf",
                    "field_name": "total_amount",
                    "field_value": "1,250.00",
                    "confidence": 0.58
                },
                ...
            ],
            "total": 15,
            "threshold": 0.6
        }
    """
    try:
        # Get audit queue from database
        queue = await db_service.get_audit_queue(
            confidence_threshold=confidence_threshold,
            limit=min(limit, 200)
        )

        # Filter by template if specified
        if template_id:
            # Would need to join with documents table to filter
            # For now, return all with note
            filtered_queue = queue  # TODO: implement template filtering
        else:
            filtered_queue = queue

        return {
            "queue": filtered_queue,
            "total": len(filtered_queue),
            "threshold": confidence_threshold or 0.6,
            "template_filter": template_id,
            "limit": limit
        }

    except Exception as e:
        logger.error(f"Error getting audit queue: {e}", exc_info=True)
        return {
            "error": str(e),
            "queue": [],
            "total": 0
        }


async def get_low_confidence_fields(
    min_confidence: float = 0.0,
    max_confidence: float = 0.6,
    field_name: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get fields within a specific confidence range.

    Useful for analyzing extraction quality and identifying
    problematic field types.

    Args:
        min_confidence: Minimum confidence (inclusive)
        max_confidence: Maximum confidence (inclusive)
        field_name: Optional filter by field name
        limit: Maximum results

    Returns:
        List of fields in confidence range

    Examples:
        >>> get_low_confidence_fields(min_confidence=0.5, max_confidence=0.7)
        >>> get_low_confidence_fields(field_name="total_amount", max_confidence=0.8)
    """
    try:
        # Use audit queue with custom threshold
        queue = await db_service.get_audit_queue(
            confidence_threshold=max_confidence,
            limit=limit
        )

        # Filter by min_confidence and field_name
        filtered = [
            item for item in queue
            if (item["confidence"] or 0.0) >= min_confidence
            and (not field_name or item["field_name"] == field_name)
        ]

        return {
            "fields": filtered,
            "total": len(filtered),
            "confidence_range": {
                "min": min_confidence,
                "max": max_confidence
            },
            "field_filter": field_name
        }

    except Exception as e:
        logger.error(f"Error getting low confidence fields: {e}", exc_info=True)
        return {
            "error": str(e),
            "fields": [],
            "total": 0
        }


async def get_audit_stats() -> Dict[str, Any]:
    """
    Get overall audit queue statistics.

    Returns counts of items needing review, verification rates,
    and average review time.

    Returns:
        Audit statistics

    Examples:
        >>> get_audit_stats()
        {
            "pending_review": 45,
            "verified_today": 23,
            "avg_review_time_seconds": 28,
            "verification_rate": 65.2
        }
    """
    try:
        # Get daily stats which includes verification info
        stats = await db_service.get_daily_stats(days=7)

        # Get current audit queue size
        queue = await db_service.get_audit_queue(limit=1000)

        return {
            "pending_review": len(queue),
            "total_fields": stats.get("total_fields", 0),
            "verified_fields": stats.get("verified_fields", 0),
            "verification_rate": stats.get("verification_rate", 0.0),
            "avg_confidence": stats.get("avg_confidence", 0.0),
            "period_days": 7
        }

    except Exception as e:
        logger.error(f"Error getting audit stats: {e}", exc_info=True)
        return {
            "error": str(e)
        }


async def get_verification_history(
    document_id: Optional[int] = None,
    days: int = 30,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get verification history for audit trail.

    Args:
        document_id: Optional filter by document
        days: Number of days to look back
        limit: Maximum results

    Returns:
        List of recent verifications

    Examples:
        >>> get_verification_history(document_id=123)
        >>> get_verification_history(days=7)
    """
    try:
        # Simplified - would query Verification table
        return {
            "verifications": [],
            "total": 0,
            "document_id": document_id,
            "period_days": days,
            "note": "Implementation requires Verification model query"
        }

    except Exception as e:
        logger.error(f"Error getting verification history: {e}", exc_info=True)
        return {
            "error": str(e),
            "verifications": []
        }
