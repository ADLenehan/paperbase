from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.schema import Schema
from app.services.elastic_service import ElasticsearchService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search/suggestions", tags=["search"])


@router.get("")
async def get_query_suggestions(
    template_id: Optional[int] = None,
    folder_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate template-aware query suggestions based on context.

    This endpoint provides smart, contextual query suggestions that help users
    discover powerful search capabilities based on the template/folder they're viewing.

    Args:
        template_id: Optional template ID to generate specific suggestions
        folder_path: Optional folder path (e.g., "invoices/acme-corp")

    Returns:
        {
            "suggestions": ["query1", "query2", ...],
            "context": "invoices" | "contracts" | "general",
            "field_hints": ["field1", "field2", ...]  # Common fields for this template
        }
    """
    elastic_service = ElasticsearchService()

    try:
        # If template_id provided, generate template-specific suggestions
        if template_id:
            template = db.query(Schema).filter(
                Schema.id == template_id
            ).first()

            if not template:
                raise HTTPException(status_code=404, detail="Template not found")

            # Extract field names from schema
            fields = template.fields if hasattr(template, 'fields') else []
            field_names = [f.get("name", f.get("field_name", "")) for f in fields if f]

            # Get common field types for smart suggestions
            amount_fields = [f for f in field_names if any(keyword in f.lower()
                for keyword in ['amount', 'total', 'price', 'cost', 'value'])]
            date_fields = [f for f in field_names if any(keyword in f.lower()
                for keyword in ['date', 'time', 'when', 'period'])]
            name_fields = [f for f in field_names if any(keyword in f.lower()
                for keyword in ['name', 'vendor', 'client', 'company', 'supplier'])]

            # Generate template-specific suggestions
            template_name_lower = template.name.lower()
            suggestions = []

            # Time-based queries
            if date_fields:
                suggestions.extend([
                    f"Show me all {template_name_lower} from last week",
                    f"Find {template_name_lower} from the last 30 days",
                    f"Which {template_name_lower} were processed in October?"
                ])

            # Amount/value queries
            if amount_fields:
                field = amount_fields[0]
                suggestions.extend([
                    f"Show me {template_name_lower} where {field} is over $1000",
                    f"What's the total {field} across all {template_name_lower}?",
                    f"Find {template_name_lower} with the highest {field}"
                ])

            # Name/entity queries
            if name_fields:
                field = name_fields[0]
                suggestions.extend([
                    f"Group {template_name_lower} by {field}",
                    f"Show me all {template_name_lower} from [specific {field}]",
                    f"Which {field} appears most frequently?"
                ])

            # Quality/confidence queries
            suggestions.extend([
                f"Find {template_name_lower} with low confidence scores",
                f"Show me {template_name_lower} that need review",
                f"Which {template_name_lower} have been verified?"
            ])

            # Pattern/anomaly queries
            suggestions.extend([
                f"Find duplicate {template_name_lower}",
                f"Show me unusual {template_name_lower}",
                f"Compare this month vs last month for {template_name_lower}"
            ])

            return {
                "suggestions": suggestions[:8],  # Return top 8
                "context": template_name_lower,
                "field_hints": field_names[:5],  # Top 5 fields
                "template_id": template_id
            }

        # If folder_path provided, infer template from path
        elif folder_path:
            # Extract template name from folder path (e.g., "invoices/acme" -> "invoices")
            template_context = folder_path.split('/')[0].lower()

            # Try to find matching template
            template = db.query(Schema).filter(
                Schema.name.ilike(f"%{template_context}%")
            ).first()

            if template:
                # Recursively call with template_id
                return await get_query_suggestions(
                    template_id=template.id,
                    folder_path=None,
                    db=db
                )

            # Fallback: context-based suggestions without specific template
            suggestions = _get_context_suggestions(template_context)
            return {
                "suggestions": suggestions,
                "context": template_context,
                "field_hints": []
            }

        # No context provided - return general suggestions
        else:
            suggestions = [
                "Show me all documents from last week",
                "Find documents with low confidence scores",
                "Which documents need review?",
                "Show me invoices over $1,000",
                "Find contracts expiring soon",
                "What documents were uploaded today?",
                "Show me documents by vendor",
                "Find duplicate documents"
            ]

            return {
                "suggestions": suggestions,
                "context": "general",
                "field_hints": []
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating query suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate suggestions: {str(e)}"
        )


def _get_context_suggestions(context: str) -> List[str]:
    """Generate context-aware suggestions based on folder name"""

    # Context-specific suggestion templates
    context_suggestions = {
        "invoice": [
            "Show me all invoices from last month",
            "Find unpaid invoices",
            "Which vendors have we paid the most?",
            "Show me invoices over $1,000",
            "Find invoices with missing purchase orders",
            "Group invoices by vendor",
            "Show me duplicate invoices",
            "What's our total spending this quarter?"
        ],
        "contract": [
            "Contracts expiring in the next 30 days",
            "Show me all active contracts",
            "Find contracts with auto-renewal clauses",
            "Which contracts are up for review?",
            "Group contracts by vendor",
            "Show me contracts over $100,000",
            "Find contracts with specific terms",
            "What contracts were signed this year?"
        ],
        "receipt": [
            "Show me all receipts from last week",
            "Find receipts over $100",
            "Group receipts by category",
            "Show me receipts without tax information",
            "Find duplicate receipts",
            "What's the total from all receipts?",
            "Show me receipts from specific vendors",
            "Find receipts that need review"
        ],
        "po": [  # Purchase Orders
            "Show me open purchase orders",
            "Find POs over $10,000",
            "Which POs are pending approval?",
            "Group POs by department",
            "Show me POs from last quarter",
            "Find POs without matching invoices",
            "What's the total value of all POs?",
            "Show me POs by vendor"
        ]
    }

    # Find matching context (partial match)
    for key, suggestions in context_suggestions.items():
        if key in context.lower():
            return suggestions

    # Default general suggestions
    return [
        f"Show me all {context} from last month",
        f"Find {context} that need review",
        f"Which {context} have low confidence?",
        f"Group {context} by date",
        f"Show me recent {context}",
        f"Find duplicate {context}",
        f"What {context} were uploaded today?",
        f"Show me {context} with specific values"
    ]
