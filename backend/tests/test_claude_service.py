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
