from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models.schema import Schema
from app.models.template import SchemaTemplate
import logging

logger = logging.getLogger(__name__)


class SchemaRegistry:
    """
    Central registry providing rich context for query generation.

    This service bridges the gap between data indexing and natural language queries
    by providing comprehensive field metadata that helps the LLM generate accurate
    Elasticsearch queries.
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_field_context(
        self,
        template_name: Optional[str] = None,
        schema_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive field information for query generation.

        Args:
            template_name: Name of the template/schema
            schema_id: ID of the schema

        Returns:
            {
                "template_name": "Invoices",
                "fields": {
                    "invoice_total": {
                        "type": "float",
                        "aliases": ["total", "amount", "cost", "price"],
                        "description": "Total invoice amount in USD",
                        "extraction_hints": ["Total:", "Amount Due:", "$"],
                        "typical_queries": ["invoices over $X", "total spending"]
                    },
                    ...
                },
                "all_field_names": ["invoice_total", "vendor_name", ...],
                "searchable_text": "invoice total amount vendor name date..."
            }
        """

        # Get schema
        schema = None
        if schema_id:
            schema = self.db.query(Schema).filter(Schema.id == schema_id).first()
        elif template_name:
            schema = self.db.query(Schema).filter(Schema.name == template_name).first()

        if not schema:
            logger.warning(f"Schema not found: template_name={template_name}, schema_id={schema_id}")
            return self._get_default_context()

        # Build field context
        field_contexts = {}
        all_field_names = []

        for field_def in schema.fields:
            field_name = field_def.get("name")
            field_type = field_def.get("type", "text")

            # Generate semantic aliases for common field names
            aliases = self._generate_aliases(field_name, field_type)

            # Build comprehensive context
            field_contexts[field_name] = {
                "type": field_type,
                "aliases": aliases,
                "description": field_def.get("description", ""),
                "extraction_hints": field_def.get("extraction_hints", []),
                "required": field_def.get("required", False),
                "confidence_threshold": field_def.get("confidence_threshold", 0.75),
                "typical_queries": self._generate_typical_queries(field_name, field_type)
            }

            all_field_names.append(field_name)
            all_field_names.extend(aliases)

        # Add standard metadata fields
        for std_field in ["filename", "uploaded_at", "processed_at", "status"]:
            all_field_names.append(std_field)
            field_contexts[std_field] = {
                "type": self._get_standard_field_type(std_field),
                "aliases": [],
                "description": self._get_standard_field_description(std_field),
                "extraction_hints": [],
                "required": False,
                "confidence_threshold": 1.0,
                "typical_queries": []
            }

        return {
            "template_name": schema.name,
            "fields": field_contexts,
            "all_field_names": list(set(all_field_names)),  # Deduplicate
            "searchable_text": " ".join(all_field_names),
            "field_count": len(field_contexts)
        }

    async def get_all_templates_context(self) -> List[Dict[str, Any]]:
        """
        Get field context for all available templates.
        Useful for cross-template queries.
        """
        schemas = self.db.query(Schema).all()
        contexts = []

        for schema in schemas:
            context = await self.get_field_context(schema_id=schema.id)
            contexts.append(context)

        return contexts

    async def get_canonical_field_mapping(self) -> Dict[str, List[str]]:
        """
        Get mapping of canonical field names to actual field names across all templates.

        Returns:
            {
                "amount": ["invoice_total", "payment_amount", "total_cost"],
                "date": ["invoice_date", "payment_date", "effective_date"],
                ...
            }
        """
        canonical_map = {}
        schemas = self.db.query(Schema).all()

        for schema in schemas:
            for field_def in schema.fields:
                field_name = field_def.get("name")
                field_type = field_def.get("type")

                # Determine canonical category
                canonical_name = self._get_canonical_name(field_name, field_type)

                if canonical_name not in canonical_map:
                    canonical_map[canonical_name] = []

                if field_name not in canonical_map[canonical_name]:
                    canonical_map[canonical_name].append(field_name)

        return canonical_map

    def _generate_aliases(self, field_name: str, field_type: str) -> List[str]:
        """Generate semantic aliases for a field name."""
        aliases = []

        # Common patterns
        name_lower = field_name.lower()

        # Amount/Money fields
        if any(term in name_lower for term in ["total", "amount", "cost", "price", "payment"]):
            aliases.extend(["amount", "total", "cost", "price"])

        # Date fields
        if "date" in name_lower or field_type == "date":
            aliases.extend(["date", "when"])
            if "effective" in name_lower:
                aliases.append("start_date")
            if "expir" in name_lower:
                aliases.append("end_date")

        # Name fields
        if any(term in name_lower for term in ["vendor", "customer", "client", "company"]):
            aliases.extend(["company", "organization", "vendor", "client"])

        # Number fields
        if "number" in name_lower or "id" in name_lower:
            aliases.extend(["number", "id", "reference"])

        # Status fields
        if "status" in name_lower:
            aliases.append("state")

        # Remove duplicates and the original field name
        aliases = [a for a in set(aliases) if a != field_name.lower()]

        return aliases

    def _generate_typical_queries(self, field_name: str, field_type: str) -> List[str]:
        """Generate typical query patterns for a field."""
        queries = []
        name_lower = field_name.lower()

        if field_type in ["number", "float", "integer"]:
            queries.extend([
                f"{field_name} over X",
                f"{field_name} less than X",
                f"{field_name} between X and Y",
                f"highest {field_name}",
                f"total {field_name}"
            ])

        if field_type == "date":
            queries.extend([
                f"{field_name} last month",
                f"{field_name} this year",
                f"{field_name} in Q1",
                f"{field_name} after YYYY-MM-DD"
            ])

        if field_type == "text":
            queries.extend([
                f"search {field_name} for 'term'",
                f"where {field_name} contains 'text'",
                f"group by {field_name}"
            ])

        return queries

    def _get_canonical_name(self, field_name: str, field_type: str) -> str:
        """Determine canonical category for a field."""
        name_lower = field_name.lower()

        # Money/Amount fields
        if any(term in name_lower for term in ["total", "amount", "cost", "price", "payment", "value"]):
            return "amount"

        # Date fields
        if "date" in name_lower or field_type == "date":
            if "effective" in name_lower or "start" in name_lower:
                return "start_date"
            elif "expir" in name_lower or "end" in name_lower:
                return "end_date"
            else:
                return "date"

        # Entity names
        if any(term in name_lower for term in ["vendor", "customer", "client", "company", "supplier"]):
            return "entity_name"

        # Numbers/IDs
        if "number" in name_lower or ("id" in name_lower and field_type != "date"):
            return "identifier"

        # Status
        if "status" in name_lower or "state" in name_lower:
            return "status"

        # Default: use field name
        return field_name

    def _get_standard_field_type(self, field_name: str) -> str:
        """Get type for standard metadata fields."""
        type_map = {
            "filename": "keyword",
            "uploaded_at": "date",
            "processed_at": "date",
            "status": "keyword"
        }
        return type_map.get(field_name, "text")

    def _get_standard_field_description(self, field_name: str) -> str:
        """Get description for standard metadata fields."""
        desc_map = {
            "filename": "Original filename of the document",
            "uploaded_at": "When the document was uploaded",
            "processed_at": "When the document was processed",
            "status": "Processing status (uploaded, analyzing, processing, completed, error)"
        }
        return desc_map.get(field_name, "")

    def _get_default_context(self) -> Dict[str, Any]:
        """Return default context when no schema is found."""
        return {
            "template_name": "Unknown",
            "fields": {
                "filename": {
                    "type": "keyword",
                    "aliases": [],
                    "description": "Document filename",
                    "extraction_hints": [],
                    "required": False,
                    "confidence_threshold": 1.0,
                    "typical_queries": []
                }
            },
            "all_field_names": ["filename", "uploaded_at", "status"],
            "searchable_text": "filename uploaded_at status",
            "field_count": 3
        }
