"""
Paperbase MCP Server

Main FastMCP server instance with all tools, resources, and prompts.
"""

from fastmcp import FastMCP
from typing import Optional, List, Dict, Any
import logging

from mcp_server.config import config
from mcp_server.tools import documents, templates, analytics, audit, ai_search
from mcp_server.resources import templates as template_resources
from mcp_server.resources import stats as stats_resources
from mcp_server.resources import documents as document_resources
from mcp_server.prompts import analysis

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name=config.SERVER_NAME,
    version=config.VERSION,
    instructions=config.DESCRIPTION  # FastMCP uses 'instructions' not 'description'
)

logger.info(f"Initializing {config.SERVER_NAME} v{config.VERSION}")


# ==================== TOOLS ====================

@mcp.tool()
async def search_documents(
    query: str,
    folder_path: Optional[str] = None,
    template_name: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search documents using natural language or keywords with intelligent query understanding.

    Args:
        query: Natural language search query (e.g., "invoices over $1000 from last week")
        folder_path: Optional folder path to restrict search
        template_name: Filter by template name
        status: Filter by document status
        min_confidence: Minimum average confidence score (0.0-1.0)
        limit: Maximum number of results (max: 100)

    Returns:
        Search results with documents and query analysis
    """
    return await documents.search_documents(
        query=query,
        folder_path=folder_path,
        template_name=template_name,
        status=status,
        min_confidence=min_confidence,
        limit=limit
    )


@mcp.tool()
async def get_document_details(document_id: int) -> Dict[str, Any]:
    """
    Get complete details for a specific document including all extracted fields.

    IMPORTANT: Always display confidence scores with field values in your response.
    Users need to see confidence to know which fields need verification.

    Args:
        document_id: Document ID

    Returns:
        Document metadata, template info, and all extracted fields with confidence scores.
        Each field includes: name, value, confidence (0.0-1.0), verified status, needs_verification flag.

        Always format responses to show: "field: value (confidence: X%)" or use visual indicators.
    """
    return await documents.get_document_details(document_id)


@mcp.tool()
async def get_document_by_filename(
    filename: str,
    exact_match: bool = False
) -> Dict[str, Any]:
    """
    Find document(s) by filename with FULL extracted fields and confidence scores.

    This tool automatically returns ALL extracted fields with confidence scores
    for each matching document. No need to make a second call!

    IMPORTANT: ALWAYS display the confidence scores in your response.
    Format as: "field: value (confidence: X%)" or use visual indicators.

    Args:
        filename: Filename to search for
        exact_match: If True, requires exact match; if False, uses partial matching

    Returns:
        List of matching documents, each containing:
        - Document metadata (filename, status, template, dates)
        - ALL extracted fields with confidence scores (0.0-1.0)
        - Verification status for each field

        Example response format:
        "Found Pinecone document with the following fields:
        - Primary Cloud Provider: AWS (confidence: 95%)
        - AWS Bedrock Integration: One-click Knowledge Bases (confidence: 88%)
        - Partnership Status: AWS Partner of the Year 2024 (confidence: 92%)"
    """
    return await documents.get_document_by_filename(filename, exact_match)


@mcp.tool()
async def list_templates() -> Dict[str, Any]:
    """
    Get all available document templates with field definitions.

    Returns:
        List of templates with metadata
    """
    return await templates.list_templates()


@mcp.tool()
async def get_template_details(template_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific template including usage statistics.

    Args:
        template_id: Template ID

    Returns:
        Template details with field definitions and stats
    """
    return await templates.get_template_details(template_id)


@mcp.tool()
async def get_template_stats(
    template_id: Optional[int] = None,
    include_field_stats: bool = False
) -> Dict[str, Any]:
    """
    Get usage statistics for template(s).

    Args:
        template_id: Specific template ID, or None for all templates
        include_field_stats: Include per-field confidence statistics

    Returns:
        Template usage statistics
    """
    return await templates.get_template_stats(template_id, include_field_stats)


@mcp.tool()
async def compare_templates(template_ids: List[int]) -> Dict[str, Any]:
    """
    Compare multiple templates to identify common and unique fields.

    Args:
        template_ids: List of template IDs to compare (2-5 templates)

    Returns:
        Comparison showing common fields and unique fields per template
    """
    return await templates.compare_templates(template_ids)


@mcp.tool()
async def get_extraction_stats(
    days: int = 7,
    template_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get document extraction statistics for a time period.

    Args:
        days: Number of days to analyze (default: 7)
        template_id: Optional filter by specific template

    Returns:
        Extraction statistics including upload counts, confidence, and verification rates
    """
    return await analytics.get_extraction_stats(days, template_id)


@mcp.tool()
async def get_audit_queue(
    confidence_threshold: Optional[float] = None,
    template_id: Optional[int] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get audit queue of fields needing human verification.

    Returns fields with confidence below threshold or manually flagged,
    sorted by confidence (lowest first).

    Args:
        confidence_threshold: Maximum confidence for inclusion (default: 0.6)
        template_id: Optional filter by template
        limit: Maximum number of items (max: 200)

    Returns:
        List of fields needing verification with document context
    """
    return await audit.get_audit_queue(confidence_threshold, template_id, limit)


@mcp.tool()
async def get_low_confidence_fields(
    min_confidence: float = 0.0,
    max_confidence: float = 0.6,
    field_name: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get fields within a specific confidence range for quality analysis.

    Args:
        min_confidence: Minimum confidence (inclusive)
        max_confidence: Maximum confidence (inclusive)
        field_name: Optional filter by field name
        limit: Maximum results

    Returns:
        List of fields in confidence range
    """
    return await audit.get_low_confidence_fields(
        min_confidence, max_confidence, field_name, limit
    )


@mcp.tool()
async def get_audit_stats() -> Dict[str, Any]:
    """
    Get overall audit queue statistics including pending reviews and verification rates.

    Returns:
        Audit statistics summary
    """
    return await audit.get_audit_stats()


@mcp.tool()
async def ask_ai(
    query: str,
    folder_path: Optional[str] = None,
    template_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ask AI a natural language question about your documents with inline confidence indicators.

    This tool provides AI-generated answers with confidence scores displayed inline,
    making it easy to see which values need verification. Each query is saved with a
    unique ID that allows viewing all source documents used in the answer.

    Args:
        query: Natural language question (e.g., "What is the back rise for size 2?")
        folder_path: Optional folder to search within
        template_id: Optional template filter (e.g., "schema_15")

    Returns:
        AI-generated answer with:
        - Inline confidence indicators like [75% ⚠️]
        - query_id: Unique identifier for this query
        - documents_link: URL to view all source documents
        - view_source_documents: Human-readable link message

    Example:
        Query: "What is the back rise for size 2 in GLNLEG?"
        Answer: "The back rise for size 2 is 7 1/2 inches [75% ⚠️]"
        Documents: "View the 3 source documents used in this answer: http://localhost:3000/documents?query_id=abc-123"

    Confidence indicators:
        [95% ✓] = High confidence (≥80%)
        [72% ⚠️] = Medium confidence (60-80%)
        [45% ⚠️ LOW] = Low confidence (<60%) - needs verification

    IMPORTANT: Always display the documents_link or view_source_documents in your response
    so users can see which documents contributed to the answer.
    """
    return await ai_search.ask_ai(query, folder_path, template_id)


# ==================== RESOURCES ====================

@mcp.resource("paperbase://templates")
async def templates_resource() -> str:
    """All available document templates"""
    import json
    result = await template_resources.get_all_templates_resource()
    return json.dumps(result["text"], indent=2)


@mcp.resource("paperbase://templates/{template_id}")
async def template_resource(template_id: int) -> str:
    """Specific template details"""
    import json
    result = await template_resources.get_template_resource(template_id)
    return json.dumps(result["text"], indent=2)


@mcp.resource("paperbase://stats/daily")
async def daily_stats_resource() -> str:
    """Daily processing statistics (last 7 days)"""
    import json
    result = await stats_resources.get_daily_stats_resource(days=7)
    return json.dumps(result["text"], indent=2)


@mcp.resource("paperbase://system/health")
async def system_health_resource() -> str:
    """System health status"""
    import json
    result = await stats_resources.get_system_health_resource()
    return json.dumps(result["text"], indent=2)


@mcp.resource("paperbase://stats/audit")
async def audit_summary_resource() -> str:
    """Audit queue summary statistics"""
    import json
    result = await stats_resources.get_audit_summary_resource()
    return json.dumps(result["text"], indent=2)


@mcp.resource("paperbase://documents/{document_id}/fields")
async def document_fields_resource(document_id: int) -> str:
    """Extracted fields for a specific document"""
    import json
    result = await document_resources.get_document_fields_resource(document_id)
    return json.dumps(result["text"], indent=2)


# ==================== PROMPTS ====================

@mcp.prompt()
async def analyze_low_confidence() -> str:
    """Analyze low-confidence extractions and identify improvement opportunities"""
    result = await analysis.analyze_low_confidence_prompt()
    return result["prompt"]


@mcp.prompt()
async def compare_templates_prompt(template_ids: str = "") -> str:
    """Compare multiple document templates to understand similarities and differences"""
    result = await analysis.compare_templates_prompt(template_ids)
    return result["prompt"]


@mcp.prompt()
async def document_summary(document_id: Optional[int] = None) -> str:
    """Generate comprehensive document extraction summary"""
    result = await analysis.document_summary_prompt(document_id)
    return result["prompt"]


# ==================== LIFECYCLE ====================

# Note: FastMCP 2.x uses lifespan context manager instead of on_startup/on_shutdown decorators
# Services are initialized as globals and cleaned up automatically

# @mcp.on_startup() - Not available in FastMCP 2.x
# async def on_startup():
#     """Initialize services on server startup"""
#     logger.info("MCP server starting up...")
#     # Services are already initialized as globals
#     logger.info("MCP server ready")


# @mcp.on_shutdown() - Not available in FastMCP 2.x
# async def on_shutdown():
#     """Cleanup on server shutdown"""
#     logger.info("MCP server shutting down...")
#     from mcp_server.services.db_service import db_service
#     from mcp_server.services.es_service import es_mcp_service
#
#     await db_service.close()
#     await es_mcp_service.close()
#     logger.info("MCP server shutdown complete")


# Export server instance
__all__ = ["mcp"]
