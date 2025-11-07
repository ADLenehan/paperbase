"""
Unit tests for audit helper utilities.

Tests the helper functions that generate audit metadata for low-confidence fields.
"""

import pytest
from sqlalchemy.orm import Session
from app.utils.audit_helpers import (
    get_low_confidence_fields_for_documents,
    get_confidence_summary,
    build_audit_url
)
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.settings import Organization, User


@pytest.fixture
def test_data(db: Session):
    """Create test documents with varying confidence scores."""

    # Create organization and user for settings
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()

    user = User(
        email="test@example.com",
        hashed_password="test",
        organization_id=org.id,
        is_active=True
    )
    db.add(user)
    db.flush()

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
            }
        ]
    )
    db.add(schema)
    db.flush()

    # Create documents with different confidence patterns
    doc1 = Document(
        schema_id=schema.id,
        filename="invoice_high_conf.pdf",
        file_path="/test/invoice_high_conf.pdf",
        status="completed"
    )
    db.add(doc1)
    db.flush()

    doc2 = Document(
        schema_id=schema.id,
        filename="invoice_low_conf.pdf",
        file_path="/test/invoice_low_conf.pdf",
        status="completed"
    )
    db.add(doc2)
    db.flush()

    # Document 1: All high confidence
    field1_high = ExtractedField(
        document_id=doc1.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.95,
        verified=False,
        source_page=1,
        source_bbox=[100, 200, 50, 20]
    )
    field2_high = ExtractedField(
        document_id=doc1.id,
        field_name="vendor_name",
        field_value="Acme Corp",
        confidence_score=0.92,
        verified=False,
        source_page=1,
        source_bbox=[100, 250, 80, 15]
    )

    # Document 2: Mixed confidence (one low, one medium)
    field1_low = ExtractedField(
        document_id=doc2.id,
        field_name="invoice_total",
        field_value="2100.00",
        confidence_score=0.58,  # LOW
        verified=False,
        source_page=1,
        source_bbox=[100, 200, 50, 20]
    )
    field2_medium = ExtractedField(
        document_id=doc2.id,
        field_name="vendor_name",
        field_value="Beta Inc",
        confidence_score=0.72,  # MEDIUM
        verified=False,
        source_page=1,
        source_bbox=[100, 250, 80, 15]
    )

    db.add_all([field1_high, field2_high, field1_low, field2_medium])
    db.commit()

    return {
        "org": org,
        "user": user,
        "schema": schema,
        "doc1": doc1,  # High confidence
        "doc2": doc2,  # Low confidence
        "field1_low": field1_low,
        "field2_medium": field2_medium
    }


@pytest.mark.asyncio
async def test_get_low_confidence_fields_returns_only_low_conf(db: Session, test_data):
    """Test that only fields below threshold are returned."""

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc1"].id, test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6  # Only fields < 0.6
    )

    # Should only return doc2's invoice_total (0.58)
    assert len(result) == 1
    assert test_data["doc2"].id in result
    assert len(result[test_data["doc2"].id]) == 1

    field_data = result[test_data["doc2"].id][0]
    assert field_data["field_name"] == "invoice_total"
    assert field_data["confidence"] == 0.58
    assert field_data["field_value"] == "2100.00"


@pytest.mark.asyncio
async def test_get_low_confidence_fields_includes_audit_url(db: Session, test_data):
    """Test that audit URLs are properly formatted."""

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6
    )

    field_data = result[test_data["doc2"].id][0]

    # Verify audit URL format
    assert "audit_url" in field_data
    audit_url = field_data["audit_url"]

    assert "/audit?" in audit_url
    assert f"field_id={test_data['field1_low'].id}" in audit_url
    assert f"document_id={test_data['doc2'].id}" in audit_url
    assert "highlight=true" in audit_url
    assert "source=ai_answer" in audit_url


@pytest.mark.asyncio
async def test_get_low_confidence_fields_includes_bbox_metadata(db: Session, test_data):
    """Test that source page and bbox are included."""

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6
    )

    field_data = result[test_data["doc2"].id][0]

    assert field_data["source_page"] == 1
    assert field_data["source_bbox"] == [100, 200, 50, 20]
    assert field_data["filename"] == "invoice_low_conf.pdf"
    assert field_data["document_id"] == test_data["doc2"].id


@pytest.mark.asyncio
async def test_get_low_confidence_fields_excludes_verified(db: Session, test_data):
    """Test that verified fields are excluded by default."""

    # Mark the low-confidence field as verified
    field = db.query(ExtractedField).filter(
        ExtractedField.id == test_data["field1_low"].id
    ).first()
    field.verified = True
    db.commit()

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6,
        include_verified=False
    )

    # Should return empty (verified field excluded)
    assert len(result) == 0 or test_data["doc2"].id not in result


