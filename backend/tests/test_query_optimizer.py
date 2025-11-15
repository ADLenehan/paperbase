"""
Unit tests for QueryOptimizer service.

Tests query intent detection, filter extraction, and Elasticsearch query building.
"""
import pytest
from app.services.query_optimizer import QueryOptimizer


@pytest.fixture
def optimizer():
    """Create QueryOptimizer instance."""
    return QueryOptimizer()


@pytest.fixture
def available_fields():
    """Sample available fields."""
    return [
        "invoice_number",
        "invoice_total",
        "invoice_date",
        "vendor_name",
        "status",
        "uploaded_at"
    ]


@pytest.mark.unit
def test_understand_query_intent_retrieve(optimizer, available_fields):
    """Test intent detection for retrieve queries."""
    query = "show me all invoices"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "retrieve"
    assert analysis["confidence"] > 0.5


@pytest.mark.unit
def test_understand_query_intent_aggregate(optimizer, available_fields):
    """Test intent detection for aggregate queries."""
    query = "how many invoices are there"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "aggregate"
    assert len(analysis["aggregations"]) > 0


@pytest.mark.unit
def test_understand_query_intent_filter(optimizer, available_fields):
    """Test intent detection for filter queries."""
    query = "filter invoices where status is completed"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "filter"


@pytest.mark.unit
def test_extract_numeric_filters_over(optimizer, available_fields):
    """Test extracting 'over X' numeric filters."""
    query = "invoices over $1000"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "range"
    assert filter_spec["operator"] == "gte"
    assert filter_spec["value"] == 1000.0


@pytest.mark.unit
def test_extract_numeric_filters_under(optimizer, available_fields):
    """Test extracting 'under X' numeric filters."""
    query = "invoices under $500"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "range"
    assert filter_spec["operator"] == "lte"
    assert filter_spec["value"] == 500.0


@pytest.mark.unit
def test_extract_numeric_filters_between(optimizer, available_fields):
    """Test extracting 'between X and Y' numeric filters."""
    query = "invoices between $1000 and $5000"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "range"
    assert filter_spec["operator"] == "range"
    assert filter_spec["value"]["gte"] == 1000.0
    assert filter_spec["value"]["lte"] == 5000.0


@pytest.mark.unit
def test_extract_date_filters_last_week(optimizer, available_fields):
    """Test extracting 'last week' date filters."""
    query = "invoices from last week"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "date_range"
    assert filter_spec["range"] == "last_week"


@pytest.mark.unit
def test_extract_date_filters_last_month(optimizer, available_fields):
    """Test extracting 'last month' date filters."""
    query = "show me invoices from last month"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "date_range"
    assert filter_spec["range"] == "last_month"


@pytest.mark.unit
def test_extract_date_filters_today(optimizer, available_fields):
    """Test extracting 'today' date filters."""
    query = "invoices uploaded today"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "date_range"
    assert filter_spec["range"] == "today"


@pytest.mark.unit
def test_extract_text_filters_quoted(optimizer, available_fields):
    """Test extracting quoted text filters."""
    query = 'invoices from "Acme Corp"'
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "match_phrase"
    assert filter_spec["value"] == "Acme Corp"


@pytest.mark.unit
def test_extract_text_filters_status(optimizer, available_fields):
    """Test extracting status filters."""
    query = "show completed invoices"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) > 0
    filter_spec = analysis["filters"][0]
    assert filter_spec["type"] == "term"
    assert filter_spec["field"] == "status"
    assert filter_spec["value"] == "completed"


@pytest.mark.unit
def test_detect_exact_match_requirement(optimizer, available_fields):
    """Test detecting exact match requirements."""
    query = 'find exactly "INV-12345"'
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["query_type"] == "exact"


@pytest.mark.unit
def test_detect_full_text_requirement(optimizer, available_fields):
    """Test detecting full text search requirement."""
    query = "find invoices with detailed description of services provided"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["requires_full_text"] is True


