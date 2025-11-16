# AskAI Document Recall & Audit Fixes

## Critical Issues Fixed (2025-11-06)

### Problem Statement

User reported two critical issues in the AskAI interface when querying with "What cloud provider are we mentioning here?" on the "One sheeter" template:

1. **Document showing "Untitled"** instead of actual filename
2. **No audit button** for low-confidence field (cloud_platform: 0.42)

Both issues were blocking the audit workflow and degrading user experience.

---

## Root Cause Analysis

### Issue 1: Filename Display

**Symptom**: Frontend showed "Untitled" instead of "Pinecone-for-AWS-Onesheet.pdf"

**Root Cause**:
- Backend returns: `{id: 75, filename: None, score: 0.0, data: {filename: 'Pinecone-for-AWS-Onesheet.pdf', ...}}`
- Frontend expects: `{id: 75, filename: 'Pinecone-for-AWS-Onesheet.pdf', ...}`
- Filename was nested inside `data` object instead of top-level

**Location**: [backend/app/services/elastic_service.py:526-534](backend/app/services/elastic_service.py#L526-L534)

### Issue 2: Missing Audit Functionality

**Symptom**:
- `cloud_platform` has confidence 0.42 (LOW - below 0.6 threshold)
- Backend returned `audit_items_total_count: 1` but `audit_items: []`
- No audit button or warning displayed

**Root Cause Chain**:

1. **EXISTS Query Field Extraction Bug**
   - Query: `{"exists": {"field": "cloud_platform"}}`
   - Extracted field: `["field"]` ❌ WRONG
   - Should extract: `["cloud_platform"]` ✅
   - **Location**: [backend/app/utils/query_field_extractor.py:236](backend/app/utils/query_field_extractor.py#L236)

2. **Incorrect Audit Item Filtering**
   - Audit items filtered by `field_lineage["queried_fields"]`
   - `queried_fields: ["field"]` (wrong)
   - Audit item has `field_name: "cloud_platform"`
   - Filter logic: `"cloud_platform" not in ["field"]` → FILTERED OUT

**Result**: Valid audit item incorrectly removed before being sent to frontend

---

## Solutions Implemented

### Fix 1: Add `filename` to Top-Level Response ✅

**File**: [backend/app/services/elastic_service.py](backend/app/services/elastic_service.py)

**Change**:
```python
# Before
{
    "id": hit["_id"],
    "score": hit["_score"],
    "data": hit["_source"],
}

# After
{
    "id": hit["_id"],
    "score": hit["_score"],
    "filename": hit["_source"].get("filename"),  # Top-level for frontend
    "data": hit["_source"],
}
```

**Impact**: Frontend can now read `filename` directly from search results

### Fix 2: Correct EXISTS Query Field Extraction ✅

**File**: [backend/app/utils/query_field_extractor.py](backend/app/utils/query_field_extractor.py)

**Change**:
```python
def _handle_field_query(self, query_type, query_value, context, parent_clause):
    """Handle single-field query types (match, term, range, exists)."""

    # NEW: Special case for "exists" query - field is a value, not a key
    if query_type == "exists" and "field" in query_value:
        field_name = query_value["field"]  # Extract "cloud_platform" from {"field": "cloud_platform"}
        self._add_field(field_name, query_type, context, parent_clause, {"exists": True})
        return

    # Original logic for other query types
    for field_name in query_value.keys():
        self._add_field(field_name, query_type, context, parent_clause, query_value[field_name])
```

**Impact**:
- EXISTS queries now correctly extract the actual field name
- Audit items no longer incorrectly filtered out
- Low-confidence fields properly surfaced to frontend

---

## Test Results

### Before Fixes ❌

```bash
Query: "What cloud provider is mentioned here?"
Template: "One sheeter"

Results:
  - Filename: "Untitled"                          # ❌ WRONG
  - Audit items count: 0                          # ❌ WRONG
  - Audit items total: 1                          # Shows it exists but filtered
  - Field lineage: ["field"]                      # ❌ WRONG
  - UI: No audit button                           # ❌ WRONG
```

### After Fixes ✅

```bash
Query: "What cloud provider is mentioned here?"
Template: "One sheeter"

Results:
  - Filename: "Pinecone-for-AWS-Onesheet.pdf"    # ✅ CORRECT
  - Audit items count: 1                          # ✅ CORRECT
  - Audit items total: 1                          # ✅ MATCHES
  - Field lineage: ["cloud_platform"]             # ✅ CORRECT
  - Audit item: cloud_platform (confidence=0.42)  # ✅ CORRECT
  - UI: Shows warning banner + "Review All" btn   # ✅ CORRECT
```

---

## Frontend Display

With the backend fixes, the frontend **already has complete audit UI** that now works:

### Warning Banner
```
⚠️ Data Quality Notice
This answer uses 1 field with low confidence scores.

[Show fields needing review →]
```

### Audit Fields Section
```
🔍 Fields Needing Review (1)                    [Review All]

📄 Pinecone-for-AWS-Onesheet.pdf
    cloud_platform: AWS (42% confidence) [Verify]
```

### Audit Actions
- Click individual field → Opens `InlineAuditModal` with PDF viewer
- Click "Review All" → Opens `BatchAuditModal` with table view
- Keyboard shortcuts: 1/2/3 (accept/correct/reject), S (skip), Esc (close)

---

## Related Fixes

This is the third fix in the VALUE EXTRACTION series:

1. **500 Internal Server Error** - Fixed missing `all_audit_items` variable ([ASKAI_IMPROVEMENTS.md](ASKAI_IMPROVEMENTS.md))
2. **VALUE EXTRACTION Pattern** - Added Claude prompt to distinguish "What is X?" from "Find X" ([ASKAI_VALUE_EXTRACTION_FIX.md](ASKAI_VALUE_EXTRACTION_FIX.md))
3. **Document Recall & Audit** - Fixed field extraction and metadata (this doc)

---

## Files Modified

1. **backend/app/services/elastic_service.py** (line 530)
   - Added `filename` to top-level search response

2. **backend/app/utils/query_field_extractor.py** (lines 236-246)
   - Special-cased EXISTS query field extraction

3. **backend/app/services/claude_service.py** (lines 1387-1425)
   - Added VALUE EXTRACTION vs TEXT SEARCH distinction (previous fix)

4. **backend/app/api/search.py** (lines 389, 411)
   - Fixed missing `all_audit_items` variable (previous fix)

---

## Testing Checklist

- [x] Filename displays correctly in search results
- [x] Low-confidence fields trigger audit UI
- [x] Field lineage extracts correct field names from EXISTS queries
- [x] Audit items properly filtered by query-relevant fields
- [x] Warning banner shows when low confidence detected
- [x] "Review All" button appears and works
- [x] Individual field audit buttons work
- [x] InlineAuditModal opens with correct field data
- [x] BatchAuditModal shows all audit items in table view

---

## Performance Impact

**Positive**:
- ✅ EXISTS queries are faster than multi_match text searches
- ✅ Accurate field extraction enables better audit filtering
- ✅ Fewer unnecessary audit items shown (only query-relevant)

**Neutral**:
- No performance degradation from fixes
- All changes are in non-critical path

---

## Future Improvements

1. **Enhanced Field Extraction**
   - Add support for more complex query types (nested, has_child, etc.)
   - Better handling of wildcard queries

2. **Smarter Audit Filtering**
   - Include fields mentioned in the answer, even if not in query
   - Track field usage in Claude's response generation

3. **Audit Workflow Enhancements**
   - Bulk approve/reject for similar fields
   - Auto-suggest corrections based on patterns
   - Track verification velocity and accuracy

---

## Related Documentation

- **Main Implementation**: [ASKAI_IMPROVEMENTS.md](ASKAI_IMPROVEMENTS.md)
- **VALUE EXTRACTION**: [ASKAI_VALUE_EXTRACTION_FIX.md](ASKAI_VALUE_EXTRACTION_FIX.md)
- **Inline Audit**: [INLINE_AUDIT_IMPLEMENTATION.md](INLINE_AUDIT_IMPLEMENTATION.md)
- **Batch Audit**: [BATCH_AUDIT_IMPLEMENTATION.md](BATCH_AUDIT_IMPLEMENTATION.md)
- **Field Lineage**: [docs/features/QUERY_FIELD_LINEAGE_IMPLEMENTATION.md](docs/features/QUERY_FIELD_LINEAGE_IMPLEMENTATION.md)

---

**Date Fixed**: 2025-11-06
**Severity**: Critical (blocking audit workflow)
**Status**: ✅ Resolved and tested
**Test Coverage**: ✅ All test cases passing
**User Impact**: ✅ Workflow restored and improved
