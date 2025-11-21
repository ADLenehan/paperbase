"""
Unit tests for Claude service.
"""
import pytest
import json
from unittest.mock import Mock, patch
from app.services.claude_service import ClaudeService
from app.core.exceptions import ClaudeError, SchemaError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_sample_documents_success(sample_schema):
    """Test successful schema generation"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [
                    {"text": "Invoice #12345\nDate: 2024-01-15\nTotal: $1,250.00"}
                ]
            }
        }
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(sample_schema))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        result = await service.analyze_sample_documents(parsed_docs)

    assert result["name"] == sample_schema["name"]
    assert len(result["fields"]) == len(sample_schema["fields"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_sample_documents_no_docs():
    """Test schema generation with no documents"""
    service = ClaudeService()

    with pytest.raises(SchemaError) as exc_info:
        await service.analyze_sample_documents([])

    assert "No documents" in str(exc_info.value.message)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_sample_documents_invalid_json():
    """Test handling invalid JSON response"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [{"text": "test"}]
            }
        }
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text="This is not JSON")]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        with pytest.raises(ClaudeError) as exc_info:
            await service.analyze_sample_documents(parsed_docs)

        assert "valid JSON" in str(exc_info.value.message)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analyze_sample_documents_missing_fields():
    """Test handling schema with missing required fields"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [{"text": "test"}]
            }
        }
    ]

    invalid_schema = {"name": "Test"}  # Missing "fields"

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(invalid_schema))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        with pytest.raises(SchemaError) as exc_info:
            await service.analyze_sample_documents(parsed_docs)

        assert "missing" in str(exc_info.value.message).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_reducto_config(sample_schema):
    """Test Reducto config generation from schema"""
    service = ClaudeService()

    config = await service.generate_reducto_config(sample_schema)

    assert config["schema_name"] == sample_schema["name"]
    assert len(config["fields"]) == len(sample_schema["fields"])
    assert config["fields"][0]["name"] == sample_schema["fields"][0]["name"]
    assert config["fields"][0]["hints"] == sample_schema["fields"][0]["extraction_hints"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_improve_extraction_rules():
    """Test extraction rule improvement"""
    service = ClaudeService()

    failed = [{"value": "wrong", "context": "..."}]
    successful = [{"value": "correct", "context": "..."}]

    improvements = {
        "extraction_hints": ["new hint 1", "new hint 2"],
        "patterns": ["\\d{5}"],
        "recommendations": "Use better patterns"
    }

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(improvements))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        result = await service.improve_extraction_rules("test_field", failed, successful)

    assert "extraction_hints" in result
    assert "patterns" in result
    assert len(result["extraction_hints"]) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_suggest_field_from_description():
    """Test field suggestion from natural language"""
    service = ClaudeService()

    field_config = {
        "name": "invoice_total",
        "type": "number",
        "required": False,
        "extraction_hints": ["Total:", "Amount:"],
        "confidence_threshold": 0.75,
        "description": "Invoice total amount"
    }

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(field_config))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        result = await service.suggest_field_from_description(
            "Add a field for invoice total"
        )

    assert result["name"] == "invoice_total"
    assert result["type"] == "number"
    assert len(result["extraction_hints"]) > 0


@pytest.mark.unit
def test_build_schema_generation_prompt():
    """Test schema generation prompt building"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [
                    {"text": "Invoice #12345"},
                    {"text": "Date: 2024-01-15"}
                ]
            }
        },
        {
            "result": {
                "chunks": [
                    {"text": "Invoice #67890"},
                    {"text": "Date: 2024-01-16"}
                ]
            }
        }
    ]

    prompt = service._build_schema_generation_prompt(parsed_docs)

    assert "Invoice #12345" in prompt
    assert "Invoice #67890" in prompt
    assert "JSON" in prompt
    assert "extraction_hints" in prompt


