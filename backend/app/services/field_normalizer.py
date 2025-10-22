"""
Field Normalizer Service

Provides cross-template field normalization for unified querying.
Enables queries like "show invoices over $1000" to work across different
invoice templates that may use different field names (invoice_total, amount, total_cost, etc.)

Key Features:
- Canonical field mapping (invoice_total → amount)
- Reverse lookup (amount → [invoice_total, payment_amount, contract_value])
- Dynamic field resolution based on SchemaRegistry
- Query rewriting for cross-template searches
"""

from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class FieldNormalizer:
    """
    Normalizes field names across templates for cross-template queries.

    This enables users to query using common terms (amount, vendor, date)
    that automatically resolve to the correct field names for each template.
    """

    def __init__(self, schema_registry):
        """
        Initialize field normalizer with schema registry.

        Args:
            schema_registry: SchemaRegistry instance for dynamic field context
        """
        self.schema_registry = schema_registry

        # Core canonical categories
        # These map semantic concepts to field patterns
        self.canonical_categories = {
            # Money/Value fields
            "amount": {
                "patterns": ["total", "amount", "cost", "price", "value", "payment", "sum", "fee", "charge"],
                "description": "Monetary amounts and values",
                "type": "number"
            },

            # Date fields
            "date": {
                "patterns": ["date", "created", "uploaded", "processed", "when"],
                "description": "General date fields",
                "type": "date"
            },
            "start_date": {
                "patterns": ["start", "effective", "begin", "commence", "from"],
                "description": "Start/effective dates",
                "type": "date"
            },
            "end_date": {
                "patterns": ["end", "expir", "terminat", "until", "to"],
                "description": "End/expiration dates",
                "type": "date"
            },

            # Entity names
            "entity_name": {
                "patterns": ["vendor", "supplier", "customer", "client", "company", "organization", "entity", "party"],
                "description": "Company or person names",
                "type": "text"
            },

            # Identifiers
            "identifier": {
                "patterns": ["number", "id", "identifier", "reference", "ref", "code"],
                "description": "Document numbers and IDs",
                "type": "text"
            },

            # Status fields
            "status": {
                "patterns": ["status", "state", "condition", "stage"],
                "description": "Status or state fields",
                "type": "keyword"
            },

            # Description/Notes
            "description": {
                "patterns": ["description", "notes", "comments", "memo", "details"],
                "description": "Descriptive text fields",
                "type": "text"
            }
        }

        # Cache for resolved mappings
        self._canonical_map: Optional[Dict[str, List[str]]] = None
        self._reverse_map: Optional[Dict[str, str]] = None

    async def initialize(self):
        """
        Initialize field mappings from SchemaRegistry.
        Must be called before using the normalizer.
        """
        if not self.schema_registry:
            logger.warning("No schema registry provided, using default mappings only")
            return

        try:
            # Get canonical mapping from registry
            registry_mapping = await self.schema_registry.get_canonical_field_mapping()

            # Build comprehensive canonical map
            self._canonical_map = {}
            self._reverse_map = {}

            # Start with registry mappings
            for canonical_name, field_names in registry_mapping.items():
                if canonical_name not in self._canonical_map:
                    self._canonical_map[canonical_name] = []
                self._canonical_map[canonical_name].extend(field_names)

                # Build reverse map
                for field_name in field_names:
                    self._reverse_map[field_name] = canonical_name

            # Add pattern-based mappings for fields not in registry
            all_templates = await self.schema_registry.get_all_templates_context()
            for template in all_templates:
                for field_name in template.get("all_field_names", []):
                    if field_name not in self._reverse_map:
                        # Try to categorize using patterns
                        canonical = self._infer_canonical_category(field_name)
                        if canonical:
                            if canonical not in self._canonical_map:
                                self._canonical_map[canonical] = []
                            if field_name not in self._canonical_map[canonical]:
                                self._canonical_map[canonical].append(field_name)
                            self._reverse_map[field_name] = canonical

            logger.info(
                f"Initialized FieldNormalizer with {len(self._canonical_map)} "
                f"canonical categories mapping to {len(self._reverse_map)} fields"
            )

        except Exception as e:
            logger.error(f"Failed to initialize FieldNormalizer: {e}")
            # Use default mappings
            self._canonical_map = {}
            self._reverse_map = {}

    def _infer_canonical_category(self, field_name: str) -> Optional[str]:
        """
        Infer canonical category from field name using pattern matching.

        Args:
            field_name: Field name to categorize

        Returns:
            Canonical category name or None
        """
        field_lower = field_name.lower()

        # Check each canonical category's patterns
        for canonical, config in self.canonical_categories.items():
            for pattern in config["patterns"]:
                if pattern in field_lower:
                    return canonical

        return None

    def get_canonical_name(self, field_name: str) -> str:
        """
        Get canonical name for a field.

        Args:
            field_name: Actual field name

        Returns:
            Canonical category name, or original field name if not found
        """
        if not self._reverse_map:
            # Fallback to pattern matching
            canonical = self._infer_canonical_category(field_name)
            return canonical if canonical else field_name

        return self._reverse_map.get(field_name, field_name)

    def get_field_names(self, canonical_name: str) -> List[str]:
        """
        Get all field names for a canonical category.

        Args:
            canonical_name: Canonical category (e.g., "amount")

        Returns:
            List of actual field names
        """
        if not self._canonical_map:
            return [canonical_name]

        return self._canonical_map.get(canonical_name, [canonical_name])

    def normalize_query_fields(
        self,
        query: Dict[str, Any],
        mode: str = "expand"
    ) -> Dict[str, Any]:
        """
        Normalize field names in an Elasticsearch query.

        Args:
            query: Elasticsearch query DSL
            mode: "expand" (canonical → all fields) or "canonicalize" (fields → canonical)

        Returns:
            Query with normalized field names
        """
        if mode == "expand":
            return self._expand_canonical_fields(query)
        else:
            return self._canonicalize_fields(query)

    def _expand_canonical_fields(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expand canonical field names to all matching actual field names.

        Converts: {"range": {"amount": {"gte": 1000}}}
        To: {"bool": {"should": [
            {"range": {"invoice_total": {"gte": 1000}}},
            {"range": {"payment_amount": {"gte": 1000}}},
            {"range": {"total_cost": {"gte": 1000}}}
        ]}}

        This allows cross-template queries.
        """
        if not isinstance(query, dict):
            return query

        # Handle different query types
        if "range" in query:
            field_name = list(query["range"].keys())[0]
            if field_name in self.canonical_categories:
                # This is a canonical field - expand it
                actual_fields = self.get_field_names(field_name)
                if len(actual_fields) > 1:
                    # Create should clause with all variations
                    return {
                        "bool": {
                            "should": [
                                {"range": {actual_field: query["range"][field_name]}}
                                for actual_field in actual_fields
                            ],
                            "minimum_should_match": 1
                        }
                    }

        elif "term" in query:
            field_name = list(query["term"].keys())[0]
            if field_name in self.canonical_categories:
                actual_fields = self.get_field_names(field_name)
                if len(actual_fields) > 1:
                    return {
                        "bool": {
                            "should": [
                                {"term": {actual_field: query["term"][field_name]}}
                                for actual_field in actual_fields
                            ],
                            "minimum_should_match": 1
                        }
                    }

        elif "match" in query:
            field_name = list(query["match"].keys())[0]
            if field_name in self.canonical_categories:
                actual_fields = self.get_field_names(field_name)
                if len(actual_fields) > 1:
                    return {
                        "bool": {
                            "should": [
                                {"match": {actual_field: query["match"][field_name]}}
                                for actual_field in actual_fields
                            ],
                            "minimum_should_match": 1
                        }
                    }

        elif "bool" in query:
            # Recursively process bool clauses
            normalized_bool = {"bool": {}}
            for clause_type in ["must", "should", "filter", "must_not"]:
                if clause_type in query["bool"]:
                    normalized_bool["bool"][clause_type] = [
                        self._expand_canonical_fields(clause)
                        for clause in query["bool"][clause_type]
                    ]

            # Preserve other bool parameters
            for key in ["minimum_should_match", "boost"]:
                if key in query["bool"]:
                    normalized_bool["bool"][key] = query["bool"][key]

            return normalized_bool

        # Return unchanged if not recognized
        return query

    def _canonicalize_fields(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert actual field names to canonical names in query.

        This is useful for query caching and pattern matching.
        """
        # Implementation similar to expand but in reverse
        # For now, return unchanged
        return query

    def build_canonical_document(
        self,
        extracted_fields: Dict[str, Any],
        template_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a canonical representation of extracted fields.

        Args:
            extracted_fields: Raw extracted fields from document
            template_name: Optional template name for context

        Returns:
            Dictionary with canonical field mappings
        """
        canonical = {}

        for field_name, field_value in extracted_fields.items():
            canonical_name = self.get_canonical_name(field_name)

            # Use canonical name as key
            # If multiple fields map to same canonical, prefer first non-null
            if canonical_name not in canonical or canonical[canonical_name] is None:
                canonical[canonical_name] = field_value

            # Also store original field name for reference
            canonical[f"_original_{canonical_name}"] = field_name

        return canonical

    def get_search_fields_for_category(
        self,
        canonical_name: str,
        boost_pattern: Optional[str] = None
    ) -> List[str]:
        """
        Get list of search fields for a canonical category with optional boosting.

        Args:
            canonical_name: Canonical category name
            boost_pattern: Optional pattern to boost (e.g., "invoice" boosts "invoice_total")

        Returns:
            List of field names with optional boost notation (e.g., "invoice_total^2")
        """
        field_names = self.get_field_names(canonical_name)

        if not boost_pattern:
            return field_names

        # Apply boosting to fields matching pattern
        boosted_fields = []
        for field_name in field_names:
            if boost_pattern.lower() in field_name.lower():
                boosted_fields.append(f"{field_name}^2")
            else:
                boosted_fields.append(field_name)

        return boosted_fields

    def get_aggregation_field(
        self,
        canonical_name: str,
        prefer_keyword: bool = True
    ) -> str:
        """
        Get best field for aggregation from canonical category.

        Args:
            canonical_name: Canonical category name
            prefer_keyword: Whether to prefer .keyword suffix for text fields

        Returns:
            Field name suitable for aggregation
        """
        field_names = self.get_field_names(canonical_name)

        if not field_names:
            return canonical_name

        # For aggregations, prefer keyword fields
        # Try to find most common field name
        # (In production, this would use field usage statistics)
        best_field = field_names[0]

        # Check if this is a text field that needs .keyword
        if prefer_keyword and canonical_name in ["entity_name", "description", "identifier"]:
            # These are text fields, append .keyword for aggregations
            best_field = f"{best_field}.keyword"

        return best_field
