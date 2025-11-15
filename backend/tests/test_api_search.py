"""
Unit tests for search API endpoints.

Tests the natural language search API with query optimization and caching.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_services():
    """Mock all external services."""
    with patch('app.api.search.ElasticsearchService') as mock_es, \
         patch('app.api.search.ClaudeService') as mock_claude, \
         patch('app.api.search.QueryOptimizer') as mock_optimizer, \
         patch('app.api.search.SchemaRegistry') as mock_registry:
        
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        mock_claude_instance = AsyncMock()
        mock_claude.return_value = mock_claude_instance
        
        mock_optimizer_instance = Mock()
        mock_optimizer.return_value = mock_optimizer_instance
        
        mock_registry_instance = AsyncMock()
        mock_registry.return_value = mock_registry_instance
        
        yield {
            'es': mock_es_instance,
            'claude': mock_claude_instance,
            'optimizer': mock_optimizer_instance,
            'registry': mock_registry_instance
        }


@pytest.mark.unit
def test_search_documents_simple_query(client, mock_services):
    """Test simple search query."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.85,
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = False
    mock_services['optimizer'].build_optimized_query.return_value = {
        'bool': {'must': [{'match': {'_all_text': 'invoices'}}]}
    }
    
    mock_services['es'].search.return_value = {
        'total': 2,
        'documents': [
            {'id': '1', 'filename': 'invoice1.pdf', 'data': {}},
            {'id': '2', 'filename': 'invoice2.pdf', 'data': {}}
        ]
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Found 2 invoices',
        'sources_used': ['1', '2'],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'show me invoices'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert 'answer' in data
    assert 'results' in data
    assert data['total'] == 2


@pytest.mark.unit
def test_search_documents_with_filters(client, mock_services):
    """Test search with filters."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'filter',
        'confidence': 0.9,
        'filters': [
            {'type': 'range', 'field': 'invoice_total', 'operator': 'gte', 'value': 1000.0}
        ],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = False
    mock_services['optimizer'].build_optimized_query.return_value = {
        'bool': {
            'must': [{'match_all': {}}],
            'filter': [{'range': {'invoice_total': {'gte': 1000.0}}}]
        }
    }
    
    mock_services['es'].search.return_value = {
        'total': 1,
        'documents': [{'id': '1', 'filename': 'invoice1.pdf', 'data': {}}]
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Found 1 invoice over $1000',
        'sources_used': ['1'],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'invoices over $1000'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1


@pytest.mark.unit
def test_search_documents_low_confidence_uses_claude(client, mock_services):
    """Test that low confidence queries use Claude."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.4,  # Low confidence
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = True
    
    mock_services['claude'].parse_natural_language_query.return_value = {
        'elasticsearch_query': {
            'query': {'bool': {'must': [{'match': {'_all_text': 'complex query'}}]}}
        },
        'explanation': 'Searching for complex query',
        'query_type': 'search'
    }
    
    mock_services['es'].search.return_value = {
        'total': 0,
        'documents': []
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'No results found',
        'sources_used': [],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'complex ambiguous query'
    })
    
    assert response.status_code == 200
    mock_services['claude'].parse_natural_language_query.assert_called_once()


