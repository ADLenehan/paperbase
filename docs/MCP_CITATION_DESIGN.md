# MCP-Friendly Citation Architecture

## Design Principles for AI Agent Consumption

When Paperbase is accessed via MCP, AI agents (Claude, GPT, etc.) need citations that enable:

1. **Proper Attribution**: "According to [document], page X..."
2. **Confidence Awareness**: "The total is $1,500 (high confidence, verified)"
3. **Source Quoting**: "The document states: 'Total Amount Due: $1,500.00'"
4. **Traceable Provenance**: Link back to exact PDF location

---

## Citation Schema for MCP

### Standard Citation Object

```json
{
  "field": {
    "name": "invoice_total",
    "value": "1500.00",
    "type": "number"
  },
  "source": {
    "document_id": 123,
    "filename": "Invoice-001.pdf",
    "page": 2,
    "bbox": {
      "x": 120,
      "y": 580,
      "width": 180,
      "height": 600,
      "page_width": 612,
      "page_height": 792
    },
    "text": "Total Amount Due: $1,500.00",
    "context": {
      "before": "Subtotal: $1,350.00\nTax (10%): $150.00\n",
      "after": "\n\nPayment Terms: Net 30"
    }
  },
  "extraction": {
    "method": "reducto_structured",
    "confidence": 0.96,
    "verified": true,
    "verified_at": "2024-11-15T10:30:00Z",
    "verified_by": "user@example.com"
  },
  "citation": {
    "short": "[Invoice-001.pdf, p.2]",
    "long": "Invoice-001.pdf, Page 2: \"Total Amount Due: $1,500.00\"",
    "academic": "Invoice-001.pdf (Page 2, verified Nov 15 2024)"
  }
}
```

### Rationale

1. **`field` section**: What was extracted (for LLM context)
2. **`source` section**: Where it came from (for attribution)
3. **`extraction` section**: How reliable is it (for confidence)
4. **`citation` section**: Pre-formatted strings (for easy quoting)

---

## MCP Tool Design

### Tool 1: `search_documents`

**Purpose**: Search with full citation support

**Input**:
```json
{
  "query": "invoices over $1000",
  "include_citations": true,
  "citation_format": "long"  // "short" | "long" | "academic"
}
```

**Output**:
```json
{
  "results": [
    {
      "document_id": 123,
      "filename": "Invoice-001.pdf",
      "fields": {
        "invoice_total": "1500.00",
        "vendor_name": "Acme Corp",
        "invoice_date": "2024-11-01"
      },
      "citations": [
        {
          // ... full citation object as above
        }
      ],
      "summary": "Invoice from Acme Corp totaling $1,500.00 [Invoice-001.pdf, p.2]"
    }
  ],
  "total": 3,
  "llm_context": {
    "query_interpretation": "Searching for invoices with total amount greater than $1000",
    "confidence_note": "All results have been verified by users",
    "suggested_answer": "Found 3 invoices meeting your criteria. The highest is from Acme Corp at $1,500.00 (Invoice-001.pdf, Page 2)."
  }
}
```

### Tool 2: `get_field_provenance`

**Purpose**: Get detailed citation for specific field

**Input**:
```json
{
  "document_id": 123,
  "field_name": "invoice_total"
}
```

**Output**:
```json
{
  "field": "invoice_total",
  "value": "1500.00",
  "full_citation": {
    // ... complete citation object
  },
  "extraction_history": [
    {
      "timestamp": "2024-11-01T14:20:00Z",
      "method": "reducto_structured",
      "value": "1500.00",
      "confidence": 0.96
    },
    {
      "timestamp": "2024-11-01T15:45:00Z",
      "method": "manual_verification",
      "value": "1500.00",
      "verified_by": "user@example.com",
      "notes": "Verified against physical document"
    }
  ],
  "source_document_url": "/api/documents/123/pdf",
  "source_location_url": "/api/documents/123/pdf?page=2&bbox=120,580,180,600"
}
```

### Tool 3: `aggregate_with_citations`

**Purpose**: Aggregate data with source tracking

**Input**:
```json
{
  "query": "sum of all invoice totals",
  "template": "Invoices"
}
```

**Output**:
```json
{
  "aggregation": {
    "type": "sum",
    "field": "invoice_total",
    "result": 15750.00,
    "count": 12
  },
  "sources": [
    {
      "document_id": 123,
      "value": 1500.00,
      "citation": "[Invoice-001.pdf, p.2]"
    },
    // ... 11 more
  ],
  "llm_summary": {
    "answer": "The total across all 12 invoices is $15,750.00",
    "citations": [
      "Invoice-001.pdf (p.2): $1,500.00",
      "Invoice-002.pdf (p.1): $2,300.00",
      // ... grouped/summarized
    ],
    "confidence": "high",
    "all_verified": true
  }
}
```