# ==================== NEW TESTS FOR SCHEMA METADATA ENHANCEMENT ====================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schema_generation_includes_search_metadata():
    """Test that generated schemas include search_metadata for each field"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [
                    {"text": "Invoice #12345\nVendor: Acme Corp\nTotal: $1,250.00"}
                ]
            }
        }
    ]

    # Mock schema with search_metadata
    enhanced_schema = {
        "name": "Test Invoices",
        "fields": [
            {
                "name": "vendor_name",
                "type": "text",
                "required": True,
                "extraction_hints": ["Vendor:", "From:"],
                "confidence_threshold": 0.75,
                "description": "Vendor name",
                "search_metadata": {
                    "example_queries": [
                        "what is the vendor name?",
                        "find invoices from Acme Corp",
                        "who is the supplier?"
                    ],
                    "query_keywords": ["vendor", "supplier", "from", "provider"],
                    "aliases": ["vendor", "supplier", "company"],
                    "field_importance": "high",
                    "boost_factor": 10.0
                }
            },
            {
                "name": "invoice_total",
                "type": "number",
                "required": True,
                "extraction_hints": ["Total:", "Amount Due:"],
                "confidence_threshold": 0.85,
                "description": "Invoice total amount",
                "search_metadata": {
                    "example_queries": [
                        "what is the invoice total?",
                        "find invoices over $5000"
                    ],
                    "query_keywords": ["total", "amount", "cost"],
                    "aliases": ["total", "amount", "cost"],
                    "field_importance": "high",
                    "boost_factor": 10.0
                },
                "aggregation_metadata": {
                    "primary_aggregation": "sum",
                    "supported_aggregations": ["sum", "avg", "min", "max"],
                    "group_by_compatible": ["vendor_name", "invoice_date"],
                    "typical_queries": ["total spending", "average invoice amount"]
                }
            }
        ]
    }

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(enhanced_schema))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        result = await service.analyze_sample_documents(parsed_docs)

    # Verify search_metadata is present
    assert len(result["fields"]) == 2

    vendor_field = result["fields"][0]
    assert "search_metadata" in vendor_field
    assert len(vendor_field["search_metadata"]["example_queries"]) >= 2
    assert len(vendor_field["search_metadata"]["query_keywords"]) >= 3
    assert "aliases" in vendor_field["search_metadata"]
    assert vendor_field["search_metadata"]["boost_factor"] == 10.0
    assert vendor_field["search_metadata"]["field_importance"] == "high"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_schema_generation_includes_aggregation_metadata():
    """Test that numeric fields include aggregation_metadata"""
    service = ClaudeService()

    parsed_docs = [
        {
            "result": {
                "chunks": [
                    {"text": "Invoice Total: $1,250.00"}
                ]
            }
        }
    ]

    # Mock schema with aggregation_metadata
    enhanced_schema = {
        "name": "Test Invoices",
        "fields": [
            {
                "name": "invoice_total",
                "type": "number",
                "required": True,
                "extraction_hints": ["Total:"],
                "confidence_threshold": 0.85,
                "description": "Invoice total amount",
                "search_metadata": {
                    "example_queries": ["what is the total?"],
                    "query_keywords": ["total", "amount"],
                    "aliases": ["total", "amount"],
                    "field_importance": "high",
                    "boost_factor": 10.0
                },
                "aggregation_metadata": {
                    "primary_aggregation": "sum",
                    "supported_aggregations": ["sum", "avg", "min", "max", "count"],
                    "group_by_compatible": ["vendor_name", "invoice_date", "status"],
                    "typical_queries": [
                        "total invoice amount",
                        "average invoice value",
                        "spending by vendor"
                    ]
                }
            }
        ]
    }

    mock_response = Mock()
    mock_response.content = [Mock(text=json.dumps(enhanced_schema))]

    with patch.object(service.client.messages, 'create', return_value=mock_response):
        result = await service.analyze_sample_documents(parsed_docs)

    # Verify aggregation_metadata is present
    total_field = result["fields"][0]
    assert "aggregation_metadata" in total_field
    assert total_field["aggregation_metadata"]["primary_aggregation"] == "sum"
    assert len(total_field["aggregation_metadata"]["supported_aggregations"]) >= 4
    assert "vendor_name" in total_field["aggregation_metadata"]["group_by_compatible"]
    assert len(total_field["aggregation_metadata"]["typical_queries"]) >= 2


@pytest.mark.unit
def test_semantic_field_mapping_guide_uses_search_metadata():
    """Test that semantic field mapping guide uses schema search_metadata"""
    service = ClaudeService()

    available_fields = ["vendor_name", "invoice_total"]

    # Mock field metadata with search_metadata
    field_metadata = {
        "fields": {
            "vendor_name": {
                "type": "text",
                "aliases": ["vendor", "supplier"],
                "search_metadata": {
                    "query_keywords": ["vendor", "supplier", "from"],
                    "boost_factor": 10.0
                }
            },
            "invoice_total": {
                "type": "number",
                "aliases": ["total", "amount"],
                "search_metadata": {
                    "query_keywords": ["total", "amount", "cost"],
                    "boost_factor": 10.0
                }
            }
        }
    }

    # Template context with search_metadata
    template_context = {
        "name": "Test Invoices",
        "fields": [
            {
                "name": "vendor_name",
                "type": "text",
                "description": "Vendor name",
                "search_metadata": {
                    "example_queries": [
                        "what is the vendor?",
                        "find invoices from Acme"
                    ],
                    "query_keywords": ["vendor", "supplier", "from"],
                    "boost_factor": 10.0,
                    "field_importance": "high"
                }
            },
            {
                "name": "invoice_total",
                "type": "number",
                "description": "Invoice total",
                "search_metadata": {
                    "example_queries": [
                        "what is the total?",
                        "find invoices over $5000"
                    ],
                    "query_keywords": ["total", "amount", "cost"],
                    "boost_factor": 10.0,
                    "field_importance": "high"
                },
                "aggregation_metadata": {
                    "primary_aggregation": "sum",
                    "supported_aggregations": ["sum", "avg"],
                    "group_by_compatible": ["vendor_name"],
                    "typical_queries": ["total spending"]
                }
            }
        ]
    }

    guide = service._build_semantic_field_mapping_guide(
        available_fields,
        field_metadata,
        template_context
    )

    # Verify guide includes schema-driven metadata
    assert "vendor_name" in guide
    assert "invoice_total" in guide
    assert "HIGH importance" in guide  # From field_importance
    assert "Search boost: 10.0x" in guide  # From boost_factor
    assert "what is the vendor?" in guide  # From example_queries
    assert "find invoices over $5000" in guide  # From example_queries
    assert "Query keywords:" in guide
    assert "vendor, supplier, from" in guide  # From query_keywords

    # Verify aggregation section
    assert "AGGREGATION INTELLIGENCE" in guide
    assert "Primary aggregation: SUM" in guide
    assert "Can group by: vendor_name" in guide
    assert "total spending" in guide  # From typical_queries


@pytest.mark.unit
def test_semantic_field_mapping_guide_fallback_without_metadata():
    """Test that guide falls back gracefully when search_metadata is missing"""
    service = ClaudeService()

    available_fields = ["vendor_name"]

    # Field metadata WITHOUT search_metadata (legacy schema)
    field_metadata = {
        "fields": {
            "vendor_name": {
                "type": "text",
                "aliases": ["vendor", "supplier"]
            }
        }
    }

    # Template context WITHOUT search_metadata
    template_context = {
        "name": "Test Invoices",
        "fields": [
            {
                "name": "vendor_name",
                "type": "text",
                "description": "Vendor name"
                # No search_metadata
            }
        ]
    }

    guide = service._build_semantic_field_mapping_guide(
        available_fields,
        field_metadata,
        template_context
    )

    # Should still generate guide with auto-generated keywords
    assert "vendor_name" in guide
    assert "Query keywords (auto-generated):" in guide  # Falls back to field name parsing
    assert "vendor" in guide or "name" in guide  # Auto-generated from field name


@pytest.mark.unit
def test_schema_registry_prefers_schema_aliases():
    """Test that SchemaRegistry uses schema-provided aliases"""
    from app.services.schema_registry import SchemaRegistry
    from app.models.schema import Schema
    from unittest.mock import Mock

    # Mock database session
    mock_db = Mock()
    registry = SchemaRegistry(mock_db)

    # Test alias preference logic
    field_def = {
        "name": "vendor_name",
        "type": "text",
        "search_metadata": {
            "aliases": ["vendor", "supplier", "company"]  # Schema-provided
        }
    }

    # Extract search_metadata and check preference
    search_meta = field_def.get("search_metadata", {})
    schema_aliases = search_meta.get("aliases", [])

    # Should prefer schema aliases
    assert schema_aliases == ["vendor", "supplier", "company"]
    assert len(schema_aliases) == 3


@pytest.mark.unit
def test_schema_registry_generates_aliases_fallback():
    """Test that SchemaRegistry falls back to auto-generation when no aliases"""
    from app.services.schema_registry import SchemaRegistry
    from unittest.mock import Mock

    mock_db = Mock()
    registry = SchemaRegistry(mock_db)

    # Test fallback logic
    field_def = {
        "name": "vendor_name",
        "type": "text"
        # No search_metadata
    }

    search_meta = field_def.get("search_metadata", {})
    schema_aliases = search_meta.get("aliases", [])

    # Should be empty, triggering fallback to _generate_aliases
    assert schema_aliases == []

    # Test auto-generation
    generated = registry._generate_aliases("vendor_name", "text")
    assert len(generated) > 0
    assert any(alias in ["company", "vendor", "organization"] for alias in generated)
