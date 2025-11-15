"""
Reducto Schema Validation Utilities

Validates schema definitions against Reducto API requirements and best practices.
Based on: https://reducto.ai/blog/document-ai-extraction-schema-tips

Key Reducto Requirements:
1. Field descriptions are MANDATORY
2. Field names should be descriptive and semantically tied to document content
3. Use enums for limited option fields
4. No embedded calculations in extraction rules
5. System prompts should include document context
"""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ReductoValidationError(Exception):
    """Raised when schema fails Reducto compatibility validation"""
    pass


class ReductoValidationWarning:
    """Represents a non-fatal validation warning"""
    def __init__(self, field_name: str, message: str, severity: str = "warning"):
        self.field_name = field_name
        self.message = message
        self.severity = severity  # "warning" or "info"

    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field_name,
            "message": self.message,
            "severity": self.severity
        }


def validate_field_description(field: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate field description meets Reducto requirements.

    Requirements:
    - Description must exist
    - Description must be meaningful (>10 chars)
    - Description should act as a prompt (guide extraction)

    Args:
        field: Field definition dict

    Returns:
        (is_valid, error_message)
    """
    field_name = field.get("name", "unknown")
    description = field.get("description", "").strip()

    # Check 1: Description exists
    if not description:
        return False, f"Field '{field_name}' missing description (REQUIRED by Reducto)"

    # Check 2: Description is meaningful
    if len(description) < 10:
        return False, f"Field '{field_name}' description too short (minimum 10 chars): '{description}'"

    # Check 3: Description is not just the field name
    if description.lower().replace("_", " ") == field_name.lower().replace("_", " "):
        return False, f"Field '{field_name}' description is just the field name. Add context about what/how to extract."

    return True, ""


def validate_field_name(field: Dict[str, Any]) -> List[ReductoValidationWarning]:
    """
    Validate field name follows Reducto best practices.

    Best practices:
    - Use descriptive names (not generic like "field_1")
    - Use snake_case
    - Match document terminology where possible
    - Avoid overly technical names

    Args:
        field: Field definition dict

    Returns:
        List of warnings
    """
    warnings = []
    field_name = field.get("name", "")

    # Check 1: Generic names
    generic_patterns = [
        r'^field_?\d+$',  # field1, field_1
        r'^data_?\d+$',   # data1, data_1
        r'^value_?\d+$',  # value1, value_1
        r'^item_?\d+$',   # item1, item_1
    ]

    for pattern in generic_patterns:
        if re.match(pattern, field_name, re.IGNORECASE):
            warnings.append(ReductoValidationWarning(
                field_name,
                f"Generic field name '{field_name}'. Use descriptive names like 'invoice_date', 'vendor_name'.",
                severity="warning"
            ))
            break

    # Check 2: Case convention
    if not re.match(r'^[a-z][a-z0-9_]*$', field_name):
        warnings.append(ReductoValidationWarning(
            field_name,
            f"Field name '{field_name}' should use snake_case (e.g., 'invoice_total' not 'InvoiceTotal')",
            severity="info"
        ))

    # Check 3: Very short names (< 3 chars)
    if len(field_name) < 3:
        warnings.append(ReductoValidationWarning(
            field_name,
            f"Very short field name '{field_name}'. Consider more descriptive name.",
            severity="info"
        ))

    return warnings


def detect_embedded_calculations(field: Dict[str, Any]) -> List[ReductoValidationWarning]:
    """
    Detect if field description suggests embedded calculations.

    Reducto best practice: Extract raw values, calculate downstream.

    Args:
        field: Field definition dict

    Returns:
        List of warnings
    """
    warnings = []
    field_name = field.get("name", "")
    description = field.get("description", "").lower()
    hints = " ".join(field.get("extraction_hints", [])).lower()
    combined_text = f"{description} {hints}"

    # Patterns that suggest calculations
    calculation_patterns = [
        (r'\b(calculate|compute|sum|total|multiply|divide|subtract|add)\b',
         "contains calculation keywords"),
        (r'\b(×|÷|\*|/|\+|-)\s*\d+',
         "contains arithmetic operators"),
        (r'\btotal\s+of\b',
         "suggests summing multiple values"),
        (r'\baverage\s+of\b',
         "suggests averaging multiple values"),
        (r'\bper\s+(month|year|day|unit)\b',
         "suggests rate calculation"),
    ]

    for pattern, reason in calculation_patterns:
        if re.search(pattern, combined_text):
            warnings.append(ReductoValidationWarning(
                field_name,
                f"Field '{field_name}' {reason}. Extract raw values instead, calculate downstream.",
                severity="warning"
            ))
            break  # Only report one calculation warning per field

    return warnings


def suggest_enum_fields(field: Dict[str, Any]) -> List[ReductoValidationWarning]:
    """
    Suggest when a field should use enum type.

    Reducto best practice: Use enums for limited option fields to eliminate inconsistencies.

    Args:
        field: Field definition dict

    Returns:
        List of suggestions
    """
    warnings = []
    field_name = field.get("name", "")
    field_type = field.get("type", "text")
    description = field.get("description", "").lower()

    # Skip if already using proper constraints
    if "enum" in field or "allowed_values" in field:
        return warnings

    # Patterns that suggest limited options
    enum_indicators = [
        r'\b(status|state|type|category|class)\b',
        r'\b(yes|no|true|false)\b',
        r'\b(approved|rejected|pending)\b',
        r'\b(active|inactive|suspended)\b',
        r'\b(one of|either|or)\b',
    ]

    for pattern in enum_indicators:
        if re.search(pattern, description):
            # Special case for boolean
            if re.search(r'\b(yes|no|true|false)\b', description) and field_type == "text":
                warnings.append(ReductoValidationWarning(
                    field_name,
                    f"Field '{field_name}' appears to be yes/no. Consider type 'boolean' instead of 'text'.",
                    severity="info"
                ))
            else:
                warnings.append(ReductoValidationWarning(
                    field_name,
                    f"Field '{field_name}' may have limited options. Consider adding enum values.",
                    severity="info"
                ))
            break

    return warnings


def validate_extraction_hints(field: Dict[str, Any]) -> List[ReductoValidationWarning]:
    """
    Validate extraction hints follow best practices.

    Best practices:
    - Include actual text from documents (labels, headers)
    - Avoid overly generic hints
    - Include variations (e.g., "Total:", "Total Amount:", "Grand Total:")

    Args:
        field: Field definition dict

    Returns:
        List of warnings
    """
    warnings = []
    field_name = field.get("name", "")
    hints = field.get("extraction_hints", [])

    # Check 1: No hints provided
    if not hints or len(hints) == 0:
        warnings.append(ReductoValidationWarning(
            field_name,
            f"Field '{field_name}' has no extraction hints. Add keywords/phrases that appear near this field in documents.",
            severity="warning"
        ))
        return warnings

    # Check 2: Too few hints
    if len(hints) < 2:
        warnings.append(ReductoValidationWarning(
            field_name,
            f"Field '{field_name}' has only {len(hints)} hint. Add variations to improve extraction.",
            severity="info"
        ))

    # Check 3: Generic hints
    generic_hints = ["value", "data", "field", "information", "text"]
    for hint in hints:
        if hint.lower().strip() in generic_hints:
            warnings.append(ReductoValidationWarning(
                field_name,
                f"Field '{field_name}' has generic hint '{hint}'. Use specific labels from documents.",
                severity="info"
            ))
            break

    return warnings


def validate_schema_for_reducto(
    schema_data: Dict[str, Any],
    strict: bool = False
) -> Dict[str, Any]:
    """
    Comprehensive validation of schema against Reducto requirements.

    Args:
        schema_data: Schema dict with 'name' and 'fields'
        strict: If True, raise exception on errors. If False, return warnings.

    Returns:
        {
            "valid": bool,
            "errors": List[str],  # Fatal errors
            "warnings": List[Dict],  # Non-fatal warnings
            "recommendations": List[str],  # Suggestions for improvement
            "reducto_compatible": bool
        }

    Raises:
        ReductoValidationError: If strict=True and validation fails
    """
    errors = []
    warnings = []
    recommendations = []

    # Validate schema structure
    if "name" not in schema_data:
        errors.append("Schema missing 'name' field")

    if "fields" not in schema_data or not isinstance(schema_data["fields"], list):
        errors.append("Schema missing or invalid 'fields' array")
        return {
            "valid": False,
            "errors": errors,
            "warnings": [],
            "recommendations": [],
            "reducto_compatible": False
        }

    fields = schema_data["fields"]

    # Validate each field
    for idx, field in enumerate(fields):
        field_name = field.get("name", f"field_{idx}")

        # CRITICAL: Validate description (REQUIRED by Reducto)
        is_valid, error_msg = validate_field_description(field)
        if not is_valid:
            errors.append(error_msg)

        # Validate field name
        name_warnings = validate_field_name(field)
        warnings.extend(name_warnings)

        # Check for embedded calculations
        calc_warnings = detect_embedded_calculations(field)
        warnings.extend(calc_warnings)

        # Suggest enum usage
        enum_suggestions = suggest_enum_fields(field)
        warnings.extend(enum_suggestions)

        # Validate extraction hints
        hint_warnings = validate_extraction_hints(field)
        warnings.extend(hint_warnings)

    # Schema-level recommendations
    if len(fields) == 0:
        errors.append("Schema has no fields")
    elif len(fields) > 50:
        recommendations.append(
            f"Schema has {len(fields)} fields. Consider splitting into multiple templates for better accuracy."
        )
    elif len(fields) > 30:
        recommendations.append(
            f"Schema has {len(fields)} fields. This may be complex for auto-extraction."
        )

    # Check field ordering (should be logical)
    field_names = [f.get("name", "") for f in fields]
    if len(field_names) > 5:
        # Simple heuristic: check if related fields are grouped
        # (e.g., vendor_name, vendor_address, vendor_phone should be together)
        base_prefixes = {}
        for name in field_names:
            prefix = name.split("_")[0] if "_" in name else name
            if prefix not in base_prefixes:
                base_prefixes[prefix] = []
            base_prefixes[prefix].append(name)

        # If any prefix has 3+ fields, suggest grouping
        for prefix, names in base_prefixes.items():
            if len(names) >= 3:
                # Check if they're consecutive
                indices = [field_names.index(n) for n in names]
                if max(indices) - min(indices) > len(names):
                    recommendations.append(
                        f"Consider grouping related '{prefix}_*' fields together for better extraction"
                    )

    # Determine if Reducto compatible
    reducto_compatible = len(errors) == 0

    # Log results
    logger.info(
        f"Reducto validation for '{schema_data.get('name', 'unknown')}': "
        f"compatible={reducto_compatible}, errors={len(errors)}, warnings={len(warnings)}"
    )

    # Raise exception if strict mode and errors exist
    if strict and errors:
        error_text = "\n".join(errors)
        raise ReductoValidationError(
            f"Schema validation failed:\n{error_text}"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": [w.to_dict() for w in warnings],
        "recommendations": recommendations,
        "reducto_compatible": reducto_compatible
    }


def format_validation_report(validation_result: Dict[str, Any]) -> str:
    """
    Format validation result as human-readable report.

    Args:
        validation_result: Output from validate_schema_for_reducto

    Returns:
        Formatted string report
    """
    lines = []

    lines.append("=" * 60)
    lines.append("Reducto Schema Validation Report")
    lines.append("=" * 60)

    # Status
    if validation_result["reducto_compatible"]:
        lines.append("✅ Schema is Reducto-compatible")
    else:
        lines.append("❌ Schema has compatibility issues")

    lines.append("")

    # Errors
    if validation_result["errors"]:
        lines.append(f"🚨 ERRORS ({len(validation_result['errors'])})")
        lines.append("-" * 60)
        for error in validation_result["errors"]:
            lines.append(f"  • {error}")
        lines.append("")

    # Warnings
    if validation_result["warnings"]:
        lines.append(f"⚠️  WARNINGS ({len(validation_result['warnings'])})")
        lines.append("-" * 60)
        for warning in validation_result["warnings"]:
            lines.append(f"  • [{warning['field']}] {warning['message']}")
        lines.append("")

    # Recommendations
    if validation_result["recommendations"]:
        lines.append(f"💡 RECOMMENDATIONS ({len(validation_result['recommendations'])})")
        lines.append("-" * 60)
        for rec in validation_result["recommendations"]:
            lines.append(f"  • {rec}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
