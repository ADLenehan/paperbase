"""
Template Tools for MCP Server

Tools for managing and querying document templates.
"""

from typing import Optional, List, Dict, Any
import logging

from mcp_server.services.db_service import db_service

logger = logging.getLogger(__name__)


async def list_templates() -> Dict[str, Any]:
    """
    Get all available document templates.

    Returns list of templates with their field definitions,
    creation dates, and usage statistics.

    Returns:
        List of templates with metadata

    Examples:
        >>> list_templates()
        {
            "templates": [
                {
                    "id": 1,
                    "name": "Invoice",
                    "fields": [...],
                    "created_at": "2024-01-15T10:30:00"
                },
                ...
            ],
            "total": 5
        }
    """
    try:
        templates = await db_service.get_all_templates()

        return {
            "templates": templates,
            "total": len(templates)
        }

    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        return {
            "error": str(e),
            "templates": [],
            "total": 0
        }


async def get_template_details(template_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific template.

    Includes field definitions, usage statistics, average confidence,
    and document count.

    Args:
        template_id: Template ID

    Returns:
        Template details with statistics

    Examples:
        >>> get_template_details(1)
        {
            "id": 1,
            "name": "Invoice",
            "fields": [
                {
                    "name": "total_amount",
                    "type": "number",
                    "required": true,
                    "description": "Invoice total amount"
                },
                ...
            ],
            "stats": {
                "document_count": 150,
                "avg_confidence": 0.89
            }
        }
    """
    try:
        template = await db_service.get_template(template_id)

        if not template:
            return {
                "error": f"Template {template_id} not found",
                "id": template_id
            }

        return template

    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}", exc_info=True)
        return {
            "error": str(e),
            "id": template_id
        }


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

    Examples:
        >>> get_template_stats()  # All templates
        >>> get_template_stats(template_id=1, include_field_stats=True)
    """
    try:
        if template_id:
            # Get stats for specific template
            template = await db_service.get_template(template_id)
            if not template:
                return {
                    "error": f"Template {template_id} not found",
                    "id": template_id
                }

            result = {
                "template_id": template_id,
                "template_name": template["name"],
                "stats": template["stats"]
            }

            if include_field_stats:
                # TODO: Add per-field statistics
                result["field_stats"] = []

            return result

        else:
            # Get stats for all templates
            templates = await db_service.get_all_templates()
            stats_list = []

            for template in templates:
                template_with_stats = await db_service.get_template(template["id"])
                stats_list.append({
                    "template_id": template["id"],
                    "template_name": template["name"],
                    "document_count": template_with_stats["stats"]["document_count"],
                    "avg_confidence": template_with_stats["stats"]["avg_confidence"]
                })

            return {
                "templates": stats_list,
                "total_templates": len(stats_list)
            }

    except Exception as e:
        logger.error(f"Error getting template stats: {e}", exc_info=True)
        return {
            "error": str(e)
        }


async def compare_templates(
    template_ids: List[int]
) -> Dict[str, Any]:
    """
    Compare multiple templates side-by-side.

    Useful for understanding differences between similar document types.

    Args:
        template_ids: List of template IDs to compare (2-5 templates)

    Returns:
        Comparison of templates showing common and unique fields

    Examples:
        >>> compare_templates([1, 2, 3])  # Compare Invoice, Receipt, Bill
    """
    try:
        if len(template_ids) < 2:
            return {
                "error": "Please provide at least 2 templates to compare",
                "template_ids": template_ids
            }

        if len(template_ids) > 5:
            return {
                "error": "Maximum 5 templates can be compared at once",
                "template_ids": template_ids
            }

        # Get all templates
        templates = []
        for template_id in template_ids:
            template = await db_service.get_template(template_id)
            if template:
                templates.append(template)
            else:
                logger.warning(f"Template {template_id} not found, skipping")

        if len(templates) < 2:
            return {
                "error": "Not enough valid templates found",
                "template_ids": template_ids
            }

        # Extract field names from each template
        all_field_names = set()
        template_fields = {}

        for template in templates:
            field_names = [field["name"] for field in template["fields"]]
            template_fields[template["id"]] = set(field_names)
            all_field_names.update(field_names)

        # Find common and unique fields
        common_fields = set.intersection(*template_fields.values())
        unique_fields = {}

        for template in templates:
            unique_fields[template["name"]] = list(
                template_fields[template["id"]] - common_fields
            )

        return {
            "templates_compared": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "field_count": len(t["fields"])
                }
                for t in templates
            ],
            "common_fields": list(common_fields),
            "unique_fields": unique_fields,
            "total_unique_fields": len(all_field_names)
        }

    except Exception as e:
        logger.error(f"Error comparing templates: {e}", exc_info=True)
        return {
            "error": str(e),
            "template_ids": template_ids
        }
