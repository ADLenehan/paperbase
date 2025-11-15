"""
Query Optimizer Service

Provides intelligent query understanding and optimization for natural language searches.
Extracted from MCP server for reuse across the application.

Key Features:
- Intent detection (search, filter, aggregate, retrieve)
- Natural language filter extraction (e.g., "over $1000" -> range query)
- Field alias resolution (e.g., "amount" -> "invoice_total")
- Date range parsing (e.g., "last month" -> date range)
- Query type selection (exact, fuzzy, semantic, hybrid)
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Query optimization and context understanding for natural language searches.

    Translates user intent into efficient Elasticsearch queries,
    understands field aliases, and handles cross-template searches.
    """

    def __init__(self, schema_registry=None):
        """
        Initialize query optimizer with field mappings.

        Args:
            schema_registry: Optional SchemaRegistry for dynamic field resolution
        """
        self.schema_registry = schema_registry

        # Common field aliases for better query understanding
        # These will be enhanced by SchemaRegistry if available
        self.field_aliases = {
            "amount": ["total", "total_amount", "amount", "price", "cost", "sum", "value"],
            "date": ["date", "created_date", "invoice_date", "effective_date", "start_date", "contract_date"],
            "vendor": ["vendor", "supplier", "customer", "company", "entity_name", "client"],
            "status": ["status", "state", "condition"],
            "number": ["number", "invoice_number", "id", "identifier", "reference", "po_number"],
        }

        # Field type mappings for query construction
        self.field_types = {
            "text": ["description", "notes", "comments", "full_text"],
            "keyword": ["status", "category", "type", "template_name"],
            "number": ["amount", "total", "quantity", "count"],
            "date": ["date", "created_at", "uploaded_at", "processed_at"],
        }

    async def initialize_from_registry(self):
        """
        Initialize field aliases from SchemaRegistry if available.
        This provides dynamic, schema-aware field resolution.
        """
        if not self.schema_registry:
            return

        try:
            # Get canonical field mapping from registry
            canonical_mapping = await self.schema_registry.get_canonical_field_mapping()

            # Merge with default aliases
            for canonical_name, field_names in canonical_mapping.items():
                if canonical_name in self.field_aliases:
                    # Extend existing aliases
                    self.field_aliases[canonical_name].extend(field_names)
                    # Deduplicate
                    self.field_aliases[canonical_name] = list(set(self.field_aliases[canonical_name]))
                else:
                    # Add new canonical mapping
                    self.field_aliases[canonical_name] = field_names

            logger.info(f"Initialized query optimizer with {len(self.field_aliases)} field aliases from registry")

        except Exception as e:
            logger.warning(f"Could not initialize from schema registry: {e}")

    def understand_query_intent(self, query: str, available_fields: List[str]) -> Dict[str, Any]:
        """
        Analyze query to understand user intent and extract query components.

        Args:
            query: Natural language query
            available_fields: List of available fields in the index

        Returns:
            Query analysis with intent, field mappings, and filters
            {
                "intent": "retrieve",  # search, filter, aggregate, retrieve
                "query_type": "hybrid",  # keyword, semantic, hybrid, exact
                "target_fields": [],
                "filters": [
                    {"type": "range", "field": "amount", "operator": "gte", "value": 1000}
                ],
                "aggregations": [],
                "sort": {"field": "uploaded_at", "order": "desc"},
                "requires_full_text": False,
                "confidence": 0.85  # How confident we are in this analysis
            }
        """
        query_lower = query.lower()

        analysis = {
            "intent": "search",  # search, filter, aggregate, retrieve
            "query_type": "hybrid",  # keyword, semantic, hybrid, exact
            "target_fields": [],
            "filters": [],
            "aggregations": [],
            "sort": None,
            "requires_full_text": False,
            "confidence": 0.5  # Start with medium confidence
        }

        # Detect intent
        if any(word in query_lower for word in ["show", "list", "get", "find", "retrieve", "display"]):
            analysis["intent"] = "retrieve"
            analysis["confidence"] += 0.1
        elif any(word in query_lower for word in ["how many", "count", "total", "sum", "average", "group by"]):
            analysis["intent"] = "aggregate"
            analysis["confidence"] += 0.2
        elif any(word in query_lower for word in ["filter", "where", "with", "having"]):
            analysis["intent"] = "filter"
            analysis["confidence"] += 0.1

        # Detect filters in natural language
        self._extract_numeric_filters(query, query_lower, available_fields, analysis)
        self._extract_date_filters(query_lower, analysis)
        self._extract_text_filters(query, query_lower, available_fields, analysis)

        # Detect exact match requirements
        if '"' in query or "exactly" in query_lower or "exact" in query_lower:
            analysis["query_type"] = "exact"
            analysis["confidence"] += 0.1

        # Detect if full text search is needed
        if len(query.split()) > 3 and analysis["intent"] == "search":
            analysis["requires_full_text"] = True

        # Detect sorting preferences
        if "recent" in query_lower or "latest" in query_lower or "newest" in query_lower:
            analysis["sort"] = {"field": "uploaded_at", "order": "desc"}
            analysis["confidence"] += 0.05
        elif "oldest" in query_lower or "earliest" in query_lower:
            analysis["sort"] = {"field": "uploaded_at", "order": "asc"}
            analysis["confidence"] += 0.05

        # Detect aggregation type
        if analysis["intent"] == "aggregate":
            if "sum" in query_lower or "total" in query_lower:
                analysis["aggregations"].append({"type": "sum"})
            elif "average" in query_lower or "avg" in query_lower:
                analysis["aggregations"].append({"type": "avg"})
            elif "count" in query_lower or "how many" in query_lower:
                analysis["aggregations"].append({"type": "count"})
            elif "group by" in query_lower:
                analysis["aggregations"].append({"type": "terms"})

        # Cap confidence at 1.0
        analysis["confidence"] = min(analysis["confidence"], 1.0)

        return analysis

    def _extract_numeric_filters(
        self,
        query: str,
        query_lower: str,
        available_fields: List[str],
        analysis: Dict[str, Any]
    ):
        """Extract numeric range filters from query."""
        # "over X", "greater than X", "more than X"
        if any(term in query_lower for term in ["over", "greater than", "more than", "above"]):
            numbers = re.findall(r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query)
            if numbers:
                value = float(numbers[0].replace(',', ''))
                # Find which field this applies to
                field = self._find_target_field(query_lower, available_fields, "amount")
                if field:
                    analysis["filters"].append({
                        "type": "range",
                        "field": field,
                        "operator": "gte",
                        "value": value
                    })
                    analysis["confidence"] += 0.15

        # "under X", "less than X", "below X"
        if any(term in query_lower for term in ["under", "less than", "below"]):
            numbers = re.findall(r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query)
            if numbers:
                value = float(numbers[0].replace(',', ''))
                field = self._find_target_field(query_lower, available_fields, "amount")
                if field:
                    analysis["filters"].append({
                        "type": "range",
                        "field": field,
                        "operator": "lte",
                        "value": value
                    })
                    analysis["confidence"] += 0.15

        # "between X and Y"
        if "between" in query_lower and " and " in query_lower:
            numbers = re.findall(r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query)
            if len(numbers) >= 2:
                min_val = float(numbers[0].replace(',', ''))
                max_val = float(numbers[1].replace(',', ''))
                field = self._find_target_field(query_lower, available_fields, "amount")
                if field:
                    analysis["filters"].append({
                        "type": "range",
                        "field": field,
                        "operator": "range",
                        "value": {"gte": min_val, "lte": max_val}
                    })
                    analysis["confidence"] += 0.2

    def _extract_date_filters(self, query_lower: str, analysis: Dict[str, Any]):
        """Extract date range filters from query."""
        date_patterns = [
            (["last week", "past week"], "last_week"),
            (["last month", "past month"], "last_month"),
            (["last year", "past year"], "last_year"),
            (["this week", "current week"], "this_week"),
            (["this month", "current month"], "this_month"),
            (["this year", "current year"], "this_year"),
            (["today"], "today"),
            (["yesterday"], "yesterday"),
            (["last 7 days"], "last_7_days"),
            (["last 30 days"], "last_30_days"),
            (["last quarter", "previous quarter"], "last_quarter"),
            (["this quarter", "current quarter"], "this_quarter"),
        ]

        for patterns, range_name in date_patterns:
            if any(pattern in query_lower for pattern in patterns):
                analysis["filters"].append({
                    "type": "date_range",
                    "field": "uploaded_at",  # Default to uploaded_at
                    "range": range_name
                })
                analysis["confidence"] += 0.1
                break  # Only match first date pattern

    def _extract_text_filters(
        self,
        query: str,
        query_lower: str,
        available_fields: List[str],
        analysis: Dict[str, Any]
    ):
        """Extract text-based filters from query."""
        # Extract quoted strings for exact matching
        quoted_strings = re.findall(r'"([^"]+)"', query)
        for quoted in quoted_strings:
            analysis["filters"].append({
                "type": "match_phrase",
                "field": "_all_text",  # Search all text
                "value": quoted
            })
            analysis["confidence"] += 0.1

        # Status filters
        status_values = ["active", "inactive", "pending", "completed", "processing", "error", "uploaded"]
        for status in status_values:
            if status in query_lower:
                analysis["filters"].append({
                    "type": "term",
                    "field": "status",
                    "value": status
                })
                analysis["confidence"] += 0.1

    def _find_target_field(
        self,
        query_lower: str,
        available_fields: List[str],
        canonical_name: str
    ) -> Optional[str]:
        """
        Find the target field for a filter based on query context.

        Args:
            query_lower: Lowercased query
            available_fields: Available fields
            canonical_name: Canonical field category (e.g., "amount")

        Returns:
            Resolved field name or None
        """
        aliases = self.field_aliases.get(canonical_name, [canonical_name])

        # Check if any alias is mentioned in query
        for alias in aliases:
            if alias in query_lower:
                # Resolve to actual field
                return self._resolve_field(canonical_name, available_fields)

        # Default: return resolved canonical field
        return self._resolve_field(canonical_name, available_fields)

    def _resolve_field(self, canonical_name: str, available_fields: List[str]) -> str:
        """
        Resolve canonical field name to actual field in index.

        Args:
            canonical_name: Common field name (e.g., "amount")
            available_fields: List of actual field names in index

        Returns:
            Best matching field name
        """
        aliases = self.field_aliases.get(canonical_name, [canonical_name])

        # Try exact match first
        for alias in aliases:
            if alias in available_fields:
                return alias

        # Try partial match
        for alias in aliases:
            for field in available_fields:
                if alias in field.lower():
                    return field

        # Default to first alias
        return aliases[0]

    def build_optimized_query(
        self,
        query: str,
        analysis: Dict[str, Any],
        available_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Build optimized Elasticsearch query based on intent analysis.

        Args:
            query: Original query text
            analysis: Query analysis from understand_query_intent
            available_fields: Available fields

        Returns:
            Elasticsearch query DSL
        """
        es_query = {"bool": {"must": [], "filter": [], "should": []}}

        # Add text search based on query type
        if analysis["query_type"] == "exact":
            # Exact phrase match
            es_query["bool"]["must"].append({
                "match_phrase": {
                    "_all_text": query
                }
            })
        elif analysis["requires_full_text"]:
            # Multi-field search with boosting
            es_query["bool"]["must"].append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "full_text^2",  # Boost full text
                        "_all_text^1.5",
                        "filename^3",  # Boost filename matches
                        "*"  # All other fields
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            })
        else:
            # Simple query string for flexible matching
            es_query["bool"]["must"].append({
                "query_string": {
                    "query": query,
                    "fields": ["_all_text", "full_text", "filename"],
                    "default_operator": "AND"
                }
            })

        # Add filters from analysis
        for filter_spec in analysis["filters"]:
            if filter_spec["type"] == "range":
                if filter_spec["operator"] == "range":
                    # Between filter with both gte and lte
                    es_query["bool"]["filter"].append({
                        "range": {
                            filter_spec["field"]: filter_spec["value"]
                        }
                    })
                else:
                    # Single operator (gte or lte)
                    es_query["bool"]["filter"].append({
                        "range": {
                            filter_spec["field"]: {
                                filter_spec["operator"]: filter_spec["value"]
                            }
                        }
                    })
            elif filter_spec["type"] == "date_range":
                date_range = self._get_date_range(filter_spec["range"])
                es_query["bool"]["filter"].append({
                    "range": {
                        filter_spec["field"]: date_range
                    }
                })
            elif filter_spec["type"] == "match_phrase":
                # Exact phrase in quotes
                es_query["bool"]["must"].append({
                    "match_phrase": {
                        filter_spec["field"]: filter_spec["value"]
                    }
                })
            elif filter_spec["type"] == "term":
                # Exact term match
                es_query["bool"]["filter"].append({
                    "term": {
                        filter_spec["field"]: filter_spec["value"]
                    }
                })

        # Clean up empty clauses
        if not es_query["bool"]["must"]:
            es_query["bool"]["must"] = [{"match_all": {}}]
        if not es_query["bool"]["filter"]:
            del es_query["bool"]["filter"]
        if not es_query["bool"]["should"]:
            del es_query["bool"]["should"]

        return es_query

    def _get_date_range(self, range_name: str) -> Dict[str, str]:
        """Get Elasticsearch date range for common ranges."""
        ranges = {
            "today": {"gte": "now/d", "lte": "now/d"},
            "yesterday": {"gte": "now-1d/d", "lte": "now-1d/d"},
            "this_week": {"gte": "now/w", "lte": "now/d"},
            "last_week": {"gte": "now-1w/w", "lte": "now-1w/w"},
            "this_month": {"gte": "now/M", "lte": "now/d"},
            "last_month": {"gte": "now-1M/M", "lte": "now-1M/M"},
            "this_quarter": {"gte": "now/M", "lte": "now/d"},  # Simplified
            "last_quarter": {"gte": "now-3M/M", "lte": "now-3M/M"},  # Simplified
            "this_year": {"gte": "now/y", "lte": "now/d"},
            "last_year": {"gte": "now-1y/y", "lte": "now-1y/y"},
            "last_7_days": {"gte": "now-7d/d", "lte": "now/d"},
            "last_30_days": {"gte": "now-30d/d", "lte": "now/d"},
        }
        return ranges.get(range_name, {"gte": "now-1d"})

    def should_use_claude(self, analysis: Dict[str, Any]) -> bool:
        """
        Determine if Claude should be consulted for query refinement.

        Low confidence queries or complex aggregations should use Claude.

        Args:
            analysis: Query analysis from understand_query_intent

        Returns:
            True if Claude should refine the query
        """
        # Use Claude if:
        # 1. Confidence is low (<0.6)
        if analysis["confidence"] < 0.6:
            return True

        # 2. Complex aggregations requested
        if len(analysis.get("aggregations", [])) > 1:
            return True

        # 3. No filters extracted but query looks like it should have filters
        query_suggests_filters = any(word in analysis.get("original_query", "").lower()
                                     for word in ["where", "with", "having", "that"])
        if query_suggests_filters and not analysis["filters"]:
            return True

        # 4. Ambiguous intent (fallback to search)
        if analysis["intent"] == "search" and analysis["confidence"] < 0.7:
            return True

        return False
