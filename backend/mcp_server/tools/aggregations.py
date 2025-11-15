"""
Aggregation Tools for MCP Server

Provides analytics and calculations across documents using Elasticsearch aggregations.
Wraps the comprehensive /api/aggregations/* endpoints.
"""

from typing import Optional, Dict, Any, List
import httpx
import logging

logger = logging.getLogger(__name__)

# Backend API URL
API_BASE_URL = "http://localhost:8000"


async def aggregate_field(
    field: str,
    aggregation_type: str = "stats",
    filters: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate statistics or group data across documents.

    This is the PRIMARY analytics tool - use it for any math/calculations.

    Args:
        field: Field to aggregate (e.g., "invoice_total", "vendor.keyword")
        aggregation_type: Type of aggregation:
            - "stats": Calculate sum, avg, min, max, count (for numbers)
            - "terms": Group by field values, get top N (for categories)
            - "date_histogram": Group by time periods (for dates)
            - "cardinality": Count unique values
            - "range": Group into value ranges
            - "percentiles": Calculate percentiles (p50, p95, p99)
        filters: Optional filters to apply before aggregating
            Example: {"status": "completed", "vendor": "Acme Corp"}
        config: Additional configuration for the aggregation
            - For terms: {"size": 10} - top 10 values
            - For date_histogram: {"interval": "month", "format": "yyyy-MM"}
            - For range: {"ranges": [{"to": 100}, {"from": 100, "to": 1000}, {"from": 1000}]}

    Returns:
        Aggregation results in structured format

    Examples:
        # Calculate invoice statistics
        >>> await aggregate_field("invoice_total", "stats")
        {
            "sum": 15234.50,
            "avg": 1523.45,
            "min": 500.00,
            "max": 5000.00,
            "count": 10
        }

        # Top 10 vendors by document count
        >>> await aggregate_field("vendor.keyword", "terms", config={"size": 10})
        {
            "buckets": [
                {"key": "Acme Corp", "doc_count": 25},
                {"key": "Beta Inc", "doc_count": 18},
                ...
            ]
        }

        # Invoices per month
        >>> await aggregate_field(
        ...     "invoice_date",
        ...     "date_histogram",
        ...     config={"interval": "month", "format": "yyyy-MM"}
        ... )
        {
            "buckets": [
                {"key_as_string": "2024-01", "doc_count": 45},
                {"key_as_string": "2024-02", "doc_count": 52},
                ...
            ]
        }

        # Filter before aggregating
        >>> await aggregate_field(
        ...     "invoice_total",
        ...     "stats",
        ...     filters={"vendor": "Acme Corp", "status": "completed"}
        ... )
        {
            "sum": 5234.50,
            "avg": 523.45,
            ...
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/aggregations/single",
                json={
                    "field": field,
                    "agg_type": aggregation_type,
                    "agg_config": config,
                    "filters": filters
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                return {
                    "error": f"Aggregation failed: {error_detail}",
                    "success": False
                }

            data = response.json()
            return {
                "success": True,
                "aggregation_type": aggregation_type,
                "field": field,
                "results": data.get("results", {}),
                "summary": _format_agg_summary(aggregation_type, data.get("results", {}))
            }

    except httpx.TimeoutException:
        return {
            "error": "Aggregation timed out after 30 seconds",
            "success": False
        }
    except httpx.ConnectError:
        return {
            "error": "Could not connect to backend API",
            "success": False
        }
    except Exception as e:
        logger.error(f"Error in aggregate_field: {e}", exc_info=True)
        return {
            "error": str(e),
            "success": False
        }


async def multi_aggregate(
    aggregations: List[Dict[str, Any]],
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute multiple aggregations in a single query.

    Use this when you need multiple calculations at once (more efficient than
    calling aggregate_field multiple times).

    Args:
        aggregations: List of aggregation definitions, each containing:
            - name: Unique name for this aggregation
            - field: Field to aggregate
            - type: Aggregation type (stats, terms, etc.)
            - config: Optional configuration (size, interval, etc.)
        filters: Optional filters to apply to ALL aggregations

    Returns:
        Dictionary with results for each named aggregation

    Examples:
        # Get multiple stats at once
        >>> await multi_aggregate([
        ...     {"name": "total_spend", "field": "invoice_total", "type": "stats"},
        ...     {"name": "by_vendor", "field": "vendor.keyword", "type": "terms", "config": {"size": 5}},
        ...     {"name": "unique_vendors", "field": "vendor.keyword", "type": "cardinality"}
        ... ])
        {
            "total_spend": {"sum": 15234.50, "avg": 1523.45, ...},
            "by_vendor": {"buckets": [{"key": "Acme", "doc_count": 25}, ...]},
            "unique_vendors": {"value": 8}
        }

        # Filtered multi-aggregation
        >>> await multi_aggregate(
        ...     aggregations=[
        ...         {"name": "completed_total", "field": "invoice_total", "type": "stats"},
        ...         {"name": "monthly_trend", "field": "invoice_date", "type": "date_histogram",
        ...          "config": {"interval": "month"}}
        ...     ],
        ...     filters={"status": "completed"}
        ... )
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/aggregations/multi",
                json={
                    "aggregations": aggregations,
                    "filters": filters
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                return {
                    "error": f"Multi-aggregation failed: {error_detail}",
                    "success": False
                }

            data = response.json()
            results = data.get("results", {})

            return {
                "success": True,
                "aggregation_count": len(aggregations),
                "results": results,
                "summary": _format_multi_agg_summary(aggregations, results)
            }

    except httpx.TimeoutException:
        return {
            "error": "Multi-aggregation timed out after 30 seconds",
            "success": False
        }
    except httpx.ConnectError:
        return {
            "error": "Could not connect to backend API",
            "success": False
        }
    except Exception as e:
        logger.error(f"Error in multi_aggregate: {e}", exc_info=True)
        return {
            "error": str(e),
            "success": False
        }


async def get_dashboard_stats() -> Dict[str, Any]:
    """
    Get pre-configured dashboard statistics.

    Returns comprehensive analytics including:
    - Document status breakdown
    - Template usage statistics
    - Monthly upload trends
    - Total document count

    This is useful for getting a quick overview of the system.

    Returns:
        Dashboard statistics with multiple aggregations

    Example:
        >>> await get_dashboard_stats()
        {
            "status_breakdown": {"buckets": [...]},
            "template_usage": {"buckets": [...]},
            "monthly_uploads": {"buckets": [...]},
            "total_documents": {"value": 1523}
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/aggregations/dashboard"
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                return {
                    "error": f"Dashboard stats failed: {error_detail}",
                    "success": False
                }

            data = response.json()
            results = data.get("results", {})

            return {
                "success": True,
                "dashboard": "overview",
                "results": results,
                "summary": _format_dashboard_summary(results)
            }

    except httpx.TimeoutException:
        return {
            "error": "Dashboard stats timed out",
            "success": False
        }
    except httpx.ConnectError:
        return {
            "error": "Could not connect to backend API",
            "success": False
        }
    except Exception as e:
        logger.error(f"Error in get_dashboard_stats: {e}", exc_info=True)
        return {
            "error": str(e),
            "success": False
        }


async def get_field_insights(field: str) -> Dict[str, Any]:
    """
    Get comprehensive insights for a specific field.

    Auto-detects field type and returns appropriate aggregations:
    - Text/Keyword fields: Top values, cardinality
    - Numeric fields: Stats, percentiles, histogram
    - Date fields: Date histogram, date range

    Args:
        field: Field name to analyze

    Returns:
        Field insights with auto-detected aggregations

    Example:
        >>> await get_field_insights("invoice_total")
        {
            "statistics": {"sum": 15234.50, "avg": 1523.45, ...},
            "unique_count": {"value": 10}
        }

        >>> await get_field_insights("vendor.keyword")
        {
            "top_values": {"buckets": [{"key": "Acme", "doc_count": 25}, ...]},
            "unique_count": {"value": 8}
        }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/aggregations/insights/{field}"
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                return {
                    "error": f"Field insights failed: {error_detail}",
                    "success": False
                }

            data = response.json()
            insights = data.get("insights", {})

            return {
                "success": True,
                "field": field,
                "insights": insights,
                "summary": _format_insights_summary(field, insights)
            }

    except httpx.TimeoutException:
        return {
            "error": "Field insights timed out",
            "success": False
        }
    except httpx.ConnectError:
        return {
            "error": "Could not connect to backend API",
            "success": False
        }
    except Exception as e:
        logger.error(f"Error in get_field_insights: {e}", exc_info=True)
        return {
            "error": str(e),
            "success": False
        }


# Helper functions for formatting summaries

def _format_agg_summary(agg_type: str, results: Dict[str, Any]) -> str:
    """Format aggregation results into human-readable summary."""
    if agg_type == "stats":
        return (
            f"Sum: ${results.get('sum', 0):,.2f}, "
            f"Average: ${results.get('avg', 0):,.2f}, "
            f"Count: {results.get('count', 0):,}"
        )
    elif agg_type == "terms":
        buckets = results.get("buckets", [])
        if buckets:
            top_3 = buckets[:3]
            summary = ", ".join([f"{b['key']} ({b['doc_count']})" for b in top_3])
            return f"Top values: {summary}"
        return "No values found"
    elif agg_type == "cardinality":
        return f"Unique values: {results.get('value', 0):,}"
    elif agg_type == "date_histogram":
        buckets = results.get("buckets", [])
        return f"Time periods: {len(buckets)} buckets"
    else:
        return f"Results available for {agg_type}"


def _format_multi_agg_summary(aggregations: List[Dict], results: Dict) -> str:
    """Format multi-aggregation results."""
    summaries = []
    for agg in aggregations:
        name = agg["name"]
        agg_type = agg["type"]
        if name in results:
            summary = _format_agg_summary(agg_type, results[name])
            summaries.append(f"{name}: {summary}")
    return " | ".join(summaries)


def _format_dashboard_summary(results: Dict) -> str:
    """Format dashboard results."""
    total = results.get("total_documents", {}).get("value", 0)
    status_buckets = results.get("status_breakdown", {}).get("buckets", [])
    status_summary = ", ".join([f"{b['key']}: {b['doc_count']}" for b in status_buckets[:3]])

    return f"Total: {total:,} documents | Status: {status_summary}"


def _format_insights_summary(field: str, insights: Dict) -> str:
    """Format field insights summary."""
    parts = []

    if "statistics" in insights:
        stats = insights["statistics"]
        parts.append(f"Stats: avg ${stats.get('avg', 0):,.2f}")

    if "top_values" in insights:
        buckets = insights["top_values"].get("buckets", [])
        if buckets:
            parts.append(f"Top: {buckets[0]['key']}")

    if "unique_count" in insights:
        parts.append(f"Unique: {insights['unique_count'].get('value', 0):,}")

    return " | ".join(parts) if parts else f"Insights for {field}"
