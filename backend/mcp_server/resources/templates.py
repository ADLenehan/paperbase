"""
Template Resources

Read-only MCP resources for template data.
URI format: paperbase://templates or paperbase://templates/{template_id}
"""

from typing import Dict, Any
import logging

from mcp_server.services.db_service import db_service

logger = logging.getLogger(__name__)


async def get_all_templates_resource() -> Dict[str, Any]:
    """
    Resource: paperbase://templates

    Returns all available templates with field definitions.
    This is a frequently accessed resource, heavily cached.

    Returns:
        Template list with metadata
    """
    try:
        templates = await db_service.get_all_templates()

        return {
            "uri": "paperbase://templates",
            "mimeType": "application/json",
            "text": {
                "templates": templates,
                "total": len(templates),
                "description": "All document extraction templates"
            }
        }

    except Exception as e:
        logger.error(f"Error fetching templates resource: {e}", exc_info=True)
        return {
            "uri": "paperbase://templates",
            "mimeType": "application/json",
            "text": {
                "error": str(e),
                "templates": []
            }
        }


async def get_template_resource(template_id: int) -> Dict[str, Any]:
    """
    Resource: paperbase://templates/{template_id}

    Returns specific template with detailed field definitions and usage stats.

    Args:
        template_id: Template ID from URI path

    Returns:
        Template details
    """
    try:
        template = await db_service.get_template(template_id)

        if not template:
            return {
                "uri": f"paperbase://templates/{template_id}",
                "mimeType": "application/json",
                "text": {
                    "error": f"Template {template_id} not found"
                }
            }

        return {
            "uri": f"paperbase://templates/{template_id}",
            "mimeType": "application/json",
            "text": template
        }

    except Exception as e:
        logger.error(f"Error fetching template {template_id} resource: {e}", exc_info=True)
        return {
            "uri": f"paperbase://templates/{template_id}",
            "mimeType": "application/json",
            "text": {
                "error": str(e)
            }
        }
