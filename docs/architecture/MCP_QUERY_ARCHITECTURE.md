# MCP Query Architecture - Universal Search Endpoint

**Status**: ✅ **CLARIFIED** - No separate MCP endpoint needed
**Date**: 2025-11-09
**Key Decision**: Use `/api/search` for ALL query operations (Web UI, MCP, API clients)

---

## 🎯 The Simple Truth

**There is ONE search endpoint:** `/api/search`

- Web UI uses it ✅
- MCP clients should use it ✅
- API consumers use it ✅
- Everyone gets the same rich responses ✅

## ✅ What `/api/search` Provides

```json
POST /api/search
{
  "query": "Show me all invoices over $1000",
  "conversation_history": [],  // Optional for follow-ups
  "template_id": null,          // Optional template filter
  "folder_path": null           // Optional folder filter
}
```

**Response includes EVERYTHING:**
```json
{
  "query": "...",
  "answer": "Natural language answer with citations",

  // ✅ Query history tracking (NEW)
  "query_id": "abc-123-uuid",
  "documents_link": "http://localhost:3000/documents?query_id=abc-123",

  // ✅ Audit metadata
  "audit_items": [{...}],                    // Low-confidence fields
  "audit_items_filtered_count": 2,           // Query-relevant only
  "audit_items_total_count": 8,              // All low-confidence
  "confidence_summary": {...},               // Quality metrics
  "field_lineage": {...},                    // Which fields were queried

  // ✅ Search results
  "results": [...],                          // Matching documents
  "total": 10,                               // Total count
  "elasticsearch_query": {...},              // Generated ES query

  // ✅ Answer metadata
  "answer_metadata": {
    "sources_used": [30, 42, 74],           // Document IDs
    "low_confidence_warnings": [...],
    "confidence_level": "high|medium|low"
  }
}
```

## ❌ What Was Removed

**`/api/mcp/search/rag/query`** - REMOVED
- This endpoint was removed because it didn't provide citations, audit, or query history
- The removal comment said: "Use the Ask AI UI instead"
- **But that's wrong** - MCP clients should use `/api/search` directly!

## 🔄 Migration Path

### Old (Broken)
```python
# MCP client tries to call non-existent endpoint
response = requests.post(
    f"{API_URL}/api/mcp/search/rag/query",
    params={"question": query}
)
# ❌ 404 Not Found
```

### New (Correct)
```python
# MCP client calls universal search endpoint
response = requests.post(
    f"{API_URL}/api/search",
    json={"query": query}
)
# ✅ Full response with query_id and documents_link
```

## 📊 Query History Flow

1. **User asks question** (via Web UI or MCP)
2. **Backend creates QueryHistory entry:**
   ```python
   query_history = QueryHistory.create_from_search(
       query=query,
       answer=answer,
       document_ids=[30, 42, 74],
       source="ask_ai"  # or "mcp"
   )
   ```
3. **Response includes:**
   - `query_id`: UUID for this query
   - `documents_link`: `/documents?query_id={uuid}`
4. **User can click link** to see source documents
5. **Documents page shows banner:**
   - "Showing documents used in query: '{query_text}'"
   - Lists only the documents actually used
   - Shows timestamp, source (Ask AI or MCP)

## 🧪 Testing Status

### ✅ Working
- `POST /api/search` - Returns query_id and documents_link
- `GET /api/documents?query_id={uuid}` - Filters to query documents
- Query history tracking for Ask AI queries

### ❌ Broken (Need to Fix)
- `backend/tests/test_mcp_audit_integration.py` - Tests non-existent `/api/mcp/search/rag/query`
- `test_search_aggregations.py:222` - References `test_rag_query()`
- PROJECT_INDEX.json - Shows stale reference to `rag_query_mcp:670`

## 🎨 MCP Client Example

**Python MCP Server:**
```python
# In app/mcp/server.py or MCP client
async def ask_question(question: str) -> str:
    """Ask a question about documents using universal search endpoint."""

    response = await httpx.post(
        f"{API_URL}/api/search",
        json={"query": question}
    )
    data = response.json()

    # Format response for MCP
    answer = data["answer"]
    query_id = data["query_id"]
    docs_link = data["documents_link"]
    audit_count = data["audit_items_filtered_count"]

    # Return structured response
    return {
        "answer": answer,
        "query_id": query_id,
        "documents_url": f"http://localhost:3000{docs_link}",
        "data_quality": {
            "low_confidence_count": audit_count,
            "audit_recommended": audit_count > 0
        },
        "next_steps": {
            "view_sources": f"Open {docs_link} to see documents used",
            "audit_data": f"Review {audit_count} low-confidence fields" if audit_count else None
        }
    }
```

## 📝 Documentation Updates Needed

1. **Update MCP docs** to point to `/api/search`
2. **Remove references** to non-existent RAG endpoint
3. **Fix broken tests** or remove them
4. **Update PROJECT_INDEX.json** to remove stale `rag_query_mcp` reference

## ✨ Benefits of Universal Endpoint

1. **Single Source of Truth** - One endpoint, one implementation
2. **Consistent Responses** - All clients get same rich data
3. **Query History for Everyone** - Web UI and MCP both tracked
4. **No Duplication** - No need to maintain separate RAG logic
5. **Better UX** - MCP users can view sources in web UI via link

## 🎯 Summary

**Question:** "How come the documents link doesn't show up in MCP responses?"
**Answer:** Because MCP was trying to call a non-existent endpoint!

**Solution:** MCP clients should call `/api/search` directly
**Result:** They get `query_id` and `documents_link` automatically

---

**Last Updated**: 2025-11-09
**Architecture Version**: 2.2 (Universal Search Endpoint)
**Status**: Ready for MCP integration testing
