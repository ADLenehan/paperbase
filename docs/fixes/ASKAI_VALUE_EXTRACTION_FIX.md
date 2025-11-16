# AskAI Value Extraction Fix

## Problem

When users asked questions like **"What cloud provider are we mentioning here?"** with the "One sheeter" template filter active, the system returned 0 results even though:
- A document existed (Pinecone-for-AWS-Onesheet.pdf)
- The document had `cloud_platform: "AWS"` in its indexed fields
- The template filter was working correctly

## Root Cause

Claude was interpreting the query as a TEXT SEARCH instead of a VALUE EXTRACTION:

**What Claude was doing (WRONG)**:
- User asks: "What cloud provider are we mentioning here?"
- Claude generates: `multi_match` query searching for the literal text "cloud provider"
- Document contains "AWS" in the `cloud_platform` field
- Document does NOT contain the text "cloud provider" anywhere
- Result: 0 matches ❌

**What Claude should do (CORRECT)**:
- User asks: "What cloud provider are we mentioning here?"
- Claude recognizes this as asking for the VALUE of the `cloud_platform` field
- Claude generates: `exists` query to find documents with `cloud_platform` populated
- Answer generation phase extracts and returns the actual value: "AWS"
- Result: 1 match, correct answer ✅

## Solution

Updated the Claude prompt in `backend/app/services/claude_service.py` (lines 1387-1425) to distinguish between:

### VALUE EXTRACTION Queries
Pattern: "What [field] is..." / "What [field] are..." / "What are the [field]..."

Examples:
- "What cloud provider are we mentioning here?"
- "What are the key features?"
- "What product name is this?"

**Query Strategy**: Use `exists` filter to find ANY document with that field populated, then extract the value in the answer

```json
{
  "bool": {
    "filter": [
      {"exists": {"field": "cloud_platform"}}
    ]
  }
}
```

### TEXT SEARCH Queries
Pattern: "Find documents about..." / "Show me documents with..." / "Search for..."

Examples:
- "Find documents about cloud platforms"
- "Show me documents mentioning AWS"
- "Search for cloud provider information"

**Query Strategy**: Use `multi_match` with field boosting to find documents containing the search terms

```json
{
  "multi_match": {
    "query": "cloud platform",
    "fields": ["cloud_platform^10", "full_text^1"],
    "type": "best_fields"
  }
}
```

## Testing

### Before Fix
```bash
Query: "What cloud provider are we mentioning here?"
Template: "One sheeter"
Results: 0 documents found ❌
Answer: "I cannot determine which cloud provider is being mentioned..."
```

### After Fix
```bash
Query: "What cloud provider are we mentioning here?"
Template: "One sheeter"
Results: 1 document found ✅
Explanation: "Retrieving documents to extract cloud_platform value"
Answer: "The cloud provider mentioned here is AWS (Amazon Web Services)..."
```

### Additional Test Cases
```bash
# Test 1: Value extraction for different field
Query: "What are the key features?"
Results: 1 ✅
Answer: Returns actual key features list

# Test 2: Text search (should still work)
Query: "Find documents about AWS"
Results: Multiple ✅
Answer: Returns documents mentioning AWS
```

## Implementation Details

**File Modified**: `backend/app/services/claude_service.py`

**Changes**:
1. Added new rule to QUERY CONSTRUCTION RULES section:
   - "⚠️ CRITICAL: Distinguish VALUE EXTRACTION from TEXT SEARCH"
   - Pattern recognition for "What [field]" queries

2. Added Example 1a (VALUE EXTRACTION):
   - Demonstrates `exists` query for field value extraction
   - Shows correct explanation pattern

3. Renamed existing Example 1 to Example 1b (TEXT SEARCH):
   - Clarifies this is for text search, not value extraction

**Additional Changes**:
1. Fixed missing `all_audit_items` variable in `backend/app/api/search.py` (lines 389, 411)
2. Cleared query cache to force re-parsing with new prompt

## Impact

- ✅ **User Experience**: Natural "What is X?" questions now work correctly
- ✅ **Accuracy**: Returns actual field values instead of "No documents found"
- ✅ **Template Context**: Template-specific fields are now properly utilized
- ✅ **Performance**: `exists` queries are faster than full-text searches
- ✅ **Backward Compatible**: TEXT SEARCH queries still work as before

## Future Improvements

1. **Pattern Recognition**: Could expand to more patterns like:
   - "Tell me about [field]"
   - "Which [field] does this mention?"
   - "Show me the [field]"

2. **Field Suggestions**: If field doesn't exist, suggest similar fields:
   - User asks: "What vendor is this?"
   - No `vendor` field exists
   - Suggest: "Did you mean 'company_name' or 'supplier'?"

3. **Multi-Value Extraction**: Handle queries asking for multiple fields:
   - "What cloud provider and product name are mentioned?"

## Related Documentation

- Main docs: [ASKAI_IMPROVEMENTS.md](./ASKAI_IMPROVEMENTS.md)
- Field lineage: [docs/features/QUERY_FIELD_LINEAGE_IMPLEMENTATION.md](./docs/features/QUERY_FIELD_LINEAGE_IMPLEMENTATION.md)
- Template matching: [CLAUDE.md](./CLAUDE.md)

---

**Date Fixed**: 2025-11-06
**Severity**: Critical (blocking user workflow)
**Status**: ✅ Resolved and tested
