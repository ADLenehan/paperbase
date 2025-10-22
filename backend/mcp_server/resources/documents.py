"""
Document Resources

Read-only MCP resources for document data.
"""

from typing import Dict, Any
import logging

from mcp_server.services.db_service import db_service

logger = logging.getLogger(__name__)


async def get_document_fields_resource(document_id: int) -> Dict[str, Any]:
    """
    Resource: paperbase://documents/{document_id}/fields

    Returns all extracted fields for a specific document.

    Args:
        document_id: Document ID from URI path

    Returns:
        Document fields with confidence scores
    """
    try:
        doc = await db_service.get_document(document_id)

        if not doc:
            return {
                "uri": f"paperbase://documents/{document_id}/fields",
                "mimeType": "application/json",
                "text": {
                    "error": f"Document {document_id} not found"
                }
            }

        return {
            "uri": f"paperbase://documents/{document_id}/fields",
            "mimeType": "application/json",
            "text": {
                "document_id": document_id,
                "filename": doc["filename"],
                "fields": doc["fields"],
                "template": doc["template"]
            }
        }

    except Exception as e:
        logger.error(f"Error fetching document {document_id} fields resource: {e}", exc_info=True)
        return {
            "uri": f"paperbase://documents/{document_id}/fields",
            "mimeType": "application/json",
            "text": {
                "error": str(e)
            }
        }
