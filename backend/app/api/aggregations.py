"""
Aggregation API Endpoints

Provides comprehensive aggregation capabilities for analytics and insights.
Supports various aggregation types, multi-dimensional analysis, and nested aggregations.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.postgres_service import PostgresService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/aggregations", tags=["aggregations"])


class AggregationRequest(BaseModel):
    """Single aggregation request"""
    field: Optional[str] = None
    agg_type: str = Field(default="terms", description="Aggregation type: terms, stats, date_histogram, range, cardinality, histogram, percentiles, extended_stats")
    agg_config: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    custom_aggs: Optional[Dict[str, Any]] = None


class MultiAggregationRequest(BaseModel):
    """Multiple aggregations in one query"""
    aggregations: List[Dict[str, Any]] = Field(
        ...,
        description="List of aggregation definitions with name, field, type, and optional config"
    )
    filters: Optional[Dict[str, Any]] = None


class NestedAggregationRequest(BaseModel):
    """Nested (hierarchical) aggregation request"""
    parent_agg: Dict[str, Any] = Field(
        ...,
        description="Parent aggregation with name, field, type, and optional config"
    )
    sub_aggs: List[Dict[str, Any]] = Field(
        ...,
        description="Sub-aggregations to nest under parent"
    )
    filters: Optional[Dict[str, Any]] = None


@router.post("/single")
async def get_single_aggregation(request: AggregationRequest):
    """
    Execute a single aggregation query.

    Examples:
    - Terms aggregation: `{"field": "status", "agg_type": "terms"}`
    - Stats aggregation: `{"field": "total_amount", "agg_type": "stats"}`
    - Date histogram: `{"field": "uploaded_at", "agg_type": "date_histogram", "agg_config": {"interval": "month"}}`
    - Range aggregation: `{"field": "total_amount", "agg_type": "range", "agg_config": {"ranges": [{"to": 100}, {"from": 100, "to": 1000}, {"from": 1000}]}}`
    """

    postgres_service = PostgresService(db)

    try:
        result = await postgres_service.get_aggregations(
            field=request.field,
            agg_type=request.agg_type,
            agg_config=request.agg_config,
            filters=request.filters,
            custom_aggs=request.custom_aggs
        )

        return {
            "success": True,
            "aggregation_type": request.agg_type,
            "field": request.field,
            "results": result
        }

    except Exception as e:
        logger.error(f"Aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi")
async def get_multi_aggregations(request: MultiAggregationRequest):
    """
    Execute multiple aggregations in a single query for efficiency.

    Example:
    ```json
    {
        "aggregations": [
            {"name": "status_breakdown", "field": "status", "type": "terms"},
            {"name": "amount_stats", "field": "total_amount", "type": "stats"},
            {"name": "monthly_uploads", "field": "uploaded_at", "type": "date_histogram", "config": {"interval": "month"}}
        ],
        "filters": {"status": "completed"}
    }
    ```

    Returns comprehensive analytics in a single API call.
    """

    postgres_service = PostgresService(db)

    try:
        result = await postgres_service.get_multi_aggregations(
            aggregations=request.aggregations,
            filters=request.filters
        )

        return {
            "success": True,
            "aggregation_count": len(request.aggregations),
            "results": result
        }

    except Exception as e:
        logger.error(f"Multi-aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nested")
async def get_nested_aggregations(request: NestedAggregationRequest):
    """
    Execute nested (hierarchical) aggregations.

    Example:
    ```json
    {
        "parent_agg": {"name": "by_status", "field": "status", "type": "terms"},
        "sub_aggs": [
            {"name": "amount_stats", "field": "total_amount", "type": "stats"},
            {"name": "unique_vendors", "field": "vendor_name", "type": "cardinality"}
        ]
    }
    ```

    Useful for grouped analytics like "stats by category" or "monthly trends by status".
    """

    postgres_service = PostgresService(db)

    try:
        result = await elastic_service.get_nested_aggregations(
            parent_agg=request.parent_agg,
            sub_aggs=request.sub_aggs,
            filters=request.filters
        )

        return {
            "success": True,
            "parent_aggregation": request.parent_agg["name"],
            "sub_aggregation_count": len(request.sub_aggs),
            "results": result
        }

    except Exception as e:
        logger.error(f"Nested aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_dashboard_aggregations():
    """
    Get pre-configured dashboard aggregations for common analytics.

    Returns:
    - Document status breakdown
    - Confidence score distribution
    - Upload trends (monthly)
    - Template usage statistics
    - Top vendors/entities
    - Amount statistics
    """

    postgres_service = PostgresService(db)

    try:
        # Define comprehensive dashboard aggregations
        aggregations = [
            # Status breakdown
            {
                "name": "status_breakdown",
                "field": "status",
                "type": "terms",
                "config": {"size": 20}
            },
            # Template usage
            {
                "name": "template_usage",
                "field": "_query_context.template_name",
                "type": "terms",
                "config": {"size": 20}
            },
            # Monthly upload trends
            {
                "name": "monthly_uploads",
                "field": "uploaded_at",
                "type": "date_histogram",
                "config": {"interval": "month", "format": "yyyy-MM"}
            },
            # Document count
            {
                "name": "total_documents",
                "field": "document_id",
                "type": "cardinality"
            },
        ]

        result = await postgres_service.get_multi_aggregations(
            aggregations=aggregations
        )

        return {
            "success": True,
            "dashboard": "overview",
            "results": result,
            "metadata": {
                "aggregations": [agg["name"] for agg in aggregations],
                "generated_at": "now"
            }
        }

    except Exception as e:
        logger.error(f"Dashboard aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/{field}")
async def get_field_insights(field: str):
    """
    Get comprehensive insights for a specific field.

    Auto-detects field type and returns appropriate aggregations:
    - Text/Keyword fields: Top values, cardinality
    - Numeric fields: Stats, percentiles, histogram
    - Date fields: Date histogram, date range
    """

    postgres_service = PostgresService(db)

    try:
        # Get field mapping to determine type
        # For MVP, we'll try multiple aggregation types and return what works

        insights = {}

        # Try terms aggregation (works for keyword fields)
        try:
            terms_result = await postgres_service.get_aggregations(
                field=field,
                agg_type="terms",
                agg_config={"size": 10}
            )
            insights["top_values"] = terms_result
        except:
            pass

        # Try stats aggregation (works for numeric fields)
        try:
            stats_result = await postgres_service.get_aggregations(
                field=field,
                agg_type="stats"
            )
            insights["statistics"] = stats_result
        except:
            pass

        # Try cardinality (works for all fields)
        try:
            cardinality_result = await postgres_service.get_aggregations(
                field=field,
                agg_type="cardinality"
            )
            insights["unique_count"] = cardinality_result
        except:
            pass

        if not insights:
            raise HTTPException(status_code=404, detail=f"Field '{field}' not found or not aggregatable")

        return {
            "success": True,
            "field": field,
            "insights": insights
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Field insights error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def execute_custom_aggregation(custom_query: Dict[str, Any]):
    """
    Execute a custom Elasticsearch aggregation query.

    Provides full flexibility for advanced users who want to write
    their own aggregation queries.

    Example:
    ```json
    {
        "aggregations": {
            "price_ranges": {
                "range": {
                    "field": "total_amount",
                    "ranges": [
                        {"to": 100},
                        {"from": 100, "to": 1000},
                        {"from": 1000}
                    ]
                },
                "aggs": {
                    "avg_confidence": {
                        "avg": {"script": "doc['confidence_scores'].values.stream().average().orElse(0)"}
                    }
                }
            }
        },
        "filters": {}
    }
    ```
    """

    postgres_service = PostgresService(db)

    try:
        aggregations = custom_query.get("aggregations")
        filters = custom_query.get("filters")

        if not aggregations:
            raise HTTPException(status_code=400, detail="aggregations field required")

        result = await postgres_service.get_aggregations(
            custom_aggs=aggregations,
            filters=filters
        )

        return {
            "success": True,
            "results": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets/{preset_name}")
async def get_preset_aggregation(preset_name: str, filters: Optional[Dict[str, Any]] = None):
    """
    Execute pre-configured aggregation presets.

    Available presets:
    - confidence_analysis: Confidence score distribution and stats
    - amount_analysis: Amount ranges and statistics
    - temporal_analysis: Upload trends over time
    - template_analysis: Template usage and field distribution
    """

    postgres_service = PostgresService(db)

    presets = {
        "confidence_analysis": [
            {
                "name": "confidence_ranges",
                "field": "confidence_scores",
                "type": "range",
                "config": {
                    "ranges": [
                        {"to": 0.6, "key": "low"},
                        {"from": 0.6, "to": 0.8, "key": "medium"},
                        {"from": 0.8, "key": "high"}
                    ]
                }
            }
        ],
        "temporal_analysis": [
            {
                "name": "daily_uploads",
                "field": "uploaded_at",
                "type": "date_histogram",
                "config": {"interval": "day", "format": "yyyy-MM-dd"}
            },
            {
                "name": "weekly_uploads",
                "field": "uploaded_at",
                "type": "date_histogram",
                "config": {"interval": "week", "format": "yyyy-'W'ww"}
            }
        ],
        "template_analysis": [
            {
                "name": "templates",
                "field": "_query_context.template_name",
                "type": "terms",
                "config": {"size": 50}
            },
            {
                "name": "template_count",
                "field": "_query_context.template_name",
                "type": "cardinality"
            }
        ]
    }

    if preset_name not in presets:
        raise HTTPException(
            status_code=404,
            detail=f"Preset '{preset_name}' not found. Available: {', '.join(presets.keys())}"
        )

    try:
        result = await postgres_service.get_multi_aggregations(
            aggregations=presets[preset_name],
            filters=filters
        )

        return {
            "success": True,
            "preset": preset_name,
            "results": result
        }

    except Exception as e:
        logger.error(f"Preset aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
