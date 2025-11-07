# MCP Tools Optimization for LLMs

## Key Findings

### ✅ Reducto Already Has Embedding-Ready Data!

**What Reducto Returns:**
```json
{
  "chunks": [
    {
      "id": "chunk_1",
      "content": "This is the text content",
      "logprobs_confidence": 0.95,
      "page": 1,
      "bbox": [x, y, width, height]
    }
  ]
}
```

**Perfect for Embeddings Because:**
- ✅ Already chunked semantically (not arbitrary splits)
- ✅ Has confidence scores per chunk
- ✅ Has page numbers and bounding boxes
- ✅ Optimal size for embedding models (Reducto optimizes chunk size)

**Action:** Use Reducto chunks directly for embeddings instead of re-chunking!

---

## Tool Optimization Audit

### Current Issues

1. **Vague Descriptions** - LLMs don't know WHEN to use which tool
2. **Missing Examples** - No concrete use cases
3. **Unclear Prioritization** - Which tool for which scenario?
4. **No Workflow Guidance** - How tools work together

### Optimized Tool Definitions

#### 🎯 PRIMARY TOOLS (Use These First)

##### 1. `rag_query` - **START HERE FOR QUESTIONS**

```json
{
  "name": "rag_query",
  "description": "🎯 PRIMARY TOOL: Answer questions about documents with citations. Use this FIRST when user asks questions about document content. Returns AI-generated answer based on actual document text with source citations.",
  "when_to_use": [
    "User asks: 'What is the total contract value?'",
    "User asks: 'Which documents mention X?'",
    "User asks: 'Summarize the key points'",
    "Any question that requires reading document content"
  ],
  "examples": [
    {
      "user": "What were the Q1 revenues?",
      "call": {"question": "What were the Q1 revenues?", "max_results": 5}
    },
    {
      "user": "Find all contracts with auto-renewal",
      "call": {"question": "Which contracts have auto-renewal clauses?", "filters": {"template": "Contracts"}}
    }
  ]
}
```

##### 2. `search_documents` - **FIND RELEVANT DOCUMENTS**

```json
{
  "name": "search_documents",
  "description": "🔍 Find documents by keywords or concepts. Use when user wants to FIND documents (not read them). Returns list of matching documents with metadata. Follow up with get_document_content to read.",
  "when_to_use": [
    "User says: 'Find all invoices from Acme Corp'",
    "User says: 'Show me contracts expiring in 2024'",
    "Need to filter documents before reading",
    "Building a list of documents to process"
  ],
  "workflow": "search_documents → get_document_content → analyze",
  "examples": [
    {
      "user": "Find all invoices over $1000",
      "call": {"query": "invoices over $1000", "max_results": 20}
    }
  ]
}
```

##### 3. `get_document_content` - **READ FULL TEXT**

```json
{
  "name": "get_document_content",
  "description": "📄 Read complete document text. Use when you have a document_id and need to read/analyze the full content. Returns entire document text with extracted fields.",
  "when_to_use": [
    "After search_documents returns results",
    "User says: 'Read document #123'",
    "Need full context for analysis",
    "Summarizing or extracting from specific document"
  ],
  "workflow": "Always call this after finding documents with search",
  "examples": [
    {
      "user": "Read the contract we just found",
      "previous": "search_documents returned doc_id=456",
      "call": {"document_id": 456}
    }
  ]
}
```

---

#### 📊 ANALYTICS TOOLS (For Data Questions)

##### 4. `get_dashboard_analytics` - **OVERVIEW STATS**

```json
{
  "name": "get_dashboard_analytics",
  "description": "📊 Get overview statistics: document counts, status breakdown, template usage. Use for general 'how many' or 'what's the status' questions. Returns pre-computed analytics.",
  "when_to_use": [
    "User asks: 'How many documents do I have?'",
    "User asks: 'What types of documents?'",
    "User asks: 'Show me an overview'",
    "Dashboard or summary views"
  ]
}
```

##### 5. `multi_aggregate` - **CUSTOM ANALYTICS**