@pytest.mark.asyncio
async def test_get_low_confidence_fields_includes_verified_when_requested(db: Session, test_data):
    """Test that verified fields can be included if requested."""

    # Mark the low-confidence field as verified
    field = db.query(ExtractedField).filter(
        ExtractedField.id == test_data["field1_low"].id
    ).first()
    field.verified = True
    db.commit()

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6,
        include_verified=True
    )

    # Should include verified field
    assert test_data["doc2"].id in result
    assert len(result[test_data["doc2"].id]) >= 1


@pytest.mark.asyncio
async def test_get_low_confidence_fields_empty_document_list(db: Session):
    """Test handling of empty document list."""

    result = await get_low_confidence_fields_for_documents(
        document_ids=[],
        db=db,
        confidence_threshold=0.6
    )

    assert result == {}


@pytest.mark.asyncio
async def test_get_confidence_summary_calculates_correctly(db: Session, test_data):
    """Test that confidence summary statistics are accurate."""

    summary = await get_confidence_summary(
        document_ids=[test_data["doc2"].id],
        db=db,
        high_threshold=0.8,
        medium_threshold=0.6
    )

    # Doc2 has: 1 low (0.58), 1 medium (0.72)
    assert summary["low_confidence_count"] == 1
    assert summary["medium_confidence_count"] == 1
    assert summary["high_confidence_count"] == 0
    assert summary["total_fields"] == 2
    assert summary["audit_recommended"] is True

    # Average: (0.58 + 0.72) / 2 = 0.65
    assert 0.64 <= summary["avg_confidence"] <= 0.66


@pytest.mark.asyncio
async def test_get_confidence_summary_multiple_documents(db: Session, test_data):
    """Test confidence summary across multiple documents."""

    summary = await get_confidence_summary(
        document_ids=[test_data["doc1"].id, test_data["doc2"].id],
        db=db,
        high_threshold=0.8,
        medium_threshold=0.6
    )

    # Doc1: 2 high (0.95, 0.92)
    # Doc2: 1 low (0.58), 1 medium (0.72)
    # Total: 2 high, 1 medium, 1 low
    assert summary["high_confidence_count"] == 2
    assert summary["medium_confidence_count"] == 1
    assert summary["low_confidence_count"] == 1
    assert summary["total_fields"] == 4
    assert summary["audit_recommended"] is True  # Has low-confidence fields


@pytest.mark.asyncio
async def test_get_confidence_summary_empty_documents(db: Session):
    """Test confidence summary with no documents."""

    summary = await get_confidence_summary(
        document_ids=[],
        db=db
    )

    assert summary["high_confidence_count"] == 0
    assert summary["medium_confidence_count"] == 0
    assert summary["low_confidence_count"] == 0
    assert summary["total_fields"] == 0
    assert summary["avg_confidence"] == 0.0
    assert summary["audit_recommended"] is False


def test_build_audit_url_basic():
    """Test basic audit URL generation."""

    url = build_audit_url(
        field_id=123,
        document_id=45
    )

    assert url == "/audit?field_id=123&document_id=45&highlight=true&source=ai_answer"


def test_build_audit_url_with_custom_source():
    """Test audit URL with custom source."""

    url = build_audit_url(
        field_id=123,
        document_id=45,
        source="mcp_rag"
    )

    assert "source=mcp_rag" in url


def test_build_audit_url_with_query_id():
    """Test audit URL with query ID for tracking."""

    url = build_audit_url(
        field_id=123,
        document_id=45,
        query_id="abc123"
    )

    assert "query_id=abc123" in url


def test_build_audit_url_no_highlight():
    """Test audit URL without auto-highlight."""

    url = build_audit_url(
        field_id=123,
        document_id=45,
        highlight=False
    )

    assert "highlight" not in url


@pytest.mark.asyncio
async def test_get_low_confidence_fields_groups_by_document(db: Session, test_data):
    """Test that results are properly grouped by document_id."""

    # Create another low-confidence field in doc2
    field3_low = ExtractedField(
        document_id=test_data["doc2"].id,
        field_name="invoice_date",
        field_value="2024-01-15",
        confidence_score=0.55,
        verified=False
    )
    db.add(field3_low)
    db.commit()

    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=0.6
    )

    # Should have 2 low-confidence fields for doc2
    assert len(result[test_data["doc2"].id]) == 2
    field_names = {f["field_name"] for f in result[test_data["doc2"].id]}
    assert "invoice_total" in field_names
    assert "invoice_date" in field_names


@pytest.mark.asyncio
async def test_get_low_confidence_fields_uses_settings_threshold(db: Session, test_data):
    """Test that default threshold comes from settings."""

    # When threshold is None, should use settings (default 0.6)
    result = await get_low_confidence_fields_for_documents(
        document_ids=[test_data["doc2"].id],
        db=db,
        confidence_threshold=None  # Use settings
    )

    # Should return field with confidence 0.58 (below default 0.6)
    assert test_data["doc2"].id in result
    assert len(result[test_data["doc2"].id]) >= 1
