# Natural Language Search - Field Mapping Issue Analysis

## Problem Summary
Users cannot find documents using natural language queries even when:
1. The document exists and is indexed
2. The information exists in an extracted field
3. A template filter is applied

### Example Scenario
**Query**: "what cloud is used in the one sheeter about pinecone?"
**Template Filter**: "One sheeter" selected
**Expected**: Find the Pinecone onesheet document with `cloud_platform: "AWS"`
**Actual**: "No documents found"

## Root Cause Analysis

### Investigation Results

#### 1. Document Exists and is Indexed Correctly
```bash
# Query: Find documents with "One sheeter" template
curl 'http://localhost:9200/documents/_search' -d '{
  "query": {
    "term": {
      "_query_context.template_name.keyword": "One sheeter"
    }
  }
}'

# Result: ✅ Found 1 document
{
  "filename": "Pinecone-for-AWS-Onesheet.pdf",
  "product_name": "Pinecone",
  "cloud_platform": "AWS",  # <-- THE ANSWER IS HERE
  "_query_context": {
    "template_name": "One sheeter",
    "field_names": ["product_name", "cloud_platform", "main_heading", ...]
  }
}
```

#### 2. Template Filter Works Correctly
- Template "One sheeter" exists in ES with 1 document
- Filter `_query_context.template_name.keyword: "One sheeter"` works
- Template has field `cloud_platform` defined

#### 3. Query Generation Issue
**Current Behavior**: Claude generates query searching `full_text` field
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "full_text": "cloud"  // ❌ Wrong field!
          }
        }
      ],
      "filter": [
        {
          "term": {
            "_query_context.template_name.keyword": "One sheeter"
          }
        }
      ]
    }
  }
}
```
**Result**: 0 documents (because "cloud" in full_text doesn't match well)

**Should Be**: Query should search in the actual extracted field
```json
{
  "query": {
    "bool": {
      "should": [
        {
          "match": {
            "cloud_platform": "cloud AWS platform"  // ✅ Right field!
          }
        },
        {
          "match": {
            "cloud_platform.keyword": "AWS"
          }
        }
      ],
      "filter": [
        {
          "term": {
            "_query_context.template_name.keyword": "One sheeter"
          }
        }
      ]
    }
  }
}
```

## The Three Core Problems

### Problem 1: Query Term → Field Name Mapping

**Issue**: Claude doesn't map natural language terms to specific field names

User says: "what **cloud** is used?"
Template has field: `cloud_platform`
Claude searches: `full_text` (generic) ❌
Should search: `cloud_platform` (specific) ✅

**Why This Happens**:
- Claude receives available field names as a flat list
- No semantic mapping between query terms and field names
- Template context (field names) not used for term→field inference

### Problem 2: Template-Specific Field Context Not Used

**Issue**: When a template filter is applied, we know EXACTLY which fields exist, but Claude doesn't leverage this

Available information when user selects "One sheeter":
```python
{
  "template_name": "One sheeter",
  "fields": [
    {"name": "cloud_platform", "type": "text", "description": "..."},
    {"name": "product_name", "type": "text", "description": "..."},
    ...
  ]
}
```

**What Claude Should Do**:
1. User asks: "what cloud is used?"
2. Parse query intent: "looking for cloud provider information"
3. Match to template field: `cloud_platform` (contains "cloud")
4. Generate targeted query: Search `cloud_platform` field

### Problem 3: Field Search Priority

**Issue**: Full-text search is too broad and misses specific field values

The document's `full_text` contains 10,000+ words of marketing copy. The word "cloud" appears 50+ times in various contexts:
- "cloud infrastructure"
- "cloud-native"
- "build in the cloud"
- "multi-cloud"

But the ACTUAL extracted value is in:
```json
{"cloud_platform": "AWS"}  // <-- This is what the user wants
```

**Current Query**: Searches all of `full_text` → poor BM25 ranking
**Better Query**: Prioritize extracted fields → direct match

## Solutions

### Solution 1: Template-Aware Field Mapping (Immediate Fix)

**What**: When template filter is active, use template field schema to guide query generation

**Implementation**:
```python
# In parse_natural_language_query or QueryOptimizer

