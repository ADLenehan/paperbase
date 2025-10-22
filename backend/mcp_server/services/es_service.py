"""
Elasticsearch Service for MCP Server

Provides optimized Elasticsearch queries with query context understanding,
natural language query support, and intelligent result formatting.

NOTE: QueryOptimizer has been moved to app.services.query_optimizer for reuse.
"""

from elasticsearch import AsyncElasticsearch
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import json

from app.services.elastic_service import ElasticsearchService
from app.services.query_optimizer import QueryOptimizer
from mcp_server.config import config
from mcp_server.services.cache_service import cached, cache_service

logger = logging.getLogger(__name__)

# QueryOptimizer is now imported from app.services.query_optimizer
# Legacy code below is kept for reference but not used

class QueryOptimizerLegacy:
    """
    Query optimization and context understanding for MCP requests.

    Translates user intent into efficient Elasticsearch queries,
    understands field aliases, and handles cross-template searches.
    """

    def __init__(self):
        """Initialize query optimizer with field mappings"""
        # Common field aliases for better query understanding
        self.field_aliases = {
            "amount": ["total", "total_amount", "amount", "price", "cost", "sum"],
            "date": ["date", "created_date", "invoice_date", "effective_date", "start_date"],
            "vendor": ["vendor", "supplier", "customer", "company", "entity_name"],
            "status": ["status", "state", "condition"],
            "number": ["number", "invoice_number", "id", "identifier", "reference"],
        }

        # Field type mappings for query construction
        self.field_types = {
            "text": ["description", "notes", "comments", "full_text"],
            "keyword": ["status", "category", "type", "template_name"],
            "number": ["amount", "total", "quantity", "count"],
            "date": ["date", "created_at", "uploaded_at", "processed_at"],
        }

    def understand_query_intent(self, query: str, available_fields: List[str]) -> Dict[str, Any]:
        """
        Analyze query to understand user intent and extract query components.

        Args:
            query: Natural language query
            available_fields: List of available fields in the index

        Returns:
            Query analysis with intent, field mappings, and filters
        """
        query_lower = query.lower()

        analysis = {
            "intent": "search",  # search, filter, aggregate, retrieve
            "query_type": "hybrid",  # keyword, semantic, hybrid, exact
            "target_fields": [],
            "filters": [],
            "aggregations": [],
            "sort": None,
            "requires_full_text": False
        }

        # Detect intent
        if any(word in query_lower for word in ["show", "list", "get", "find", "retrieve"]):
            analysis["intent"] = "retrieve"
        elif any(word in query_lower for word in ["how many", "count", "total", "sum", "average"]):
            analysis["intent"] = "aggregate"
        elif any(word in query_lower for word in ["filter", "where", "with", "having"]):
            analysis["intent"] = "filter"

        # Detect filters in natural language
        # e.g., "invoices over $1000" -> range filter on amount
        if "over" in query_lower or "greater than" in query_lower or "more than" in query_lower:
            # Extract numeric value
            import re
            numbers = re.findall(r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query)
            if numbers:
                value = float(numbers[0].replace(',', ''))
                # Find which field this applies to
                for field_name, aliases in self.field_aliases.items():
                    if any(alias in query_lower for alias in aliases):
                        analysis["filters"].append({
                            "type": "range",
                            "field": self._resolve_field(field_name, available_fields),
                            "operator": "gte",
                            "value": value
                        })

        if "under" in query_lower or "less than" in query_lower or "below" in query_lower:
            import re
            numbers = re.findall(r'\$?(\d+(?:,\d{3})*(?:\.\d+)?)', query)
            if numbers:
                value = float(numbers[0].replace(',', ''))
                for field_name, aliases in self.field_aliases.items():
                    if any(alias in query_lower for alias in aliases):
                        analysis["filters"].append({
                            "type": "range",
                            "field": self._resolve_field(field_name, available_fields),
                            "operator": "lte",
                            "value": value
                        })

        # Detect date filters
        if "last week" in query_lower or "past week" in query_lower:
            analysis["filters"].append({
                "type": "date_range",
                "field": "uploaded_at",
                "range": "last_week"
            })
        elif "last month" in query_lower or "past month" in query_lower:
            analysis["filters"].append({
                "type": "date_range",
                "field": "uploaded_at",
                "range": "last_month"
            })
        elif "today" in query_lower:
            analysis["filters"].append({
                "type": "date_range",
                "field": "uploaded_at",
                "range": "today"
            })

        # Detect exact match requirements
        if '"' in query or "exactly" in query_lower or "exact" in query_lower:
            analysis["query_type"] = "exact"

        # Detect if full text search is needed
        if len(query.split()) > 3 and analysis["intent"] == "search":
            analysis["requires_full_text"] = True

        # Detect sorting preferences
        if "recent" in query_lower or "latest" in query_lower or "newest" in query_lower:
            analysis["sort"] = {"field": "uploaded_at", "order": "desc"}
        elif "oldest" in query_lower or "earliest" in query_lower:
            analysis["sort"] = {"field": "uploaded_at", "order": "asc"}

        return analysis

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

        # Clean up empty clauses
        if not es_query["bool"]["must"]:
            es_query["bool"]["must"] = [{"match_all": {}}]
        if not es_query["bool"]["filter"]:
            del es_query["bool"]["filter"]
        if not es_query["bool"]["should"]:
            del es_query["bool"]["should"]

        return es_query

    def _get_date_range(self, range_name: str) -> Dict[str, str]:
        """Get Elasticsearch date range for common ranges"""
        ranges = {
            "today": {"gte": "now/d", "lte": "now/d"},
            "last_week": {"gte": "now-1w/d", "lte": "now/d"},
            "last_month": {"gte": "now-1M/d", "lte": "now/d"},
            "last_year": {"gte": "now-1y/d", "lte": "now/d"}
        }
        return ranges.get(range_name, {"gte": "now-1d"})


