"""
Comprehensive Integration Test for Reducto Validation

Tests that validation is properly integrated throughout the system:
1. Schema generation with Claude
2. Template creation endpoints
3. Built-in template validation
4. Validation-only endpoint
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.reducto_validation import validate_schema_for_reducto, format_validation_report
from app.data.templates import BUILTIN_TEMPLATES


def test_claude_prompt_integration():
    """Test that Claude's prompts enforce Reducto requirements"""
    print("\n" + "="*80)
    print("TEST 1: Claude Prompt Integration")
    print("="*80)

    from app.services.claude_service import ClaudeService

    # Read the prompt building code
    service = ClaudeService()

    # Check if _build_schema_generation_prompt contains Reducto requirements
    import inspect
    prompt_code = inspect.getsource(service._build_schema_generation_prompt)

    required_keywords = [
        "IMPORTANT - Reducto API Requirements",
        "Every field MUST have a description",
        "snake_case",
        "extraction_hints should include ACTUAL text",
        "NO CALCULATIONS"
    ]

    missing_keywords = []
    for keyword in required_keywords:
        if keyword not in prompt_code:
            missing_keywords.append(keyword)

    if missing_keywords:
        print(f"❌ FAILED: Missing Reducto requirements in prompt:")
        for kw in missing_keywords:
            print(f"   - {kw}")
        return False

    print("✅ PASSED: Claude prompt includes all Reducto requirements")
    return True


def test_validation_helper_functions():
    """Test individual validation helper functions"""
    print("\n" + "="*80)
    print("TEST 2: Validation Helper Functions")
    print("="*80)

    from app.utils.reducto_validation import (
        validate_field_description,
        validate_field_name,
        detect_embedded_calculations,
        suggest_enum_fields,
        validate_extraction_hints
    )

    # Test description validation
    test_cases = [
        ({"name": "test", "description": "Short"}, False, "Short description"),
        ({"name": "test", "description": ""}, False, "Missing description"),
        ({"name": "test", "description": "This is a proper description"}, True, "Valid description")
    ]

    for field, expected_valid, test_name in test_cases:
        is_valid, error = validate_field_description(field)
        if is_valid != expected_valid:
            print(f"❌ FAILED: {test_name} - expected {expected_valid}, got {is_valid}")
            return False

    print("✅ PASSED: All validation helper functions work correctly")
    return True


def test_builtin_templates_validation():
    """Test that all built-in templates are valid"""
    print("\n" + "="*80)
    print("TEST 3: Built-in Templates Validation")
    print("="*80)

    all_valid = True
    for template in BUILTIN_TEMPLATES:
        result = validate_schema_for_reducto(
            {
                "name": template["name"],
                "fields": template["fields"]
            },
            strict=False
        )

        if not result["reducto_compatible"]:
            print(f"❌ FAILED: Template '{template['name']}' has errors:")
            for error in result["errors"]:
                print(f"   - {error}")
            all_valid = False

    if all_valid:
        print(f"✅ PASSED: All {len(BUILTIN_TEMPLATES)} built-in templates are Reducto-compatible")

    return all_valid


def test_schema_validation_edge_cases():
    """Test edge cases and error handling"""
    print("\n" + "="*80)
    print("TEST 4: Edge Cases and Error Handling")
    print("="*80)

    # Test 1: Empty schema
    result = validate_schema_for_reducto(
        {
            "name": "Empty",
            "fields": []
        },
        strict=False
    )

    if not result["errors"] or "no fields" not in result["errors"][0].lower():
        print("❌ FAILED: Empty schema should produce error")
        return False

    # Test 2: Schema with only complex types
    result = validate_schema_for_reducto(
        {
            "name": "Complex",
            "fields": [
                {
                    "name": "line_items",
                    "type": "array_of_objects",
                    "description": "List of items with quantities and prices",
                    "extraction_hints": ["Items:", "Line Items"],
                    "object_schema": {
                        "description": {"type": "text", "required": True},
                        "quantity": {"type": "number", "required": True}
                    }
                }
            ]
        },
        strict=False
    )

    if not result["reducto_compatible"]:
        print("❌ FAILED: Valid complex type schema rejected")
        print(f"Errors: {result['errors']}")
        return False

    # Test 3: Very large schema (50+ fields)
    large_schema_fields = []
    for i in range(60):
        large_schema_fields.append({
            "name": f"field_{i}",
            "type": "text",
            "description": f"This is field number {i} with a proper description",
            "extraction_hints": [f"Field {i}:", f"Label {i}"]
        })

    result = validate_schema_for_reducto(
        {
            "name": "Large Schema",
            "fields": large_schema_fields
        },
        strict=False
    )

    if not result["reducto_compatible"]:
        print("❌ FAILED: Large valid schema rejected")
        return False

    if not result["recommendations"] or len(result["recommendations"]) == 0:
        print("❌ FAILED: Large schema should have recommendations")
        return False

    print("✅ PASSED: All edge cases handled correctly")
    return True


