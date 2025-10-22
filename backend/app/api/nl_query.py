from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import json
import hashlib

from app.core.database import get_db
from app.services.claude_service import ClaudeService
from app.services.elastic_service import ElasticsearchService
from app.services.schema_registry import SchemaRegistry
from app.models.schema import Schema, FieldDefinition
from app.models.extraction import Extraction
from app.models.query_pattern import QueryPattern, QueryCache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["natural-language-query"])


class NLQueryRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Dict[str, str]]] = None


class NLQueryResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    summary: str
    query_explanation: str
    suggested_actions: List[str]
    total_count: int
    aggregations: Optional[Dict[str, Any]] = None
    clarifying_question: Optional[str] = None


@router.post("/natural-language", response_model=NLQueryResponse)
async def natural_language_query(
    request: NLQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Process natural language queries and return conversational results.
    Now enhanced with Schema Registry and query caching for better performance.

    Examples:
    - "Show me all invoices from Acme Corp over $5,000 last quarter"
    - "Total spending by vendor this year"
    - "Find duplicate invoices"
    - "Show contracts expiring in 30 days"
    - "What was the average invoice amount last month?"
    """
    claude_service = ClaudeService()
    elastic_service = ElasticsearchService()
    schema_registry = SchemaRegistry(db)

    try:
        # NEW: Check query cache first (exact match)
        query_hash = _hash_query(request.query)
        cached_result = db.query(QueryCache).filter(
            QueryCache.query_hash == query_hash
        ).first()

        if cached_result:
            logger.info(f"Cache HIT for query: {request.query}")
            cached_result.hit_count += 1
            cached_result.last_accessed = datetime.utcnow()
            db.commit()

            # Execute cached ES query
            search_results = await elastic_service.search(
                query=None,
                filters=None,
                custom_query=cached_result.es_query.get("query"),
                page=1,
                size=100
            )

            results = search_results.get("documents", [])
            total_count = search_results.get("total", 0)

            # Generate fresh summary (results may have changed)
            summary = await claude_service.generate_query_summary(
                query=request.query,
                results=results,
                total_count=total_count,
                query_type=cached_result.query_type
            )

            return NLQueryResponse(
                query=request.query,
                results=[_format_result(r) for r in results[:20]],
                summary=summary,
                query_explanation=cached_result.explanation,
                suggested_actions=_generate_suggested_actions(
                    cached_result.query_type, total_count, results
                ),
                total_count=total_count
            )

        # Cache miss - proceed with full processing
        logger.info(f"Cache MISS for query: {request.query}")

        # NEW: Get enriched field context from Schema Registry
        # Try to infer template from query or use all templates
        field_metadata = await schema_registry.get_all_templates_context()

        # Combine all fields with their metadata
        all_field_names = []
        combined_metadata = {"fields": {}}

        for template_context in field_metadata:
            all_field_names.extend(template_context.get("all_field_names", []))
            combined_metadata["fields"].update(template_context.get("fields", {}))

        # Add standard fields
        all_field_names.extend([
            "filename", "uploaded_at", "processed_at",
            "status", "template_name", "confidence_scores"
        ])

        # Deduplicate
        available_fields = list(set(all_field_names))

        # NEW: Parse the query using Claude with enhanced field metadata
        parsed_query = await claude_service.parse_natural_language_query(
            query=request.query,
            available_fields=available_fields,
            field_metadata=combined_metadata,
            conversation_history=request.conversation_history
        )

        logger.info(f"Parsed query: {json.dumps(parsed_query, indent=2)}")

        # Check if clarification is needed
        if parsed_query.get("needs_clarification"):
            return NLQueryResponse(
                query=request.query,
                results=[],
                summary="",
                query_explanation="",
                suggested_actions=[],
                total_count=0,
                clarifying_question=parsed_query.get("clarifying_question")
            )

        # Build Elasticsearch query
        es_query = parsed_query.get("elasticsearch_query", {})

        # Execute the query
        search_results = await elastic_service.search(
            query=None,
            filters=None,
            custom_query=es_query.get("query"),
            page=1,
            size=100  # Get more results for aggregations
        )

        results = search_results.get("documents", [])
        total_count = search_results.get("total", 0)

        # Handle aggregation queries
        aggregations = None
        if parsed_query.get("query_type") == "aggregation":
            aggregations = await _handle_aggregation_query(
                parsed_query, elastic_service, results
            )

        # Generate conversational summary
        summary = await claude_service.generate_query_summary(
            query=request.query,
            results=results,
            total_count=total_count,
            query_type=parsed_query.get("query_type"),
            aggregations=aggregations
        )

        # Generate suggested actions
        suggested_actions = _generate_suggested_actions(
            query_type=parsed_query.get("query_type"),
            total_count=total_count,
            results=results
        )

        # NEW: Cache the successful query for future use
        try:
            cache_entry = QueryCache(
                query_hash=query_hash,
                original_query=request.query,
                template_name=None,  # Could be inferred from query
                es_query=es_query,
                explanation=parsed_query.get("explanation", ""),
                query_type=parsed_query.get("query_type", "search"),
                hit_count=0,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow()
            )
            db.add(cache_entry)
            db.commit()
            logger.info(f"Cached query: {request.query[:50]}...")
        except Exception as cache_error:
            logger.warning(f"Failed to cache query: {cache_error}")
            # Non-fatal - continue with response

        return NLQueryResponse(
            query=request.query,
            results=[_format_result(r) for r in results[:20]],  # Return top 20
            summary=summary,
            query_explanation=parsed_query.get("explanation", ""),
            suggested_actions=suggested_actions,
            total_count=total_count,
            aggregations=aggregations
        )

    except Exception as e:
        logger.error(f"Error processing NL query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


async def _handle_aggregation_query(
    parsed_query: Dict[str, Any],
    elastic_service: ElasticsearchService,
    results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Handle aggregation queries like totals, averages, grouping."""

    agg_type = parsed_query.get("aggregation", {}).get("type")
    field = parsed_query.get("aggregation", {}).get("field")

    if not agg_type or not field:
        return None

    aggregations = {}

    if agg_type == "sum":
        total = sum(
            float(r.get("data", {}).get(field, 0) or 0)
            for r in results
        )
        aggregations["total"] = total
        aggregations["field"] = field
        aggregations["type"] = "sum"

    elif agg_type == "avg":
        values = [
            float(r.get("data", {}).get(field, 0) or 0)
            for r in results
        ]
        avg = sum(values) / len(values) if values else 0
        aggregations["average"] = avg
        aggregations["field"] = field
        aggregations["type"] = "avg"
        aggregations["count"] = len(values)

    elif agg_type == "group_by":
        groups = {}
        for r in results:
            key = r.get("data", {}).get(field, "Unknown")
            if key not in groups:
                groups[key] = {"count": 0, "total": 0}
            groups[key]["count"] += 1

            # If there's a value field, sum it
            value_field = parsed_query.get("aggregation", {}).get("value_field")
            if value_field:
                groups[key]["total"] += float(
                    r.get("data", {}).get(value_field, 0) or 0
                )

        aggregations["groups"] = groups
        aggregations["field"] = field
        aggregations["type"] = "group_by"

    elif agg_type == "count":
        aggregations["count"] = len(results)
        aggregations["type"] = "count"

    return aggregations


def _format_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format a single result for frontend display."""
    return {
        "id": result.get("id"),
        "filename": result.get("data", {}).get("filename", "Unknown"),
        "score": result.get("score", 0),
        "data": result.get("data", {}),
        "highlights": result.get("highlights", {})
    }


def _generate_suggested_actions(
    query_type: str,
    total_count: int,
    results: List[Dict[str, Any]]
) -> List[str]:
    """Generate contextual suggested actions based on results."""

    suggestions = []

    if total_count == 0:
        suggestions.append("Try broadening your search terms")
        suggestions.append("Check if documents have been processed")
        return suggestions

    # Common actions
    if total_count > 0:
        suggestions.append("Export results to CSV")
        suggestions.append("View all documents")

    if query_type == "search":
        suggestions.append("Refine search with filters")
        suggestions.append("Sort by confidence score")

    elif query_type == "aggregation":
        suggestions.append("View detailed breakdown")
        suggestions.append("Download report")

    elif query_type == "anomaly":
        suggestions.append("Flag items for review")
        suggestions.append("Create verification task")

    # Check for low confidence results
    low_confidence = [
        r for r in results
        if any(
            score < 0.7
            for score in r.get("data", {}).get("confidence_scores", {}).values()
        )
    ]

    if low_confidence:
        suggestions.append(f"Review {len(low_confidence)} low-confidence extractions")

    return suggestions[:4]  # Return top 4


def _hash_query(query: str) -> str:
    """Generate a hash for query caching."""
    # Normalize query (lowercase, strip whitespace)
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


@router.get("/cache/stats")
async def get_cache_stats(db: Session = Depends(get_db)):
    """
    Get query cache statistics for monitoring and optimization.
    """
    from sqlalchemy import func

    # Cache statistics
    total_cached_queries = db.query(QueryCache).count()
    total_hits = db.query(func.sum(QueryCache.hit_count)).scalar() or 0

    # Top cached queries
    top_queries = db.query(QueryCache).order_by(
        QueryCache.hit_count.desc()
    ).limit(10).all()

    # Calculate cache hit rate
    cache_hit_rate = (total_hits / (total_cached_queries + total_hits)) if (total_cached_queries + total_hits) > 0 else 0

    # Estimated cost savings (assuming $0.003 per Claude API call)
    cost_savings = total_hits * 0.003

    return {
        "total_cached_queries": total_cached_queries,
        "total_cache_hits": total_hits,
        "cache_hit_rate": f"{cache_hit_rate * 100:.1f}%",
        "estimated_cost_savings": f"${cost_savings:.2f}",
        "top_queries": [
            {
                "query": q.original_query,
                "hits": q.hit_count,
                "query_type": q.query_type,
                "last_used": q.last_accessed.isoformat() if q.last_accessed else None
            }
            for q in top_queries
        ]
    }


@router.delete("/cache/clear")
async def clear_cache(db: Session = Depends(get_db)):
    """
    Clear the query cache (for testing or maintenance).
    """
    deleted_count = db.query(QueryCache).delete()
    db.commit()

    return {
        "success": True,
        "deleted_entries": deleted_count,
        "message": f"Cleared {deleted_count} cached queries"
    }


@router.get("/suggestions")
async def get_query_suggestions(db: Session = Depends(get_db)):
    """
    Get suggested queries to help users discover capabilities.
    """

    # Get some stats to personalize suggestions
    total_extractions = db.query(Extraction).count()

    # Get available templates
    templates = db.query(Schema).limit(5).all()
    template_names = [t.name for t in templates]

    suggestions = [
        {
            "category": "Search & Filter",
            "queries": [
                "Show me all documents uploaded this week",
                "Find invoices over $1,000",
                "Show contracts expiring in the next 30 days",
                f"Search for {template_names[0] if template_names else 'invoices'} from last month"
            ]
        },
        {
            "category": "Analytics & Aggregation",
            "queries": [
                "What's the total value of all invoices this year?",
                "Show me average invoice amount by vendor",
                "Group documents by template type",
                "How many documents were processed last month?"
            ]
        },
        {
            "category": "Quality & Anomalies",
            "queries": [
                "Find documents with low confidence scores",
                "Show me potential duplicate invoices",
                "Which extractions need verification?",
                "Find unusually high invoice amounts"
            ]
        },
        {
            "category": "Trends & Insights",
            "queries": [
                "Show monthly document upload trend",
                "Top 5 vendors by invoice count",
                "Compare spending: last month vs this month",
                "Which templates are most used?"
            ]
        }
    ]

    return {
        "suggestions": suggestions,
        "total_documents": total_extractions,
        "available_templates": template_names
    }