---

## API Response Format for MCP

### Existing Search Endpoint Enhancement

**Before** (current):
```json
// GET /api/search
{
  "results": [
    {
      "id": "123",
      "data": {
        "filename": "invoice.pdf",
        "invoice_total": 1500
      }
    }
  ]
}
```

**After** (with citations):
```json
// GET /api/search?include_citations=true
{
  "results": [
    {
      "id": "123",
      "data": {
        "filename": "invoice.pdf",
        "invoice_total": 1500
      },
      "citations": {
        "invoice_total": {
          "value": "1500.00",
          "source_text": "Total Amount Due: $1,500.00",
          "page": 2,
          "bbox": [120, 580, 180, 600],
          "confidence": 0.96,
          "verified": true,
          "citation_string": "[invoice.pdf, p.2]"
        }
      }
    }
  ],
  "mcp_context": {
    "query": "invoices over $1000",
    "citation_format": "Cite as: [filename, p.X]",
    "all_verified": true,
    "confidence_summary": "12 high-confidence results"
  }
}
```

---

## LLM Prompt Integration

When an LLM uses MCP to query Paperbase, it should receive context like:

```
System: You are searching a document database. All results include citations.
When referencing data, ALWAYS cite the source using the provided citation strings.

Search Results:
1. Invoice-001.pdf
   - Total: $1,500.00 [source: "Total Amount Due: $1,500.00", page 2, verified]
   - Vendor: Acme Corp [source: "Bill To: Acme Corporation", page 1, 98% confidence]

Citation Format: Use [filename, p.X] for inline citations.
Confidence Note: All results verified by users (high reliability).

Now answer the user's question using these sources.
```

---

## Implementation Strategy

### Phase 1A: Backend Schema (Week 1, Days 1-2)

1. **Add `document_blocks` table**:
```sql
CREATE TABLE document_blocks (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id),
    block_id VARCHAR(255),
    block_type VARCHAR(50),
    text_content TEXT,
    confidence FLOAT,
    page INT,
    bbox JSON,
    context_before TEXT,  -- NEW: 200 chars before
    context_after TEXT,   -- NEW: 200 chars after
    parse_metadata JSON
);
```

2. **Add `source_text` to `ExtractedField`**:
```sql
ALTER TABLE extracted_fields
ADD COLUMN source_text TEXT,
ADD COLUMN source_block_ids JSON,
ADD COLUMN extraction_method VARCHAR(50),
ADD COLUMN context_before TEXT,
ADD COLUMN context_after TEXT;
```

3. **Backfill existing data**:
```python
# Extract from reducto_parse_result JSON
for doc in documents:
    parse_result = doc.reducto_parse_result
    for chunk in parse_result['chunks']:
        block = DocumentBlock(
            document_id=doc.id,
            block_id=chunk['id'],
            text_content=chunk['content'],
            # ... etc
        )
```

### Phase 1B: Extraction Enhancement (Week 1, Days 3-4)

Update `reducto_service.py` to link extractions to source blocks:

```python
async def extract_structured(self, schema, file_path, job_id):
    # ... existing extraction logic ...

    # NEW: Link extractions to parse blocks
    for field_name, extraction in extractions.items():
        # Find source block in parse result
        source_block = self._find_source_block(
            field_name=field_name,
            extraction=extraction,
            parse_result=cached_parse_result
        )

        if source_block:
            extraction['source_text'] = source_block['content']
            extraction['context_before'] = self._get_context_before(source_block)
            extraction['context_after'] = self._get_context_after(source_block)
            extraction['source_block_id'] = source_block['id']
```

### Phase 1C: API Enhancement (Week 1, Day 5)

Add citation support to search endpoint:

```python
# backend/app/api/search.py

@router.post("")
async def search_documents(
    request: SearchRequest,
    include_citations: bool = Query(True),  # NEW: Default ON for MCP
    citation_format: str = Query("long"),   # short|long|academic
    db: Session = Depends(get_db)
):
    # ... existing search logic ...

    # NEW: Enrich results with citations
    if include_citations:
        results = await citation_service.enrich_with_citations(
            results=search_results,
            format=citation_format,
            db=db
        )

    # NEW: Add MCP context
    mcp_context = {
        "query": request.query,
        "citation_format": f"Cite as: {citation_format}",
        "all_verified": all(r.verified for r in results),
        "confidence_summary": _summarize_confidence(results)
    }

    return {
        "results": results,
        "mcp_context": mcp_context  # NEW: For AI agents
    }
```