# 1. If template_id provided, fetch template fields
if template_id:
    template_fields = get_template_fields(template_id, db)
    # Returns: [
    #   {"name": "cloud_platform", "description": "Cloud provider (AWS/GCP/Azure)", ...},
    #   {"name": "product_name", "description": "Product name", ...}
    # ]

# 2. Build enhanced field context for Claude
field_context = {
    "cloud_platform": {
        "aliases": ["cloud", "cloud provider", "platform", "AWS", "GCP", "Azure"],
        "type": "text",
        "description": "Cloud provider used"
    }
}

# 3. Enhanced prompt for Claude
prompt = f"""
User query: "{query}"
Template: "{template_name}" with these fields:
{json.dumps(field_context, indent=2)}

IMPORTANT: This is a template-specific query. You KNOW these exact fields exist.
When the user asks about "cloud", they likely want the "cloud_platform" field.

Generate a query that:
1. Searches specific fields that match the query intent
2. Prioritizes exact field matches over full_text
3. Uses both the field value AND full_text as fallback
"""
```

**Expected Result**:
```json
{
  "query": {
    "bool": {
      "should": [
        {"match": {"cloud_platform": {"query": "cloud AWS", "boost": 10}}},
        {"match": {"full_text": {"query": "cloud", "boost": 1}}}
      ],
      "minimum_should_match": 1,
      "filter": [
        {"term": {"_query_context.template_name.keyword": "One sheeter"}}
      ]
    }
  }
}
```

### Solution 2: Query-Time Field Expansion

**What**: Automatically search across semantically related fields

**Implementation**:
```python
def expand_query_fields(query_terms, available_fields):
    """
    Map query terms to relevant fields using fuzzy matching

    Example:
    - "cloud" → ["cloud_platform", "infrastructure", "_all_text"]
    - "price" → ["pricing", "cost", "amount", "total"]
    """
    field_map = {}

    for term in query_terms:
        matching_fields = []
        for field in available_fields:
            # Fuzzy match: does field name contain term or vice versa?
            if term.lower() in field.lower() or field.lower() in term.lower():
                matching_fields.append(field)

        field_map[term] = matching_fields if matching_fields else ["_all_text"]

    return field_map

# Usage in query generation
query_terms = ["cloud"]
field_mapping = expand_query_fields(query_terms, template_fields)
# Returns: {"cloud": ["cloud_platform"]}

# Generate multi-field query
{
  "multi_match": {
    "query": "cloud",
    "fields": ["cloud_platform^10", "_all_text^1"],  # Boost specific field
    "type": "best_fields"
  }
}
```

### Solution 3: Enhance Field Metadata in Index

**What**: Add searchable field metadata to help with semantic matching

**Implementation**:
```python
# When indexing documents, add field aliases
doc = {
    "cloud_platform": "AWS",
    "cloud_platform_meta": {
        "aliases": ["cloud", "cloud provider", "platform", "infrastructure"],
        "description": "Cloud platform used (AWS/GCP/Azure)"
    },
    "_field_index": "cloud_platform cloud provider platform AWS GCP Azure ...",
    "_all_fields": {
        "cloud_platform": "AWS"  # Normalized for searching
    }
}

# In query generation, search _field_index first
{
  "bool": {
    "should": [
      # Step 1: Find documents with relevant fields
      {
        "match": {
          "_field_index": "cloud"  # Finds docs with "cloud_platform" field
        }
      },
      # Step 2: Match in those specific fields
      {
        "nested": {
          "path": "_all_fields",
          "query": {
            "match": {
              "_all_fields.cloud_platform": "AWS"
            }
          }
        }
      }
    ]
  }
}
```

### Solution 4: Template Field Registry with Semantic Aliases

**What**: Pre-define semantic mappings for common query patterns

**Implementation**:
```python
# In backend/app/services/schema_registry.py or similar

FIELD_ALIASES = {
    # Financial
    "price": ["price", "cost", "amount", "total", "subtotal", "fee"],
    "date": ["date", "created_at", "timestamp", "when", "time"],
    "vendor": ["vendor", "supplier", "seller", "company", "merchant"],

    # Technical
    "cloud": ["cloud_platform", "platform", "provider", "infrastructure"],
    "database": ["database", "db", "storage", "data_store"],

    # Add more as needed...
}

