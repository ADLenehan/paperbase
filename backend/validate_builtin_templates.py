"""
Validate all built-in templates against Reducto requirements

This script checks if the built-in templates are Reducto-compatible
and reports any issues that need to be fixed.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.data.templates import BUILTIN_TEMPLATES
from app.utils.reducto_validation import validate_schema_for_reducto, format_validation_report


def validate_all_builtin_templates():
    """Validate all built-in templates"""
    print("\n" + "🔍 " * 20)
    print("BUILT-IN TEMPLATE VALIDATION")
    print("🔍 " * 20 + "\n")

    all_compatible = True
    total_errors = 0
    total_warnings = 0

    for template in BUILTIN_TEMPLATES:
        print(f"\n{'='*80}")
        print(f"Validating: {template['name']} ({template['category']})")
        print(f"Description: {template['description']}")
        print(f"{'='*80}")

        # Validate template
        validation_result = validate_schema_for_reducto(
            {
                "name": template["name"],
                "fields": template["fields"]
            },
            strict=False
        )

        # Print report
        print(format_validation_report(validation_result))

        # Track results
        if not validation_result["reducto_compatible"]:
            all_compatible = False

        total_errors += len(validation_result["errors"])
        total_warnings += len(validation_result["warnings"])

    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print(f"Total templates: {len(BUILTIN_TEMPLATES)}")
    print(f"Compatible: {sum(1 for t in BUILTIN_TEMPLATES if validate_schema_for_reducto({'name': t['name'], 'fields': t['fields']}, strict=False)['reducto_compatible'])}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")

    if all_compatible and total_errors == 0:
        print("\n✅ ALL BUILT-IN TEMPLATES ARE REDUCTO-COMPATIBLE!")
        return 0
    elif total_errors == 0:
        print(f"\n⚠️  All templates compatible, but {total_warnings} warnings")
        return 0
    else:
        print(f"\n❌ VALIDATION FAILED: {total_errors} errors found")
        print("\nTemplates with errors need to be fixed before deployment!")
        return 1


if __name__ == "__main__":
    try:
        exit_code = validate_all_builtin_templates()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
