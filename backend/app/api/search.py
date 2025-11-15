import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.schema import Schema
from app.services.answer_cache import get_answer_cache
from app.services.claude_service import ClaudeService
from app.services.postgres_service import PostgresService
from app.services.query_optimizer import QueryOptimizer
from app.utils.query_field_extractor import (
    extract_fields_from_es_query,
    filter_audit_items_by_fields,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    folder_path: Optional[str] = None
    template_id: Optional[str] = None  # Changed to str to support "schema_15" or "template_1" format
    conversation_history: Optional[List[Dict[str, str]]] = None


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
    import hashlib
    from datetime import datetime

    from app.models.query_pattern import QueryCache
    from app.services.schema_registry import SchemaRegistry

    claude_service = ClaudeService()
    postgres_service = PostgresService(db)
    schema_registry = SchemaRegistry(db)

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

            # Add template filter if specified
            if request.template_id:
                es_query = _add_template_filter(es_query, request.template_id, db)

            # Extract field lineage from query
            field_lineage = extract_fields_from_es_query(es_query)
            logger.info(f"Extracted {len(field_lineage['queried_fields'])} queried fields from cached query")

            search_results = await postgres_service.search(
                query=None,
                filters=None,
                custom_query=es_query,
                page=1,
                size=20
            )

            # Generate fresh answer with confidence metadata
            answer_result = await claude_service.answer_question_about_results(
                query=request.query,
                search_results=search_results.get("documents", []),
                total_count=search_results.get("total", 0),
                include_confidence_metadata=True
            )

            answer = answer_result.get("answer", "No answer available.")

            # Get audit metadata for low-confidence fields
            from app.utils.audit_helpers import (
                get_confidence_summary,
                get_low_confidence_fields_for_documents,
            )

            document_ids = [doc.get("id") for doc in search_results.get("documents", []) if doc.get("id")]

            low_conf_fields_grouped = await get_low_confidence_fields_for_documents(
                document_ids=document_ids,
                db=db,
                confidence_threshold=None
            )

            # Flatten and update source
            all_audit_items = []
            for doc_id, fields in low_conf_fields_grouped.items():
                for field in fields:
                    field["audit_url"] = field["audit_url"].replace("source=ai_answer", "source=search_answer")
                    all_audit_items.append(field)

            # Filter audit items to only fields used in query
            audit_items = filter_audit_items_by_fields(
                all_audit_items,
                field_lineage["queried_fields"]
            )

            logger.info(f"Filtered audit items from {len(all_audit_items)} to {len(audit_items)} (query-relevant only)")

            confidence_summary = await get_confidence_summary(document_ids=document_ids, db=db)

            # NEW: Save query history for viewing source documents
            from app.core.config import settings
            from app.models.query_history import QueryHistory

            query_history = QueryHistory.create_from_search(
                query=request.query,
                answer=answer,
                document_ids=document_ids,
                source="ask_ai"
            )
            db.add(query_history)
            db.commit()
            db.refresh(query_history)

            # Build link to documents page with query filter
            documents_link = f"{settings.FRONTEND_URL}/documents?query_id={query_history.id}"

            return {
                "query": request.query,
                "answer": answer,
                "answer_metadata": {
                    "sources_used": answer_result.get("sources_used", []),
                    "low_confidence_warnings": answer_result.get("low_confidence_warnings", []),
                    "confidence_level": answer_result.get("confidence_level", "unknown")
                },
                "field_lineage": field_lineage,
                "audit_items": audit_items,
                "audit_items_filtered_count": len(audit_items),
                "audit_items_total_count": len(all_audit_items),
                "confidence_summary": confidence_summary,
                "explanation": cached_result.explanation,
                "results": search_results.get("documents", []),
                "total": search_results.get("total", 0),
                "sql_query": {"query": es_query},  # ES query format for backward compatibility
                "cached": True,
                "optimization_used": False,
                "folder_path": request.folder_path,
                # NEW: Query history fields
                "query_id": query_history.id,
                "documents_link": documents_link
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
        # NOTE: "template_name" is NOT added here because the actual field is "_query_context.template_name.keyword"
        # Adding "template_name" causes Claude to generate invalid filters
        all_field_names.extend([
            "filename", "uploaded_at", "processed_at",
            "status", "confidence_scores", "folder_path"
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

            # NEW: Extract template-specific context if template filter is active
            template_context = None
            if request.template_id:
                template_context = _get_template_context(request.template_id, db)
                if template_context:
                    logger.info(f"Template-specific query for: {template_context.get('name', 'unknown')}")
                else:
                    logger.warning(f"Template {request.template_id} not found for context extraction")

            nl_result = await claude_service.parse_natural_language_query(
                query=request.query,
                available_fields=available_fields,
                field_metadata=combined_metadata,
                conversation_history=request.conversation_history,
                template_context=template_context  # NEW parameter
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

        # Add template filter if specified
        if request.template_id:
            es_query = _add_template_filter(es_query, request.template_id, db)

        # Extract field lineage from query
        field_lineage = extract_fields_from_es_query(es_query)
        logger.info(f"Extracted {len(field_lineage['queried_fields'])} queried fields: {field_lineage['queried_fields']}")

        # Check if this is an aggregation query
        aggregation_spec = None
        if use_claude and nl_result:
            aggregation_spec = nl_result.get("aggregation")
        # Note: QueryOptimizer doesn't currently detect aggregations
        # If it did, we'd need to extract aggregation spec from query_analysis here

        if query_type == "aggregation" and aggregation_spec:
            # Execute aggregation query instead of document search
            logger.info(f"Executing aggregation query: type={aggregation_spec.get('type')}, field={aggregation_spec.get('field')}")

            agg_field = aggregation_spec.get("field")
            agg_type = aggregation_spec.get("type")

            # Validate aggregation parameters
            if not agg_type:
                logger.warning(f"Aggregation spec missing type: {aggregation_spec}. Falling back to normal search.")
                # Fall through to normal search by skipping aggregation branch
                query_type = "search"
            elif agg_type != "count" and not agg_field:
                logger.warning(f"Aggregation type '{agg_type}' requires field but none provided. Falling back to normal search.")
                # Fall through to normal search
                query_type = "search"

            if query_type == "aggregation":  # Only execute if validation passed
                # Map aggregation types to ES aggregation types
                agg_type_mapping = {
                    "sum": "stats",
                    "avg": "stats",
                    "count": "value_count",
                    "min": "stats",
                    "max": "stats",
                    "group_by": "terms"
                }

                es_agg_type = agg_type_mapping.get(agg_type, "stats")

                # Log warning if unknown aggregation type
                if agg_type not in agg_type_mapping:
                    logger.warning(f"Unknown aggregation type '{agg_type}', defaulting to 'stats'")

                # Execute aggregation
                agg_results = await postgres_service.get_aggregations(
                    field=agg_field,
                    agg_type=es_agg_type,
                    filters=es_query
                )

                # For aggregation queries, we don't need individual documents
                search_results = {
                    "documents": [],
                    "total": agg_results.get("doc_count", 0)
                }

                # Check answer cache (for aggregations, use empty result_ids)
                answer_cache = get_answer_cache()
                cache_filters = {}
                if request.template_id:
                    cache_filters["template_id"] = request.template_id
                if request.folder_path:
                    cache_filters["folder_path"] = request.folder_path
                cached_answer = answer_cache.get(request.query, [], cache_filters)

                if cached_answer:
                    logger.info("Using cached answer for aggregation query")
                    answer_result = cached_answer
                else:
                    # Generate answer with aggregation results
                    answer_result = await claude_service.answer_question_about_results(
                        query=request.query,
                        search_results=[],
                        total_count=agg_results.get("doc_count", 0),
                        include_confidence_metadata=True,
                        aggregation_results=agg_results,
                        aggregation_type=agg_type
                    )
                    # Cache the answer
                    answer_cache.set(request.query, [], answer_result, cache_filters)

        # Execute normal search if not aggregation query (or if aggregation validation failed)
        if query_type != "aggregation" or not aggregation_spec:
            # Execute PostgreSQL query for normal search
            search_results = await postgres_service.search(
                query=None,
                filters=None,
                custom_query=es_query,
                page=1,
                size=20
            )

            # Extract document IDs for cache key
            result_ids = [doc.get("id") for doc in search_results.get("documents", []) if doc.get("id")]

            # Check answer cache before calling Claude
            answer_cache = get_answer_cache()
            cache_filters = {}
            if request.template_id:
                cache_filters["template_id"] = request.template_id
            if request.folder_path:
                cache_filters["folder_path"] = request.folder_path
            cached_answer = answer_cache.get(request.query, result_ids, cache_filters)

            if cached_answer:
                logger.info(f"Using cached answer for query: {request.query[:50]}...")
                answer_result = cached_answer
            else:
                # Generate natural language answer with confidence metadata
                answer_result = await claude_service.answer_question_about_results(
                    query=request.query,
                    search_results=search_results.get("documents", []),
                    total_count=search_results.get("total", 0),
                    include_confidence_metadata=True
                )
                # Cache the answer
                answer_cache.set(request.query, result_ids, answer_result, cache_filters)

        answer = answer_result.get("answer", "No answer available.")

        # Get audit metadata for low-confidence fields
        from app.utils.audit_helpers import (
            get_confidence_summary,
            get_low_confidence_fields_for_documents,
        )

        # Skip audit metadata for aggregation queries (no individual documents to audit)
        if query_type == "aggregation" and aggregation_spec:
            audit_items = []
            all_audit_items = []
            confidence_summary = {"low_confidence_count": 0, "total_fields": 0}
            logger.info("Skipping audit metadata for aggregation query (no documents returned)")
        else:
            document_ids = [doc.get("id") for doc in search_results.get("documents", []) if doc.get("id")]

            # OPTIMIZATION: Filter fields in SQL query, not Python
            low_conf_fields_grouped = await get_low_confidence_fields_for_documents(
                document_ids=document_ids,
                db=db,
                confidence_threshold=None,
                field_names=field_lineage["queried_fields"]  # Filter in SQL WHERE clause
            )

            # Flatten and update source (no need to filter in Python anymore)
            audit_items = []
            for doc_id, fields in low_conf_fields_grouped.items():
                for field in fields:
                    field["audit_url"] = field["audit_url"].replace("source=ai_answer", "source=search_answer")
                    audit_items.append(field)

            # Since we filtered in SQL, all_audit_items equals audit_items
            all_audit_items = audit_items

            logger.info(f"Found {len(audit_items)} query-relevant audit items (filtered in SQL)")

            confidence_summary = await get_confidence_summary(document_ids=document_ids, db=db)

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

        # NEW: Save query history for viewing source documents
        from app.core.config import settings
        from app.models.query_history import QueryHistory

        # Extract document IDs from search results (skip for aggregation queries)
        if query_type == "aggregation" and aggregation_spec:
            document_ids_for_history = []
        else:
            document_ids_for_history = [doc.get("id") for doc in search_results.get("documents", []) if doc.get("id")]

        query_history = QueryHistory.create_from_search(
            query=request.query,
            answer=answer,
            document_ids=document_ids_for_history,
            source="ask_ai"
        )
        db.add(query_history)
        db.commit()
        db.refresh(query_history)

        # Build link to documents page with query filter
        documents_link = f"{settings.FRONTEND_URL}/documents?query_id={query_history.id}"

        return {
            "query": request.query,
            "answer": answer,
            "answer_metadata": {
                "sources_used": answer_result.get("sources_used", []),
                "low_confidence_warnings": answer_result.get("low_confidence_warnings", []),
                "confidence_level": answer_result.get("confidence_level", "unknown")
            },
            "field_lineage": field_lineage,
            "audit_items": audit_items,
            "audit_items_filtered_count": len(audit_items),
            "audit_items_total_count": len(all_audit_items),
            "confidence_summary": confidence_summary,
            "explanation": explanation,
            "results": search_results.get("documents", []),
            "total": search_results.get("total", 0),
            "sql_query": {"query": es_query},  # ES query format for backward compatibility
            "cached": False,
            "optimization_used": not use_claude,
            "query_confidence": query_analysis["confidence"],
            "folder_path": request.folder_path,
            # NEW: Query history fields
            "query_id": query_history.id,
            "documents_link": documents_link
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


def _get_template_context(template_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get template field information for query optimization.

    Returns:
        {
            "name": "Template Name",
            "fields": [{"name": "field_name", "type": "text", "description": "...", ...}]
        }
    """
    from app.models.template import SchemaTemplate

    if template_id.startswith("schema_"):
        # User-created schema
        schema_id = int(template_id.split("_")[1])
        schema = db.query(Schema).filter(Schema.id == schema_id).first()
        if schema:
            return {
                "name": schema.name,
                "fields": schema.fields
            }
    elif template_id.startswith("template_"):
        # Built-in template
        tmpl_id = int(template_id.split("_")[1])
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == tmpl_id).first()
        if template:
            return {
                "name": template.name,
                "fields": template.fields
            }
    else:
        # Legacy numeric ID
        try:
            numeric_id = int(template_id)
            schema = db.query(Schema).filter(Schema.id == numeric_id).first()
            if schema:
                return {
                    "name": schema.name,
                    "fields": schema.fields
                }
        except ValueError:
            pass

    return None


def _add_template_filter(es_query: Dict[str, Any], template_id: str, db: Session) -> Dict[str, Any]:
    """
    Add template filter to ES query by looking up template name.

    Args:
        template_id: Either "schema_15" for user schemas or "template_1" for built-in templates
    """
    from app.models.template import SchemaTemplate

    # Parse the template_id to determine type and ID
    template_name = None

    if template_id.startswith("schema_"):
        # User-created schema
        schema_id = int(template_id.split("_")[1])
        schema = db.query(Schema).filter(Schema.id == schema_id).first()
        if schema:
            template_name = schema.name
        else:
            logger.warning(f"Schema {schema_id} not found, skipping template filter")
            return es_query
    elif template_id.startswith("template_"):
        # Built-in template
        tmpl_id = int(template_id.split("_")[1])
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == tmpl_id).first()
        if template:
            template_name = template.name
        else:
            logger.warning(f"Template {tmpl_id} not found, skipping template filter")
            return es_query
    else:
        # Legacy numeric ID - try as schema first
        try:
            numeric_id = int(template_id)
            schema = db.query(Schema).filter(Schema.id == numeric_id).first()
            if schema:
                template_name = schema.name
            else:
                logger.warning(f"Schema {numeric_id} not found, skipping template filter")
                return es_query
        except ValueError:
            logger.warning(f"Invalid template_id format: {template_id}")
            return es_query

    if not template_name:
        return es_query

    template_filter = {
        "term": {
            "_query_context.template_name.keyword": template_name
        }
    }

    # Wrap existing query in bool must with template filter
    if not es_query:
        return {"bool": {"filter": [template_filter]}}

    # If query already has bool, add to filter
    if "bool" in es_query:
        if "filter" not in es_query["bool"]:
            es_query["bool"]["filter"] = []
        elif not isinstance(es_query["bool"]["filter"], list):
            es_query["bool"]["filter"] = [es_query["bool"]["filter"]]
        es_query["bool"]["filter"].append(template_filter)
        return es_query

    # Wrap non-bool query
    return {
        "bool": {
            "must": [es_query],
            "filter": [template_filter]
        }
    }



@router.get("/filters")
async def get_available_filters(db: Session = Depends(get_db)):
    """Get available filter options and value distributions"""

    postgres_service = PostgresService(db)

    try:
        # Get aggregations for common fields
        aggregations = {}

        # Example: Get status distribution
        status_agg = await postgres_service.get_aggregations("status")
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
async def get_index_statistics(db: Session = Depends(get_db)):
    """
    Get PostgreSQL index statistics for monitoring and optimization.

    Returns:
        Document count, storage size, field count, and index health.

    Useful for:
    - Monitoring index health
    - Database capacity planning
    - Performance optimization
    """
    postgres_service = PostgresService(db)

    try:
        stats = await postgres_service.get_index_stats()

        # Add health status based on document count
        doc_count = stats.get("document_count", 0)
        if doc_count >= 100000:
            health_status = "warning"
            health_message = "Large document count - consider partitioning"
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
    storage_mb = stats.get("storage_size_mb", 0)
    if storage_mb > 1000:
        recommendations.append("Consider implementing table partitioning for large datasets")

    # Document count recommendations
    doc_count = stats.get("document_count", 0)
    if doc_count > 100000:
        recommendations.append("Consider table partitioning by date or schema for better performance")
        recommendations.append("Review index usage and add missing indexes for common queries")

    if doc_count > 1000000:
        recommendations.append("Consider PostgreSQL read replicas for scaling read operations")

    # Index recommendations
    if stats.get("missing_indexes"):
        recommendations.append("Add recommended indexes for better query performance")

    if not recommendations:
        recommendations.append("Index is healthy - no action needed")

    return recommendations