def get_semantic_fields(query_term, available_fields):
    """
    Get fields that semantically match a query term
    """
    # Check if term has known aliases
    if query_term.lower() in FIELD_ALIASES:
        aliases = FIELD_ALIASES[query_term.lower()]
        return [f for f in available_fields if any(a in f.lower() for a in aliases)]

    # Fallback to fuzzy matching
    return [f for f in available_fields if query_term.lower() in f.lower()]
```

## Recommended Implementation Plan

### Phase 1: Quick Fix (1-2 hours)
1. **Update Claude Prompt** in `parse_natural_language_query()`:
   - Add explicit instruction to search specific fields when template is known
   - Include field descriptions and aliases in prompt
   - Boost field-specific matches over full_text

**File**: `backend/app/services/claude_service.py` line ~1120

```python
# Add to prompt when template_id is provided
if template_id:
    template_info = get_template_fields(template_id, db)
    field_guidance = "\n".join([
        f"- {f['name']}: {f.get('description', '')} (aliases: {', '.join(f.get('aliases', []))})"
        for f in template_info
    ])

    prompt += f"""

TEMPLATE-SPECIFIC QUERY OPTIMIZATION:
This query is filtered to template "{template_name}" with these fields:
{field_guidance}

IMPORTANT RULES:
1. Match query terms to specific field names (e.g., "cloud" → "cloud_platform")
2. Use multi_match across relevant fields with boost: {{field}}^10, full_text^1
3. Prioritize exact field matches over full_text search
4. If user asks about a field value, search THAT FIELD, not full_text
"""
```

### Phase 2: Field Mapping System (4-6 hours)
1. Add `get_semantic_fields()` helper function
2. Build field alias registry
3. Integrate with QueryOptimizer
4. Update field metadata enrichment

**File**: `backend/app/utils/field_mapper.py` (new file)

### Phase 3: Enhanced Indexing (8-10 hours)
1. Add `_field_index` with searchable field metadata
2. Enhance field metadata with semantic aliases
3. Update index mapping to support nested field search
4. Re-index existing documents

**File**: `backend/app/services/elastic_service.py`

## Testing Strategy

### Test Case 1: Basic Field Mapping
```python
# Query: "what cloud is used?"
# Template: "One sheeter"
# Expected: Find document with cloud_platform="AWS"

query = "what cloud is used?"
template_id = "schema_15"
result = search(query, template_id)

assert result["total"] > 0
assert result["results"][0]["cloud_platform"] == "AWS"
```

### Test Case 2: Semantic Aliases
```python
# Query: "what platform" (alias for cloud_platform)
# Should still find cloud_platform field

query = "what platform is this?"
result = search(query, template_id="schema_15")

assert "cloud_platform" in result["field_lineage"]["queried_fields"]
```

### Test Case 3: Cross-Field Search
```python
# Query should search both specific field AND full_text

query = "AWS infrastructure"
es_query = parse_nl_query(query, template_id="schema_15")

# Should have multi_match or bool query with both fields
assert "cloud_platform" in str(es_query)
assert "full_text" in str(es_query)
```

## Success Metrics

After implementing Phase 1:
- ✅ Queries like "what cloud is used?" should find the document
- ✅ Field-specific queries should search the right fields
- ✅ Template-filtered searches should be more accurate

After implementing Phase 2+3:
- ✅ Semantic aliases work ("platform" → `cloud_platform`)
- ✅ 80%+ of natural language queries hit the right fields
- ✅ Reduced false negatives (finding documents that exist but weren't matched)

## Related Files

- `backend/app/services/claude_service.py` - Query generation (line ~1053)
- `backend/app/api/search.py` - Search endpoint (line ~24)
- `backend/app/services/elastic_service.py` - ES indexing (line ~270)
- `frontend/src/pages/ChatSearch.jsx` - Frontend UI
- `backend/app/utils/query_field_extractor.py` - Field lineage tracking

## References

- Elasticsearch Multi-Match Query: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-multi-match-query.html
- Field Boosting: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-match-query.html#match-field-params
- Query String Syntax: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html
