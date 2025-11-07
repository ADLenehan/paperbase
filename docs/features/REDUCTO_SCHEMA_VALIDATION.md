# Reducto Schema Validation

**Status**: ✅ Complete
**Date**: 2025-11-03
**Priority**: High (Ensures Reducto API compatibility)

## Overview

Automatic validation of schema definitions against Reducto API requirements and best practices. Prevents common schema errors that could cause extraction failures and provides actionable recommendations for improvement.

## Why This Matters

**Problem**: Users creating templates could unknowingly violate Reducto's requirements, causing:
- Extraction failures (missing field descriptions)
- Poor extraction quality (generic field names, bad hints)
- Unnecessary costs (embedded calculations, inefficient schemas)
- Inconsistent results (not using enums for limited-value fields)

**Solution**: Automatic validation catches these issues before template creation, with clear error messages and recommendations.

## Reducto Requirements Enforced

Based on [Reducto's official best practices](https://reducto.ai/blog/document-ai-extraction-schema-tips):

### 1. **Field Descriptions (MANDATORY)**
- Every field MUST have a description
- Minimum 10 characters
- Descriptions act as prompts to guide LLM extraction
- Must be more than just the field name

**Example:**
```json
{
  "name": "invoice_total",
  "description": "Total invoice amount including tax and fees"  // ✅ Good
}
```

**Bad:**
```json
{
  "name": "invoice_total",
  "description": "Total"  // ❌ Too short
}
```

### 2. **Field Naming Conventions**
- Use snake_case (not camelCase or PascalCase)
- Descriptive names (not generic like "field1")
- Match document terminology where possible

**Example:**
```json
{
  "name": "po_number",  // ✅ Matches "PO Number" in document
  "description": "Purchase order number from document header"
}
```

**Bad:**
```json
{
  "name": "field1",  // ❌ Generic
  "description": "Some number from the document"
}
```

### 3. **Extraction Hints**
- Include ACTUAL text from documents (labels, headers)
- Provide multiple variations
- Avoid generic hints like "value" or "data"

**Example:**
```json
{
  "name": "invoice_date",
  "extraction_hints": [
    "Invoice Date:",
    "Date:",
    "Dated:",
    "Issue Date:"
  ]  // ✅ Multiple specific variations
}
```

**Bad:**
```json
{
  "name": "invoice_date",
  "extraction_hints": ["Date"]  // ❌ Too generic, only one hint
}
```

### 4. **No Embedded Calculations**
- Extract raw values only
- Perform calculations downstream in application code
- Reducto should NOT calculate derived values

**Example:**
```json
{
  "name": "unit_price",
  "description": "Price per unit as shown in the invoice"  // ✅ Raw value
}
```

**Bad:**
```json
{
  "name": "annual_cost",
  "description": "Monthly cost multiplied by 12"  // ❌ Calculation
}
```

### 5. **Use Enums for Limited Options**
- Eliminates inconsistencies (Y vs Yes vs true)
- Use boolean type for yes/no fields
- Consider enum constraints for status, category, type fields

**Example:**
```json
{
  "name": "payment_status",
  "type": "text",
  "description": "Current payment status",
  "enum": ["Paid", "Pending", "Overdue", "Cancelled"]  // ✅ Limited options
}
```

## Implementation

### Validation Module

**File**: `backend/app/utils/reducto_validation.py`

**Functions**:
- `validate_field_description()` - Check description requirements
- `validate_field_name()` - Check naming conventions
- `detect_embedded_calculations()` - Warn about calculations
- `suggest_enum_fields()` - Suggest when to use enums
- `validate_extraction_hints()` - Check hint quality
- `validate_schema_for_reducto()` - Main validation function
- `format_validation_report()` - Human-readable report

**Severity Levels**:
- **Errors** (🚨): MUST be fixed (schema will fail on Reducto)
- **Warnings** (⚠️): SHOULD be fixed (may cause poor extraction)
- **Recommendations** (💡): NICE to fix (optimization suggestions)

### API Integration

#### 1. Schema Generation Endpoint

**POST** `/api/bulk/generate-schema`

**Response** (enhanced):
```json
{
  "success": true,
  "suggested_fields": [...],
  "complexity": {...},
  "reducto_validation": {
    "compatible": true,
    "errors": [],
    "warnings": [
      {
        "field": "total_amount",
        "message": "Contains calculation keywords. Extract raw values instead...",
        "severity": "warning"
      }
    ],
    "recommendations": [
      "Consider grouping related 'vendor_*' fields together for better extraction"
    ]
  },
  "message": "Generated 8 field suggestions"
}
```

#### 2. Template Creation Endpoint

**POST** `/api/bulk/create-new-template`

**Response** (enhanced):
```json
{
  "success": true,
  "schema_id": 42,
  "schema": {...},
  "reducto_validation": {
    "compatible": false,
    "errors": [
      "Field 'field1' missing description (REQUIRED by Reducto)",
      "Field 'date' description too short (minimum 10 chars): 'Date'"
    ],
    "warnings": [...],
    "recommendations": [...]
  },
  "message": "Created new template 'Invoice' with 8 fields ⚠️ 2 Reducto compatibility issues"
}
```

**Behavior**:
- ✅ Templates with errors are still created (allows user override)
- ⚠️ Warnings logged to help improve extraction quality
- 📊 Frontend can display validation results to user

#### 3. Validation-Only Endpoint (NEW)

**POST** `/api/bulk/validate-schema`

**Request**:
```json
{
  "template_name": "Test Invoice",
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "description": "Unique invoice identifier",
      "extraction_hints": ["Invoice #:", "Invoice No:"],
      "confidence_threshold": 0.8
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "validation": {
    "valid": true,
    "reducto_compatible": true,
    "errors": [],
    "warnings": [],
    "recommendations": []
  },
  "report": "============================================================\nReducto Schema Validation Report\n...",
  "message": "✅ Schema is Reducto-compatible"
}
```

**Use Cases**:
- Test schema before creating template
- Debug validation issues
- Automated testing

### Claude Prompt Enhancement

**Updated**: `claude_service.py` - `_build_schema_generation_prompt()`

**Added Section**:
```
IMPORTANT - Reducto API Requirements (MANDATORY):
- **Every field MUST have a description** (minimum 10 characters)
- Descriptions act as prompts to guide extraction - be specific about what to extract
- Field names MUST be descriptive and use snake_case (e.g., "invoice_date" not "field1")
- Field names should match document terminology where possible
- extraction_hints should include ACTUAL text from documents
- Include multiple hint variations
- **NO CALCULATIONS**: Extract raw values only
- Use boolean type for yes/no fields
- Consider using enum values for fields with limited options
```

**Impact**: Claude now generates Reducto-compatible schemas by default.

## Validation Examples

### Example 1: Valid Schema

```json
{
  "name": "Invoice Template",
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "required": true,
      "description": "Unique invoice identifier typically found at the top of the document",
      "extraction_hints": ["Invoice No:", "Invoice Number:", "Invoice #"],
      "confidence_threshold": 0.8
    },
    {
      "name": "total_amount",
      "type": "number",
      "required": true,
      "description": "Total invoice amount including tax and fees",
      "extraction_hints": ["Total:", "Amount Due:", "Total Amount:", "Grand Total:"],
      "confidence_threshold": 0.85
    }
  ]
}
```

**Result**: ✅ Reducto-compatible (may have minor warnings)

### Example 2: Invalid Schema

```json
{
  "name": "Bad Invoice",
  "fields": [
    {
      "name": "field1",  // ❌ Generic name
      "type": "text",
      "required": true,
      // ❌ Missing description!
      "extraction_hints": ["Value"],  // ❌ Generic hint
      "confidence_threshold": 0.8
    },
    {
      "name": "date",
      "type": "date",
      "required": true,
      "description": "Date",  // ❌ Too short
      "extraction_hints": [],  // ❌ No hints!
      "confidence_threshold": 0.75
    }
  ]
}
```

**Result**: ❌ Not Reducto-compatible (3 errors, 5 warnings)

**Errors**:
- Field 'field1' missing description (REQUIRED by Reducto)
- Field 'date' description too short (minimum 10 chars): 'Date'

**Warnings**:
- Generic field name 'field1'. Use descriptive names like 'invoice_date', 'vendor_name'
- Field 'field1' has generic hint 'Value'. Use specific labels from documents
- Field 'date' has no extraction hints. Add keywords/phrases...

## Testing

### Unit Tests

**File**: `backend/test_reducto_validation.py`

**Test Cases**:
1. ✅ Valid schema (passes all checks)
2. ❌ Invalid schema (missing descriptions)
3. ⚠️ Schema with warnings (calculations, generic names)
4. ✅ Complex data schema (arrays, tables)

**Run Tests**:
```bash
cd backend
python3 test_reducto_validation.py
```

**Expected Output**:
```
🔍 🔍 🔍 REDUCTO SCHEMA VALIDATION TEST SUITE 🔍 🔍 🔍

TEST 1: VALID SCHEMA
✅ Schema is Reducto-compatible
✅ Test PASSED: Valid schema accepted

TEST 2: INVALID SCHEMA
❌ Schema has compatibility issues
🚨 ERRORS (3)
✅ Test PASSED: Invalid schema rejected with 3 errors

TEST 3: SCHEMA WITH WARNINGS
✅ Schema is Reducto-compatible
⚠️ WARNINGS (8)
✅ Test PASSED: Schema accepted with 8 warnings

TEST 4: COMPLEX DATA SCHEMA
✅ Schema is Reducto-compatible
✅ Test PASSED: Complex schema accepted

✅ ALL TESTS PASSED!
```

### Integration Testing

1. **Generate Schema** - Check that Claude produces Reducto-compatible schemas
2. **Create Template** - Verify validation runs and returns results
3. **Validate Endpoint** - Test standalone validation API

## Benefits

### 1. **Prevents Extraction Failures**
- Catches missing descriptions before API call
- Ensures field names won't confuse Reducto
- Validates extraction hints are useful

### 2. **Improves Extraction Quality**
- Better descriptions → better extraction
- Multiple hints → higher accuracy
- Proper field types → correct data parsing

### 3. **Reduces Costs**
- No embedded calculations → faster extraction
- Efficient schemas → fewer tokens
- Fewer retries due to errors

### 4. **Better User Experience**
- Clear error messages
- Actionable recommendations
- Catches issues early (before processing documents)

## Future Enhancements

### Phase 2 (Optional)
- [ ] **Strict Mode**: Block template creation if errors exist
- [ ] **Auto-Fix**: Suggest corrections for common issues
- [ ] **Field Templates**: Pre-validated field snippets
- [ ] **Batch Validation**: Validate all existing templates
- [ ] **Analytics**: Track common validation issues

### Phase 3 (Nice-to-Have)
- [ ] **UI Validation Feedback**: Real-time validation in field editor
- [ ] **Validation Score**: Overall schema quality score (0-100)
- [ ] **Best Practice Library**: Examples of well-validated schemas
- [ ] **Custom Rules**: Allow users to add validation rules

## Migration Notes

### Existing Templates

**No Breaking Changes**: Existing templates are NOT re-validated. Validation only applies to:
- New template creation
- Schema generation endpoint
- Explicit validation requests

**Optional Cleanup**:
```bash
# Validate all existing templates (manual process)
python3 scripts/validate_all_templates.py
```

### Backwards Compatibility

- ✅ Existing API responses unchanged (new fields added)
- ✅ Old templates continue to work
- ✅ No database migrations required
- ✅ Validation is optional (doesn't block creation)

## Related Documentation

- [Reducto API Documentation](https://docs.reducto.ai)
- [Schema Best Practices](https://reducto.ai/blog/document-ai-extraction-schema-tips)
- [Complex Data Extraction](./COMPLEX_TABLE_EXTRACTION.md)
- [Template Matching](../../MULTI_TEMPLATE_EXTRACTION.md)

## Summary

✅ **Complete** - Reducto validation is fully integrated
📊 **Impact** - Prevents extraction failures, improves quality
🎯 **Next Steps** - Consider UI integration for real-time validation

---

**Last Updated**: 2025-11-03
**Author**: Claude Code
**Status**: Production Ready