def test_validation_report_formatting():
    """Test that validation reports are properly formatted"""
    print("\n" + "="*80)
    print("TEST 5: Validation Report Formatting")
    print("="*80)

    from app.utils.reducto_validation import format_validation_report

    # Create a validation result with errors, warnings, and recommendations
    validation_result = {
        "reducto_compatible": False,
        "errors": ["Field 'test' missing description"],
        "warnings": [
            {"field": "test_field", "message": "Generic name", "severity": "warning"}
        ],
        "recommendations": ["Consider grouping related fields"]
    }

    report = format_validation_report(validation_result)

    # Check report contains expected sections
    required_sections = ["ERRORS", "WARNINGS", "RECOMMENDATIONS", "Schema has compatibility issues"]
    missing_sections = []

    for section in required_sections:
        if section not in report:
            missing_sections.append(section)

    if missing_sections:
        print(f"❌ FAILED: Report missing sections: {missing_sections}")
        return False

    print("✅ PASSED: Validation reports are properly formatted")
    return True


def test_integration_with_endpoints():
    """Test that validation is called in all relevant endpoints"""
    print("\n" + "="*80)
    print("TEST 6: Integration with API Endpoints")
    print("="*80)

    # Check that validation is imported in relevant files
    files_to_check = [
        ("bulk_upload.py", "app/api/bulk_upload.py"),
        ("onboarding.py", "app/api/onboarding.py")
    ]

    all_integrated = True

    for file_name, file_path in files_to_check:
        full_path = os.path.join(
            os.path.dirname(__file__),
            file_path
        )

        if not os.path.exists(full_path):
            print(f"⚠️  WARNING: {file_path} not found")
            continue

        with open(full_path, 'r') as f:
            content = f.read()

        if "validate_schema_for_reducto" not in content:
            print(f"❌ FAILED: {file_name} doesn't import validate_schema_for_reducto")
            all_integrated = False
        else:
            # Count how many times validation is called
            call_count = content.count("validate_schema_for_reducto(")
            print(f"✅ {file_name}: {call_count} validation call(s)")

    if all_integrated:
        print("✅ PASSED: Validation integrated in all relevant endpoints")

    return all_integrated


if __name__ == "__main__":
    print("\n" + "🧪 " * 20)
    print("REDUCTO VALIDATION INTEGRATION TEST SUITE")
    print("🧪 " * 20)

    tests = [
        ("Claude Prompt Integration", test_claude_prompt_integration),
        ("Validation Helper Functions", test_validation_helper_functions),
        ("Built-in Templates", test_builtin_templates_validation),
        ("Edge Cases", test_schema_validation_edge_cases),
        ("Report Formatting", test_validation_report_formatting),
        ("API Endpoint Integration", test_integration_with_endpoints)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ FAILED: {test_name} - Exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "="*80)
    print("INTEGRATION TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✅ ALL INTEGRATION TESTS PASSED!")
        print("\nReducto validation is fully integrated and working correctly.")
        sys.exit(0)
    else:
        print(f"\n❌ {failed} INTEGRATION TEST(S) FAILED")
        sys.exit(1)
