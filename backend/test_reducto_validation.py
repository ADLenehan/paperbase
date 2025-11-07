"""
Test script for Reducto schema validation

Demonstrates validation with various schema examples:
1. Valid schema (passes all checks)
2. Invalid schema (missing descriptions)
3. Schema with warnings (generic names, calculations, etc.)
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.reducto_validation import validate_schema_for_reducto, format_validation_report


def test_valid_schema():
    """Test a well-formed schema that should pass validation"""
    print("\n" + "="*80)
    print("TEST 1: VALID SCHEMA")
    print("="*80)

    schema = {
        "name": "Invoice Template",
        "fields": [
            {
                "name": "invoice_number",
                "type": "text",
                "required": True,
                "description": "Unique invoice identifier typically found at the top of the document",
                "extraction_hints": ["Invoice No:", "Invoice Number:", "Invoice #"],
                "confidence_threshold": 0.8
            },
            {
                "name": "invoice_date",
                "type": "date",
                "required": True,
                "description": "Date the invoice was issued",
                "extraction_hints": ["Date:", "Invoice Date:", "Dated:"],
                "confidence_threshold": 0.75
            },
            {
                "name": "vendor_name",
                "type": "text",
                "required": True,
                "description": "Name of the vendor or supplier issuing the invoice",
                "extraction_hints": ["From:", "Vendor:", "Supplier:", "Billed By:"],
                "confidence_threshold": 0.8
            },
            {
                "name": "total_amount",
                "type": "number",
                "required": True,
                "description": "Total invoice amount including tax and fees",
                "extraction_hints": ["Total:", "Amount Due:", "Total Amount:", "Grand Total:"],
                "confidence_threshold": 0.85
            },
            {
                "name": "payment_status",
                "type": "text",
                "required": False,
                "description": "Current payment status of the invoice",
                "extraction_hints": ["Status:", "Payment Status:"],
                "confidence_threshold": 0.7
            }
        ]
    }

    result = validate_schema_for_reducto(schema, strict=False)
    print(format_validation_report(result))

    assert result["reducto_compatible"], "Valid schema should pass validation"
    print("\n✅ Test PASSED: Valid schema accepted")


def test_invalid_schema():
    """Test schema with missing required fields (descriptions)"""
    print("\n" + "="*80)
    print("TEST 2: INVALID SCHEMA (Missing Descriptions)")
    print("="*80)

    schema = {
        "name": "Bad Invoice Template",
        "fields": [
            {
                "name": "field1",  # Generic name
                "type": "text",
                "required": True,
                # Missing description!
                "extraction_hints": ["Value"],
                "confidence_threshold": 0.8
            },
            {
                "name": "invoice_date",
                "type": "date",
                "required": True,
                "description": "Date",  # Too short
                "extraction_hints": ["Date:"],
                "confidence_threshold": 0.75
            },
            {
                "name": "vendor",
                "type": "text",
                "required": True,
                "description": "vendor",  # Just the field name
                "extraction_hints": [],  # No hints!
                "confidence_threshold": 0.8
            }
        ]
    }

    result = validate_schema_for_reducto(schema, strict=False)
    print(format_validation_report(result))

    assert not result["reducto_compatible"], "Invalid schema should fail validation"
    assert len(result["errors"]) >= 3, "Should have multiple errors"
    print(f"\n✅ Test PASSED: Invalid schema rejected with {len(result['errors'])} errors")


def test_schema_with_warnings():
    """Test schema that's valid but has warnings"""
    print("\n" + "="*80)
    print("TEST 3: SCHEMA WITH WARNINGS")
    print("="*80)

    schema = {
        "name": "Invoice with Calculations",
        "fields": [
            {
                "name": "InvoiceNumber",  # Wrong case
                "type": "text",
                "required": True,
                "description": "Invoice number from the document header",
                "extraction_hints": ["Invoice:"],
                "confidence_threshold": 0.8
            },
            {
                "name": "monthly_cost",
                "type": "number",
                "required": False,
                "description": "Monthly cost calculated by multiplying unit price by 12",  # CALCULATION!
                "extraction_hints": ["Monthly:", "Per Month:"],
                "confidence_threshold": 0.7
            },
            {
                "name": "status",
                "type": "text",  # Should be enum or boolean
                "required": False,
                "description": "Payment status - either approved or rejected",  # Limited options
                "extraction_hints": ["Status:"],
                "confidence_threshold": 0.7
            },
            {
                "name": "field_1",  # Generic name
                "type": "text",
                "required": False,
                "description": "Some additional field for miscellaneous data",
                "extraction_hints": ["Data"],  # Generic hint
                "confidence_threshold": 0.6
            }
        ]
    }

    result = validate_schema_for_reducto(schema, strict=False)
    print(format_validation_report(result))

    assert result["reducto_compatible"], "Schema should still be compatible despite warnings"
    assert len(result["warnings"]) > 0, "Should have warnings"
    print(f"\n✅ Test PASSED: Schema accepted with {len(result['warnings'])} warnings")


def test_complex_data_schema():
    """Test schema with complex types (arrays, tables)"""
    print("\n" + "="*80)
    print("TEST 4: COMPLEX DATA SCHEMA")
    print("="*80)

    schema = {
        "name": "Contract with Line Items",
        "fields": [
            {
                "name": "contract_number",
                "type": "text",
                "required": True,
                "description": "Unique contract identifier",
                "extraction_hints": ["Contract No:", "Contract #"],
                "confidence_threshold": 0.8
            },
            {
                "name": "line_items",
                "type": "array_of_objects",
                "required": True,
                "description": "List of contract line items with descriptions, quantities, and prices",
                "extraction_hints": ["Line Items:", "Items:", "Description"],
                "confidence_threshold": 0.75,
                "object_schema": {
                    "description": {"type": "text", "required": True},
                    "quantity": {"type": "number", "required": True},
                    "unit_price": {"type": "number", "required": True}
                }
            },
            {
                "name": "available_colors",
                "type": "array",
                "item_type": "text",
                "required": False,
                "description": "List of available color options for the product",
                "extraction_hints": ["Colors:", "Available in:"],
                "confidence_threshold": 0.7
            },
            {
                "name": "size_measurements",
                "type": "table",
                "required": True,
                "description": "Table of size measurements with dynamic columns for different sizes",
                "extraction_hints": ["Measurements:", "Size Chart:", "Grading Table"],
                "confidence_threshold": 0.7,
                "table_schema": {
                    "row_identifier": "size_code",
                    "columns": ["chest", "waist", "hip"],
                    "dynamic_columns": True,
                    "value_type": "number"
                }
            }
        ]
    }

    result = validate_schema_for_reducto(schema, strict=False)
    print(format_validation_report(result))

    assert result["reducto_compatible"], "Complex schema should be valid"
    print(f"\n✅ Test PASSED: Complex schema accepted")


if __name__ == "__main__":
    print("\n" + "🔍 " * 20)
    print("REDUCTO SCHEMA VALIDATION TEST SUITE")
    print("🔍 " * 20)

    try:
        test_valid_schema()
        test_invalid_schema()
        test_schema_with_warnings()
        test_complex_data_schema()

        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nValidation system is working correctly and ready for use.")
        print("\nNext steps:")
        print("1. Update Claude prompts to generate Reducto-compatible schemas")
        print("2. Add validation to template creation endpoints")
        print("3. Display validation warnings in the UI")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