### Phase 1D: New MCP Endpoints (Week 2, Days 1-2)

```python
# backend/app/api/mcp.py

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

@router.get("/citations/{document_id}/{field_name}")
async def get_field_citation(
    document_id: int,
    field_name: str,
    db: Session = Depends(get_db)
):
    """Get detailed citation for specific field (MCP tool)"""
    # ... implementation

@router.post("/search")
async def mcp_search(
    query: str,
    include_full_citations: bool = True,
    db: Session = Depends(get_db)
):
    """MCP-optimized search with pre-formatted citations"""
    # ... implementation
```

### Phase 1E: ES Indexing Update (Week 2, Day 3)

```python
# backend/app/services/elastic_service.py

async def index_document(self, document_id, ...):
    # ... existing logic ...

    # NEW: Add field_provenance for citation retrieval
    doc["field_provenance"] = []
    for field_name, field_value in extracted_fields.items():
        doc["field_provenance"].append({
            "field_name": field_name,
            "value": field_value,
            "source_text": field_metadata.get("source_text"),
            "page": field_metadata.get("page"),
            "bbox": field_metadata.get("bbox"),
            "confidence": confidence_scores.get(field_name),
            "verified": field_metadata.get("verified", False)
        })
```

---

## Testing Strategy

### Test 1: MCP Tool Simulation

```python
# Test as if Claude MCP is calling
response = requests.post("/api/mcp/search", json={
    "query": "invoices over $1000",
    "include_full_citations": True
})

assert "citations" in response.json()["results"][0]
assert "citation_string" in response.json()["results"][0]["citations"]["invoice_total"]
```

### Test 2: LLM Context Quality

```python
# Ensure LLM gets enough context to cite properly
result = response.json()["results"][0]
citation = result["citations"]["invoice_total"]

assert citation["source_text"]  # Must have source text
assert citation["page"]  # Must have page number
assert citation["confidence"] > 0  # Must have confidence
```

### Test 3: Citation Format Variations

```python
# Test different formats for different use cases
short = get_citation(format="short")
assert short == "[Invoice-001.pdf, p.2]"

long = get_citation(format="long")
assert "Total Amount Due: $1,500.00" in long

academic = get_citation(format="academic")
assert "verified Nov 15 2024" in academic
```

---

## MCP Server Configuration

When deploying as MCP server:

```json
// mcp_config.json
{
  "tools": [
    {
      "name": "search_documents",
      "description": "Search documents with full citation support. Always returns source attribution for LLM citation.",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"},
          "include_citations": {"type": "boolean", "default": true},
          "citation_format": {"type": "string", "enum": ["short", "long", "academic"]}
        }
      }
    },
    {
      "name": "get_field_provenance",
      "description": "Get detailed source information for a specific extracted field",
      "input_schema": {
        "type": "object",
        "properties": {
          "document_id": {"type": "integer"},
          "field_name": {"type": "string"}
        }
      }
    }
  ]
}
```

---

## Example MCP Usage

### Claude Desktop using Paperbase MCP

```
User: "What were our top invoices last quarter?"

Claude → MCP Tool Call:
{
  "tool": "search_documents",
  "arguments": {
    "query": "invoices Q4 2024 sorted by total descending",
    "include_citations": true,
    "citation_format": "long"
  }
}

MCP Response:
{
  "results": [
    {
      "filename": "Invoice-042.pdf",
      "invoice_total": "5200.00",
      "citations": {
        "invoice_total": {
          "source_text": "Total Amount Due: $5,200.00",
          "page": 2,
          "citation_string": "Invoice-042.pdf, Page 2: \"Total Amount Due: $5,200.00\""
        }
      }
    }
  ]
}

Claude → User:
"Your top invoices last quarter were:
1. $5,200.00 from Beta Inc [Invoice-042.pdf, Page 2: "Total Amount Due: $5,200.00"]
2. $3,800.00 from Acme Corp [Invoice-038.pdf, Page 1]
3. $2,900.00 from Gamma LLC [Invoice-051.pdf, Page 2]

All values verified by users."
```

---

## Benefits for MCP

1. **Trust**: LLMs can properly cite sources, increasing user trust
2. **Transparency**: Users see exactly where data came from
3. **Verification**: LLMs know which data is verified vs low-confidence
4. **Context**: Source text helps LLMs understand data semantics
5. **Debugging**: When LLM makes errors, citations help trace back

---

## Next Steps

1. Implement backend schema changes (document_blocks + source_text)
2. Update extraction logic to populate source_text
3. Add MCP endpoints with citation support
4. Test with sample MCP client
5. Document MCP tools in README

**Estimated Timeline**: 2 weeks for Phase 1 with full MCP support