@pytest.mark.unit
def test_search_documents_with_folder_filter(client, mock_services):
    """Test search with folder path filter."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.85,
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = False
    mock_services['optimizer'].build_optimized_query.return_value = {
        'bool': {'must': [{'match_all': {}}]}
    }
    
    mock_services['es'].search.return_value = {
        'total': 1,
        'documents': [{'id': '1', 'filename': 'invoice1.pdf', 'data': {}}]
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Found 1 invoice in folder',
        'sources_used': ['1'],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'invoices',
        'folder_path': 'invoices/acme-corp'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data['folder_path'] == 'invoices/acme-corp'


@pytest.mark.unit
def test_search_documents_with_conversation_history(client, mock_services):
    """Test search with conversation history."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.5,
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = True
    
    mock_services['claude'].parse_natural_language_query.return_value = {
        'elasticsearch_query': {
            'query': {'bool': {'must': [{'match_all': {}}]}}
        },
        'explanation': 'Follow-up query',
        'query_type': 'search'
    }
    
    mock_services['es'].search.return_value = {
        'total': 1,
        'documents': [{'id': '1', 'filename': 'invoice1.pdf', 'data': {}}]
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Follow-up answer',
        'sources_used': ['1'],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    conversation_history = [
        {'role': 'user', 'content': 'Show me invoices'},
        {'role': 'assistant', 'content': 'Found 5 invoices'}
    ]
    
    response = client.post('/api/search', json={
        'query': 'which ones are over $1000?',
        'conversation_history': conversation_history
    })
    
    assert response.status_code == 200


@pytest.mark.unit
def test_search_documents_aggregation_query(client, mock_services):
    """Test aggregation query."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'aggregate',
        'confidence': 0.85,
        'filters': [],
        'aggregations': [{'type': 'sum'}],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = True
    
    mock_services['claude'].parse_natural_language_query.return_value = {
        'elasticsearch_query': {
            'query': {'bool': {'must': [{'match_all': {}}]}}
        },
        'explanation': 'Sum aggregation',
        'query_type': 'aggregation',
        'aggregation': {
            'type': 'sum',
            'field': 'invoice_total'
        }
    }
    
    mock_services['es'].get_aggregations.return_value = {
        'sum': {'value': 15000.0},
        'doc_count': 10
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Total sum is $15,000 across 10 invoices',
        'sources_used': [],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'what is the total sum of all invoices?'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert 'answer' in data


@pytest.mark.unit
def test_search_documents_empty_results(client, mock_services):
    """Test search with no results."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.85,
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = False
    mock_services['optimizer'].build_optimized_query.return_value = {
        'bool': {'must': [{'match': {'_all_text': 'nonexistent'}}]}
    }
    
    mock_services['es'].search.return_value = {
        'total': 0,
        'documents': []
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'No documents found matching your query',
        'sources_used': [],
        'low_confidence_warnings': [],
        'confidence_level': 'high'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'nonexistent documents'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 0
    assert len(data['results']) == 0


@pytest.mark.unit
def test_get_available_filters(client):
    """Test getting available filters."""
    with patch('app.api.search.SchemaRegistry') as mock_registry:
        mock_registry_instance = AsyncMock()
        mock_registry.return_value = mock_registry_instance
        
        mock_registry_instance.get_all_templates_context.return_value = [
            {
                'template_name': 'Invoice',
                'all_field_names': ['invoice_number', 'invoice_total'],
                'fields': {}
            }
        ]
        
        response = client.get('/api/search/filters')
        
        assert response.status_code == 200
        data = response.json()
        assert 'fields' in data


@pytest.mark.unit
def test_get_index_statistics(client):
    """Test getting index statistics."""
    with patch('app.api.search.ElasticsearchService') as mock_es:
        mock_es_instance = AsyncMock()
        mock_es.return_value = mock_es_instance
        
        mock_es_instance.get_index_stats.return_value = {
            'total_documents': 100,
            'total_fields': 50,
            'field_limit': 1000
        }
        
        response = client.get('/api/search/index-stats')
        
        assert response.status_code == 200
        data = response.json()
        assert 'total_documents' in data


@pytest.mark.unit
def test_search_documents_invalid_request(client):
    """Test search with invalid request."""
    response = client.post('/api/search', json={})
    
    assert response.status_code == 422  # Validation error


@pytest.mark.unit
def test_search_documents_with_audit_metadata(client, mock_services):
    """Test search returns audit metadata for low confidence fields."""
    mock_services['optimizer'].understand_query_intent.return_value = {
        'intent': 'search',
        'confidence': 0.85,
        'filters': [],
        'aggregations': [],
        'query_type': 'hybrid',
        'requires_full_text': False,
        'sort': None
    }
    
    mock_services['optimizer'].should_use_claude.return_value = False
    mock_services['optimizer'].build_optimized_query.return_value = {
        'bool': {'must': [{'match_all': {}}]}
    }
    
    mock_services['es'].search.return_value = {
        'total': 1,
        'documents': [{'id': '1', 'filename': 'invoice1.pdf', 'data': {}}]
    }
    
    mock_services['claude'].answer_question_about_results.return_value = {
        'answer': 'Found 1 invoice',
        'sources_used': ['1'],
        'low_confidence_warnings': ['invoice_total has low confidence'],
        'confidence_level': 'medium'
    }
    
    mock_services['registry'].get_all_templates_context.return_value = []
    
    response = client.post('/api/search', json={
        'query': 'invoices'
    })
    
    assert response.status_code == 200
    data = response.json()
    assert 'audit_items' in data
    assert 'confidence_summary' in data
