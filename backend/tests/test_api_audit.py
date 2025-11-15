"""
Unit tests for audit API endpoints.

Tests the audit queue, field verification, and bulk operations.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import Document, ExtractedField
from app.models.schema import Schema


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.unit
def test_get_audit_queue_success(client, db_session):
    """Test getting audit queue."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,  # Low confidence
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    response = client.get('/api/audit/queue')
    
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert 'total' in data


@pytest.mark.unit
def test_get_audit_queue_with_filters(client, db_session):
    """Test getting audit queue with filters."""
    response = client.get('/api/audit/queue?min_confidence=0.5&max_confidence=0.7')
    
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data


@pytest.mark.unit
def test_get_audit_queue_count_only(client, db_session):
    """Test getting audit queue count only."""
    response = client.get('/api/audit/queue?count_only=true')
    
    assert response.status_code == 200
    data = response.json()
    assert 'count' in data
    assert 'priority_counts' in data


@pytest.mark.unit
def test_get_audit_queue_by_priority(client, db_session):
    """Test getting audit queue filtered by priority."""
    response = client.get('/api/audit/queue?priority=critical')
    
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data


@pytest.mark.unit
def test_get_document_audit_fields(client, db_session):
    """Test getting audit fields for specific document."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    response = client.get(f'/api/audit/document/{doc.id}')
    
    assert response.status_code == 200
    data = response.json()
    assert data['document_id'] == doc.id
    assert 'items' in data


@pytest.mark.unit
def test_get_document_audit_fields_not_found(client):
    """Test getting audit fields for non-existent document."""
    response = client.get('/api/audit/document/999999')
    
    assert response.status_code == 404


@pytest.mark.unit
def test_verify_field_correct(client, db_session):
    """Test verifying field as correct."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/verify', json={
            'field_id': field.id,
            'action': 'correct'
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.unit
def test_verify_field_incorrect(client, db_session):
    """Test verifying field as incorrect with correction."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/verify', json={
            'field_id': field.id,
            'action': 'incorrect',
            'corrected_value': '1500.00',
            'notes': 'Corrected value'
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.unit
def test_verify_field_not_found(client, db_session):
    """Test verifying field as not found."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/verify', json={
            'field_id': field.id,
            'action': 'not_found'
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.unit
def test_verify_field_invalid_action(client, db_session):
    """Test verifying field with invalid action."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    response = client.post('/api/audit/verify', json={
        'field_id': field.id,
        'action': 'invalid_action'
    })
    
    assert response.status_code == 400


@pytest.mark.unit
def test_verify_field_missing_corrected_value(client, db_session):
    """Test verifying field as incorrect without corrected value."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    response = client.post('/api/audit/verify', json={
        'field_id': field.id,
        'action': 'incorrect'
    })
    
    assert response.status_code == 400


@pytest.mark.unit
def test_verify_and_regenerate(client, db_session):
    """Test verify field and regenerate answer."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es, \
         patch('app.api.audit.ClaudeService') as mock_claude:
        
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        mock_es_instance.get_document_by_id.return_value = {
            'id': doc.id,
            'filename': 'test.pdf'
        }
        
        mock_claude_instance = AsyncMock()
        mock_claude.return_value = mock_claude_instance
        mock_claude_instance.answer_question_about_results.return_value = {
            'answer': 'Updated answer',
            'sources_used': [str(doc.id)],
            'low_confidence_warnings': [],
            'confidence_level': 'high'
        }
        
        response = client.post('/api/audit/verify-and-regenerate', json={
            'field_id': field.id,
            'action': 'correct',
            'original_query': 'show me invoices',
            'document_ids': [doc.id]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'updated_answer' in data


@pytest.mark.unit
def test_bulk_verify_fields(client, db_session):
    """Test bulk field verification."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field1 = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    field2 = ExtractedField(
        document_id=doc.id,
        field_name="invoice_number",
        field_value="INV-001",
        confidence_score=0.58,
        verified=False
    )
    db_session.add_all([field1, field2])
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/bulk-verify', json={
            'verifications': [
                {'field_id': field1.id, 'action': 'correct'},
                {'field_id': field2.id, 'action': 'correct'}
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['verified_count'] == 2


@pytest.mark.unit
def test_get_audit_stats(client, db_session):
    """Test getting audit statistics."""
    response = client.get('/api/audit/stats')
    
    assert response.status_code == 200
    data = response.json()
    assert 'total_pending' in data
    assert 'by_priority' in data
    assert 'by_template' in data


@pytest.mark.unit
def test_verify_field_updates_elasticsearch(client, db_session):
    """Test that field verification updates Elasticsearch."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc = Document(
        schema_id=schema.id,
        filename="test.pdf",
        file_path="/test/test.pdf",
        status="completed"
    )
    db_session.add(doc)
    db_session.flush()
    
    field = ExtractedField(
        document_id=doc.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    db_session.add(field)
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/verify', json={
            'field_id': field.id,
            'action': 'incorrect',
            'corrected_value': '1500.00'
        })
        
        assert response.status_code == 200
        mock_es_instance.update_document.assert_called_once()


@pytest.mark.unit
def test_verify_field_returns_next_item(client, db_session):
    """Test that field verification returns next item in queue."""
    schema = Schema(name="Test Invoice", category="invoices", fields=[])
    db_session.add(schema)
    db_session.flush()
    
    doc1 = Document(
        schema_id=schema.id,
        filename="test1.pdf",
        file_path="/test/test1.pdf",
        status="completed"
    )
    doc2 = Document(
        schema_id=schema.id,
        filename="test2.pdf",
        file_path="/test/test2.pdf",
        status="completed"
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()
    
    field1 = ExtractedField(
        document_id=doc1.id,
        field_name="invoice_total",
        field_value="1000.00",
        confidence_score=0.55,
        verified=False
    )
    field2 = ExtractedField(
        document_id=doc2.id,
        field_name="invoice_total",
        field_value="2000.00",
        confidence_score=0.52,
        verified=False
    )
    db_session.add_all([field1, field2])
    db_session.commit()
    
    with patch('app.api.audit.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        response = client.post('/api/audit/verify', json={
            'field_id': field1.id,
            'action': 'correct'
        })
        
        assert response.status_code == 200
        data = response.json()
        assert 'next_item' in data
        if data['next_item']:
            assert data['next_item']['field_id'] == field2.id
