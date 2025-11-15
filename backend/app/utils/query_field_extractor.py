"""
Query Field Extractor

Extracts field references from Elasticsearch query DSL to enable:
- Query-to-field lineage tracking
- Impact analysis when fields change
- Audit trail filtering (only show fields used in query)
- Query optimization and debugging

Supports all ES query types used in Paperbase:
- match, match_phrase, query_string, multi_match
- term, range, prefix, exists
- bool (must, should, filter, must_not)
- Nested and compound queries
"""

import logging
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class QueryFieldExtractor:
    """
    Extracts field references from Elasticsearch query DSL.

    Example:
        >>> extractor = QueryFieldExtractor()
        >>> es_query = {
        ...     "bool": {
        ...         "must": [{"match": {"vendor_name": "Acme"}}],
        ...         "filter": [{"range": {"invoice_total": {"gte": 1000}}}]
        ...     }
        ... }
        >>> result = extractor.extract_fields(es_query)
        >>> result["queried_fields"]
        ['vendor_name', 'invoice_total']
    """

    # ES query types that contain field references
    FIELD_QUERY_TYPES = {
        "match", "match_phrase", "match_phrase_prefix",
        "term", "terms", "range", "prefix", "wildcard",
        "exists", "fuzzy", "regexp", "ids"
    }

    # ES query types with explicit "fields" parameter
    MULTI_FIELD_QUERY_TYPES = {
        "multi_match", "query_string", "simple_query_string"
    }

    # Boolean query clauses
    BOOL_CLAUSES = {"must", "should", "filter", "must_not"}

    # Synthetic/helper fields to flag separately
    SYNTHETIC_FIELDS = {
        "_all_text", "_field_index", "_query_context",
        "_confidence_metrics", "_citation_metadata",
        "_id", "_index", "_score"
    }

    def __init__(self, max_depth: int = 10):
        """
        Initialize the field extractor.

        Args:
            max_depth: Maximum recursion depth for nested queries (default: 10)
        """
        self.max_depth = max_depth
        self._reset()

    def _reset(self):
        """Reset internal state for a new extraction."""
        self.queried_fields: Set[str] = set()
        self.field_contexts: Dict[str, List[str]] = {}
        self.synthetic_fields: Set[str] = set()
        self.field_clauses: Dict[str, List[Dict[str, Any]]] = {}

    def extract_fields(self, es_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all field references from an Elasticsearch query.

        Args:
            es_query: Elasticsearch query DSL as a dictionary

        Returns:
            Dictionary with:
                - queried_fields: List of field names referenced in query
                - field_contexts: Map of field -> list of query contexts
                - synthetic_fields: List of helper/synthetic fields
                - field_clauses: Map of field -> list of clause details

        Example:
            {
                "queried_fields": ["vendor_name", "invoice_total"],
                "field_contexts": {
                    "vendor_name": ["query:match"],
                    "invoice_total": ["filter:range"]
                },
                "synthetic_fields": ["_all_text"],
                "field_clauses": {
                    "vendor_name": [
                        {"type": "match", "clause": "query", "query": {...}}
                    ]
                }
            }
        """
        self._reset()

        try:
            self._extract_fields_recursive(es_query, depth=0, context="root")

            # Separate synthetic fields from real fields
            real_fields = self.queried_fields - self.synthetic_fields

            return {
                "queried_fields": sorted(list(real_fields)),
                "field_contexts": {
                    field: contexts
                    for field, contexts in self.field_contexts.items()
                    if field in real_fields
                },
                "synthetic_fields": sorted(list(self.synthetic_fields)),
                "field_clauses": {
                    field: clauses
                    for field, clauses in self.field_clauses.items()
                    if field in real_fields
                },
                "total_field_references": len(self.queried_fields),
                "real_field_count": len(real_fields),
                "synthetic_field_count": len(self.synthetic_fields)
            }
        except Exception as e:
            logger.error(f"Error extracting fields from query: {e}", exc_info=True)
            return {
                "queried_fields": [],
                "field_contexts": {},
                "synthetic_fields": [],
                "field_clauses": {},
                "error": str(e)
            }

    def _extract_fields_recursive(
        self,
        query_node: Any,
        depth: int,
        context: str,
        parent_clause: Optional[str] = None
    ):
        """
        Recursively extract fields from query node.

        Args:
            query_node: Current node in query DSL tree
            depth: Current recursion depth
            context: Query context (e.g., "query:match", "filter:range")
            parent_clause: Parent bool clause (must/should/filter/must_not)
        """
        # Depth check to prevent infinite recursion
        if depth > self.max_depth:
            logger.warning(f"Max recursion depth {self.max_depth} reached")
            return

        # Handle None or non-dict/non-list nodes
        if query_node is None:
            return

        if not isinstance(query_node, (dict, list)):
            return

        # Handle list of queries (e.g., in bool clauses)
        if isinstance(query_node, list):
            for item in query_node:
                self._extract_fields_recursive(
                    item, depth + 1, context, parent_clause
                )
            return

        # Handle dictionary queries
        for key, value in query_node.items():
            # Bool query - recurse into clauses
            if key == "bool":
                self._handle_bool_query(value, depth, context)

            # Field-level query types
            elif key in self.FIELD_QUERY_TYPES:
                self._handle_field_query(key, value, context, parent_clause)

            # Multi-field query types
            elif key in self.MULTI_FIELD_QUERY_TYPES:
                self._handle_multi_field_query(key, value, context, parent_clause)

            # Nested query
            elif key == "nested":
                self._handle_nested_query(value, depth, context)

            # Aggregations (future support)
            elif key == "aggs" or key == "aggregations":
                self._handle_aggregations(value, depth, context)

            # Recurse into other structures
            elif isinstance(value, (dict, list)):
                self._extract_fields_recursive(
                    value, depth + 1, context, parent_clause
                )

    def _handle_bool_query(self, bool_query: Dict[str, Any], depth: int, context: str):
        """Handle boolean query clauses (must/should/filter/must_not)."""
        for clause in self.BOOL_CLAUSES:
            if clause in bool_query:
                clause_context = f"{context}:bool:{clause}"
                self._extract_fields_recursive(
                    bool_query[clause],
                    depth + 1,
                    clause_context,
                    parent_clause=clause
                )

    def _handle_field_query(
        self,
        query_type: str,
        query_value: Any,
        context: str,
        parent_clause: Optional[str]
    ):
        """
        Handle single-field query types (match, term, range, etc.).

        Example: {"match": {"vendor_name": "Acme"}}
                 {"range": {"invoice_total": {"gte": 1000}}}
                 {"exists": {"field": "cloud_platform"}}
        """
        if not isinstance(query_value, dict):
            return

        # Special case for "exists" query - field is a value, not a key
        if query_type == "exists" and "field" in query_value:
            field_name = query_value["field"]
            self._add_field(
                field_name,
                query_type,
                context,
                parent_clause,
                {"exists": True}
            )
            return

        # The field name is the key in the query_value dict
        for field_name in query_value.keys():
            self._add_field(
                field_name,
                query_type,
                context,
                parent_clause,
                query_value[field_name]
            )

    def _handle_multi_field_query(
        self,
        query_type: str,
        query_value: Dict[str, Any],
        context: str,
        parent_clause: Optional[str]
    ):
        """
        Handle multi-field query types (query_string, multi_match, etc.).

        Example: {"query_string": {"query": "Acme", "fields": ["vendor", "company"]}}
        """
        # Extract fields from "fields" parameter
        fields = query_value.get("fields", [])

        # Handle default_field for query_string
        if "default_field" in query_value:
            fields.append(query_value["default_field"])

        # Handle field for simple queries
        if "field" in query_value:
            fields.append(query_value["field"])

        for field_name in fields:
            # Remove boost syntax (e.g., "vendor_name^2" -> "vendor_name")
            clean_field = field_name.split("^")[0]

            # Remove wildcard suffix (e.g., "vendor*" -> "vendor")
            clean_field = clean_field.rstrip("*")

            self._add_field(
                clean_field,
                query_type,
                context,
                parent_clause,
                query_value.get("query", "")
            )

    def _handle_nested_query(self, nested_query: Dict[str, Any], depth: int, context: str):
        """Handle nested query with path."""
        path = nested_query.get("path", "")
        nested_context = f"{context}:nested:{path}"

        if "query" in nested_query:
            self._extract_fields_recursive(
                nested_query["query"],
                depth + 1,
                nested_context
            )

    def _handle_aggregations(self, aggs: Dict[str, Any], depth: int, context: str):
        """Handle aggregations (future support for field usage in aggs)."""
        # Aggregations can reference fields in various ways
        # For now, just recurse to find any field references
        self._extract_fields_recursive(aggs, depth + 1, f"{context}:agg")

    def _add_field(
        self,
        field_name: str,
        query_type: str,
        context: str,
        parent_clause: Optional[str],
        query_details: Any
    ):
        """Add a field reference with context."""
        # Add to queried fields
        self.queried_fields.add(field_name)

        # Check if synthetic field
        if field_name in self.SYNTHETIC_FIELDS or field_name.startswith("_"):
            self.synthetic_fields.add(field_name)

        # Build context string
        full_context = f"{parent_clause or 'query'}:{query_type}"

        # Add context
        if field_name not in self.field_contexts:
            self.field_contexts[field_name] = []
        if full_context not in self.field_contexts[field_name]:
            self.field_contexts[field_name].append(full_context)

        # Add clause details
        if field_name not in self.field_clauses:
            self.field_clauses[field_name] = []

        self.field_clauses[field_name].append({
            "type": query_type,
            "clause": parent_clause or "query",
            "context": context,
            "query_preview": str(query_details)[:100]  # Truncate for brevity
        })


def extract_fields_from_es_query(es_query: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to extract fields from an ES query.

    Args:
        es_query: Elasticsearch query DSL

    Returns:
        Field extraction results

    Example:
        >>> es_query = {"match": {"vendor_name": "Acme"}}
        >>> result = extract_fields_from_es_query(es_query)
        >>> result["queried_fields"]
        ['vendor_name']
    """
    extractor = QueryFieldExtractor()
    return extractor.extract_fields(es_query)


def filter_audit_items_by_fields(
    audit_items: List[Dict[str, Any]],
    queried_fields: List[str]
) -> List[Dict[str, Any]]:
    """
    Filter audit items to only include fields referenced in the query.

    Args:
        audit_items: List of audit items with field_name key
        queried_fields: List of field names used in query

    Returns:
        Filtered list of audit items

    Example:
        >>> audit_items = [
        ...     {"field_name": "vendor_name", "confidence": 0.5},
        ...     {"field_name": "address", "confidence": 0.4}
        ... ]
        >>> queried_fields = ["vendor_name"]
        >>> filtered = filter_audit_items_by_fields(audit_items, queried_fields)
        >>> len(filtered)
        1
    """
    queried_fields_set = set(queried_fields)

    return [
        item for item in audit_items
        if item.get("field_name") in queried_fields_set
    ]
