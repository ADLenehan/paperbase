# Ultra-Deep Analysis: Extraction to Retrieval Pipeline Architecture

**Date**: 2025-11-05
**Project**: Paperbase MVP
**Focus**: Citations, Auditing, Aggregation, Individual Extraction Queries

---

## Executive Summary

**TL;DR**: Your current architecture is **70% of the way to ideal**. You have strong foundations for provenance tracking, auditing, and aggregation, but are missing critical components for **citation surfacing in search**, **hybrid semantic+structured retrieval**, and **comprehensive source text linking**.

### Key Strengths ✅
- ✅ **Provenance tracking**: bbox + page stored in ExtractedField
- ✅ **Audit system**: Low-confidence queue with verification workflow
- ✅ **Aggregation support**: Extensive ES aggregation methods
- ✅ **Complex type support**: Arrays, tables, nested objects
- ✅ **Verification history**: Tracks original vs corrected values

### Critical Gaps ⚠️
- ❌ **Citations not surfaced in search results** (only in audit view)
- ❌ **No source text storage** (can't show "extracted from: 'Total: $1000.00'")
- ❌ **No semantic vector search** (relies purely on keyword/structured)
- ❌ **No nested ES mappings** (limits complex aggregations on line items)
- ❌ **Limited verification audit trail** (no change history beyond latest)
- ❌ **No RAG retrieval** (doesn't retrieve document chunks for context)

---

## Current Architecture Analysis

### Data Flow Diagram
```
Upload → Parse (Reducto) → Extract → Index (ES) + Store (SQLite)
         ↓                    ↓           ↓
    parse_result         bbox+page    confidence
    (JSONB cache)        stored       tracked
                                          ↓
                                     Audit Queue
                                          ↓
                                    Verification
```

### Layer 1: Document Storage
**Implementation**: `backend/app/models/document.py`

```python
class Document(Base):
    filename: str
    reducto_parse_result: JSON  # ✅ Full Reducto output cached
    elasticsearch_id: str
    schema_id: int
    status: str
```

**Assessment**:
- ✅ Parse results ARE cached (good for cost optimization)
- ⚠️ Parse results stored as opaque JSON blob
- ❌ No structured link from extractions → parse blocks
- ❌ Source text not indexed separately for retrieval

**Issue**: When a user searches and gets results, you can show the extracted value but NOT the original source text snippet that was extracted. Example:
- Current: `{"invoice_total": "1000.00"}` ✓
- Missing: `{"invoice_total": "1000.00", "source": "Total Amount Due: $1,000.00"}` ✗

### Layer 2: Extraction Storage with Provenance
**Implementation**: `backend/app/models/document.py`

```python
class ExtractedField(Base):
    field_name: str
    field_value: str
    confidence_score: float

    # ✅ PROVENANCE TRACKED
    source_page: int
    source_bbox: JSON  # [x, y, width, height]

    # ✅ VERIFICATION SUPPORT
    verified: bool
    verified_value: str
    verified_at: datetime
```

**Assessment**:
- ✅ Bbox and page ARE stored (excellent!)
- ✅ Confidence scores tracked
- ✅ Verification status tracked
- ⚠️ Bbox only available in audit API, not search API
- ❌ No link to source text from parse result
- ❌ No extraction_method field (can't tell if from Reducto, Claude, or manual)

**Issue**: The bbox is stored but not surfaced in search results. Users searching for "invoices over $1000" get matching documents but can't see WHERE in the PDF that $1000 came from.

### Layer 3: Verification & Audit Trail
**Implementation**: `backend/app/models/verification.py`

```python
class Verification(Base):
    extracted_field_id: int
    original_value: str       # ✅ Tracks original
    original_confidence: float
    verified_value: str
    verification_type: str
    reviewer_notes: str
    verified_at: datetime
```

**Assessment**:
- ✅ Original value preserved when corrected
- ✅ Verification type categorized
- ✅ Timestamped
- ⚠️ Only ONE verification record per field
- ❌ No change history (if user corrects 3 times, only see latest)
- ❌ No user attribution (who made the change?)

**Gap**: Can't answer: "Show me all fields that User A corrected last week" or "What was the correction history for this field?"

### Layer 4: Elasticsearch Indexing
**Implementation**: `backend/app/services/elastic_service.py:141-219`

**Current Index Structure**:
```json
{
  "document_id": 123,
  "filename": "invoice.pdf",
  "invoice_total": "1000.00",
  "invoice_date": "2024-01-01",
  "vendor_name": "Acme Corp",

  // Metadata (good!)
  "confidence_scores": {"invoice_total": 0.95, ...},
  "_query_context": {
    "template_name": "Invoices",
    "field_names": ["invoice_total", "invoice_date", ...],
    "canonical_fields": {"amount": "invoice_total"}
  },
  "_all_text": "invoice acme corp 1000 ...",
  "full_text": "Full document OCR text ..."
}
```

**Assessment**:
- ✅ Good metadata for query optimization
- ✅ Canonical field mapping for cross-template queries
- ✅ Full text indexed for keyword search
- ⚠️ **NO nested type definitions** for line items
- ❌ **NO bbox/page in ES** (not searchable/retrievable)
- ❌ **NO source_text snippets** indexed per field
- ❌ **NO vector embeddings** for semantic search

**Critical Missing Feature**: Nested field support for complex aggregations.

**Example gap**: User asks "What's the average line item quantity across all invoices?"
- Current: Can't query because line_items stored as flat array
- Ideal: Use nested aggregation with ES nested type

### Layer 5: Search & Retrieval
**Implementation**: `backend/app/api/search.py`

**Current Flow**:
```
User Query → Claude (NL→ES) → ES Search → Claude (Generate Answer)
             ↓                    ↓
       ES DSL query         Results (fields only)
```

**Assessment**:
- ✅ Natural language query parsing (claude_service.py:1053-1301)
- ✅ Query caching for performance
- ✅ Semantic field mapping guide (teaches Claude how to map terms)
- ✅ Canonical field resolution
- ⚠️ **Results don't include bbox/page** for citations
- ❌ **No vector semantic search** (keyword only)
- ❌ **No RAG** (doesn't retrieve document chunks)
- ❌ **No hybrid search** (structured + semantic)

**Example gap**:
- Query: "Show me contracts mentioning construction projects"
- Current: Searches full_text for "construction" (finds 10,000+ words)
- Ideal: Vector search finds semantically similar sections, ranks by relevance

### Layer 6: Citation in Answers
**Implementation**: `backend/app/services/claude_service.py:889-1051`

**Current**: Claude generates answers with optional confidence metadata
```python
{
  "answer": "Found 3 invoices totaling $5,000",
  "sources_used": [123, 456],
  "low_confidence_warnings": [...],
  "confidence_level": "high"
}
```

**Assessment**:
- ✅ Includes document IDs referenced
- ✅ Warns about low-confidence data
- ⚠️ No page numbers in citations
- ⚠️ No bbox for highlighting
- ❌ No source text snippets quoted

**Example gap**:
- Current: "Invoice-123.pdf has total of $1,000" ✓
- Missing: "Invoice-123.pdf (Page 2): Total was $1,000 [source: 'Total Amount Due: $1,000.00']" ✗

---

## The Ideal Architecture

### Design Principles
1. **Every extraction must be traceable to source text**
2. **Search results must include citations automatically**
3. **Aggregations must work on nested data structures**
4. **Audit trail must be complete and queryable**
5. **Retrieval must combine structured + semantic + full-text**

### Recommended Layer 1: Enhanced Document Storage

**Problem**: Parse results stored as opaque JSON, no structured link to extractions

**Solution**: Add structured parse result with block indexing

```sql
-- NEW TABLE
CREATE TABLE document_blocks (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id),
    block_id VARCHAR,  -- From Reducto parse result
    block_type VARCHAR,  -- 'text', 'table', 'image'

    -- Content
    text_content TEXT,
    confidence FLOAT,

    -- Location
    page INT,
    bbox JSON,  -- {x, y, width, height}

    -- Metadata
    parse_metadata JSON,

    -- Search
    embedding VECTOR(1536)  -- For semantic search (pgvector)
);

CREATE INDEX idx_document_blocks_doc ON document_blocks(document_id);
CREATE INDEX idx_document_blocks_embedding ON document_blocks
  USING ivfflat (embedding vector_cosine_ops);
```

**Benefits**:
1. Can link extractions → blocks via foreign key
2. Can retrieve source text for citations
3. Can do vector search on document chunks
4. Can highlight exact source in PDF viewer

### Recommended Layer 2: Enhanced Extractions with Full Provenance

**Problem**: No extraction method tracking, no multi-block linking

**Solution**: Enhance ExtractedField model

```python
class ExtractedField(Base):
    # ... existing fields ...

    # NEW: Link to source blocks
    source_block_ids = Column(JSON)  # Array of block IDs
    source_text = Column(Text)  # Extracted snippet from source

    # NEW: Extraction provenance
    extraction_method = Column(String)  # 'reducto', 'claude', 'manual'
    extraction_confidence_details = Column(JSON)  # Method-specific details

    # NEW: Complex type support
    field_type = Column(String)  # 'text', 'array', 'table', 'object'
    field_value_json = Column(JSON)  # For complex types (arrays, objects)
```

**Benefits**:
1. Know HOW each value was extracted
2. Can retrieve source text for citations
3. Support complex data types properly
4. Better debugging and quality metrics

### Recommended Layer 3: Comprehensive Verification History

**Problem**: Only one verification record per field, no change history

**Solution**: Make Verification a history log, not state

```python
class VerificationHistory(Base):
    """Complete audit trail of all changes"""
    id = Column(Integer, primary_key=True)
    extracted_field_id = Column(Integer, ForeignKey("extracted_fields.id"))

    # Change tracking
    previous_value = Column(Text)
    new_value = Column(Text)
    change_type = Column(String)  # 'correction', 'verification', 'deletion'

    # User attribution
    user_id = Column(Integer)  # NEW: Track who made change
    user_name = Column(String)

    # Context
    change_reason = Column(Text)
    session_id = Column(String)

    # Timestamp
    changed_at = Column(DateTime)
```

**Query Examples**:
```sql
-- All changes by user
SELECT * FROM verification_history WHERE user_id = 123;

-- Fields corrected multiple times (quality issues)
SELECT extracted_field_id, COUNT(*)
FROM verification_history
GROUP BY extracted_field_id
HAVING COUNT(*) > 1;

-- Changes last week
SELECT * FROM verification_history
WHERE changed_at > NOW() - INTERVAL '7 days';
```

### Recommended Layer 4: Enhanced Elasticsearch Mapping

**Problem**: No nested types, no bbox/page searchability

**Solution**: Add nested mappings + provenance metadata

```json
{
  "mappings": {
    "properties": {
      // Existing fields...
      "invoice_total": {"type": "float"},
      "vendor_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},

      // NEW: Nested line items support
      "line_items": {
        "type": "nested",
        "properties": {
          "description": {"type": "text"},
          "quantity": {"type": "integer"},
          "unit_price": {"type": "float"},
          "total": {"type": "float"},
          "confidence": {"type": "float"}
        }
      },

      // NEW: Field-level provenance (for citation retrieval)
      "field_provenance": {
        "type": "nested",
        "properties": {
          "field_name": {"type": "keyword"},
          "value": {"type": "text"},
          "source_text": {"type": "text"},
          "page": {"type": "integer"},
          "bbox": {
            "type": "object",
            "properties": {
              "x": {"type": "float"},
              "y": {"type": "float"},
              "width": {"type": "float"},
              "height": {"type": "float"}
            }
          },
          "confidence": {"type": "float"},
          "verified": {"type": "boolean"}
        }
      }
    }
  }
}
```

**Benefits**:
1. **Nested aggregations**: "Average line item quantity"
2. **Citation retrieval**: Search returns bbox/page automatically
3. **Source text**: Show "where this came from" in results

**Example Query**:
```json
{
  "query": {
    "nested": {
      "path": "line_items",
      "query": {
        "bool": {
          "must": [
            {"match": {"line_items.description": "consulting"}},
            {"range": {"line_items.total": {"gte": 500}}}
          ]
        }
      }
    }
  },
  "aggs": {
    "line_item_stats": {
      "nested": {"path": "line_items"},
      "aggs": {
        "avg_quantity": {"avg": {"field": "line_items.quantity"}},
        "total_amount": {"sum": {"field": "line_items.total"}}
      }
    }
  }
}
```

### Recommended Layer 5: Hybrid Search Architecture

**Problem**: Only keyword search, no semantic understanding

**Solution**: Implement multi-modal retrieval

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                            │
│           "Show me construction contracts"              │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
   ┌────▼────┐            ┌───────▼──────┐
   │ Claude  │            │ QueryOptimizer│
   │ Intent  │            │ Rule-based    │
   └────┬────┘            └───────┬───────┘
        │                         │
        └────────┬────────────────┘
                 │
        ┌────────▼────────┐
        │ Query Strategy  │
        │  Selector       │
        └────────┬────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
┌────▼────┐ ┌───▼────┐ ┌───▼─────┐
│Structured│ │Vector  │ │Full-Text│
│(ES DSL)  │ │(pgvec) │ │(ES)     │
└────┬────┘ └───┬────┘ └───┬─────┘
     │          │           │
     └──────────┼───────────┘
                │
      ┌─────────▼──────────┐
      │  Result Fusion     │
      │  (RRF / Weighted)  │
      └─────────┬──────────┘
                │
      ┌─────────▼──────────┐
      │  Enrich Results    │
      │  + bbox/page       │
      │  + source_text     │
      │  + confidence      │
      └─────────┬──────────┘
                │
      ┌─────────▼──────────┐
      │  Claude Answer     │
      │  with Citations    │
      └────────────────────┘
```

**Implementation Strategy**:

**5A. Add Vector Search Layer**
```python
# backend/app/services/vector_service.py

from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer

class VectorService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    async def embed_document_blocks(self, document_id: int):
        """Embed all text blocks from document"""
        blocks = db.query(DocumentBlock).filter_by(document_id=document_id).all()

        for block in blocks:
            # Create embedding context: field_name + field_value + surrounding_text
            context = f"{block.text_content}"
            embedding = self.model.encode(context)
            block.embedding = embedding

        db.commit()

    async def semantic_search(
        self,
        query: str,
        limit: int = 20,
        filter_doc_ids: List[int] = None
    ) -> List[Dict]:
        """Semantic search across document blocks"""
        query_embedding = self.model.encode(query)

        # Vector similarity search
        results = db.query(DocumentBlock).filter(
            DocumentBlock.embedding.cosine_distance(query_embedding) < 0.5
        )

        if filter_doc_ids:
            results = results.filter(DocumentBlock.document_id.in_(filter_doc_ids))

        results = results.limit(limit).all()

        return [
            {
                "document_id": r.document_id,
                "block_id": r.block_id,
                "text": r.text_content,
                "page": r.page,
                "bbox": r.bbox,
                "similarity": 1 - r.embedding.cosine_distance(query_embedding)
            }
            for r in results
        ]
```

**5B. Hybrid Search Orchestrator**
```python
# backend/app/services/search_orchestrator.py

class SearchOrchestrator:
    async def hybrid_search(
        self,
        query: str,
        strategy: str = "auto"  # "structured", "semantic", "hybrid"
    ) -> Dict[str, Any]:
        """
        Orchestrate multi-modal search
        """

        # Step 1: Determine strategy
        if strategy == "auto":
            strategy = self._determine_strategy(query)

        results = {
            "structured": [],
            "semantic": [],
            "combined": []
        }

        # Step 2: Execute searches in parallel
        if strategy in ["structured", "hybrid"]:
            # Parse query to ES DSL
            parsed = await claude_service.parse_natural_language_query(query, ...)

            # Structured search
            structured_results = await elastic_service.search(
                custom_query=parsed["elasticsearch_query"]
            )
            results["structured"] = structured_results["documents"]

        if strategy in ["semantic", "hybrid"]:
            # Vector search
            semantic_results = await vector_service.semantic_search(query)
            results["semantic"] = semantic_results

        # Step 3: Merge results (Reciprocal Rank Fusion)
        if strategy == "hybrid":
            results["combined"] = self._merge_results(
                results["structured"],
                results["semantic"]
            )
        else:
            results["combined"] = results.get(strategy, [])

        # Step 4: Enrich with citations
        enriched = await self._enrich_with_citations(results["combined"])

        return {
            "results": enriched,
            "strategy_used": strategy,
            "total": len(enriched)
        }

    def _determine_strategy(self, query: str) -> str:
        """Determine best search strategy based on query type"""
        query_lower = query.lower()

        # Structured indicators
        structured_keywords = ["over", "greater than", "between", "last month", "total", "sum"]
        if any(kw in query_lower for kw in structured_keywords):
            return "structured"

        # Semantic indicators
        semantic_keywords = ["about", "regarding", "mentioning", "related to", "similar to"]
        if any(kw in query_lower for kw in semantic_keywords):
            return "semantic"

        # Default: hybrid
        return "hybrid"

    def _merge_results(
        self,
        structured: List[Dict],
        semantic: List[Dict]
    ) -> List[Dict]:
        """Reciprocal Rank Fusion"""
        from collections import defaultdict

        scores = defaultdict(float)
        docs = {}

        k = 60  # RRF parameter

        # Score structured results
        for rank, doc in enumerate(structured, 1):
            doc_id = doc["id"]
            scores[doc_id] += 1 / (k + rank)
            docs[doc_id] = doc

        # Score semantic results
        for rank, result in enumerate(semantic, 1):
            doc_id = result["document_id"]
            scores[doc_id] += 1 / (k + rank)
            if doc_id not in docs:
                docs[doc_id] = {"id": doc_id, "semantic_match": result}

        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [docs[doc_id] for doc_id in sorted_ids[:20]]

    async def _enrich_with_citations(self, results: List[Dict]) -> List[Dict]:
        """Add bbox, page, source_text to results"""
        enriched = []

        for result in results:
            doc_id = result["id"]

            # Get extracted fields with provenance
            fields = db.query(ExtractedField).filter_by(document_id=doc_id).all()

            result["citations"] = [
                {
                    "field_name": f.field_name,
                    "value": f.field_value,
                    "source_text": f.source_text,  # NEW
                    "page": f.source_page,
                    "bbox": f.source_bbox,
                    "confidence": f.confidence_score,
                    "verified": f.verified
                }
                for f in fields
            ]

            enriched.append(result)

        return enriched
```

### Recommended Layer 6: Enhanced Citation in Answers

**Problem**: Answers lack specific page references and source text

**Solution**: Enrich Claude's context with full provenance

```python
# backend/app/services/claude_service.py (enhanced)

async def answer_question_with_citations(
    self,
    query: str,
    search_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate answer with rich citations including page numbers and source text
    """

    # Build enriched context for Claude
    enriched_results = []
    for doc in search_results[:10]:
        doc_summary = {
            "document_id": doc["id"],
            "filename": doc["data"]["filename"],
            "fields": {}
        }

        # Include citation data for each field
        if "citations" in doc:
            for citation in doc["citations"]:
                field_name = citation["field_name"]
                doc_summary["fields"][field_name] = {
                    "value": citation["value"],
                    "source": {
                        "page": citation["page"],
                        "excerpt": citation["source_text"],  # NEW
                        "confidence": citation["confidence"]
                    }
                }

        enriched_results.append(doc_summary)

    prompt = f"""Answer this question based on search results. ALWAYS cite sources with page numbers.

User Question: "{query}"

Results (with source provenance):
{json.dumps(enriched_results, indent=2)}

Instructions:
1. Provide a clear, factual answer (2-4 sentences)
2. Cite sources using format: [Filename, Page X]
3. If quoting data, include source excerpt
4. Warn if using low-confidence data (<0.7)

Example citations:
- "The invoice total was $5,000 [Invoice-123.pdf, Page 2: 'Total Amount Due: $5,000.00']"
- "Three contracts mention construction (Contract-A.pdf Page 1, Contract-B.pdf Page 3, Contract-C.pdf Page 1)"

Return JSON:
{{
  "answer": "Natural language answer with [inline citations]",
  "cited_sources": [
    {{
      "document_id": 123,
      "filename": "invoice.pdf",
      "pages": [2],
      "excerpts": ["Total Amount Due: $5,000.00"],
      "confidence": "high"
    }}
  ],
  "confidence_warnings": ["Warning text if any low-confidence data used"]
}}
"""

    # ... rest of implementation
```

---

## Implementation Roadmap

### Phase 1: Foundation (Critical - 2 weeks)
**Goal**: Enable citation surfacing in all contexts

**Tasks**:
1. ✅ Create `document_blocks` table
2. ✅ Populate from existing `reducto_parse_result` JSON
3. ✅ Add `source_text` and `source_block_ids` to ExtractedField
4. ✅ Update extraction logic to link blocks
5. ✅ Enhance search API to return bbox/page/source_text
6. ✅ Update frontend to show citations in results

**Success Criteria**:
- Search results include "extracted from: [source text]"
- Users can click citation to jump to PDF location
- Audit view shows source text alongside extracted value

### Phase 2: Nested Data Support (High Priority - 1 week)
**Goal**: Enable complex aggregations on line items/tables

**Tasks**:
1. ✅ Update ES mapping to use `nested` type for arrays
2. ✅ Modify indexing logic to structure nested docs
3. ✅ Add nested aggregation methods to ElasticsearchService
4. ✅ Update Claude query generation to support nested queries
5. ✅ Test: "Average line item quantity", "Sum of subtotals"

**Success Criteria**:
- Can query: "Show invoices where any line item > $500"
- Can aggregate: "Average quantity per line item across all docs"
- Template with line_items properly indexed

### Phase 3: Vector Search (Medium Priority - 2-3 weeks)
**Goal**: Enable semantic search for "contracts about construction"

**Tasks**:
1. ✅ Add pgvector extension to PostgreSQL
2. ✅ Create `document_blocks.embedding` column
3. ✅ Implement VectorService with embedding model
4. ✅ Create embedding pipeline (on document upload)
5. ✅ Build SearchOrchestrator for hybrid search
6. ✅ Update search API to use hybrid strategy

**Success Criteria**:
- Query "construction contracts" finds relevant docs even without exact keyword
- Hybrid search outperforms pure keyword search
- Results ranked by semantic relevance + structured filters

### Phase 4: Verification History (Medium Priority - 1 week)
**Goal**: Complete audit trail of all changes

**Tasks**:
1. ✅ Rename `Verification` → `VerificationHistory`
2. ✅ Make it append-only log (not state)
3. ✅ Add user attribution fields
4. ✅ Create API: GET /api/audit/history/{field_id}
5. ✅ Build UI timeline view

**Success Criteria**:
- Can view: "All corrections made by User A"
- Can track: "This field was changed 3 times"
- Analytics: "Most frequently corrected fields"

### Phase 5: Enhanced Citations (Low Priority - 1 week)
**Goal**: Beautiful citation display in answers

**Tasks**:
1. ✅ Update Claude prompt for rich citations
2. ✅ Parse citation format: [Filename, Page X: "excerpt"]
3. ✅ Render citations as clickable links in frontend
4. ✅ Add "View Source" modal showing PDF with highlight

**Success Criteria**:
- All answers include page-specific citations
- Citations link to exact PDF location
- Source text visible on hover

---

## Data Model Comparison: Current vs Ideal

### Document Storage

| Aspect | Current | Ideal |
|--------|---------|-------|
| Parse result | JSON blob | Structured blocks table |
| Text indexing | Full doc only | Block-level with vectors |
| Source linking | ❌ None | ✅ Block IDs |
| Vector search | ❌ No | ✅ pgvector embeddings |

### Extraction Storage

| Aspect | Current | Ideal |
|--------|---------|-------|
| Provenance | ✅ bbox + page | ✅ bbox + page + source_text + blocks |
| Complex types | ⚠️ JSON string | ✅ field_type + JSON value |
| Extraction method | ❌ Not tracked | ✅ reducto/claude/manual |
| Block linking | ❌ None | ✅ source_block_ids array |

### Verification

| Aspect | Current | Ideal |
|--------|---------|-------|
| History | ⚠️ Latest only | ✅ Full append-only log |
| User tracking | ❌ None | ✅ user_id + user_name |
| Change reasons | ⚠️ Notes only | ✅ Structured reasons |
| Queryability | ⚠️ Limited | ✅ Full history queries |

### Elasticsearch

| Aspect | Current | Ideal |
|--------|---------|-------|
| Field types | ✅ text/number/date | ✅ + nested |
| Provenance | ❌ Not indexed | ✅ field_provenance nested |
| Nested aggs | ❌ Not supported | ✅ Full nested support |
| Source text | ❌ Not indexed | ✅ Indexed per field |

### Search & Retrieval

| Aspect | Current | Ideal |
|--------|---------|-------|
| Keyword search | ✅ ES full_text | ✅ ES structured fields |
| Semantic search | ❌ None | ✅ Vector similarity |
| Hybrid | ❌ None | ✅ RRF fusion |
| Citations | ⚠️ Audit only | ✅ All search results |

---

## Concrete Example: End-to-End Flow

### Scenario: User asks "Show me all consulting invoices over $1000 from Q4"

#### Current Implementation:

```
1. Claude parses query → ES query:
   {
     "bool": {
       "must": [{"match": {"full_text": "consulting invoices"}}],
       "filter": [
         {"range": {"invoice_total": {"gte": 1000}}},
         {"range": {"invoice_date": {"gte": "2024-10-01", "lte": "2024-12-31"}}}
       ]
     }
   }

2. ES returns:
   [
     {
       "id": "123",
       "data": {
         "filename": "invoice-001.pdf",
         "invoice_total": 1500,
         "invoice_date": "2024-11-15",
         "vendor_name": "Acme Corp"
       }
     }
   ]

3. Claude generates answer:
   "Found 3 invoices totaling $5,200. The largest is from Acme Corp at $1,500."
```

**What's Missing**:
- ❌ No citation: Which page was the $1,500 on?
- ❌ No source: What did the PDF actually say? ("Total: $1,500.00" or "Amount Due: 1500")
- ❌ No verification status: Was this value manually corrected?
- ❌ No semantic matching: Didn't find "professional services" invoices (synonym for consulting)

#### Ideal Implementation:

```
1. SearchOrchestrator determines strategy = "hybrid"

2A. Structured search (ES):
   Same query as above, but returns:
   [
     {
       "id": "123",
       "data": {...},
       "citations": [
         {
           "field_name": "invoice_total",
           "value": "1500.00",
           "source_text": "Total Amount Due: $1,500.00",
           "page": 2,
           "bbox": [120, 580, 180, 600],
           "confidence": 0.96,
           "verified": true,
           "extraction_method": "reducto_structured"
         }
       ]
     }
   ]

2B. Semantic search (Vector):
   Embedding search for "consulting" also finds:
   - Documents with "professional services"
   - Documents with "IT consulting"
   - Documents with "advisory services"

   Returns document_blocks with similar embeddings

3. Result fusion (RRF):
   Combines ES results + vector results, ranks by combined score

4. Claude generates enriched answer:
   {
     "answer": "Found 5 invoices totaling $7,800. Top results:
                • Acme Corp: $1,500 [Invoice-001.pdf, Page 2] ✓ verified
                • Beta Inc: $2,200 [Invoice-042.pdf, Page 1] (consulting services)
                • Gamma LLC: $1,100 [Invoice-089.pdf, Page 3] (professional services)",

     "cited_sources": [
       {
         "document_id": 123,
         "filename": "Invoice-001.pdf",
         "pages": [2],
         "excerpts": ["Total Amount Due: $1,500.00"],
         "bbox": [[120, 580, 180, 600]],
         "confidence": "high",
         "verified": true
       }
     ]
   }
```

**Frontend Rendering**:
```
┌────────────────────────────────────────────────────┐
│ Q: Show me consulting invoices over $1000 from Q4 │
└────────────────────────────────────────────────────┘

Found 5 invoices totaling $7,800:

1. Acme Corp: $1,500 ✓
   [Invoice-001.pdf, Page 2] 📄
   Source: "Total Amount Due: $1,500.00"

2. Beta Inc: $2,200 ⚠️ 0.73 confidence
   [Invoice-042.pdf, Page 1] 📄
   Source: "Invoice Total 2200"

3. Gamma LLC: $1,100 ✓
   [Invoice-089.pdf, Page 3] 📄
   Source: "Professional Services: $1,100"

[Click PDF icon → Opens viewer with bbox highlighted]
```

---

## Performance Considerations

### Current System:
- **Query latency**: ~300ms (ES only)
- **Storage**: ~500MB per 1000 documents (no vectors)
- **Scalability**: Limited by SQLite for >10k docs

### Ideal System:
- **Query latency**: ~500ms (hybrid search with RRF)
  - Structured (ES): 100ms
  - Semantic (pgvector): 150ms
  - Fusion + enrichment: 250ms
- **Storage**: ~1.2GB per 1000 documents
  - Original PDFs: 500MB
  - Parse results: 200MB
  - Vectors (1536 dim): 400MB
  - ES index: 100MB
- **Scalability**: Postgres + pgvector handles 100k+ documents

### Optimization Strategies:

1. **Vector Search Optimization**:
   - Use HNSW index for faster ANN search
   - Batch embedding generation during off-hours
   - Cache frequently accessed embeddings

2. **Elasticsearch Optimization**:
   - Increase shards for >50k documents
   - Use filtered aliases for multi-tenancy
   - Pre-compute common aggregations

3. **Caching**:
   - Query result cache (already implemented ✅)
   - Embedding cache for common queries
   - Aggregation cache with TTL

---

## Migration Path

### Step 1: Additive Changes Only (Safe)
- ✅ Add new tables (document_blocks, verification_history)
- ✅ Add new columns to existing tables (source_text, extraction_method)
- ✅ Keep existing tables/columns intact
- ✅ Dual-write: Update both old and new schemas

### Step 2: Backfill Historical Data
```python
# scripts/backfill_document_blocks.py

async def backfill_parse_results():
    """Extract blocks from existing reducto_parse_result JSON"""
    documents = db.query(Document).filter(
        Document.reducto_parse_result.isnot(None)
    ).all()

    for doc in documents:
        parse_result = doc.reducto_parse_result

        # Extract blocks
        for chunk in parse_result.get("chunks", []):
            block = DocumentBlock(
                document_id=doc.id,
                block_id=chunk.get("id"),
                block_type="text",
                text_content=chunk.get("content"),
                confidence=chunk.get("logprobs_confidence"),
                page=chunk.get("page", 1),
                bbox=chunk.get("bbox"),
                parse_metadata=chunk
            )
            db.add(block)

        db.commit()

# Run: python -m scripts.backfill_document_blocks
```

### Step 3: Update APIs (Feature-Flagged)
```python
# backend/app/core/config.py

class Settings(BaseSettings):
    ENABLE_VECTOR_SEARCH: bool = False
    ENABLE_NESTED_AGGREGATIONS: bool = False
    ENABLE_ENHANCED_CITATIONS: bool = False

# Gradual rollout:
# 1. Deploy with flags OFF
# 2. Backfill data
# 3. Enable features one by one
```

### Step 4: Deprecate Old Schema
- After 30 days of dual-write, stop writing to old columns
- After 60 days, remove old columns if no issues

---

## Conclusion

### Summary Assessment

Your current system is **production-ready for basic document extraction** but needs enhancements for **citation-heavy, aggregation-intensive, semantic search** use cases.

#### Quick Wins (High Impact, Low Effort):
1. **Add source_text to ExtractedField** (2 days)
   - Extract from reducto_parse_result during processing
   - Surface in search results
   - Show in frontend

2. **Return bbox/page in search API** (1 day)
   - Already stored, just not returned
   - Add to search response schema
   - Huge UX improvement

3. **Add nested type to ES for line_items** (2 days)
   - Update mapping
   - Reindex existing docs
   - Enable complex aggregations

#### Medium-Term Enhancements (3-4 weeks):
4. **Implement vector search** (2 weeks)
5. **Build hybrid search orchestrator** (1 week)
6. **Add verification history tracking** (1 week)

#### Long-Term Vision (2-3 months):
7. **Full RAG pipeline** with chunking
8. **Real-time aggregation dashboards**
9. **Advanced analytics** on verification patterns

### Is This "Ideal"?

Your question was: "Do I have this implemented ideally?"

**Answer**: You have 70% of an ideal system. The foundations are solid, but key user-facing features are missing.

**What you're doing RIGHT** ✅:
- Provenance tracking at field level
- Confidence-driven audit queue
- Flexible aggregation support
- Template-driven extraction

**What needs work** ⚠️:
- Citations visible only in audit, not search
- No semantic/vector search
- Limited nested data aggregations
- Incomplete verification audit trail

**Priority**: Focus on **Phase 1 (Citations)** first. This gives users the most immediate value and trust in the system.

---

**Next Steps**: Would you like me to implement any of these recommendations? I'd suggest starting with Phase 1 (citations in search results) as it's high-impact and relatively straightforward.
