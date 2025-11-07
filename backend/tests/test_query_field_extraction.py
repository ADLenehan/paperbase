"""
Tests for Query Field Extractor

Tests field extraction from various Elasticsearch query DSL structures.
"""

import pytest
from app.utils.query_field_extractor import (
    QueryFieldExtractor,
    extract_fields_from_es_query,
    filter_audit_items_by_fields
)


class TestSimpleQueries:
    """Test simple single-clause queries."""

    def test_match_query(self):
        """Test field extraction from match query."""
        query = {"match": {"vendor_name": "Acme"}}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["vendor_name"]
        assert "vendor_name" in result["field_contexts"]
        assert "query:match" in result["field_contexts"]["vendor_name"]

    def test_term_query(self):
        """Test field extraction from term query."""
        query = {"term": {"status": "active"}}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["status"]
        assert result["field_contexts"]["status"] == ["query:term"]

    def test_range_query(self):
        """Test field extraction from range query."""
        query = {"range": {"invoice_total": {"gte": 1000, "lte": 5000}}}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["invoice_total"]
        assert "query:range" in result["field_contexts"]["invoice_total"]

    def test_exists_query(self):
        """Test field extraction from exists query."""
        query = {"exists": {"field": "vendor_email"}}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["field"]

    def test_prefix_query(self):
        """Test field extraction from prefix query."""
        query = {"prefix": {"company_name": "Acme"}}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["company_name"]