```json
{
  "name": "multi_aggregate",
  "description": "📈 Custom analytics across multiple dimensions. Use for specific analytical questions requiring calculations (sum, avg, count, etc.). More powerful than dashboard.",
  "when_to_use": [
    "User asks: 'What's the average invoice amount?'",
    "User asks: 'Total revenue by vendor?'",
    "Need custom metrics not in dashboard"
  ],
  "examples": [
    {
      "user": "What's the total invoice amount by vendor?",
      "call": {
        "aggregations": [
          {"name": "by_vendor", "field": "vendor_name", "type": "terms"},
          {"name": "total_amount", "field": "total_amount", "type": "sum"}
        ]
      }
    }
  ]
}
```

---

#### 🔧 UTILITY TOOLS (Support Tools)

##### 6. `list_fields` - **DISCOVER SCHEMA**

```json
{
  "name": "list_fields",
  "description": "🔍 Discover what fields exist across documents. Use when you need to know what data is available or what to search/aggregate on. Returns all searchable fields with descriptions.",
  "when_to_use": [
    "Starting a new task - understand schema first",
    "User asks: 'What data do you have?'",
    "Before constructing complex queries",
    "When field names are unclear"
  ],
  "workflow": "Call this FIRST when exploring unknown document set"
}
```

##### 7. `list_templates` - **DISCOVER DOCUMENT TYPES**

```json
{
  "name": "list_templates",
  "description": "📑 List available document types (templates) with their schemas. Use to understand what types of documents exist.",
  "when_to_use": [
    "User asks: 'What types of documents can you process?'",
    "Need to filter by document type",
    "Understanding data structure"
  ]
}
```

##### 8. `get_document_chunks` - **PROCESS LONG DOCS**

```json
{
  "name": "get_document_chunks",
  "description": "📜 Get document in paginated chunks for very long documents. Use ONLY when get_document_content returns a document too large for your context window.",
  "when_to_use": [
    "get_document_content returns >100k characters",
    "Processing document section by section",
    "Memory constraints"
  ],
  "workflow": "Try get_document_content first. Use chunks only if needed."
}
```

---

## Tool Selection Decision Tree

```
User Question
    │
    ├─ "Find/Search for..."
    │   └─> search_documents
    │       └─> get_document_content (to read results)
    │
    ├─ "What is/are..." (content question)
    │   └─> rag_query (answers with citations)
    │
    ├─ "How many..." (count/stats)
    │   └─> get_dashboard_analytics
    │       OR multi_aggregate (if complex)
    │
    ├─ "Calculate/Sum/Average..." (analytics)
    │   └─> multi_aggregate
    │
    ├─ "What fields exist?"
    │   └─> list_fields
    │
    └─ "Read document #X"
        └─> get_document_content
```

---

## Common Workflows

### Workflow 1: Answer Question from Corpus
```
User: "What's the total contract value in Q1?"

1. rag_query({
     question: "What's the total contract value in Q1?",
     filters: {"template": "Contracts"}
   })

Returns: "The total Q1 contract value is $2.3M across 5 contracts."
         + citations to source documents
```

### Workflow 2: Find & Analyze Specific Documents
```
User: "Find invoices over $1000 and summarize them"

1. search_documents({
     query: "invoices over $1000",
     max_results: 20
   })
   → Returns: [doc_id: 101, 102, 103...]

2. For each doc_id:
   get_document_content({document_id: 101})
   → Returns: full text + extracted fields

3. Analyze and summarize
```

### Workflow 3: Discover & Explore
```
User: "What documents do I have?"

1. get_dashboard_analytics()
   → Returns: counts, types, status

2. list_templates()
   → Returns: Invoices, Contracts, etc.

3. search_documents({query: "*", max_results: 10})
   → Returns: sample documents
```

### Workflow 4: Deep Analytics
```
User: "Show me revenue breakdown by vendor"

1. multi_aggregate({
     aggregations: [
       {name: "by_vendor", field: "vendor_name", type: "terms"},
       {name: "revenue", field: "total_amount", type: "sum"}
     ]
   })

Returns: Aggregated stats with totals per vendor
```

---

## Response Format Optimization

### Current vs Optimized

#### ❌ Current (Less LLM-Friendly)
```json
{
  "success": true,
  "documents": [...],
  "total": 42
}
```

