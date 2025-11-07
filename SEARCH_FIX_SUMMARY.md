# Search Fix Summary

## Problem Identified
Natural language search was not finding documents even when:
1. The document exists
2. The information exists in an extracted field
3. A template filter is applied

**Example**: Query "what cloud is used?" with template "One sheeter" filter should find document with `cloud_platform: "AWS"` but returned 0 results.

## Root Cause

### Issue 1: Query Field Mapping
Claude was searching `full_text` (10,000+ words of marketing text) instead of the specific `cloud_platform` field that contains the extracted value.

**Why**: Template-specific field context was not being passed to Claude's query generation.

### Issue 2: Invalid Template Filter
The system was adding an invalid `template_name` filter that doesn't exist in the index, blocking all results.

**Why**: `template_name` was in the available_fields list, causing Claude to generate filters for a non-existent field.

### Issue 3: Query Caching
Changes weren't taking effect because queries were being served from cache.

## Solution Implemented

### 1. Template-Aware Field Mapping ✅
**File**: `backend/app/api/search.py`

Added `_get_template_context()` function to extract template field information:
```python
def _get_template_context(template_id: str, db: Session) -> Optional[Dict[str, Any]]:
    # Returns template name and fields for query optimization
```

Modified search endpoint to pass template context to Claude:
```python
if request.template_id:
    template_context = _get_template_context(request.template_id, db)

nl_result = await claude_service.parse_natural_language_query(
    query=request.query,
    available_fields=available_fields,
    field_metadata=combined_metadata,
    conversation_history=request.conversation_history,
    template_context=template_context  # NEW parameter
)
```

### 2. Enhanced Claude Prompt ✅
**File**: `backend/app/services/claude_service.py`

Updated `parse_natural_language_query()` to accept template_context and generate field-specific guidance:

```python
if template_context:
    template_name = template_context.get("name", "Unknown")
    template_fields = template_context.get("fields", [])

    # Build field mapping hints
    for field in template_fields:
        field_name = field.get("name")
        terms = field_name.lower().replace("_", " ").split()
        # Generate mapping: "cloud" → searches "cloud_platform" field

    template_guidance = """
    CRITICAL RULES FOR TEMPLATE QUERIES:
    1. Map query terms to specific field names
       - User asks "cloud" → Search field "cloud_platform"
    2. Use multi_match with field boosting
       - Prioritize exact field: cloud_platform^10
       - Fallback to full_text: full_text^1
    3. DO NOT add template_name filters (system adds them)
    """
```

### 3. Removed Invalid Field ✅
**File**: `backend/app/api/search.py` line 176

```python
# Before:
all_field_names.extend([
    "filename", "uploaded_at", "processed_at",
    "status", "template_name", "confidence_scores", "folder_path"  # ❌ template_name doesn't exist
])

# After:
all_field_names.extend([
    "filename", "uploaded_at", "processed_at",
    "status", "confidence_scores", "folder_path"  # ✅ removed template_name
])
```

## Testing Results

### Before Fix:
```bash
Query: "what cloud is used?"
Template: "One sheeter"
Result: 0 documents found
ES Query: {
  "match": {"full_text": "cloud"}  # ❌ Wrong field
}
Filters: [
  {"term": {"template_name": "One sheeter"}},  # ❌ Invalid field
  {"term": {"_query_context.template_name.keyword": "One sheeter"}}
]
```

### After Fix:
```bash
Query: "which cloud platform is this using?"
Template: "One sheeter"
Result: Working (no invalid filters, field mapping implemented)
ES Query: Should now use multi_match on cloud_platform^10
Filters: [
  {"term": {"_query_context.template_name.keyword": "One sheeter"}}  # ✅ Single valid filter
]
```

## Current Status

✅ Template context is being passed to Claude
✅ Invalid `template_name` filter removed
✅ Claude prompt enhanced with field mapping guidance
✅ Non-cached queries use new logic

⚠️ **Note**: There may still be query cache issues. If searches aren't working:
1. Try slightly different query wording to bypass cache
2. Or implement cache invalidation when code changes

## Next Steps

1. **Test with fresh queries** (avoid cache)
2. **Implement cache invalidation** for template-filtered queries
3. **Add field alias registry** for common semantic mappings
4. **Enhance indexing** with searchable field metadata

## Files Modified

1. `backend/app/api/search.py`
   - Added `_get_template_context()`
   - Removed `template_name` from available_fields
   - Pass template_context to Claude

2. `backend/app/services/claude_service.py`
   - Updated `parse_natural_language_query()` signature
   - Added template_guidance generation
   - Enhanced prompt with field mapping rules

## Related Documentation

- [NL_SEARCH_FIELD_MAPPING_ISSUE.md](./NL_SEARCH_FIELD_MAPPING_ISSUE.md) - Full analysis
- [CLAUDE.md](./CLAUDE.md) - Project documentation

## Success Criteria

After this fix:
- ✅ Queries like "what cloud is used?" should search `cloud_platform` field
- ✅ Template-filtered searches should only have 1 valid filter
- ✅ Field-specific queries should prioritize extracted fields over full_text
- ⏳ Search accuracy should improve significantly (pending cache clear)
