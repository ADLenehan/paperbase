"""
Unit tests for analytics endpoints.
"""
import pytest
from datetime import datetime, timedelta
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.verification import Verification


@pytest.mark.unit
def test_get_dashboard_metrics_empty(client, db_session):
    """Test dashboard metrics with no data"""
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200

    data = response.json()
    assert data["documents"]["total"] == 0
    assert data["verification"]["queue_size"] == 0
    assert data["processing"]["error_rate"] == 0


@pytest.mark.unit
def test_get_dashboard_metrics_with_data(client, db_session):
    """Test dashboard metrics with sample data"""
    # Create schema
    schema = Schema(
        name="Test Schema",
        fields=[{"name": "test_field", "type": "text"}]
    )
    db_session.add(schema)
    db_session.commit()

    # Create documents
    doc1 = Document(
        filename="test1.pdf",
        file_path="/tmp/test1.pdf",
        schema_id=schema.id,
        status="completed",
        uploaded_at=datetime.utcnow() - timedelta(hours=2),
        processed_at=datetime.utcnow() - timedelta(hours=1)
    )
    doc2 = Document(
        filename="test2.pdf",
        file_path="/tmp/test2.pdf",
        schema_id=schema.id,
        status="processing"
    )
    doc3 = Document(
        filename="test3.pdf",
        file_path="/tmp/test3.pdf",
        schema_id=schema.id,
        status="error"
    )

    db_session.add_all([doc1, doc2, doc3])
    db_session.commit()

    # Create extracted fields
    field1 = ExtractedField(
        document_id=doc1.id,
        field_name="test_field",
        value="test value",
        confidence_score=0.85,
        needs_verification=False,
        verified=False,
        extracted_at=datetime.utcnow()
    )
    field2 = ExtractedField(
        document_id=doc1.id,
        field_name="test_field",
        value="test value 2",
        confidence_score=0.55,
        needs_verification=True,
        verified=False,
        extracted_at=datetime.utcnow()
    )

    db_session.add_all([field1, field2])
    db_session.commit()

    # Create verification
    verification = Verification(
        extracted_field_id=field1.id,
        verification_type="correct",
        verified_at=datetime.utcnow()
    )
    db_session.add(verification)
    db_session.commit()

    # Test endpoint
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200

    data = response.json()
    assert data["documents"]["total"] == 3
    assert data["documents"]["completed"] == 1
    assert data["documents"]["processing"] == 1
    assert data["documents"]["errors"] == 1
    assert data["verification"]["queue_size"] == 1
    assert data["verification"]["total_verified"] == 1
    assert data["verification"]["accuracy"] == 100.0


@pytest.mark.unit
def test_get_schema_stats(client, db_session):
    """Test schema statistics endpoint"""
    # Create schemas
    schema1 = Schema(
        name="Schema 1",
        fields=[
            {"name": "field1", "type": "text"},
            {"name": "field2", "type": "number"}
        ]
    )
    schema2 = Schema(
        name="Schema 2",
        fields=[{"name": "field1", "type": "text"}]
    )

    db_session.add_all([schema1, schema2])
    db_session.commit()

    # Create documents for schema1
    doc1 = Document(
        filename="doc1.pdf",
        file_path="/tmp/doc1.pdf",
        schema_id=schema1.id,
        status="completed"
    )
    doc2 = Document(
        filename="doc2.pdf",
        file_path="/tmp/doc2.pdf",
        schema_id=schema1.id,
        status="completed"
    )

    db_session.add_all([doc1, doc2])
    db_session.commit()

    # Create extracted fields
    field1 = ExtractedField(
        document_id=doc1.id,
        field_name="field1",
        value="value1",
        confidence_score=0.9,
        extracted_at=datetime.utcnow()
    )
    field2 = ExtractedField(
        document_id=doc2.id,
        field_name="field1",
        value="value2",
        confidence_score=0.8,
        extracted_at=datetime.utcnow()
    )

    db_session.add_all([field1, field2])
    db_session.commit()

    # Test endpoint
    response = client.get("/api/analytics/schemas")
    assert response.status_code == 200

    data = response.json()
    assert "schemas" in data
    assert len(data["schemas"]) == 2

    # Find schema1 stats
    schema1_stats = next(s for s in data["schemas"] if s["schema_name"] == "Schema 1")
    assert schema1_stats["document_count"] == 2
    assert schema1_stats["completed_count"] == 2
    assert schema1_stats["field_count"] == 2
    assert schema1_stats["average_confidence"] == 0.85  # (0.9 + 0.8) / 2


@pytest.mark.unit
def test_get_trends(client, db_session):
    """Test trends endpoint"""
    # Create schema
    schema = Schema(
        name="Test Schema",
        fields=[{"name": "field1", "type": "text"}]
    )
    db_session.add(schema)
    db_session.commit()

    # Create documents with different dates
    now = datetime.utcnow()

    for i in range(5):
        doc = Document(
            filename=f"doc{i}.pdf",
            file_path=f"/tmp/doc{i}.pdf",
            schema_id=schema.id,
            status="completed",
            processed_at=now - timedelta(days=i)
        )
        db_session.add(doc)
        db_session.flush()

        field = ExtractedField(
            document_id=doc.id,
            field_name="field1",
            value=f"value{i}",
            confidence_score=0.8 + (i * 0.02),
            extracted_at=now - timedelta(days=i)
        )
        db_session.add(field)

    db_session.commit()

    # Test endpoint
    response = client.get("/api/analytics/trends?days=7")
    assert response.status_code == 200

    data = response.json()
    assert "documents_processed" in data
    assert "confidence_trend" in data
    assert len(data["documents_processed"]) > 0
    assert len(data["confidence_trend"]) > 0


@pytest.mark.unit
def test_get_trends_custom_days(client, db_session):
    """Test trends endpoint with custom day range"""
    response = client.get("/api/analytics/trends?days=30")
    assert response.status_code == 200

    data = response.json()
    assert "documents_processed" in data
    assert "confidence_trend" in data


@pytest.mark.unit
def test_dashboard_confidence_by_field(client, db_session):
    """Test confidence aggregation by field"""
    # Create schema
    schema = Schema(
        name="Test Schema",
        fields=[
            {"name": "field1", "type": "text"},
            {"name": "field2", "type": "number"}
        ]
    )
    db_session.add(schema)
    db_session.commit()

    # Create document
    doc = Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        schema_id=schema.id,
        status="completed"
    )
    db_session.add(doc)
    db_session.commit()

    # Create fields with different confidence scores
    fields = [
        ExtractedField(
            document_id=doc.id,
            field_name="field1",
            value="value1",
            confidence_score=0.9,
            extracted_at=datetime.utcnow()
        ),
        ExtractedField(
            document_id=doc.id,
            field_name="field1",
            value="value2",
            confidence_score=0.8,
            extracted_at=datetime.utcnow()
        ),
        ExtractedField(
            document_id=doc.id,
            field_name="field2",
            value="123",
            confidence_score=0.95,
            extracted_at=datetime.utcnow()
        )
    ]
    db_session.add_all(fields)
    db_session.commit()

    # Test endpoint
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200

    data = response.json()
    confidence_by_field = data["confidence"]["by_field"]

    # Find field1
    field1_data = next(f for f in confidence_by_field if f["field"] == "field1")
    assert field1_data["average"] == 0.85  # (0.9 + 0.8) / 2

    # Find field2
    field2_data = next(f for f in confidence_by_field if f["field"] == "field2")
    assert field2_data["average"] == 0.95