#### ✅ Optimized (More LLM-Friendly)
```json
{
  "success": true,
  "summary": "Found 42 invoices matching your query",
  "action": "Use get_document_content with these IDs to read full text",
  "documents": [
    {
      "id": 123,
      "filename": "invoice_001.pdf",
      "preview": "ACME Corp - Invoice #001 - Total: $1,500",
      "confidence": "high",
      "extracted_fields": {
        "vendor": "ACME Corp",
        "total": 1500,
        "date": "2024-01-15"
      }
    }
  ],
  "total": 42,
  "suggested_next_steps": [
    "Call get_document_content(123) to read full text",
    "Call multi_aggregate to get total amounts"
  ]
}
```

---

## Implementation: Enhanced Tool Descriptions

### Add to Each Tool Response

```python
@router.post("/api/mcp/search/documents")
async def search_documents_mcp(...):
    # ... existing logic ...

    return {
        "success": True,
        "summary": f"Found {total} documents matching '{query}'",
        "documents": documents,
        "total": total,

        # NEW: Guide LLM on next steps
        "next_steps": {
            "to_read": "Call get_document_content(doc_id) to read full text",
            "to_analyze": "Call rag_query with a specific question",
            "to_aggregate": "Call multi_aggregate for statistics"
        },

        # NEW: Quick preview of top result
        "top_result_preview": documents[0]["filename"] if documents else None
    }
```

---

## Reducto Chunks for Embeddings

### Use Reducto's Native Chunks

```python
async def index_document_with_reducto_chunks(
    document_id: int,
    reducto_parse_result: Dict[str, Any]
):
    """
    Index document using Reducto's native chunks for embeddings.

    Reducto already provides optimal chunks - use them directly!
    """
    from app.services.embedding_service import EmbeddingService

    embedding_service = EmbeddingService()
    chunks = reducto_parse_result.get("chunks", [])

    # Generate embeddings for each Reducto chunk
    chunk_texts = [chunk.get("content", "") for chunk in chunks]
    embeddings = await embedding_service.embed_batch(chunk_texts)

    # Index with chunk metadata
    doc = {
        "document_id": document_id,
        "full_text": " ".join(chunk_texts),
        "chunks": [
            {
                "chunk_id": chunk.get("id"),
                "text": chunk.get("content"),
                "embedding": embedding,
                "page": chunk.get("page"),
                "bbox": chunk.get("bbox"),
                "confidence": chunk.get("logprobs_confidence", 1.0)
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
    }

    await elastic_service.index(doc)
```

**Benefits:**
- ✅ No re-chunking needed
- ✅ Preserves Reducto's semantic boundaries
- ✅ Includes confidence per chunk
- ✅ Has page/bbox for citations
- ✅ Optimal chunk size (Reducto optimizes this)

---

## Tool Description Template

Use this template for all tools:

```json
{
  "name": "tool_name",
  "description": "🎯 PRIMARY/SECONDARY/UTILITY: One-line purpose. When to use.",
  "when_to_use": ["Scenario 1", "Scenario 2"],
  "when_not_to_use": ["Don't use for X", "Use Y instead"],
  "examples": [
    {"user_intent": "...", "tool_call": {...}, "result": "..."}
  ],
  "workflow": "Step 1 → Step 2",
  "related_tools": ["other_tool_1", "other_tool_2"]
}
```

---

## Summary

### What We Found

1. ✅ **Reducto has perfect embedding data** - use chunks directly
2. ⚠️ **Tool descriptions need more context** - LLMs need examples
3. ⚠️ **Missing workflow guidance** - which tool when?
4. ⚠️ **Response formats could be clearer** - add summaries

### Optimizations to Implement

1. **Update tool descriptions** with:
   - When to use (scenarios)
   - Examples
   - Workflows
   - Related tools

2. **Enhance responses** with:
   - Summary field
   - Suggested next steps
   - Preview of results

3. **Use Reducto chunks** for embeddings:
   - Don't re-chunk
   - Preserve semantic boundaries
   - Include confidence scores

### Impact

**Before:** LLM has to guess which tool to use
**After:** LLM has clear guidance on tool selection and workflows

**Before:** Responses are raw data
**After:** Responses include guidance and summaries

**Before:** Re-chunking documents (losing structure)
**After:** Using Reducto's optimized chunks (preserving structure)
