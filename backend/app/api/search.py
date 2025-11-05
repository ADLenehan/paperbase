from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from app.services.elastic_service import ElasticsearchService
from app.services.claude_service import ClaudeService
from app.services.query_optimizer import QueryOptimizer
from app.core.database import get_db
from app.models.schema import Schema, FieldDefinition
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    folder_path: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    include_citations: bool = True  # NEW: Default ON for MCP compatibility
    citation_format: str = "long"  # NEW: short|long|academic


@router.post("")
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    AI-powered search endpoint with hybrid query optimization and natural language understanding.

    Flow:
    1. Check QueryCache for exact match
    2. Use QueryOptimizer for intent detection and filter extraction
    3. If high confidence (>0.7), execute directly
    4. If low confidence, refine with Claude
    5. Execute ES query and generate answer
    6. Cache successful queries

    Args:
        query: Natural language search query
        folder_path: Optional folder path to restrict search (e.g., "invoices" or "invoices/acme-corp")
        conversation_history: Optional conversation context for follow-up questions
    """
    from app.services.schema_registry import SchemaRegistry
    from app.models.query_pattern import QueryCache
    import hashlib
    from datetime import datetime

    from app.services.citation_service import CitationService

    claude_service = ClaudeService()
    elastic_service = ElasticsearchService()
    schema_registry = SchemaRegistry(db)
    citation_service = CitationService()

    # Initialize QueryOptimizer with SchemaRegistry for dynamic field resolution
    query_optimizer = QueryOptimizer(schema_registry=schema_registry)
    await query_optimizer.initialize_from_registry()

    try:
        # Build cache key including folder context
        cache_key = f"{request.query.lower().strip()}|{request.folder_path or ''}"
        query_hash = hashlib.sha256(cache_key.encode()).hexdigest()

        # STEP 1: Check query cache first for exact match
        cached_result = db.query(QueryCache).filter(
            QueryCache.query_hash == query_hash
        ).first()

        if cached_result:
            logger.info(f"Cache HIT for query: {request.query}")
            cached_result.hit_count += 1
            cached_result.last_accessed = datetime.utcnow()
            db.commit()

            # Execute cached ES query with folder filter
            es_query = cached_result.es_query.get("query", {})
            if request.folder_path:
                # Add folder filter to cached query
                es_query = _add_folder_filter(es_query, request.folder_path)

            search_results = await elastic_service.search(
                query=None,
                filters=None,
                custom_query=es_query,
                page=1,
                size=20
            )

            # NEW: Enrich with citations if requested (MCP-friendly)
            results = search_results.get("documents", [])
            if request.include_citations:
                results = await citation_service.enrich_search_results_with_citations(
                    results=results,
                    db=db,
                    citation_format=request.citation_format
                )

            # Generate fresh answer
            answer = await claude_service.answer_question_about_results(
                query=request.query,
                search_results=results,
                total_count=search_results.get("total", 0)
            )

            # Build MCP context for AI agents
            mcp_context = {
                "citation_format": f"Cite sources using format: {request.citation_format}",
                "all_fields_have_citations": request.include_citations,
                "instructions": "When referencing data, always cite the source using the provided citation strings."
            }

            return {
                "query": request.query,
                "answer": answer,
                "explanation": cached_result.explanation,
                "results": results,
                "total": search_results.get("total", 0),
                "elasticsearch_query": {"query": es_query},
                "cached": True,
                "optimization_used": False,
                "folder_path": request.folder_path,
                "mcp_context": mcp_context if request.include_citations else None
            }

        # Cache miss - proceed with optimization
        logger.info(f"Cache MISS for query: {request.query}")

        # Get enhanced field context from Schema Registry
        field_metadata_list = await schema_registry.get_all_templates_context()

        # Combine all fields with their metadata
        all_field_names = []
        combined_metadata = {"fields": {}}

        for template_context in field_metadata_list:
            all_field_names.extend(template_context.get("all_field_names", []))
            combined_metadata["fields"].update(template_context.get("fields", {}))

        # Add standard fields
        all_field_names.extend([
            "filename", "uploaded_at", "processed_at",
            "status", "template_name", "confidence_scores", "folder_path"
        ])

        # Deduplicate
        available_fields = list(set(all_field_names))

        # STEP 2: Use QueryOptimizer for fast intent detection and filter extraction
        query_analysis = query_optimizer.understand_query_intent(
            query=request.query,
            available_fields=available_fields
        )

        logger.info(
            f"Query analysis: intent={query_analysis['intent']}, "
            f"confidence={query_analysis['confidence']:.2f}, "
            f"filters={len(query_analysis['filters'])}"
        )

        # STEP 3: Decide whether to use Claude for refinement
        use_claude = query_optimizer.should_use_claude(query_analysis)

        es_query = None
        explanation = ""
        query_type = query_analysis["intent"]

        if use_claude:
            # Low confidence or complex query - use Claude for refinement
            logger.info(f"Using Claude for query refinement (confidence: {query_analysis['confidence']:.2f})")

            nl_result = await claude_service.parse_natural_language_query(
                query=request.query,
                available_fields=available_fields,
                field_metadata=combined_metadata,
                conversation_history=request.conversation_history
            )

            es_query = nl_result.get("elasticsearch_query", {}).get("query", {})
            explanation = nl_result.get("explanation", "")
            query_type = nl_result.get("query_type", query_analysis["intent"])
        else:
            # High confidence - use QueryOptimizer directly (faster, cheaper)
            logger.info(f"Using QueryOptimizer directly (confidence: {query_analysis['confidence']:.2f})")

            es_query = query_optimizer.build_optimized_query(
                query=request.query,
                analysis=query_analysis,
                available_fields=available_fields
            )

            # Build explanation from analysis
            filter_descriptions = []
            for f in query_analysis["filters"]:
                if f["type"] == "range":
                    filter_descriptions.append(f"{f['field']} {f['operator']} {f['value']}")
                elif f["type"] == "date_range":
                    filter_descriptions.append(f"date in {f['range']}")

            explanation = f"Searching with {query_analysis['intent']} intent"
            if filter_descriptions:
                explanation += f" with filters: {', '.join(filter_descriptions)}"

        # Add folder filter if specified
        if request.folder_path:
            es_query = _add_folder_filter(es_query, request.folder_path)

        # Execute ES query
        search_results = await elastic_service.search(
            query=None,
            filters=None,
            custom_query=es_query,
            page=1,
            size=20
        )

        # Generate natural language answer
        answer = await claude_service.answer_question_about_results(
            query=request.query,
            search_results=search_results.get("documents", []),
            total_count=search_results.get("total", 0)
        )

        # NEW: Enrich with citations if requested (MCP-friendly)
        results = search_results.get("documents", [])
        if request.include_citations:
            results = await citation_service.enrich_search_results_with_citations(
                results=results,
                db=db,
                citation_format=request.citation_format
            )

        # Cache the successful query (without folder-specific results)
        try:
            cache_entry = QueryCache(
                query_hash=query_hash,
                original_query=request.query,
                template_name=None,
                es_query={"query": es_query},
                explanation=explanation,
                query_type=query_type,
                hit_count=0,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow()
            )
            db.add(cache_entry)
            db.commit()
            logger.info(f"Cached query: {request.query[:50]}...")
        except Exception as cache_error:
            logger.warning(f"Failed to cache query: {cache_error}")

        # Build MCP context for AI agents
        mcp_context = {
            "citation_format": f"Cite sources using format: {request.citation_format}",
            "all_fields_have_citations": request.include_citations,
            "instructions": "When referencing data, always cite the source using the provided citation strings.",
            "confidence_summary": f"{len([r for r in results if r.get('citations', {}).get('confidence', 0) > 0.8])} high-confidence results"
        }

        return {
            "query": request.query,
            "answer": answer,
            "explanation": explanation,
            "results": results,
            "total": search_results.get("total", 0),
            "elasticsearch_query": {"query": es_query},
            "cached": False,
            "optimization_used": not use_claude,
            "query_confidence": query_analysis["confidence"],
            "folder_path": request.folder_path,
            "mcp_context": mcp_context if request.include_citations else None
        }

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _add_folder_filter(es_query: Dict[str, Any], folder_path: str) -> Dict[str, Any]:
    """Add folder_path filter to ES query using prefix match"""
    folder_filter = {
        "prefix": {
            "folder_path.keyword": folder_path
        }
    }

    # Wrap existing query in bool must with folder filter
    if not es_query:
        return {"bool": {"filter": [folder_filter]}}

    # If query already has bool, add to filter
    if "bool" in es_query:
        if "filter" not in es_query["bool"]:
            es_query["bool"]["filter"] = []
        elif not isinstance(es_query["bool"]["filter"], list):
            es_query["bool"]["filter"] = [es_query["bool"]["filter"]]
        es_query["bool"]["filter"].append(folder_filter)
        return es_query

    # Wrap non-bool query
    return {
        "bool": {
            "must": [es_query],
            "filter": [folder_filter]
        }
    }



@router.get("/filters")
async def get_available_filters():
    """Get available filter options and value distributions"""

    elastic_service = ElasticsearchService()

    try:
        # Get aggregations for common fields
        aggregations = {}

        # Example: Get status distribution
        status_agg = await elastic_service.get_aggregations("status")
        aggregations["status"] = status_agg

        return {
            "available_filters": [
                {
                    "field": "status",
                    "type": "keyword",
                    "values": aggregations.get("status", {})
                },
                {
                    "field": "confidence",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0
                }
            ]
        }

    except Exception as e:
        logger.error(f"Error getting filters: {e}")
        return {"available_filters": []}


@router.get("/index-stats")
async def get_index_statistics():
    """
    Get Elasticsearch index statistics for monitoring and optimization.

    Returns:
        Document count, storage size, field count, and field limit utilization.

    Useful for:
    - Monitoring index health
    - Detecting mapping explosion risk
    - Capacity planning
    """
    elastic_service = ElasticsearchService()

    try:
        stats = await elastic_service.get_index_stats()

        # Add health status based on utilization
        field_utilization = stats["field_utilization_pct"]
        if field_utilization >= 90:
            health_status = "critical"
            health_message = "Field limit nearly exhausted - risk of mapping explosion"
        elif field_utilization >= 70:
            health_status = "warning"
            health_message = "Field count is high - monitor for unexpected growth"
        else:
            health_status = "healthy"
            health_message = "Index is operating within normal parameters"

        return {
            **stats,
            "health_status": health_status,
            "health_message": health_message,
            "recommendations": _get_index_recommendations(stats)
        }

    except Exception as e:
        logger.error(f"Error getting index stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get index statistics: {str(e)}")


def _get_index_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on index statistics"""
    recommendations = []

    # Storage recommendations
    if stats["storage_size_mb"] > 1000:
        recommendations.append("Consider implementing index lifecycle management for large indices")

    # Field count recommendations
    if stats["field_utilization_pct"] > 70:
        recommendations.append("Review schema definitions to remove unused fields")
        recommendations.append("Consider consolidating similar fields across templates")

    if stats["field_utilization_pct"] > 90:
        recommendations.append("URGENT: Increase field limit or restructure schemas to avoid mapping rejection")

    # Document count recommendations
    if stats["document_count"] > 100000:
        recommendations.append("Consider scaling to multiple shards for better performance")
        recommendations.append("Enable replicas for production redundancy")

    if stats["document_count"] > 1000000:
        recommendations.append("Migrate to time-based indices for better manageability")

    if not recommendations:
        recommendations.append("Index is healthy - no action needed")

    return recommendations


