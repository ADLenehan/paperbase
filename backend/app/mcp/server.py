"""
Paperbase MCP Server - Elegant Integration

Exposes existing Paperbase services as MCP tools for Claude and other AI assistants.
All tools are thin wrappers around existing APIs - zero logic duplication.

Usage:
    # Run standalone for testing
    python -m app.mcp.server

    # Or integrated with FastAPI (see main.py)
"""

import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import EmbeddedResource, TextContent, Tool

logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("paperbase")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """
    List all available MCP tools.
    Called by Claude when it first connects.
    """
    return [
        Tool(
            name="search_documents",
            description="""
            Search documents using natural language or filters.

            Examples:
            - "invoices over $1000"
            - "contracts from Acme Corp"
            - "documents uploaded this week"
            - "receipts with missing purchase orders"

            Returns: List of matching documents with metadata and extracted fields.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query or keywords"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters",
                        "properties": {
                            "vendor": {"type": "string"},
                            "amount_min": {"type": "number"},
                            "amount_max": {"type": "number"},
                            "date_from": {"type": "string"},
                            "date_to": {"type": "string"},
                            "template": {"type": "string"}
                        }
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        ),

        Tool(
            name="get_document",
            description="""
            Retrieve a specific document by ID.

            Returns: Full document with all extracted fields, metadata,
            confidence scores, and verification status.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "integer",
                        "description": "Document ID to retrieve"
                    }
                },
                "required": ["document_id"]
            }
        ),

        Tool(
            name="get_audit_queue",
            description="""
            Get documents and fields that need human review.

            Returns items with low confidence scores or flagged anomalies.
            These are part of the Human-in-the-Loop (HITL) workflow.

            Use this to find what needs verification before suggesting corrections.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max items to return",
                        "default": 50
                    },
                    "max_confidence": {
                        "type": "number",
                        "description": "Only show items below this confidence (0-1)",
                        "default": 0.6
                    }
                }
            }
        ),

        Tool(
            name="verify_extraction",
            description="""
            Verify or correct an extracted field value (HITL).

            Use this when you notice an incorrect extraction or want to confirm a value.
            Verifications help the system learn and improve over time.

            Returns: Verification record with updated confidence.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer"},
                    "field_name": {"type": "string"},
                    "verified_value": {
                        "type": "string",
                        "description": "The correct value for this field"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional explanation of the correction"
                    }
                },
                "required": ["document_id", "field_name", "verified_value"]
            }
        ),

        Tool(
            name="get_templates",
            description="""
            List all available document templates/schemas.

            Templates define what fields to extract from different document types
            (invoices, contracts, receipts, etc.).

            Returns: List of templates with field definitions.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    }
                }
            }
        ),

        Tool(
            name="get_statistics",
            description="""
            Get system statistics and analytics.

            Returns document counts, processing stats, confidence distributions,
            and Elasticsearch index health.

            Useful for understanding system status and data quality.
            """,
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """
    Execute an MCP tool.
    Called when Claude invokes a tool.

    This routes to existing Paperbase services - no duplication!
    """
    logger.info(f"MCP tool called: {name} with args: {arguments}")

    try:
        if name == "search_documents":
            return await _search_documents(arguments)

        elif name == "get_document":
            return await _get_document(arguments)

        elif name == "get_audit_queue":
            return await _get_audit_queue(arguments)

        elif name == "verify_extraction":
            return await _verify_extraction(arguments)

        elif name == "get_templates":
            return await _get_templates(arguments)

        elif name == "get_statistics":
            return await _get_statistics(arguments)

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}\n\nPlease check the logs for details."
        )]


# Tool Implementations (thin wrappers around existing services)

async def _search_documents(args: Dict[str, Any]) -> List[TextContent]:
    """
    Search documents using PostgreSQL service.
    Reuses: app/services/postgres_service.py
    """
    from app.core.database import SessionLocal
    from app.services.postgres_service import PostgresService

    query = args.get("query", "")
    filters = args.get("filters", {})
    limit = args.get("limit", 20)

    db = SessionLocal()
    postgres_service = PostgresService(db)

    try:
        # Call existing search method
        results = await postgres_service.search(
            query=query,
            filters=filters,
            page=1,
            size=limit
        )

        documents = results.get("documents", [])
        total = results.get("total", 0)

        if total == 0:
            return [TextContent(
                type="text",
                text=f"No documents found matching '{query}'"
            )]

        # Format results for Claude
        response = f"Found {total} documents (showing {len(documents)}):\n\n"

        for doc in documents[:10]:  # Show first 10
            data = doc.get("data", {})
            response += f"📄 **{data.get('filename', 'Unknown')}**\n"
            response += f"   ID: {data.get('document_id')}\n"

            # Show key extracted fields
            for field, value in data.items():
                if field.startswith("_") or field in ["document_id", "filename", "full_text"]:
                    continue

                # Show confidence if available
                confidence = data.get("confidence_scores", {}).get(field)
                conf_str = f" (confidence: {confidence:.2f})" if confidence else ""

                response += f"   {field}: {value}{conf_str}\n"

            response += "\n"

        if total > 10:
            response += f"... and {total - 10} more documents\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()


async def _get_document(args: Dict[str, Any]) -> List[TextContent]:
    """
    Get a specific document.
    Reuses: app/services/postgres_service.py
    """
    from app.core.database import SessionLocal
    from app.services.postgres_service import PostgresService

    doc_id = args.get("document_id")

    db = SessionLocal()
    postgres_service = PostgresService(db)

    try:
        doc = await postgres_service.get_document(doc_id)

        if not doc:
            return [TextContent(
                type="text",
                text=f"Document {doc_id} not found"
            )]

        # Format document for Claude
        response = f"📄 **Document {doc_id}**: {doc.get('filename')}\n\n"
        response += "**Extracted Fields:**\n"

        for field, value in doc.items():
            # Skip metadata
            if field.startswith("_") or field in ["document_id", "filename", "full_text"]:
                continue

            # Show confidence
            confidence = doc.get("confidence_scores", {}).get(field)
            conf_str = f" (confidence: {confidence:.2f})" if confidence else ""

            response += f"  • **{field}**: {value}{conf_str}\n"

        # Show verification status
        response += "\n**Status:**\n"
        verified_count = sum(1 for k, v in doc.items() if isinstance(v, dict) and v.get("verified"))
        response += f"  • {verified_count} fields verified\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()


async def _get_audit_queue(args: Dict[str, Any]) -> List[TextContent]:
    """
    Get items needing review.
    Reuses: app/api/audit.py
    """
    from app.core.database import SessionLocal
    from app.models.document import Document, ExtractedField

    limit = args.get("limit", 50)
    max_confidence = args.get("max_confidence", 0.6)

    db = SessionLocal()

    try:
        # Query low-confidence fields (reuses existing logic)
        fields = db.query(ExtractedField).join(Document).filter(
            ExtractedField.confidence < max_confidence,
            ExtractedField.verified == False
        ).order_by(
            ExtractedField.confidence.asc()
        ).limit(limit).all()

        if not fields:
            return [TextContent(
                type="text",
                text="✓ Audit queue is empty - all extractions look good!"
            )]

        response = f"Found {len(fields)} items needing review:\n\n"

        for field in fields[:10]:  # Show first 10
            doc = field.document
            response += f"📋 **Document {doc.id}**: {doc.filename}\n"
            response += f"   Field: **{field.field_name}**\n"
            response += f"   Value: {field.field_value}\n"
            response += f"   Confidence: {field.confidence:.2f}\n"

            # Suggest why it needs review
            if field.confidence < 0.3:
                response += "   ⚠️ Very low confidence - likely incorrect\n"
            elif field.confidence < 0.5:
                response += "   ⚠️ Low confidence - please verify\n"
            else:
                response += "   ℹ️ Medium confidence - quick check recommended\n"

            response += "\n"

        if len(fields) > 10:
            response += f"... and {len(fields) - 10} more items\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()


async def _verify_extraction(args: Dict[str, Any]) -> List[TextContent]:
    """
    Submit a verification.
    Reuses: app/api/audit.py verification logic
    """
    from datetime import datetime

    from app.core.database import SessionLocal
    from app.models.document import ExtractedField
    from app.models.verification import Verification

    doc_id = args["document_id"]
    field_name = args["field_name"]
    verified_value = args["verified_value"]
    notes = args.get("notes", "")

    db = SessionLocal()

    try:
        # Find the extracted field
        field = db.query(ExtractedField).filter(
            ExtractedField.document_id == doc_id,
            ExtractedField.field_name == field_name
        ).first()

        if not field:
            return [TextContent(
                type="text",
                text=f"Field '{field_name}' not found for document {doc_id}"
            )]

        # Create verification record
        verification = Verification(
            document_id=doc_id,
            field_name=field_name,
            original_value=field.field_value,
            verified_value=verified_value,
            verified_by="claude_mcp",
            verified_at=datetime.utcnow(),
            notes=notes
        )

        db.add(verification)

        # Update field
        field.field_value = verified_value
        field.verified = True
        field.confidence = 1.0  # Human-verified is 100% confident

        db.commit()

        return [TextContent(
            type="text",
            text=f"✓ Verified **{field_name}** = '{verified_value}' for document {doc_id}"
        )]

    finally:
        db.close()


async def _get_templates(args: Dict[str, Any]) -> List[TextContent]:
    """
    List templates.
    Reuses: app/models/template.py
    """
    from app.core.database import SessionLocal
    from app.models.template import SchemaTemplate

    category = args.get("category")

    db = SessionLocal()

    try:
        query = db.query(SchemaTemplate)

        if category:
            query = query.filter(SchemaTemplate.category == category)

        templates = query.all()

        if not templates:
            return [TextContent(
                type="text",
                text="No templates found"
            )]

        response = f"Found {len(templates)} templates:\n\n"

        for template in templates:
            response += f"📋 **{template.name}**\n"
            response += f"   Category: {template.category}\n"
            response += f"   Fields: {len(template.fields)} fields\n"

            # Show field names
            field_names = [f["name"] for f in template.fields]
            response += f"   ({', '.join(field_names[:5])}"
            if len(field_names) > 5:
                response += f", +{len(field_names) - 5} more"
            response += ")\n\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()


async def _get_statistics(args: Dict[str, Any]) -> List[TextContent]:
    """
    Get system statistics.
    Reuses: postgres_service.get_index_stats() and DB queries
    """
    from app.core.database import SessionLocal
    from app.models.document import Document
    from app.services.postgres_service import PostgresService

    postgres_service = PostgresService(db)
    db = SessionLocal()

    try:
        # Get ES stats
        es_stats = await postgres_service.get_index_stats()

        # Get document counts by status
        total_docs = db.query(Document).count()
        processing = db.query(Document).filter(Document.status == "processing").count()
        completed = db.query(Document).filter(Document.status == "completed").count()
        failed = db.query(Document).filter(Document.status == "failed").count()

        response = "📊 **Paperbase Statistics**\n\n"

        response += "**Documents:**\n"
        response += f"  • Total: {total_docs}\n"
        response += f"  • Completed: {completed}\n"
        response += f"  • Processing: {processing}\n"
        response += f"  • Failed: {failed}\n\n"

        response += "**Elasticsearch:**\n"
        response += f"  • Indexed documents: {es_stats['document_count']}\n"
        response += f"  • Storage: {es_stats['storage_size_mb']} MB\n"
        response += f"  • Fields: {es_stats['field_count']}/{es_stats['field_limit']}\n"
        response += f"  • Health: {es_stats['health_status']}\n\n"

        if es_stats.get('recommendations'):
            response += "**Recommendations:**\n"
            for rec in es_stats['recommendations']:
                response += f"  • {rec}\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()
        db.close()


# Resources (read-only data sources)

@app.list_resources()
async def list_resources() -> List[EmbeddedResource]:
    """
    List available resources.
    Resources provide read-only access to data.
    """
    return [
        EmbeddedResource(
            uri="paperbase://templates",
            name="Document Templates",
            description="List of all available document templates/schemas",
            mimeType="application/json"
        ),
        EmbeddedResource(
            uri="paperbase://stats",
            name="System Statistics",
            description="Document counts, processing stats, index health",
            mimeType="application/json"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI"""
    if uri == "paperbase://templates":
        from app.core.database import SessionLocal
        from app.models.template import SchemaTemplate

        db = SessionLocal()
        try:
            templates = db.query(SchemaTemplate).all()

            template_list = [
                {
                    "id": t.id,
                    "name": t.name,
                    "category": t.category,
                    "fields": t.fields
                }
                for t in templates
            ]

            return json.dumps(template_list, indent=2)
        finally:
            db.close()

    elif uri == "paperbase://stats":
        # Return statistics
        result = await _get_statistics({})
        return result[0].text

    else:
        raise ValueError(f"Unknown resource: {uri}")


# Entry point for standalone testing
if __name__ == "__main__":
    import asyncio

    async def main():
        # Run server with stdio transport (for Claude Desktop)
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

    asyncio.run(main())
