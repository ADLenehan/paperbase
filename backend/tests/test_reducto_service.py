"""
Unit tests for Reducto service.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.reducto_service import ReductoService
from app.core.exceptions import ReductoError, FileUploadError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_document_success():
    """Test successful document parsing"""
    service = ReductoService()

    mock_response = {
        "chunks": [
            {
                "id": "chunk_1",
                "text": "Sample text",
                "page": 1,
                "logprobs_confidence": 0.92
            }
        ],
        "metadata": {"pages": 1}
    }

    with patch("app.services.reducto_service.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock()
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = Mock()
        mock_client.return_value.__aenter__.return_value.post = mock_post

        with patch("builtins.open", create=True):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    result = await service.parse_document("/tmp/test.pdf")

    assert "result" in result
    assert "confidence_scores" in result
    assert result["result"] == mock_response
    assert "chunk_1" in result["confidence_scores"]
    assert result["confidence_scores"]["chunk_1"] == 0.92


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_document_file_not_found():
    """Test parsing with non-existent file"""
    service = ReductoService()

    with pytest.raises(FileUploadError) as exc_info:
        await service.parse_document("/tmp/nonexistent.pdf")

    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_parse_document_api_error():
    """Test handling Reducto API errors"""
    service = ReductoService()

    with patch("app.services.reducto_service.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock()
        mock_post.return_value.raise_for_status.side_effect = Exception("API Error")
        mock_client.return_value.__aenter__.return_value.post = mock_post

        with patch("builtins.open", create=True):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with pytest.raises(ReductoError):
                        await service.parse_document("/tmp/test.pdf")


@pytest.mark.unit
def test_extract_confidence_scores():
    """Test confidence score extraction from chunks"""
    service = ReductoService()

    result = {
        "chunks": [
            {"id": "1", "logprobs_confidence": 0.9},
            {"id": "2", "logprobs_confidence": 0.8},
            {"id": "3", "text": "no confidence"}
        ]
    }

    scores = service._extract_confidence_scores(result)

    assert "1" in scores
    assert "2" in scores
    assert scores["1"] == 0.9
    assert scores["2"] == 0.8
    assert "3" not in scores


@pytest.mark.unit
def test_get_confidence_label():
    """Test confidence label generation"""
    service = ReductoService()

    assert service.get_confidence_label(0.9) == "High"
    assert service.get_confidence_label(0.75) == "Medium"
    assert service.get_confidence_label(0.5) == "Low"


@pytest.mark.unit
def test_extract_field_from_chunks():
    """Test field extraction from chunks using hints"""
    service = ReductoService()

    chunks = [
        {
            "id": "1",
            "text": "Invoice #12345\nDate: 2024-01-15",
            "page": 1,
            "logprobs_confidence": 0.92
        },
        {
            "id": "2",
            "text": "Total: $1,250.00",
            "page": 1,
            "logprobs_confidence": 0.88
        }
    ]

    # Test finding invoice number
    result = service.extract_field_from_chunks(chunks, ["Invoice #", "Invoice No"])

    assert result is not None
    assert result["confidence"] == 0.92
    assert result["page"] == 1
    assert "12345" in result["value"]


@pytest.mark.unit
def test_extract_field_from_chunks_not_found():
    """Test field extraction when hint not found"""
    service = ReductoService()

    chunks = [
        {
            "id": "1",
            "text": "Some random text",
            "page": 1,
            "logprobs_confidence": 0.92
        }
    ]

    result = service.extract_field_from_chunks(chunks, ["Invoice #", "Invoice No"])

    assert result is None


@pytest.mark.unit
def test_extract_value_after_hint():
    """Test value extraction after hint"""
    service = ReductoService()

    text = "Invoice #: 12345\nDate: 2024-01-15"

    value = service._extract_value_after_hint(text, "Invoice #")
    assert value == "12345"

    value = service._extract_value_after_hint(text, "Date:")
    assert value == "2024-01-15"

    value = service._extract_value_after_hint(text, "Not found")
    assert value == ""