class ElasticsearchMCPService:
    """
    MCP-optimized Elasticsearch service with query optimization
    and intelligent result formatting.
    """

    def __init__(self):
        """Initialize ES service with query optimizer"""
        self.es_service = ElasticsearchService()
        self.optimizer = QueryOptimizer()
        logger.info("Elasticsearch MCP service initialized")

    async def search_with_context(
        self,
        query: str,
        available_fields: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Context-aware search with query optimization.

        Args:
            query: Natural language or keyword query
            available_fields: Available fields (auto-detected if None)
            folder_path: Optional folder filter
            limit: Max results
            offset: Pagination offset

        Returns:
            Search results with query explanation
        """
        # Get available fields if not provided
        if available_fields is None:
            available_fields = await self._get_available_fields()

        # Analyze query intent
        analysis = self.optimizer.understand_query_intent(query, available_fields)

        # Build optimized query
        es_query = self.optimizer.build_optimized_query(query, analysis, available_fields)

        # Add folder filter if specified
        if folder_path:
            if "filter" not in es_query["bool"]:
                es_query["bool"]["filter"] = []
            es_query["bool"]["filter"].append({
                "prefix": {"folder_path.keyword": folder_path}
            })

        # Execute search
        search_results = await self.es_service.search(
            query=None,
            custom_query=es_query,
            page=(offset // limit) + 1,
            size=limit
        )

        return {
            "results": search_results.get("documents", []),
            "total": search_results.get("total", 0),
            "query_analysis": {
                "intent": analysis["intent"],
                "query_type": analysis["query_type"],
                "filters_applied": len(analysis["filters"]),
                "sort": analysis.get("sort")
            },
            "elasticsearch_query": es_query
        }

    async def _get_available_fields(self) -> List[str]:
        """Get list of available fields from ES index mapping"""
        try:
            mapping = await self.es_service.client.indices.get_mapping(
                index=self.es_service.index_name
            )
            properties = mapping[self.es_service.index_name]["mappings"]["properties"]
            return list(properties.keys())
        except Exception as e:
            logger.warning(f"Could not fetch ES mapping: {e}")
            return []

    async def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document from ES by ID"""
        return await self.es_service.get_document(document_id)

    async def get_aggregations(
        self,
        field: str,
        size: int = 10
    ) -> Dict[str, Any]:
        """Get aggregations for analytics"""
        return await self.es_service.get_aggregations(field)

    async def execute_custom_query(
        self,
        es_query: Dict[str, Any],
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Execute custom Elasticsearch query (for advanced users).

        Args:
            es_query: Elasticsearch query DSL
            limit: Max results

        Returns:
            Search results
        """
        search_results = await self.es_service.search(
            query=None,
            custom_query=es_query,
            page=1,
            size=limit
        )

        return {
            "results": search_results.get("documents", []),
            "total": search_results.get("total", 0)
        }

    async def health_check(self) -> bool:
        """Check ES connection health"""
        return await self.es_service.health_check()

    async def close(self):
        """Close ES connection"""
        await self.es_service.close()


# Global ES MCP service instance
es_mcp_service = ElasticsearchMCPService()