class TestMultiFieldQueries:
    """Test queries that reference multiple fields."""

    def test_multi_match_query(self):
        """Test field extraction from multi_match query."""
        query = {
            "multi_match": {
                "query": "Acme Corporation",
                "fields": ["vendor_name", "company_name", "legal_name"]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"vendor_name", "company_name", "legal_name"}
        assert all(
            "query:multi_match" in result["field_contexts"][field]
            for field in result["queried_fields"]
        )

    def test_query_string(self):
        """Test field extraction from query_string."""
        query = {
            "query_string": {
                "query": "Acme AND active",
                "fields": ["vendor", "status"]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"vendor", "status"}

    def test_multi_match_with_boost(self):
        """Test field extraction with boost syntax."""
        query = {
            "multi_match": {
                "query": "search term",
                "fields": ["title^2", "description", "tags^1.5"]
            }
        }
        result = extract_fields_from_es_query(query)

        # Should strip boost notation
        assert set(result["queried_fields"]) == {"title", "description", "tags"}


class TestBoolQueries:
    """Test boolean compound queries."""

    def test_simple_bool_must(self):
        """Test bool query with must clause."""
        query = {
            "bool": {
                "must": [
                    {"match": {"vendor_name": "Acme"}},
                    {"match": {"status": "active"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"vendor_name", "status"}
        assert "must:match" in result["field_contexts"]["vendor_name"]

    def test_bool_with_filter(self):
        """Test bool query with filter clause."""
        query = {
            "bool": {
                "must": [{"match": {"description": "invoice"}}],
                "filter": [
                    {"range": {"invoice_total": {"gte": 1000}}},
                    {"term": {"status": "paid"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"description", "invoice_total", "status"}
        assert "filter:range" in result["field_contexts"]["invoice_total"]
        assert "filter:term" in result["field_contexts"]["status"]

    def test_nested_bool_queries(self):
        """Test deeply nested bool queries."""
        query = {
            "bool": {
                "must": [
                    {
                        "bool": {
                            "should": [
                                {"match": {"vendor_name": "Acme"}},
                                {"match": {"company_name": "Acme"}}
                            ]
                        }
                    }
                ],
                "filter": [
                    {"range": {"invoice_total": {"gte": 1000}}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"vendor_name", "company_name", "invoice_total"}

    def test_bool_must_not(self):
        """Test bool query with must_not clause."""
        query = {
            "bool": {
                "must": [{"match": {"status": "active"}}],
                "must_not": [{"term": {"deleted": True}}]
            }
        }
        result = extract_fields_from_es_query(query)

        assert set(result["queried_fields"]) == {"status", "deleted"}
        assert "must_not:term" in result["field_contexts"]["deleted"]


class TestComplexQueries:
    """Test complex real-world query patterns."""

    def test_invoice_search_query(self):
        """Test realistic invoice search query."""
        query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": "Acme Corporation",
                            "fields": ["vendor_name", "company_name"]
                        }
                    }
                ],
                "filter": [
                    {"range": {"invoice_total": {"gte": 1000}}},
                    {"range": {"invoice_date": {"gte": "2024-01-01"}}},
                    {"term": {"status": "paid"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        expected_fields = {
            "vendor_name", "company_name", "invoice_total",
            "invoice_date", "status"
        }
        assert set(result["queried_fields"]) == expected_fields

    def test_empty_query(self):
        """Test extraction from empty query."""
        query = {}
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == []
        assert result["field_contexts"] == {}

    def test_malformed_query(self):
        """Test extraction from malformed query doesn't crash."""
        query = {"match": None}
        result = extract_fields_from_es_query(query)

        # Should handle gracefully
        assert "queried_fields" in result
        assert isinstance(result["queried_fields"], list)


class TestSyntheticFields:
    """Test handling of synthetic/helper fields."""

    def test_synthetic_field_detection(self):
        """Test that synthetic fields are separated."""
        query = {
            "bool": {
                "must": [
                    {"match": {"_all_text": "search term"}},
                    {"match": {"vendor_name": "Acme"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert "vendor_name" in result["queried_fields"]
        assert "_all_text" not in result["queried_fields"]
        assert "_all_text" in result["synthetic_fields"]

    def test_multiple_synthetic_fields(self):
        """Test multiple synthetic fields are flagged."""
        query = {
            "bool": {
                "must": [
                    {"query_string": {"query": "test", "fields": ["_all_text", "_field_index"]}},
                    {"match": {"real_field": "value"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert result["queried_fields"] == ["real_field"]
        assert set(result["synthetic_fields"]) == {"_all_text", "_field_index"}


class TestFieldContexts:
    """Test field context tracking."""

    def test_field_multiple_contexts(self):
        """Test field used in multiple query contexts."""
        query = {
            "bool": {
                "must": [{"match": {"vendor_name": "Acme"}}],
                "should": [{"term": {"vendor_name": "Acme Corp"}}]
            }
        }
        result = extract_fields_from_es_query(query)

        assert "vendor_name" in result["queried_fields"]
        contexts = result["field_contexts"]["vendor_name"]
        assert "must:match" in contexts
        assert "should:term" in contexts
        assert len(contexts) == 2

    def test_field_clause_details(self):
        """Test detailed clause information is captured."""
        query = {"range": {"invoice_total": {"gte": 1000}}}
        result = extract_fields_from_es_query(query)

        assert "invoice_total" in result["field_clauses"]
        clauses = result["field_clauses"]["invoice_total"]
        assert len(clauses) == 1
        assert clauses[0]["type"] == "range"
        assert clauses[0]["clause"] == "query"


class TestAuditItemFiltering:
    """Test audit item filtering by queried fields."""

    def test_filter_audit_items(self):
        """Test basic audit item filtering."""
        audit_items = [
            {"field_name": "vendor_name", "confidence": 0.5, "field_value": "Acme"},
            {"field_name": "address", "confidence": 0.4, "field_value": "123 Main St"},
            {"field_name": "invoice_total", "confidence": 0.7, "field_value": "$1,250"}
        ]
        queried_fields = ["vendor_name", "invoice_total"]

        filtered = filter_audit_items_by_fields(audit_items, queried_fields)

        assert len(filtered) == 2
        assert all(item["field_name"] in queried_fields for item in filtered)

    def test_filter_no_matches(self):
        """Test filtering when no fields match."""
        audit_items = [
            {"field_name": "address", "confidence": 0.4},
            {"field_name": "phone", "confidence": 0.5}
        ]
        queried_fields = ["vendor_name"]

        filtered = filter_audit_items_by_fields(audit_items, queried_fields)

        assert len(filtered) == 0

    def test_filter_all_match(self):
        """Test filtering when all fields match."""
        audit_items = [
            {"field_name": "vendor_name", "confidence": 0.5},
            {"field_name": "invoice_total", "confidence": 0.6}
        ]
        queried_fields = ["vendor_name", "invoice_total", "extra_field"]

        filtered = filter_audit_items_by_fields(audit_items, queried_fields)

        assert len(filtered) == 2

    def test_filter_empty_audit_items(self):
        """Test filtering with empty audit items list."""
        audit_items = []
        queried_fields = ["vendor_name"]

        filtered = filter_audit_items_by_fields(audit_items, queried_fields)

        assert len(filtered) == 0

    def test_filter_empty_queried_fields(self):
        """Test filtering with empty queried fields."""
        audit_items = [
            {"field_name": "vendor_name", "confidence": 0.5}
        ]
        queried_fields = []

        filtered = filter_audit_items_by_fields(audit_items, queried_fields)

        assert len(filtered) == 0


class TestExtractorConfiguration:
    """Test QueryFieldExtractor configuration options."""

    def test_max_depth_limit(self):
        """Test that max depth limit is respected."""
        # Create deeply nested query
        query = {"bool": {"must": [{"bool": {"must": [{"bool": {"must": []}}]}}]}}

        # Should not crash with deep nesting
        extractor = QueryFieldExtractor(max_depth=5)
        result = extractor.extract_fields(query)

        assert isinstance(result["queried_fields"], list)

    def test_extractor_reuse(self):
        """Test that extractor can be reused for multiple queries."""
        extractor = QueryFieldExtractor()

        query1 = {"match": {"field1": "value1"}}
        result1 = extractor.extract_fields(query1)

        query2 = {"match": {"field2": "value2"}}
        result2 = extractor.extract_fields(query2)

        # Results should be independent
        assert result1["queried_fields"] == ["field1"]
        assert result2["queried_fields"] == ["field2"]


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_none_query(self):
        """Test handling of None query."""
        result = extract_fields_from_es_query(None)
        assert result["queried_fields"] == []

    def test_string_query(self):
        """Test handling of string instead of dict."""
        result = extract_fields_from_es_query("not a dict")
        assert result["queried_fields"] == []

    def test_list_query(self):
        """Test handling of list of queries."""
        queries = [
            {"match": {"field1": "value1"}},
            {"term": {"field2": "value2"}}
        ]
        result = extract_fields_from_es_query(queries)

        # Should handle list gracefully
        assert isinstance(result["queried_fields"], list)

    def test_query_with_null_values(self):
        """Test query with null field values."""
        query = {
            "bool": {
                "must": [{"match": {"vendor_name": None}}],
                "filter": None
            }
        }
        result = extract_fields_from_es_query(query)

        # Should still extract field name
        assert "vendor_name" in result["queried_fields"]

    def test_wildcard_in_field_name(self):
        """Test handling of wildcard in field names."""
        query = {
            "query_string": {
                "query": "test",
                "fields": ["vendor*", "company_name"]
            }
        }
        result = extract_fields_from_es_query(query)

        # Should strip wildcards
        assert set(result["queried_fields"]) == {"vendor", "company_name"}


class TestStatistics:
    """Test extraction statistics."""

    def test_statistics_counts(self):
        """Test that statistics are calculated correctly."""
        query = {
            "bool": {
                "must": [
                    {"match": {"_all_text": "search"}},
                    {"match": {"vendor_name": "Acme"}},
                    {"term": {"status": "active"}}
                ]
            }
        }
        result = extract_fields_from_es_query(query)

        assert result["real_field_count"] == 2  # vendor_name, status
        assert result["synthetic_field_count"] == 1  # _all_text
        assert result["total_field_references"] == 3

    def test_statistics_with_duplicates(self):
        """Test statistics when same field appears multiple times."""
        query = {
            "bool": {
                "must": [{"match": {"vendor_name": "Acme"}}],
                "should": [{"term": {"vendor_name": "Acme Corp"}}]
            }
        }
        result = extract_fields_from_es_query(query)

        # Should count unique fields
        assert result["real_field_count"] == 1
        assert result["total_field_references"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
