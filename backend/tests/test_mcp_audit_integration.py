"""
Integration tests for MCP RAG endpoint with audit metadata.

Tests that the /api/mcp/search/rag/query endpoint properly includes
audit items and confidence summaries for low-confidence fields.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.document import Document, ExtractedField
from app.models.schema import Schema


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_documents_with_low_confidence(db: Session):
    """Create test documents with low-confidence fields for RAG testing."""

    # Create schema
    schema = Schema(
        name="Test Invoice",
        category="invoices",
        fields=[
            {
                "name": "invoice_total",
                "type": "number",
                "required": True
            },
            {
                "name": "vendor_name",
                "type": "text",
                "required": True
            },
            {
                "name": "invoice_date",
                "type": "date",
                "required": True
            }
        ]
    )
    db.add(schema)
    db.flush()

    # Document 1: High confidence invoice
    doc1 = Document(
        schema_id=schema.id,
        filename="invoice_001.pdf",
        file_path="/test/invoice_001.pdf",
        status="completed",
        elasticsearch_id="1"
    )
    db.add(doc1)
    db.flush()

    # High confidence fields
    ExtractedField(
        document_id=doc1.id,
        field_name="invoice_total",
        field_value="1500.00",
        confidence_score=0.95,
        verified=False,
        source_page=1,
        source_bbox=[100, 200, 50, 20]
    )
    ExtractedField(
        document_id=doc1.id,
        field_name="vendor_name",
        field_value="Acme Corp",
        confidence_score=0.92,
        verified=False,
        source_page=1,
        source_bbox=[100, 250, 80, 15]
    )

    # Document 2: Low confidence invoice
    doc2 = Document(
        schema_id=schema.id,
        filename="invoice_002.pdf",
        file_path="/test/invoice_002.pdf",
        status="completed",
        elasticsearch_id="2"
    )
    db.add(doc2)
    db.flush()

    # Low confidence fields
    field_low_1 = ExtractedField(
        document_id=doc2.id,
        field_name="invoice_total",
        field_value="2100.00",
        confidence_score=0.58,  # LOW
        verified=False,
        source_page=1,
        source_bbox=[100, 200, 50, 20]
    )
    field_low_2 = ExtractedField(
        document_id=doc2.id,
        field_name="vendor_name",
        field_value="Beta Inc",
        confidence_score=0.55,  # LOW
        verified=False,
        source_page=1,
        source_bbox=[100, 250, 80, 15]
    )
    field_medium = ExtractedField(
        document_id=doc2.id,
        field_name="invoice_date",
        field_value="2024-01-15",
        confidence_score=0.75,  # MEDIUM
        verified=False,
        source_page=1,
        source_bbox=[100, 300, 60, 15]
    )

    db.add_all([field_low_1, field_low_2, field_medium])
    db.commit()

    return {
        "doc1": doc1,
        "doc2": doc2,
        "field_low_1": field_low_1,
        "field_low_2": field_low_2
    }


@pytest.mark.integration
def test_mcp_rag_includes_audit_items_for_low_confidence(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that RAG endpoint includes audit_items for low-confidence fields."""

    # Mock Elasticsearch to return our test documents
    mock_elasticsearch.search.return_value = {
        "total": 2,
        "documents": [
            {
                "id": "1",
                "score": 0.9,
                "data": {
                    "filename": "invoice_001.pdf",
                    "full_text": "Invoice from Acme Corp for $1,500",
                    "invoice_total": "1500.00",
                    "vendor_name": "Acme Corp"
                }
            },
            {
                "id": "2",
                "score": 0.8,
                "data": {
                    "filename": "invoice_002.pdf",
                    "full_text": "Invoice from Beta Inc for $2,100",
                    "invoice_total": "2100.00",
                    "vendor_name": "Beta Inc"
                }
            }
        ]
    }

    # Mock Claude answer
    mock_claude.answer_question_about_results.return_value = \
        "Found 2 invoices totaling $3,600. Acme Corp: $1,500, Beta Inc: $2,100."

    # Call RAG endpoint
    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "What are the invoice totals?"}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "success" in data
    assert data["success"] is True
    assert "answer" in data
    assert "audit_items" in data
    assert "confidence_summary" in data
    assert "data_quality" in data

    # Verify audit_items populated
    audit_items = data["audit_items"]
    assert len(audit_items) == 2  # 2 low-confidence fields from doc2

    # Verify audit item structure
    for item in audit_items:
        assert "field_id" in item
        assert "document_id" in item
        assert "field_name" in item
        assert "field_value" in item
        assert "confidence" in item
        assert "audit_url" in item
        assert "source_page" in item
        assert "source_bbox" in item

        # Verify confidence is low
        assert item["confidence"] < 0.6

        # Verify audit URL format
        assert "/audit?" in item["audit_url"]
        assert "source=mcp_rag" in item["audit_url"]
        assert "highlight=true" in item["audit_url"]


