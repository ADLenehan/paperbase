"""
MCP Server Search Interface

Provides clean, structured search and aggregation tools optimized for MCP consumption.
All endpoints return structured JSON suitable for tool-based interaction.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.services.elastic_service import ElasticsearchService
from app.services.claude_service import ClaudeService
from app.services.query_optimizer import QueryOptimizer
from app.core.database import get_db
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mcp/search", tags=["mcp-search"])


class MCPSearchRequest(BaseModel):
    """MCP-optimized search request"""
    query: str = Field(..., description="Search query (natural language or keywords)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters as key-value pairs")
    folder_path: Optional[str] = Field(None, description="Restrict search to specific folder")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    include_aggregations: bool = Field(False, description="Include aggregation summaries")


class MCPAggregationRequest(BaseModel):
    """MCP-optimized aggregation request"""
    field: str = Field(..., description="Field to aggregate")
    aggregation_type: str = Field("terms", description="Type: terms, stats, date_histogram, cardinality")
    filters: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")


class MCPSearchResponse(BaseModel):
    """Structured search response for MCP"""
    success: bool
    query: str
    total_results: int
    returned_results: int
    documents: List[Dict[str, Any]]
    aggregations: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any]


@router.post("/documents", response_model=MCPSearchResponse)
async def search_documents_mcp(request: MCPSearchRequest):
    """
    Search documents with MCP-optimized response format.

    Returns structured results suitable for tool consumption:
    - Clean document list with essential fields
    - Optional aggregation summaries
    - Metadata about query execution

    Example:
    ```json
    {
        "query": "invoices over $1000 from last month",
        "max_results": 10,
        "include_aggregations": true
    }
    ```
    """

    from app.services.schema_registry import SchemaRegistry

    elastic_service = ElasticsearchService()
    claude_service = ClaudeService()

    try:
        # Get database session
        from app.core.database import SessionLocal
        db = SessionLocal()

        try:
            schema_registry = SchemaRegistry(db)
            query_optimizer = QueryOptimizer(schema_registry=schema_registry)
            await query_optimizer.initialize_from_registry()

            # Get field context
            field_metadata_list = await schema_registry.get_all_templates_context()
            all_field_names = []
            combined_metadata = {"fields": {}}

            for template_context in field_metadata_list:
                all_field_names.extend(template_context.get("all_field_names", []))
                combined_metadata["fields"].update(template_context.get("fields", {}))

            all_field_names.extend([
                "filename", "uploaded_at", "processed_at",
                "status", "template_name", "confidence_scores", "folder_path"
            ])
            available_fields = list(set(all_field_names))

            # Analyze query
            query_analysis = query_optimizer.understand_query_intent(
                query=request.query,
                available_fields=available_fields
            )

            # Build ES query
            use_claude = query_optimizer.should_use_claude(query_analysis)

            if use_claude:
                nl_result = await claude_service.parse_natural_language_query(
                    query=request.query,
                    available_fields=available_fields,
                    field_metadata=combined_metadata
                )
                es_query = nl_result.get("elasticsearch_query", {}).get("query", {})
            else:
                es_query = query_optimizer.build_optimized_query(
                    query=request.query,
                    analysis=query_analysis,
                    available_fields=available_fields
                )

            # Add filters
            if request.filters:
                if "bool" not in es_query:
                    es_query = {"bool": {"must": [es_query] if es_query else [{"match_all": {}}]}}

                if "filter" not in es_query["bool"]:
                    es_query["bool"]["filter"] = []

                for field, value in request.filters.items():
                    es_query["bool"]["filter"].append({"term": {field: value}})

            # Add folder filter
            if request.folder_path:
                if "bool" not in es_query:
                    es_query = {"bool": {"must": [es_query] if es_query else [{"match_all": {}}]}}

                if "filter" not in es_query["bool"]:
                    es_query["bool"]["filter"] = []

                es_query["bool"]["filter"].append({
                    "prefix": {"folder_path.keyword": request.folder_path}
                })

            # Execute search
            search_results = await elastic_service.search(
                query=None,
                filters=None,
                custom_query=es_query,
                page=1,
                size=request.max_results
            )

            # Clean up documents for MCP response
            cleaned_documents = []
            for doc in search_results.get("documents", []):
                cleaned_doc = {
                    "id": doc["id"],
                    "score": doc["score"],
                    **doc["data"]
                }
                cleaned_documents.append(cleaned_doc)

            # Get aggregations if requested
            aggregations_result = None
            if request.include_aggregations and search_results.get("total", 0) > 0:
                # Get common aggregations
                try:
                    agg_filters = request.filters or {}
                    aggregations_result = await elastic_service.get_multi_aggregations(
                        aggregations=[
                            {"name": "by_status", "field": "status", "type": "terms", "config": {"size": 10}},
                            {"name": "by_template", "field": "_query_context.template_name", "type": "terms", "config": {"size": 10}}
                        ],
                        filters=agg_filters
                    )
                except Exception as agg_error:
                    logger.warning(f"Aggregation error: {agg_error}")

            response = MCPSearchResponse(
                success=True,
                query=request.query,
                total_results=search_results.get("total", 0),
                returned_results=len(cleaned_documents),
                documents=cleaned_documents,
                aggregations=aggregations_result,
                metadata={
                    "query_confidence": query_analysis.get("confidence", 0.0),
                    "used_claude": use_claude,
                    "folder_path": request.folder_path,
                    "filters_applied": len(request.filters) if request.filters else 0
                }
            )

            return response

        finally:
            db.close()

    except Exception as e:
        logger.error(f"MCP search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{document_id}")
async def get_document_mcp(document_id: int):
    """
    Get a single document by ID with full details.

    Returns complete document data including all extracted fields,
    confidence scores, and metadata.
    """

    elastic_service = ElasticsearchService()

    try:
        document = await elastic_service.get_document(document_id)

        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        return {
            "success": True,
            "document_id": document_id,
            "document": document
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP get document error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aggregate")
async def aggregate_mcp(request: MCPAggregationRequest):
    """
    Execute an aggregation query.

    Returns aggregation results in a clean, structured format.

    Example:
    ```json
    {
        "field": "status",
        "aggregation_type": "terms"
    }
    ```
    """

    elastic_service = ElasticsearchService()

    try:
        result = await elastic_service.get_aggregations(
            field=request.field,
            agg_type=request.aggregation_type,
            agg_config=request.config,
            filters=request.filters
        )

        return {
            "success": True,
            "field": request.field,
            "aggregation_type": request.aggregation_type,
            "results": result
        }

    except Exception as e:
        logger.error(f"MCP aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fields")
async def list_available_fields():
    """
    List all available searchable fields across all templates.

    Returns field names, types, descriptions, and aliases.
    Useful for building queries and understanding schema.
    """

    from app.core.database import SessionLocal
    from app.services.schema_registry import SchemaRegistry

    try:
        db = SessionLocal()
        schema_registry = SchemaRegistry(db)

        try:
            # Get all templates with field metadata
            templates_context = await schema_registry.get_all_templates_context()

            all_fields = {}
            for context in templates_context:
                template_name = context.get("template_name", "unknown")
                fields = context.get("fields", {})

                for field_name, field_info in fields.items():
                    if field_name not in all_fields:
                        all_fields[field_name] = {
                            "name": field_name,
                            "type": field_info.get("type", "text"),
                            "description": field_info.get("description", ""),
                            "aliases": field_info.get("aliases", []),
                            "templates": [template_name]
                        }
                    else:
                        # Field exists in multiple templates
                        all_fields[field_name]["templates"].append(template_name)

            # Add system fields
            system_fields = {
                "filename": {"name": "filename", "type": "keyword", "description": "Document filename", "aliases": [], "templates": ["*"]},
                "status": {"name": "status", "type": "keyword", "description": "Processing status", "aliases": [], "templates": ["*"]},
                "uploaded_at": {"name": "uploaded_at", "type": "date", "description": "Upload timestamp", "aliases": [], "templates": ["*"]},
                "folder_path": {"name": "folder_path", "type": "keyword", "description": "Virtual folder path", "aliases": [], "templates": ["*"]},
            }

            all_fields.update(system_fields)

            return {
                "success": True,
                "total_fields": len(all_fields),
                "fields": list(all_fields.values())
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"MCP list fields error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates():
    """
    List all available document templates.

    Returns template names, categories, and field lists.
    """

    from app.core.database import SessionLocal
    from app.models.schema import Schema

    try:
        db = SessionLocal()

        try:
            templates = db.query(Schema).all()

            template_list = []
            for template in templates:
                template_list.append({
                    "id": template.id,
                    "name": template.name,
                    "category": template.category,
                    "description": template.description,
                    "field_count": len(template.fields),
                    "fields": [f["name"] for f in template.fields]
                })

            return {
                "success": True,
                "total_templates": len(template_list),
                "templates": template_list
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"MCP list templates error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_search_stats():
    """
    Get overall search and document statistics.

    Returns counts, distributions, and health metrics.
    """

    elastic_service = ElasticsearchService()

    try:
        # Get comprehensive stats
        aggregations = await elastic_service.get_multi_aggregations(
            aggregations=[
                {"name": "total_docs", "field": "document_id", "type": "cardinality"},
                {"name": "status_breakdown", "field": "status", "type": "terms", "config": {"size": 20}},
                {"name": "template_usage", "field": "_query_context.template_name", "type": "terms", "config": {"size": 20}},
            ]
        )

        return {
            "success": True,
            "statistics": aggregations
        }

    except Exception as e:
        logger.error(f"MCP stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/explain")
async def explain_query(query: str = Query(..., description="Natural language query to explain")):
    """
    Explain how a natural language query will be executed.

    Returns the Elasticsearch query that would be generated,
    along with confidence scores and optimization notes.

    Useful for debugging and understanding query behavior.
    """

    from app.core.database import SessionLocal
    from app.services.schema_registry import SchemaRegistry

    try:
        db = SessionLocal()

        try:
            schema_registry = SchemaRegistry(db)
            query_optimizer = QueryOptimizer(schema_registry=schema_registry)
            await query_optimizer.initialize_from_registry()

            # Get field context
            field_metadata_list = await schema_registry.get_all_templates_context()
            all_field_names = []

            for template_context in field_metadata_list:
                all_field_names.extend(template_context.get("all_field_names", []))

            all_field_names.extend([
                "filename", "uploaded_at", "processed_at",
                "status", "template_name", "confidence_scores", "folder_path"
            ])
            available_fields = list(set(all_field_names))

            # Analyze query
            query_analysis = query_optimizer.understand_query_intent(
                query=query,
                available_fields=available_fields
            )

            # Build ES query
            es_query = query_optimizer.build_optimized_query(
                query=query,
                analysis=query_analysis,
                available_fields=available_fields
            )

            return {
                "success": True,
                "query": query,
                "analysis": {
                    "intent": query_analysis.get("intent"),
                    "confidence": query_analysis.get("confidence"),
                    "query_type": query_analysis.get("query_type"),
                    "target_fields": query_analysis.get("target_fields", []),
                    "filters": query_analysis.get("filters", []),
                    "would_use_claude": query_optimizer.should_use_claude(query_analysis)
                },
                "elasticsearch_query": es_query
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"MCP explain query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
