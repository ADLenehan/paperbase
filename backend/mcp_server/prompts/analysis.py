"""
Analysis Prompts

Reusable prompt templates for document analysis workflows.
"""

from typing import Dict, Any
import logging

from mcp_server.services.db_service import db_service

logger = logging.getLogger(__name__)


async def analyze_low_confidence_prompt() -> Dict[str, Any]:
    """
    Prompt: analyze-low-confidence

    Template for analyzing the audit queue and identifying patterns
    in low-confidence extractions.

    Returns:
        Prompt with instructions and current audit queue data
    """
    try:
        # Get current audit queue
        queue = await db_service.get_audit_queue(limit=50)

        # Get stats for context
        stats = await db_service.get_daily_stats(days=7)

        prompt_text = f"""# Analyze Low-Confidence Extractions

I need help analyzing document extractions that have low confidence scores.

## Current Audit Queue
- Pending review: {len(queue)} fields
- Average confidence: {stats.get('avg_confidence', 0.0):.2f}
- Verification rate: {stats.get('verification_rate', 0.0):.1f}%

## Top Low-Confidence Items
"""
        # Add top 10 items
        for i, item in enumerate(queue[:10], 1):
            prompt_text += f"\n{i}. **{item['field_name']}** in {item['filename']}\n"
            prompt_text += f"   - Value: {item['field_value']}\n"
            prompt_text += f"   - Confidence: {item['confidence']:.2f}\n"

        prompt_text += """

## Please analyze:
1. Are there patterns in which fields have low confidence?
2. Are certain document types more problematic?
3. What improvements could increase extraction accuracy?
4. Should confidence thresholds be adjusted?

Use the `get_audit_queue` and `get_extraction_stats` tools to gather more data as needed.
"""

        return {
            "name": "analyze-low-confidence",
            "description": "Analyze low-confidence extractions and identify improvement opportunities",
            "arguments": [],
            "prompt": prompt_text
        }

    except Exception as e:
        logger.error(f"Error generating analyze-low-confidence prompt: {e}", exc_info=True)
        return {
            "name": "analyze-low-confidence",
            "description": "Analyze low-confidence extractions",
            "arguments": [],
            "prompt": f"Error loading audit data: {str(e)}"
        }


async def compare_templates_prompt(template_ids: str = "") -> Dict[str, Any]:
    """
    Prompt: compare-templates

    Template for comparing multiple document templates to understand
    similarities and differences.

    Args:
        template_ids: Comma-separated template IDs (e.g., "1,2,3")

    Returns:
        Prompt for template comparison
    """
    try:
        # Get all templates for context
        templates = await db_service.get_all_templates()

        prompt_text = """# Compare Document Templates

I need to compare document templates to understand their similarities and differences.

## Available Templates
"""
        for template in templates:
            prompt_text += f"\n- **{template['name']}** (ID: {template['id']}) - {len(template['fields'])} fields"

        if template_ids:
            ids = [int(id.strip()) for id in template_ids.split(",")]
            prompt_text += f"\n\n## Templates to Compare\nIDs: {ids}\n"
        else:
            prompt_text += "\n\n## Please specify which templates to compare\n"
            prompt_text += "Provide template IDs separated by commas (e.g., 1,2,3)\n"

        prompt_text += """

## Analysis Questions:
1. What fields do these templates have in common?
2. What unique fields does each template have?
3. Could any templates be merged or standardized?
4. Are there naming inconsistencies across templates?

Use the `compare_templates` tool with the template IDs to perform the comparison.
"""

        return {
            "name": "compare-templates",
            "description": "Compare multiple document templates",
            "arguments": [
                {
                    "name": "template_ids",
                    "description": "Comma-separated template IDs to compare",
                    "required": False
                }
            ],
            "prompt": prompt_text
        }

    except Exception as e:
        logger.error(f"Error generating compare-templates prompt: {e}", exc_info=True)
        return {
            "name": "compare-templates",
            "description": "Compare document templates",
            "arguments": [],
            "prompt": f"Error loading template data: {str(e)}"
        }


async def document_summary_prompt(document_id: int = None) -> Dict[str, Any]:
    """
    Prompt: document-summary

    Template for generating a comprehensive summary of a document's
    extraction results and quality.

    Args:
        document_id: Optional document ID to analyze

    Returns:
        Prompt for document summary
    """
    try:
        if document_id:
            # Get document details
            doc = await db_service.get_document(document_id)

            if doc:
                prompt_text = f"""# Document Extraction Summary

Analyze the extraction results for **{doc['filename']}** (ID: {document_id})

## Document Information
- Status: {doc['status']}
- Template: {doc['template']['name'] if doc['template'] else 'None'}
- Uploaded: {doc['uploaded_at']}
- Total Fields: {len(doc['fields'])}

## Extracted Fields
"""
                for field in doc['fields']:
                    status = "✓" if field['verified'] else ("⚠" if field['needs_verification'] else "○")
                    prompt_text += f"\n{status} **{field['name']}**: {field['value']} (confidence: {field['confidence']:.2f})"

                prompt_text += """

## Please provide:
1. Overall extraction quality assessment
2. Fields that may need verification
3. Any anomalies or concerns
4. Recommendations for improvement
"""
            else:
                prompt_text = f"Document {document_id} not found. Please provide a valid document ID."
        else:
            prompt_text = """# Document Extraction Summary

Please provide a document ID to analyze.

Use the `search_documents` tool to find documents, or `get_recent_documents` to see recent uploads.

Example: document-summary(document_id=123)
"""

        return {
            "name": "document-summary",
            "description": "Generate comprehensive document extraction summary",
            "arguments": [
                {
                    "name": "document_id",
                    "description": "Document ID to analyze",
                    "required": False
                }
            ],
            "prompt": prompt_text
        }

    except Exception as e:
        logger.error(f"Error generating document-summary prompt: {e}", exc_info=True)
        return {
            "name": "document-summary",
            "description": "Document extraction summary",
            "arguments": [],
            "prompt": f"Error loading document data: {str(e)}"
        }
