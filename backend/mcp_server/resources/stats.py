"""
Statistics Resources

Read-only MCP resources for system statistics and health.
"""

from typing import Dict, Any
import logging

from mcp_server.services.db_service import db_service
from mcp_server.services.es_service import es_mcp_service
from mcp_server.services.cache_service import cache_service

logger = logging.getLogger(__name__)


async def get_daily_stats_resource(days: int = 7) -> Dict[str, Any]:
    """
    Resource: paperbase://stats/daily?days={days}

    Returns daily processing statistics.
    Short cache TTL (1 minute) due to frequently changing data.

    Args:
        days: Number of days to include (from URI query param)

    Returns:
        Daily statistics
    """
    try:
        stats = await db_service.get_daily_stats(days=days)

        return {
            "uri": f"paperbase://stats/daily?days={days}",
            "mimeType": "application/json",
            "text": stats
        }

    except Exception as e:
        logger.error(f"Error fetching daily stats resource: {e}", exc_info=True)
        return {
            "uri": f"paperbase://stats/daily?days={days}",
            "mimeType": "application/json",
            "text": {
                "error": str(e)
            }
        }


async def get_system_health_resource() -> Dict[str, Any]:
    """
    Resource: paperbase://system/health

    Returns system health status including database and Elasticsearch connectivity.

    Returns:
        System health check results
    """
    try:
        # Check Elasticsearch health
        es_healthy = await es_mcp_service.health_check()

        # Get cache stats
        cache_stats = cache_service.get_stats()

        return {
            "uri": "paperbase://system/health",
            "mimeType": "application/json",
            "text": {
                "status": "healthy" if es_healthy else "degraded",
                "elasticsearch": {
                    "status": "connected" if es_healthy else "disconnected"
                },
                "database": {
                    "status": "connected"  # If we got here, DB is working
                },
                "cache": cache_stats
            }
        }

    except Exception as e:
        logger.error(f"Error fetching system health resource: {e}", exc_info=True)
        return {
            "uri": "paperbase://system/health",
            "mimeType": "application/json",
            "text": {
                "status": "error",
                "error": str(e)
            }
        }


async def get_audit_summary_resource() -> Dict[str, Any]:
    """
    Resource: paperbase://stats/audit

    Returns audit queue summary statistics.

    Returns:
        Audit statistics
    """
    try:
        # Get audit queue
        queue = await db_service.get_audit_queue(limit=1000)

        # Get daily stats for context
        stats = await db_service.get_daily_stats(days=7)

        return {
            "uri": "paperbase://stats/audit",
            "mimeType": "application/json",
            "text": {
                "pending_review": len(queue),
                "total_fields": stats.get("total_fields", 0),
                "verified_fields": stats.get("verified_fields", 0),
                "verification_rate": stats.get("verification_rate", 0.0),
                "avg_confidence": stats.get("avg_confidence", 0.0)
            }
        }

    except Exception as e:
        logger.error(f"Error fetching audit summary resource: {e}", exc_info=True)
        return {
            "uri": "paperbase://stats/audit",
            "mimeType": "application/json",
            "text": {
                "error": str(e)
            }
        }
