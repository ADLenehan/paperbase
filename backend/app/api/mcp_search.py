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

            # Add LLM-friendly response enhancements
            enhanced_response = response.model_dump()
            enhanced_response["summary"] = f"Found {search_results.get('total', 0)} documents matching '{request.query}'"

            if cleaned_documents:
                enhanced_response["top_result_preview"] = {
                    "id": cleaned_documents[0]["id"],
                    "filename": cleaned_documents[0].get("filename", "Unknown"),
                    "excerpt": str(cleaned_documents[0].get("full_text", ""))[:200] + "..." if cleaned_documents[0].get("full_text") else "No preview"
                }

                enhanced_response["next_steps"] = {
                    "to_read_content": f"Call get_document_content({cleaned_documents[0]['id']}) to read the full text",
                    "to_answer_question": "Call rag_query with a specific question about these documents",
                    "to_analyze": "Call multi_aggregate to calculate statistics across results"
                }
            else:
                enhanced_response["next_steps"] = {
                    "suggestion": "Try broadening your search query or checking filters"
                }

            return enhanced_response

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


@router.get("/document/{document_id}/content")
async def get_document_content_mcp(document_id: int):
    """
    Get full document content for LLM analysis.

    Returns the complete parsed text of the document along with metadata.
    This is the primary tool for LLMs to read and analyze document content.

    **Use Cases:**
    - Full document analysis
    - Summarization
    - Question answering with full context
    - Content extraction
    """

    elastic_service = ElasticsearchService()

    try:
        doc = await elastic_service.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        # Extract full text (may be very long)
        full_text = doc.get("full_text", "")

        # Get metadata
        query_context = doc.get("_query_context", {})

        # Enhanced response with summary and guidance
        return {
            "success": True,
            "summary": f"Document '{doc.get('filename')}' ({len(full_text):,} characters, {len(query_context.get('field_names', []))} fields extracted)",
            "document_id": document_id,
            "filename": doc.get("filename"),
            "content": full_text,
            "content_length": len(full_text),
            "metadata": {
                "uploaded_at": doc.get("uploaded_at"),
                "processed_at": doc.get("processed_at"),
                "template": query_context.get("template_name"),
                "status": doc.get("status"),
                "field_count": len(query_context.get("field_names", []))
            },
            "extracted_fields": {
                k: v for k, v in doc.items()
                if not k.startswith("_") and k not in ["document_id", "filename", "full_text", "uploaded_at", "processed_at", "confidence_scores"]
            },
            "content_preview": full_text[:500] + "..." if len(full_text) > 500 else full_text,
            "next_steps": {
                "to_analyze": "Process this content with your analysis logic",
                "to_chunk": f"If content is too long, use get_document_chunks({document_id}) for paginated access",
                "to_ask_question": "Use rag_query to ask specific questions about this document"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{document_id}/chunks")
async def get_document_chunks_mcp(
    document_id: int,
    chunk_size: int = Query(default=2000, ge=100, le=10000, description="Characters per chunk"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    overlap: int = Query(default=200, ge=0, le=1000, description="Character overlap between chunks")
):
    """
    Get document content in chunks for processing long documents.

    This is useful when documents are too long to fit in a single LLM context window.
    Returns paginated chunks with overlap to maintain context between chunks.

    **Parameters:**
    - chunk_size: Characters per chunk (100-10000)
    - page: Which chunk to return (1-indexed)
    - overlap: Characters to overlap between chunks (maintains context)

    **Use Cases:**
    - Processing very long documents
    - Progressive analysis
    - Memory-efficient document reading
    """

    elastic_service = ElasticsearchService()

    try:
        doc = await elastic_service.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        full_text = doc.get("full_text", "")

        if not full_text:
            return {
                "success": True,
                "document_id": document_id,
                "chunks": [],
                "total_chunks": 0,
                "message": "Document has no text content"
            }

        # Split into chunks with overlap
        chunks = []
        start = 0
        chunk_num = 0

        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))
            chunk_text = full_text[start:end]

            chunk_num += 1
            chunks.append({
                "chunk_number": chunk_num,
                "start_char": start,
                "end_char": end,
                "content": chunk_text,
                "length": len(chunk_text)
            })

            # Move start position with overlap
            start = end - overlap
            if start >= len(full_text):
                break

        # Return requested page
        total_chunks = len(chunks)
        if page > total_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Page {page} out of range. Document has {total_chunks} chunks."
            )

        requested_chunk = chunks[page - 1]

        return {
            "success": True,
            "document_id": document_id,
            "filename": doc.get("filename"),
            "chunk": requested_chunk,
            "pagination": {
                "current_page": page,
                "total_chunks": total_chunks,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "has_next": page < total_chunks,
                "has_previous": page > 1
            },
            "metadata": {
                "total_characters": len(full_text),
                "template": doc.get("_query_context", {}).get("template_name")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/query")
async def rag_query_mcp(
    question: str = Query(..., description="Question to answer"),
    max_results: int = Query(default=5, ge=1, le=20, description="Max documents to use as context"),
    filters: Optional[Dict[str, Any]] = None
):
    """
    Answer a question using the document corpus (RAG - Retrieval Augmented Generation).

    This tool searches the document corpus for relevant information and uses it
    to generate an answer grounded in actual document content.

    **How it works:**
    1. Search for relevant documents matching the question
    2. Extract text from top matching documents
    3. Send question + context to Claude for answering
    4. Return answer with source citations

    **Use Cases:**
    - Question answering grounded in documents
    - Research and discovery
    - Fact checking against corpus
    - Summary generation with citations

    **Example:**
    ```
    Question: "What were the total contract values in Q1 2024?"
    Returns: Answer with specific values and source document references
    ```
    """

    elastic_service = ElasticsearchService()
    claude_service = ClaudeService()

    try:
        from app.core.database import SessionLocal
        from app.services.schema_registry import SchemaRegistry

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
                query=question,
                available_fields=available_fields
            )

            # Build ES query (use optimizer for efficiency)
            if query_optimizer.should_use_claude(query_analysis):
                nl_result = await claude_service.parse_natural_language_query(
                    query=question,
                    available_fields=available_fields,
                    field_metadata=combined_metadata
                )
                es_query = nl_result.get("elasticsearch_query", {}).get("query", {})
            else:
                es_query = query_optimizer.build_optimized_query(
                    query=question,
                    analysis=query_analysis,
                    available_fields=available_fields
                )

            # Add filters if provided
            if filters:
                if "bool" not in es_query:
                    es_query = {"bool": {"must": [es_query] if es_query else [{"match_all": {}}]}}
                if "filter" not in es_query["bool"]:
                    es_query["bool"]["filter"] = []
                for field, value in filters.items():
                    es_query["bool"]["filter"].append({"term": {field: value}})

            # Execute search
            search_results = await elastic_service.search(
                query=None,
                filters=None,
                custom_query=es_query,
                page=1,
                size=max_results
            )

            # Build context from results
            context_chunks = []
            for doc in search_results.get("documents", []):
                data = doc["data"]
                # Get full text (limit to first 2000 chars per doc to avoid token limits)
                text = data.get("full_text", "")[:2000]

                context_chunks.append({
                    "text": text,
                    "source": data.get("filename", "Unknown"),
                    "document_id": doc["id"],
                    "score": doc["score"]
                })

            if not context_chunks:
                return {
                    "success": True,
                    "question": question,
                    "answer": "No relevant documents found to answer this question.",
                    "sources": [],
                    "confidence": "none"
                }

            # Build prompt for Claude
            context_text = "\n\n---\n\n".join([
                f"Document: {c['source']}\n{c['text']}"
                for c in context_chunks
            ])

            prompt = f"""Answer the following question based ONLY on the provided documents.
If the documents don't contain enough information to answer confidently, say so.
Cite the specific documents you used in your answer.

Documents:
{context_text}

Question: {question}

Provide a clear, concise answer with citations to specific documents."""

            # Get answer from Claude
            answer = await claude_service.answer_question_about_results(
                query=question,
                search_results=search_results.get("documents", []),
                total_count=search_results.get("total", 0)
            )

            # Enhanced response with LLM guidance
            response = {
                "success": True,
                "summary": f"Answered based on {len(context_chunks)} relevant documents",
                "question": question,
                "answer": answer,
                "sources": [
                    {
                        "document_id": c["document_id"],
                        "filename": c["source"],
                        "relevance_score": round(c["score"], 3),
                        "excerpt": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"]
                    }
                    for c in context_chunks
                ],
                "confidence": "high" if len(context_chunks) >= 3 else "medium" if len(context_chunks) >= 1 else "low",
                "metadata": {
                    "num_sources": len(context_chunks),
                    "total_matches": search_results.get("total", 0),
                    "query_method": "claude" if query_optimizer.should_use_claude(query_analysis) else "optimizer"
                },
                "next_steps": {
                    "to_read_source": f"Call get_document_content({context_chunks[0]['document_id']}) to read full source document" if context_chunks else None,
                    "to_refine": "Ask a follow-up question with rag_query for more detail",
                    "to_find_more": "Use search_documents to find additional related documents"
                }
            }

            return response

        finally:
            db.close()

    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
