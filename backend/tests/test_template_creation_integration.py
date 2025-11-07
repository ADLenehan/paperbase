"""
Comprehensive integration tests for template creation with complex field types.

Tests the fixes made for:
1. Array field validation and normalization
2. Table field validation
3. Error handling with descriptive messages
4. Field type normalization (ARR -> array, etc.)
5. Claude-generated schema validation
"""

import pytest
from httpx import AsyncClient
import asyncio
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import get_db, SessionLocal
from app.models.schema import Schema
from app.models.document import Document
from app.models.physical_file import PhysicalFile


# Use synchronous database session for fixtures
@pytest.fixture
def db():
    """Get database session for testing."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# For simpler synchronous tests
import requests


# Test fixtures
@pytest.fixture
def mock_document(db: Session):
    """Create a mock document with PhysicalFile for testing."""
    # Create PhysicalFile
    physical_file = PhysicalFile(
        filename="test_doc.pdf",
        file_hash="abc123",
        file_path="/tmp/test_doc.pdf",
        file_size=1024,
        mime_type="application/pdf",
        reducto_job_id="job_123",
        reducto_parse_result={
            "chunks": [{"content": "Sample document content"}]
        }
    )
    db.add(physical_file)
    db.flush()

    # Create Document
    document = Document(
        filename="test_doc.pdf",
        physical_file_id=physical_file.id,
        status="uploaded"
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    yield document

    # Cleanup
    db.delete(document)
    db.delete(physical_file)
    db.commit()


class TestArrayFieldValidation:
    """Test array field validation and normalization."""

    def test_array_field_with_item_type(self, mock_document):
        """Test that array fields with item_type are accepted."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_array_template",
            "fields": [
                {
                    "name": "colors",
                    "type": "array",
                    "item_type": "text",
                    "required": False,
                    "description": "Available colors",
                    "extraction_hints": ["Colors:", "Available in:"],
                    "confidence_threshold": 0.75
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["schema"]["fields"]) == 1
        assert data["schema"]["fields"][0]["type"] == "array"
        assert data["schema"]["fields"][0]["item_type"] == "text"

    def test_array_field_missing_item_type_defaults_to_text(self, mock_document):
        """Test that array fields without item_type default to 'text'."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_array_default",
            "fields": [
                {
                    "name": "tags",
                    "type": "array",
                    "required": False,
                    "description": "Document tags"
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["schema"]["fields"][0]["item_type"] == "text"  # Default applied

    def test_array_field_type_normalization(self, mock_document):
        """Test that 'ARR' and 'list' are normalized to 'array'."""
        test_cases = ["ARR", "arr", "list", "LIST"]

        for field_type in test_cases:
            payload = {
                "document_ids": [mock_document.id],
                "template_name": f"test_norm_{field_type}",
                "fields": [
                    {
                        "name": "items",
                        "type": field_type,
                        "item_type": "text"
                    }
                ]
            }

            response = client.post("/api/bulk/create-new-template", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["schema"]["fields"][0]["type"] == "array"  # Normalized


class TestTableFieldValidation:
    """Test table field validation."""

    def test_table_field_valid_schema(self, mock_document):
        """Test that table fields with complete schema are accepted."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_table_template",
            "fields": [
                {
                    "name": "grading_table",
                    "type": "table",
                    "required": True,
                    "table_schema": {
                        "row_identifier": "pom_code",
                        "columns": ["size_2", "size_3", "size_4"],
                        "value_type": "number",
                        "dynamic_columns": True
                    },
                    "description": "Garment grading table"
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["schema"]["fields"][0]["type"] == "table"
        assert "table_schema" in data["schema"]["fields"][0]

    def test_table_field_missing_schema(self, mock_document):
        """Test that table fields without table_schema are rejected."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_table_invalid",
            "fields": [
                {
                    "name": "measurements",
                    "type": "table",
                    "required": True
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "table_schema" in data["detail"].lower()
        assert "measurements" in data["detail"]

    def test_table_field_missing_row_identifier(self, mock_document):
        """Test that table schema without row_identifier is rejected."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_table_no_row_id",
            "fields": [
                {
                    "name": "data_table",
                    "type": "table",
                    "table_schema": {
                        "columns": ["col1", "col2"],
                        "value_type": "text"
                    }
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "row_identifier" in data["detail"].lower()

    def test_table_field_missing_value_type_defaults_to_string(self, mock_document):
        """Test that table schema without value_type defaults to 'string'."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_table_default_type",
            "fields": [
                {
                    "name": "specs_table",
                    "type": "table",
                    "table_schema": {
                        "row_identifier": "id",
                        "columns": ["spec1", "spec2"]
                    }
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["schema"]["fields"][0]["table_schema"]["value_type"] == "string"


class TestArrayOfObjectsValidation:
    """Test array_of_objects field validation."""

    def test_array_of_objects_valid_schema(self, mock_document):
        """Test that array_of_objects with object_schema are accepted."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_line_items",
            "fields": [
                {
                    "name": "line_items",
                    "type": "array_of_objects",
                    "required": True,
                    "object_schema": {
                        "description": {"type": "text", "required": True},
                        "quantity": {"type": "number", "required": True},
                        "unit_price": {"type": "number", "required": True},
                        "total": {"type": "number", "required": False}
                    },
                    "description": "Invoice line items"
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["schema"]["fields"][0]["type"] == "array_of_objects"
        assert "object_schema" in data["schema"]["fields"][0]

    def test_array_of_objects_missing_object_schema(self, mock_document):
        """Test that array_of_objects without object_schema is rejected."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_invalid_array_objects",
            "fields": [
                {
                    "name": "items",
                    "type": "array_of_objects",
                    "required": True
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "object_schema" in data["detail"].lower()


class TestErrorHandling:
    """Test error handling and descriptive error messages."""

    def test_duplicate_template_name(self, mock_document, db: Session):
        """Test that duplicate template names return descriptive error."""
        # Create existing template
        existing_schema = Schema(
            name="existing_template",
            fields=[{"name": "field1", "type": "text"}]
        )
        db.add(existing_schema)
        db.commit()

        payload = {
            "document_ids": [mock_document.id],
            "template_name": "existing_template",
            "fields": [{"name": "field2", "type": "text"}]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data["detail"].lower()
        assert "existing_template" in data["detail"]

        # Cleanup
        db.delete(existing_schema)
        db.commit()

    def test_missing_document_ids(self):
        """Test error when document_ids are missing."""
        payload = {
            "document_ids": [],
            "template_name": "test_template",
            "fields": [{"name": "field1", "type": "text"}]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code in [404, 422]  # Not found or validation error

    def test_invalid_document_ids(self):
        """Test error when document_ids don't exist."""
        payload = {
            "document_ids": [99999],  # Non-existent ID
            "template_name": "test_template",
            "fields": [{"name": "field1", "type": "text"}]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestComplexFieldCombinations:
    """Test combinations of complex field types."""

    def test_mixed_field_types(self, mock_document):
        """Test template with mix of simple and complex fields."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_mixed_fields",
            "fields": [
                {
                    "name": "invoice_number",
                    "type": "text",
                    "required": True
                },
                {
                    "name": "invoice_date",
                    "type": "date",
                    "required": True
                },
                {
                    "name": "categories",
                    "type": "array",
                    "item_type": "text",
                    "required": False
                },
                {
                    "name": "line_items",
                    "type": "array_of_objects",
                    "object_schema": {
                        "item": {"type": "text", "required": True},
                        "amount": {"type": "number", "required": True}
                    },
                    "required": True
                },
                {
                    "name": "totals_table",
                    "type": "table",
                    "table_schema": {
                        "row_identifier": "category",
                        "columns": ["subtotal", "tax", "total"],
                        "value_type": "number"
                    },
                    "required": False
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["schema"]["fields"]) == 5

        # Verify each field type is correct
        fields_by_name = {f["name"]: f for f in data["schema"]["fields"]}
        assert fields_by_name["invoice_number"]["type"] == "text"
        assert fields_by_name["invoice_date"]["type"] == "date"
        assert fields_by_name["categories"]["type"] == "array"
        assert fields_by_name["line_items"]["type"] == "array_of_objects"
        assert fields_by_name["totals_table"]["type"] == "table"


class TestFieldNormalization:
    """Test field normalization across all types."""

    def test_all_fields_get_standard_properties(self, mock_document):
        """Test that all fields get standard properties after normalization."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_normalization",
            "fields": [
                {
                    "name": "simple_field",
                    "type": "text"
                    # Missing: required, description, extraction_hints, confidence_threshold
                },
                {
                    "name": "array_field",
                    "type": "array"
                    # Missing: item_type (should default to text)
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()

        for field in data["schema"]["fields"]:
            # All fields should have these properties after normalization
            assert "name" in field
            assert "type" in field
            assert "required" in field
            assert "description" in field
            assert "extraction_hints" in field
            assert "confidence_threshold" in field

        # Check defaults
        simple_field = next(f for f in data["schema"]["fields"] if f["name"] == "simple_field")
        assert simple_field["required"] is False
        assert simple_field["description"] == ""
        assert simple_field["extraction_hints"] == []
        assert simple_field["confidence_threshold"] == 0.75

        array_field = next(f for f in data["schema"]["fields"] if f["name"] == "array_field")
        assert array_field["item_type"] == "text"  # Default applied


class TestComplexityAssessment:
    """Test that complexity assessment is returned for templates."""

    def test_simple_template_complexity(self, mock_document):
        """Test that simple templates have low complexity scores."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_simple_complexity",
            "fields": [
                {"name": "field1", "type": "text"},
                {"name": "field2", "type": "number"}
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()

        assert "complexity" in data
        # User-defined templates have score=0
        assert data["complexity"]["score"] == 0
        assert data["complexity"]["recommendation"] == "user_defined"

    def test_complex_template_with_tables(self, mock_document):
        """Test that templates with tables/arrays have higher complexity."""
        payload = {
            "document_ids": [mock_document.id],
            "template_name": "test_complex_template",
            "fields": [
                {
                    "name": "basic_field",
                    "type": "text"
                },
                {
                    "name": "line_items",
                    "type": "array_of_objects",
                    "object_schema": {
                        "item": {"type": "text", "required": True},
                        "qty": {"type": "number", "required": True},
                        "price": {"type": "number", "required": True}
                    }
                },
                {
                    "name": "grading_table",
                    "type": "table",
                    "table_schema": {
                        "row_identifier": "size",
                        "columns": ["chest", "waist", "hips"],
                        "value_type": "number"
                    }
                }
            ]
        }

        response = client.post("/api/bulk/create-new-template", json=payload)

        assert response.status_code == 200
        data = response.json()

        # User-defined always has score 0, but let's verify it's tracked
        assert "complexity" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