@pytest.mark.unit
def test_detect_sort_recent(optimizer, available_fields):
    """Test detecting recent/latest sorting."""
    query = "show me the most recent invoices"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["sort"] is not None
    assert analysis["sort"]["field"] == "uploaded_at"
    assert analysis["sort"]["order"] == "desc"


@pytest.mark.unit
def test_detect_sort_oldest(optimizer, available_fields):
    """Test detecting oldest sorting."""
    query = "show me the oldest invoices"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["sort"] is not None
    assert analysis["sort"]["field"] == "uploaded_at"
    assert analysis["sort"]["order"] == "asc"


@pytest.mark.unit
def test_detect_aggregation_sum(optimizer, available_fields):
    """Test detecting sum aggregation."""
    query = "what is the total sum of all invoices"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "aggregate"
    assert len(analysis["aggregations"]) > 0
    assert analysis["aggregations"][0]["type"] == "sum"


@pytest.mark.unit
def test_detect_aggregation_average(optimizer, available_fields):
    """Test detecting average aggregation."""
    query = "what is the average invoice amount"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "aggregate"
    assert len(analysis["aggregations"]) > 0
    assert analysis["aggregations"][0]["type"] == "avg"


@pytest.mark.unit
def test_detect_aggregation_count(optimizer, available_fields):
    """Test detecting count aggregation."""
    query = "how many invoices do we have"
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert analysis["intent"] == "aggregate"
    assert len(analysis["aggregations"]) > 0
    assert analysis["aggregations"][0]["type"] == "count"


@pytest.mark.unit
def test_resolve_field_exact_match(optimizer, available_fields):
    """Test field resolution with exact match."""
    field = optimizer._resolve_field("invoice_total", available_fields)
    
    assert field == "invoice_total"


@pytest.mark.unit
def test_resolve_field_alias_match(optimizer, available_fields):
    """Test field resolution with alias match."""
    field = optimizer._resolve_field("amount", available_fields)
    
    assert field in available_fields
    assert "total" in field.lower()


@pytest.mark.unit
def test_find_target_field_with_context(optimizer, available_fields):
    """Test finding target field with query context."""
    query_lower = "invoices with total over 1000"
    
    field = optimizer._find_target_field(query_lower, available_fields, "amount")
    
    assert field == "invoice_total"


@pytest.mark.unit
def test_build_optimized_query_exact(optimizer, available_fields):
    """Test building exact match query."""
    query = "INV-12345"
    analysis = {
        "intent": "search",
        "query_type": "exact",
        "filters": [],
        "requires_full_text": False
    }
    
    es_query = optimizer.build_optimized_query(query, analysis, available_fields)
    
    assert "bool" in es_query
    assert "must" in es_query["bool"]
    assert "match_phrase" in es_query["bool"]["must"][0]


@pytest.mark.unit
def test_build_optimized_query_full_text(optimizer, available_fields):
    """Test building full text search query."""
    query = "invoice for services rendered"
    analysis = {
        "intent": "search",
        "query_type": "hybrid",
        "filters": [],
        "requires_full_text": True
    }
    
    es_query = optimizer.build_optimized_query(query, analysis, available_fields)
    
    assert "bool" in es_query
    assert "must" in es_query["bool"]
    assert "multi_match" in es_query["bool"]["must"][0]


@pytest.mark.unit
def test_build_optimized_query_with_range_filter(optimizer, available_fields):
    """Test building query with range filter."""
    query = "invoices"
    analysis = {
        "intent": "search",
        "query_type": "hybrid",
        "filters": [
            {
                "type": "range",
                "field": "invoice_total",
                "operator": "gte",
                "value": 1000.0
            }
        ],
        "requires_full_text": False
    }
    
    es_query = optimizer.build_optimized_query(query, analysis, available_fields)
    
    assert "bool" in es_query
    assert "filter" in es_query["bool"]
    assert "range" in es_query["bool"]["filter"][0]