@pytest.mark.integration
def test_mcp_rag_confidence_summary_accurate(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that confidence_summary statistics are accurate."""

    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "2",
                "score": 0.8,
                "data": {
                    "filename": "invoice_002.pdf",
                    "full_text": "Invoice from Beta Inc",
                    "invoice_total": "2100.00"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Invoice total is $2,100."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "What is the invoice total?"}
    )

    assert response.status_code == 200
    data = response.json()

    summary = data["confidence_summary"]

    # Doc2 has: 2 low (0.58, 0.55), 1 medium (0.75)
    assert summary["low_confidence_count"] == 2
    assert summary["medium_confidence_count"] == 1
    assert summary["high_confidence_count"] == 0
    assert summary["total_fields"] == 3
    assert summary["audit_recommended"] is True


@pytest.mark.integration
def test_mcp_rag_data_quality_object(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that data_quality provides quick overview."""

    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "2",
                "score": 0.8,
                "data": {
                    "filename": "invoice_002.pdf",
                    "full_text": "Invoice"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Found invoice."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "Show me invoices"}
    )

    data = response.json()
    quality = data["data_quality"]

    assert "total_fields_cited" in quality
    assert "low_confidence_count" in quality
    assert "audit_recommended" in quality
    assert "avg_confidence" in quality

    assert quality["low_confidence_count"] == 2
    assert quality["audit_recommended"] is True


@pytest.mark.integration
def test_mcp_rag_no_audit_items_for_high_confidence(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that no audit_items when all fields are high confidence."""

    # Return only doc1 (all high confidence)
    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "1",
                "score": 0.9,
                "data": {
                    "filename": "invoice_001.pdf",
                    "full_text": "Invoice from Acme Corp",
                    "invoice_total": "1500.00"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Invoice total is $1,500."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "What is the total?"}
    )

    data = response.json()

    # Should have empty audit_items (all fields high confidence)
    assert data["audit_items"] == []
    assert data["confidence_summary"]["low_confidence_count"] == 0
    assert data["data_quality"]["audit_recommended"] is False


@pytest.mark.integration
def test_mcp_rag_backward_compatible(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that all existing response fields are still present."""

    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "1",
                "score": 0.9,
                "data": {
                    "filename": "test.pdf",
                    "full_text": "Test content"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Test answer."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "Test question"}
    )

    data = response.json()

    # Verify all existing fields present
    assert "success" in data
    assert "summary" in data
    assert "question" in data
    assert "answer" in data
    assert "sources" in data
    assert "confidence" in data
    assert "metadata" in data
    assert "next_steps" in data

    # Verify new fields present
    assert "audit_items" in data
    assert "confidence_summary" in data
    assert "data_quality" in data


@pytest.mark.integration
def test_mcp_rag_next_steps_includes_audit_recommendation(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that next_steps includes audit recommendation when needed."""

    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "2",
                "score": 0.8,
                "data": {
                    "filename": "invoice_002.pdf",
                    "full_text": "Invoice"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Found invoice."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "Show invoices"}
    )

    data = response.json()
    next_steps = data["next_steps"]

    # Should include audit recommendation
    assert "to_review_data" in next_steps
    assert next_steps["to_review_data"] is not None
    assert "low-confidence fields" in next_steps["to_review_data"]


@pytest.mark.integration
def test_mcp_rag_audit_url_includes_correct_source(
    client: TestClient,
    test_documents_with_low_confidence,
    mock_elasticsearch,
    mock_claude
):
    """Test that audit URLs have source=mcp_rag for tracking."""

    mock_elasticsearch.search.return_value = {
        "total": 1,
        "documents": [
            {
                "id": "2",
                "score": 0.8,
                "data": {
                    "filename": "invoice_002.pdf",
                    "full_text": "Invoice"
                }
            }
        ]
    }

    mock_claude.answer_question_about_results.return_value = "Found invoice."

    response = client.post(
        "/api/mcp/search/rag/query",
        params={"question": "Show invoices"}
    )

    data = response.json()
    audit_items = data["audit_items"]

    # All audit URLs should have source=mcp_rag
    for item in audit_items:
        assert "source=mcp_rag" in item["audit_url"]
        assert "source=ai_answer" not in item["audit_url"]
