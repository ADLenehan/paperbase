"""
Unit tests for ElasticsearchService.

Tests the core Elasticsearch operations including indexing, searching,
aggregations, and template matching.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.services.elastic_service import ElasticsearchService


@pytest.fixture
def es_service():
    """Create ElasticsearchService instance with mocked client."""
    with patch('app.services.elastic_service.AsyncElasticsearch') as mock_es:
        service = ElasticsearchService()
        service.client = AsyncMock()
        return service


@pytest.fixture
def sample_schema():
    """Sample schema for testing."""
    return {
        "id": 1,
        "name": "Test Invoice",
        "fields": [
            {
                "name": "invoice_number",
                "type": "text",
                "required": True,
                "extraction_hints": ["Invoice #"],
                "description": "Invoice number"
            },
            {
                "name": "invoice_total",
                "type": "number",
                "required": True,
                "extraction_hints": ["Total:"],
                "description": "Total amount"
            },
            {
                "name": "invoice_date",
                "type": "date",
                "required": True,
                "extraction_hints": ["Date:"],
                "description": "Invoice date"
            }
        ]
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_index_success(es_service, sample_schema):
    """Test successful index creation."""
    es_service.client.indices.exists.return_value = False
    es_service.client.indices.create.return_value = {"acknowledged": True}

    await es_service.create_index(sample_schema)

    es_service.client.indices.create.assert_called_once()
    call_args = es_service.client.indices.create.call_args
    assert call_args[1]["index"] == "documents"
    assert "mappings" in call_args[1]["body"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_index_update_existing(es_service, sample_schema):
    """Test updating existing index."""
    es_service.client.indices.exists.return_value = True
    es_service.client.indices.put_mapping.return_value = {"acknowledged": True}

    await es_service.create_index(sample_schema)

    es_service.client.indices.put_mapping.assert_called_once()
    es_service.client.indices.create.assert_not_called()


@pytest.mark.unit
def test_get_es_field_type(es_service):
    """Test field type mapping."""
    assert es_service._get_es_field_type("text") == "text"
    assert es_service._get_es_field_type("date") == "date"
    assert es_service._get_es_field_type("number") == "float"
    assert es_service._get_es_field_type("integer") == "integer"
    assert es_service._get_es_field_type("boolean") == "boolean"
    assert es_service._get_es_field_type("unknown") == "text"


@pytest.mark.unit
def test_build_complex_field_mapping_array(es_service):
    """Test array field mapping."""
    field = {
        "name": "tags",
        "type": "array",
        "item_type": "text"
    }
    
    mapping = es_service._build_complex_field_mapping(field)
    
    assert mapping["type"] == "text"
    assert "fields" in mapping
    assert "keyword" in mapping["fields"]


@pytest.mark.unit
def test_build_complex_field_mapping_array_of_objects(es_service):
    """Test array_of_objects field mapping."""
    field = {
        "name": "line_items",
        "type": "array_of_objects",
        "object_schema": {
            "description": {"type": "text"},
            "quantity": {"type": "number"},
            "price": {"type": "number"}
        }
    }
    
    mapping = es_service._build_complex_field_mapping(field)
    
    assert mapping["type"] == "object"
    assert "properties" in mapping
    assert "description" in mapping["properties"]
    assert "quantity" in mapping["properties"]
    assert "price" in mapping["properties"]


@pytest.mark.unit
def test_build_complex_field_mapping_table(es_service):
    """Test table field mapping."""
    field = {
        "name": "grading_specs",
        "type": "table",
        "table_schema": {
            "row_identifier": "grade",
            "columns": ["tolerance", "measurement"],
            "value_type": "string",
            "dynamic_columns": True,
            "column_pattern": ".*"
        }
    }
    
    mapping = es_service._build_complex_field_mapping(field)
    
    assert mapping["type"] == "nested"
    assert "properties" in mapping
    assert "grade" in mapping["properties"]
    assert mapping["dynamic"] == "true"
    assert "dynamic_templates" in mapping


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_success(es_service, sample_schema):
    """Test successful document indexing."""
    es_service.client.index.return_value = {"_id": "123"}
    
    extracted_fields = {
        "invoice_number": "INV-001",
        "invoice_total": 1250.00,
        "invoice_date": "2024-01-15"
    }
    confidence_scores = {
        "invoice_number": 0.95,
        "invoice_total": 0.88,
        "invoice_date": 0.92
    }
    
    result = await es_service.index_document(
        document_id=1,
        filename="invoice.pdf",
        extracted_fields=extracted_fields,
        confidence_scores=confidence_scores,
        full_text="Invoice #INV-001 Date: 2024-01-15 Total: $1,250.00",
        schema=sample_schema
    )
    
    assert result == "123"
    es_service.client.index.assert_called_once()
    
    call_args = es_service.client.index.call_args
    doc = call_args[1]["document"]
    
    assert doc["document_id"] == 1
    assert doc["filename"] == "invoice.pdf"
    assert doc["invoice_number"] == "INV-001"
    assert "_query_context" in doc
    assert "_all_text" in doc
    assert "_field_index" in doc
    assert "_confidence_metrics" in doc
    assert "_citation_metadata" in doc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_with_low_confidence(es_service, sample_schema):
    """Test document indexing with low confidence fields."""
    es_service.client.index.return_value = {"_id": "123"}
    
    extracted_fields = {
        "invoice_number": "INV-001",
        "invoice_total": 1250.00
    }
    confidence_scores = {
        "invoice_number": 0.55,  # Low confidence
        "invoice_total": 0.88
    }
    
    result = await es_service.index_document(
        document_id=1,
        filename="invoice.pdf",
        extracted_fields=extracted_fields,
        confidence_scores=confidence_scores,
        schema=sample_schema
    )
    
    call_args = es_service.client.index.call_args
    doc = call_args[1]["document"]
    
    assert doc["_citation_metadata"]["has_low_confidence_fields"] is True
    assert "invoice_number" in doc["_citation_metadata"]["low_confidence_field_names"]


@pytest.mark.unit
def test_build_canonical_fields(es_service):
    """Test canonical field mapping."""
    extracted_fields = {
        "invoice_total": 1250.00,
        "vendor_name": "Acme Corp",
        "invoice_date": "2024-01-15",
        "invoice_number": "INV-001"
    }
    field_metadata = {}
    
    canonical = es_service._build_canonical_fields(extracted_fields, field_metadata)
    
    assert "amount" in canonical
    assert canonical["amount"] == 1250.00
    assert "entity_name" in canonical
    assert canonical["entity_name"] == "Acme Corp"
    assert "date" in canonical
    assert "identifier" in canonical


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_with_query(es_service):
    """Test search with text query."""
    es_service.client.search.return_value = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_id": "1",
                    "_score": 1.5,
                    "_source": {
                        "filename": "invoice1.pdf",
                        "invoice_total": 1250.00
                    },
                    "highlight": {}
                },
                {
                    "_id": "2",
                    "_score": 1.2,
                    "_source": {
                        "filename": "invoice2.pdf",
                        "invoice_total": 2100.00
                    },
                    "highlight": {}
                }
            ]
        }
    }
    
    results = await es_service.search(query="invoice", page=1, size=10)
    
    assert results["total"] == 2
    assert len(results["documents"]) == 2
    assert results["documents"][0]["filename"] == "invoice1.pdf"
    assert results["page"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_with_filters(es_service):
    """Test search with filters."""
    es_service.client.search.return_value = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "1",
                    "_score": 1.5,
                    "_source": {"filename": "invoice1.pdf"},
                    "highlight": {}
                }
            ]
        }
    }
    
    filters = {"status": "completed"}
    results = await es_service.search(filters=filters)
    
    assert results["total"] == 1
    es_service.client.search.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_with_custom_query(es_service):
    """Test search with custom query."""
    es_service.client.search.return_value = {
        "hits": {
            "total": {"value": 0},
            "hits": []
        }
    }
    
    custom_query = {
        "bool": {
            "must": [{"match": {"full_text": "test"}}]
        }
    }
    
    results = await es_service.search(custom_query=custom_query)
    
    assert results["total"] == 0
    es_service.client.search.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_document_success(es_service):
    """Test getting document by ID."""
    es_service.client.get.return_value = {
        "_source": {
            "document_id": 1,
            "filename": "test.pdf"
        }
    }
    
    doc = await es_service.get_document(1)
    
    assert doc is not None
    assert doc["document_id"] == 1
    assert doc["filename"] == "test.pdf"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_document_not_found(es_service):
    """Test getting non-existent document."""
    es_service.client.get.side_effect = Exception("Not found")
    
    doc = await es_service.get_document(999)
    
    assert doc is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_document(es_service):
    """Test updating document fields."""
    es_service.client.update.return_value = {"result": "updated"}
    
    updated_fields = {"invoice_total": 1500.00}
    await es_service.update_document(1, updated_fields)
    
    es_service.client.update.assert_called_once()
    call_args = es_service.client.update.call_args
    assert call_args[1]["id"] == "1"
    assert call_args[1]["doc"] == updated_fields


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_document(es_service):
    """Test deleting document."""
    es_service.client.delete.return_value = {"result": "deleted"}
    
    await es_service.delete_document("123")
    
    es_service.client.delete.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_aggregations(es_service):
    """Test getting aggregations."""
    es_service.client.search.return_value = {
        "aggregations": {
            "status_counts": {
                "buckets": [
                    {"key": "completed", "doc_count": 10},
                    {"key": "pending", "doc_count": 5}
                ]
            }
        }
    }
    
    aggs = await es_service.get_aggregations(
        field="status",
        agg_type="terms"
    )
    
    assert "status_counts" in aggs
    assert len(aggs["status_counts"]["buckets"]) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_multi_aggregations(es_service):
    """Test multiple aggregations in one request."""
    es_service.client.search.return_value = {
        "aggregations": {
            "agg_0": {
                "buckets": [{"key": "completed", "doc_count": 10}]
            },
            "agg_1": {
                "value": 15000.00
            }
        }
    }
    
    aggregations = [
        {"field": "status", "type": "terms"},
        {"field": "invoice_total", "type": "sum"}
    ]
    
    results = await es_service.get_multi_aggregations(aggregations)
    
    assert "agg_0" in results
    assert "agg_1" in results


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check(es_service):
    """Test Elasticsearch health check."""
    es_service.client.ping.return_value = True
    
    is_healthy = await es_service.health_check()
    
    assert is_healthy is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_optimize_for_bulk_indexing(es_service):
    """Test bulk indexing optimization."""
    es_service.client.indices.put_settings.return_value = {"acknowledged": True}
    
    await es_service.optimize_for_bulk_indexing(True)
    
    es_service.client.indices.put_settings.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_refresh_index(es_service):
    """Test index refresh."""
    es_service.client.indices.refresh.return_value = {"_shards": {"successful": 1}}
    
    await es_service.refresh_index()
    
    es_service.client.indices.refresh.assert_called_once()


@pytest.mark.unit
def test_calculate_text_similarity(es_service):
    """Test text similarity calculation."""
    text1 = "Invoice #12345 Date: 2024-01-15 Total: $1,250.00"
    text2 = "Invoice #67890 Date: 2024-01-16 Total: $2,100.00"
    
    similarity = es_service._calculate_text_similarity(text1, text2)
    
    assert 0.0 <= similarity <= 1.0
    assert similarity > 0.3  # Should have some similarity


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_similar_templates(es_service):
    """Test finding similar templates."""
    es_service.client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "1",
                    "_score": 0.85,
                    "_source": {
                        "template_id": 1,
                        "template_name": "Invoice Template"
                    }
                }
            ]
        }
    }
    
    similar = await es_service.find_similar_templates(
        document_text="Invoice #12345",
        document_fields=["invoice_number", "invoice_total"],
        min_score=0.4
    )
    
    assert len(similar) == 1
    assert similar[0]["template_id"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cluster_uploaded_documents(es_service):
    """Test document clustering."""
    documents = [
        {
            "id": 1,
            "full_text": "Invoice #12345 Total: $1,250.00",
            "field_names": ["invoice_number", "invoice_total"]
        },
        {
            "id": 2,
            "full_text": "Invoice #67890 Total: $2,100.00",
            "field_names": ["invoice_number", "invoice_total"]
        },
        {
            "id": 3,
            "full_text": "Contract Agreement between parties",
            "field_names": ["contract_number", "parties"]
        }
    ]
    
    clusters = await es_service.cluster_uploaded_documents(
        documents,
        similarity_threshold=0.75
    )
    
    assert len(clusters) >= 1
    assert all("documents" in cluster for cluster in clusters)