@pytest.mark.unit
def test_build_optimized_query_with_date_range(optimizer, available_fields):
    """Test building query with date range filter."""
    query = "invoices"
    analysis = {
        "intent": "search",
        "query_type": "hybrid",
        "filters": [
            {
                "type": "date_range",
                "field": "uploaded_at",
                "range": "last_week"
            }
        ],
        "requires_full_text": False
    }
    
    es_query = optimizer.build_optimized_query(query, analysis, available_fields)
    
    assert "bool" in es_query
    assert "filter" in es_query["bool"]
    assert "range" in es_query["bool"]["filter"][0]


@pytest.mark.unit
def test_build_optimized_query_with_term_filter(optimizer, available_fields):
    """Test building query with term filter."""
    query = "invoices"
    analysis = {
        "intent": "search",
        "query_type": "hybrid",
        "filters": [
            {
                "type": "term",
                "field": "status",
                "value": "completed"
            }
        ],
        "requires_full_text": False
    }
    
    es_query = optimizer.build_optimized_query(query, analysis, available_fields)
    
    assert "bool" in es_query
    assert "filter" in es_query["bool"]
    assert "term" in es_query["bool"]["filter"][0]


@pytest.mark.unit
def test_get_date_range_today(optimizer):
    """Test getting date range for 'today'."""
    date_range = optimizer._get_date_range("today")
    
    assert "gte" in date_range
    assert "lte" in date_range
    assert "now/d" in date_range["gte"]


@pytest.mark.unit
def test_get_date_range_last_week(optimizer):
    """Test getting date range for 'last week'."""
    date_range = optimizer._get_date_range("last_week")
    
    assert "gte" in date_range
    assert "lte" in date_range


@pytest.mark.unit
def test_get_date_range_last_30_days(optimizer):
    """Test getting date range for 'last 30 days'."""
    date_range = optimizer._get_date_range("last_30_days")
    
    assert "gte" in date_range
    assert "lte" in date_range
    assert "now-30d" in date_range["gte"]


@pytest.mark.unit
def test_should_use_claude_low_confidence(optimizer):
    """Test Claude usage decision for low confidence."""
    analysis = {
        "confidence": 0.5,
        "aggregations": []
    }
    
    should_use = optimizer.should_use_claude(analysis)
    
    assert should_use is True


@pytest.mark.unit
def test_should_use_claude_high_confidence(optimizer):
    """Test Claude usage decision for high confidence."""
    analysis = {
        "confidence": 0.85,
        "aggregations": []
    }
    
    should_use = optimizer.should_use_claude(analysis)
    
    assert should_use is False


@pytest.mark.unit
def test_should_use_claude_complex_aggregations(optimizer):
    """Test Claude usage decision for complex aggregations."""
    analysis = {
        "confidence": 0.75,
        "aggregations": [
            {"type": "sum"},
            {"type": "avg"}
        ]
    }
    
    should_use = optimizer.should_use_claude(analysis)
    
    assert should_use is True


@pytest.mark.unit
def test_complex_query_with_multiple_filters(optimizer, available_fields):
    """Test complex query with multiple filters."""
    query = 'invoices from "Acme Corp" over $1000 from last month'
    
    analysis = optimizer.understand_query_intent(query, available_fields)
    
    assert len(analysis["filters"]) >= 2
    assert analysis["confidence"] > 0.6


@pytest.mark.unit
def test_confidence_calculation(optimizer, available_fields):
    """Test confidence score calculation."""
    query1 = "show invoices"
    analysis1 = optimizer.understand_query_intent(query1, available_fields)
    
    query2 = "show invoices over $1000 from last week"
    analysis2 = optimizer.understand_query_intent(query2, available_fields)
    
    assert analysis2["confidence"] > analysis1["confidence"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_initialize_from_registry(optimizer):
    """Test initialization from schema registry."""
    class MockRegistry:
        async def get_canonical_field_mapping(self):
            return {
                "amount": ["invoice_total", "payment_amount"],
                "date": ["invoice_date", "payment_date"]
            }
    
    optimizer.schema_registry = MockRegistry()
    await optimizer.initialize_from_registry()
    
    assert "amount" in optimizer.field_aliases
    assert "invoice_total" in optimizer.field_aliases["amount"]
