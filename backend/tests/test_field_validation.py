"""
Unit tests for field validation and normalization in bulk_upload.py

Tests the _validate_and_normalize_fields() function for:
1. Array field validation
2. Table field validation
3. Array_of_objects validation
4. Field type normalization
5. Default value application
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.bulk_upload import _validate_and_normalize_fields


class TestArrayFieldValidation:
    """Test array field validation and normalization."""

    def test_array_field_with_item_type(self):
        """Test that array fields with item_type are preserved."""
        fields = [
            {
                "name": "colors",
                "type": "array",
                "item_type": "text",
                "required": False,
                "description": "Available colors"
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert len(result) == 1
        assert result[0]["type"] == "array"
        assert result[0]["item_type"] == "text"
        assert result[0]["name"] == "colors"

    def test_array_field_missing_item_type_defaults_to_text(self):
        """Test that array fields without item_type default to 'text'."""
        fields = [
            {
                "name": "tags",
                "type": "array"
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert result[0]["item_type"] == "text"  # Default applied

    def test_array_field_type_normalization(self):
        """Test that 'ARR', 'arr', 'list' are normalized to 'array'."""
        test_cases = [
            ("ARR", "array"),
            ("arr", "array"),
            ("list", "array"),
            ("LIST", "array"),
            ("array", "array")  # Already correct
        ]

        for input_type, expected_type in test_cases:
            fields = [
                {
                    "name": "items",
                    "type": input_type,
                    "item_type": "text"
                }
            ]

            result = _validate_and_normalize_fields(fields)

            assert result[0]["type"] == expected_type, f"Failed for input type: {input_type}"


class TestTableFieldValidation:
    """Test table field validation."""

    def test_table_field_valid_schema(self):
        """Test that table fields with complete schema are accepted."""
        fields = [
            {
                "name": "grading_table",
                "type": "table",
                "required": True,
                "table_schema": {
                    "row_identifier": "pom_code",
                    "columns": ["size_2", "size_3", "size_4"],
                    "value_type": "number",
                    "dynamic_columns": True
                }
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert result[0]["type"] == "table"
        assert "table_schema" in result[0]
        assert result[0]["table_schema"]["row_identifier"] == "pom_code"
        assert result[0]["table_schema"]["value_type"] == "number"

    def test_table_field_missing_schema_raises_error(self):
        """Test that table fields without table_schema raise ValueError."""
        fields = [
            {
                "name": "measurements",
                "type": "table",
                "required": True
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            _validate_and_normalize_fields(fields)

        assert "table_schema" in str(exc_info.value).lower()
        assert "measurements" in str(exc_info.value)

    def test_table_field_missing_row_identifier_raises_error(self):
        """Test that table schema without row_identifier raises ValueError."""
        fields = [
            {
                "name": "data_table",
                "type": "table",
                "table_schema": {
                    "columns": ["col1", "col2"],
                    "value_type": "text"
                }
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            _validate_and_normalize_fields(fields)

        assert "row_identifier" in str(exc_info.value).lower()

    def test_table_field_missing_columns_raises_error(self):
        """Test that table schema without columns raises ValueError."""
        fields = [
            {
                "name": "data_table",
                "type": "table",
                "table_schema": {
                    "row_identifier": "id",
                    "value_type": "text"
                }
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            _validate_and_normalize_fields(fields)

        assert "columns" in str(exc_info.value).lower()

    def test_table_field_missing_value_type_defaults_to_string(self):
        """Test that table schema without value_type defaults to 'string'."""
        fields = [
            {
                "name": "specs_table",
                "type": "table",
                "table_schema": {
                    "row_identifier": "id",
                    "columns": ["spec1", "spec2"]
                }
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert result[0]["table_schema"]["value_type"] == "string"

    def test_table_type_normalization(self):
        """Test that 'TBL', 'tbl', 'grid' are normalized to 'table'."""
        test_cases = [
            ("TBL", "table"),
            ("tbl", "table"),
            ("grid", "table"),
            ("GRID", "table"),
            ("table", "table")  # Already correct
        ]

        for input_type, expected_type in test_cases:
            fields = [
                {
                    "name": "data",
                    "type": input_type,
                    "table_schema": {
                        "row_identifier": "id",
                        "columns": ["col1"]
                    }
                }
            ]

            result = _validate_and_normalize_fields(fields)

            assert result[0]["type"] == expected_type, f"Failed for input type: {input_type}"


class TestArrayOfObjectsValidation:
    """Test array_of_objects field validation."""

    def test_array_of_objects_valid_schema(self):
        """Test that array_of_objects with object_schema are accepted."""
        fields = [
            {
                "name": "line_items",
                "type": "array_of_objects",
                "required": True,
                "object_schema": {
                    "description": {"type": "text", "required": True},
                    "quantity": {"type": "number", "required": True},
                    "unit_price": {"type": "number", "required": True}
                }
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert result[0]["type"] == "array_of_objects"
        assert "object_schema" in result[0]
        assert "description" in result[0]["object_schema"]
        assert "quantity" in result[0]["object_schema"]

    def test_array_of_objects_missing_object_schema_raises_error(self):
        """Test that array_of_objects without object_schema raises ValueError."""
        fields = [
            {
                "name": "items",
                "type": "array_of_objects",
                "required": True
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            _validate_and_normalize_fields(fields)

        assert "object_schema" in str(exc_info.value).lower()
        assert "items" in str(exc_info.value)


class TestStandardFieldNormalization:
    """Test that all fields get standard properties."""

    def test_all_fields_get_required_property(self):
        """Test that all fields get 'required' property with default False."""
        fields = [
            {"name": "field1", "type": "text"},
            {"name": "field2", "type": "number"}
        ]

        result = _validate_and_normalize_fields(fields)

        for field in result:
            assert "required" in field
            assert field["required"] is False

    def test_all_fields_get_description_property(self):
        """Test that all fields get 'description' property with default empty string."""
        fields = [
            {"name": "field1", "type": "text"}
        ]

        result = _validate_and_normalize_fields(fields)

        assert "description" in result[0]
        assert result[0]["description"] == ""

    def test_all_fields_get_extraction_hints_property(self):
        """Test that all fields get 'extraction_hints' property with default empty list."""
        fields = [
            {"name": "field1", "type": "text"}
        ]

        result = _validate_and_normalize_fields(fields)

        assert "extraction_hints" in result[0]
        assert result[0]["extraction_hints"] == []

    def test_all_fields_get_confidence_threshold_property(self):
        """Test that all fields get 'confidence_threshold' property with default 0.75."""
        fields = [
            {"name": "field1", "type": "text"}
        ]

        result = _validate_and_normalize_fields(fields)

        assert "confidence_threshold" in result[0]
        assert result[0]["confidence_threshold"] == 0.75

    def test_existing_properties_are_preserved(self):
        """Test that existing properties are not overwritten."""
        fields = [
            {
                "name": "custom_field",
                "type": "text",
                "required": True,
                "description": "Custom description",
                "extraction_hints": ["Hint 1", "Hint 2"],
                "confidence_threshold": 0.9
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert result[0]["required"] is True
        assert result[0]["description"] == "Custom description"
        assert result[0]["extraction_hints"] == ["Hint 1", "Hint 2"]
        assert result[0]["confidence_threshold"] == 0.9


class TestComplexFieldCombinations:
    """Test combinations of different field types."""

    def test_mixed_field_types(self):
        """Test validation with mix of simple and complex fields."""
        fields = [
            {
                "name": "invoice_number",
                "type": "text",
                "required": True
            },
            {
                "name": "categories",
                "type": "array",
                "item_type": "text"
            },
            {
                "name": "line_items",
                "type": "array_of_objects",
                "object_schema": {
                    "item": {"type": "text", "required": True},
                    "amount": {"type": "number", "required": True}
                }
            },
            {
                "name": "totals_table",
                "type": "table",
                "table_schema": {
                    "row_identifier": "category",
                    "columns": ["subtotal", "tax"],
                    "value_type": "number"
                }
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert len(result) == 4
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "array"
        assert result[2]["type"] == "array_of_objects"
        assert result[3]["type"] == "table"

    def test_multiple_complex_fields(self):
        """Test validation with multiple complex fields."""
        fields = [
            {
                "name": "colors",
                "type": "array",
                "item_type": "text"
            },
            {
                "name": "sizes",
                "type": "array",
                "item_type": "text"
            },
            {
                "name": "line_items",
                "type": "array_of_objects",
                "object_schema": {
                    "item": {"type": "text"}
                }
            },
            {
                "name": "table1",
                "type": "table",
                "table_schema": {
                    "row_identifier": "id",
                    "columns": ["col1"]
                }
            },
            {
                "name": "table2",
                "type": "table",
                "table_schema": {
                    "row_identifier": "key",
                    "columns": ["val1", "val2"]
                }
            }
        ]

        result = _validate_and_normalize_fields(fields)

        assert len(result) == 5
        # All should have standard properties
        for field in result:
            assert "name" in field
            assert "type" in field
            assert "required" in field
            assert "description" in field


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_fields_list(self):
        """Test that empty fields list returns empty list."""
        fields = []

        result = _validate_and_normalize_fields(fields)

        assert result == []

    def test_field_with_all_properties_already_set(self):
        """Test that fields with all properties already set are not modified."""
        fields = [
            {
                "name": "complete_field",
                "type": "text",
                "required": True,
                "description": "A complete field",
                "extraction_hints": ["hint1", "hint2"],
                "confidence_threshold": 0.85
            }
        ]

        result = _validate_and_normalize_fields(fields)

        # All properties should be preserved as-is
        assert result[0] == {
            "name": "complete_field",
            "type": "text",
            "required": True,
            "description": "A complete field",
            "extraction_hints": ["hint1", "hint2"],
            "confidence_threshold": 0.85
        }

    def test_case_insensitive_type_normalization(self):
        """Test that type normalization is case-insensitive."""
        test_cases = [
            "TEXT", "NUMBER", "DATE", "BOOLEAN",
            "text", "number", "date", "boolean",
            "Text", "Number", "Date", "Boolean"
        ]

        for field_type in test_cases:
            fields = [{"name": "field", "type": field_type}]
            result = _validate_and_normalize_fields(fields)
            # Should be lowercased
            assert result[0]["type"] == field_type.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
