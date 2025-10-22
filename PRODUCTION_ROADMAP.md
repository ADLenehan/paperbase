# Production Roadmap: MCP Document Analysis Product

## Current State ✅

**What Works:**
- ✅ Document upload and processing (Reducto)
- ✅ Structured field extraction with confidence scores
- ✅ Elasticsearch indexing with full text
- ✅ Search API (keyword + natural language)
- ✅ Comprehensive aggregations (8 types)
- ✅ MCP server interface (9 tools)
- ✅ File serving (preview/download)
- ✅ Template matching and multi-template extraction

**Architecture:**
```
Upload → Parse (Reducto) → Extract Fields → Index (ES) → Search (MCP)
   ↓                          ↓                 ↓
SQLite DB              Confidence Scores    Full Text
```

---

## What's Missing for Production 🚧

### 1. **Document Content Access for LLMs** [CRITICAL]

**Problem:** LLMs can search documents but can't read the actual content.

**Current:** Search returns metadata and extracted fields, not full text.

**Needed:**
- [ ] `get_document_content` MCP tool - Returns full parsed text
- [ ] `get_document_page` MCP tool - Returns specific page content
- [ ] `get_document_section` MCP tool - Returns chunks by section/heading
- [ ] `get_document_excerpt` MCP tool - Returns text around a search match

**Example Usage:**
```python
# LLM workflow
results = mcp.search_documents("contracts expiring in 2024")
for doc in results:
    content = mcp.get_document_content(doc.id)
    analysis = llm.analyze(content)
```

**Implementation:**
- Add endpoints to `mcp_search.py`
- Retrieve from Elasticsearch `full_text` field
- Support pagination for long documents
- Return with metadata (page numbers, confidence, etc.)

---

### 2. **Semantic/Vector Search** [HIGH PRIORITY] ✅ **YOU ALREADY HAVE IT**

**Problem:** Current search is keyword-based. No semantic understanding.

**Current:** Elasticsearch BM25 + Claude query optimization

**IMPORTANT:** You're running **Elasticsearch 8.11** which has native vector search!
- ✅ `dense_vector` field type built-in
- ✅ kNN search built-in
- ✅ Hybrid search (BM25 + kNN) built-in
- ✅ No external vector DB needed!

**Actually Needed:** (2-3 hours, not days!)
- [ ] Add embedding generation (OpenAI or Cohere API)
- [ ] Update index mapping to add `dense_vector` field
- [ ] Add `vector_search()` method to ElasticsearchService
- [ ] Expose via MCP tool: `semantic_search`

**See:** `VECTOR_SEARCH_QUICKSTART.md` for complete implementation

**Corrected Cost Estimate:**
- Embeddings: ~$0.02 per 1M tokens (OpenAI) = ~$0.00004 per doc
- Storage: $0 (already included in ES)
- Per-doc cost: ~$0.0001 (one-time, 100x cheaper than I said!)
- 1000 docs: ~$0.10 total (not $5-10!)

**Time Estimate:** 2-3 hours (not 3-5 days!)

---

### 3. **Document Analysis Tools** [MEDIUM PRIORITY]

**Problem:** LLMs can find docs but can't perform common analysis tasks.

**Needed MCP Tools:**

#### a. Compare Documents
```python
@mcp_tool
def compare_documents(doc_id_1: int, doc_id_2: int) -> dict:
    """Compare two documents and return differences"""
    # Returns: common fields, differences, similarity score
```

#### b. Extract Citations
```python
@mcp_tool
def extract_citations(doc_id: int, query: str) -> list:
    """Find and extract specific passages from document"""
    # Returns: matching passages with page numbers and context
```

#### c. Summarize Document
```python
@mcp_tool
def summarize_document(doc_id: int, style: str = "brief") -> str:
    """Generate summary of document"""
    # Uses cached summaries or generates on-demand
```

#### d. Analyze Field Confidence
```python
@mcp_tool
def get_low_confidence_fields(doc_id: int, threshold: float = 0.6) -> list:
    """Get fields needing human review"""
    # Returns: fields below confidence threshold with extraction context
```

---

### 4. **Batch Operations** [MEDIUM PRIORITY]

**Problem:** Processing one document at a time is slow.

**Needed:**
- [ ] Batch upload API (100+ files)
- [ ] Background job queue (Celery or RQ)
- [ ] Progress tracking
- [ ] Webhook notifications
- [ ] MCP tool: `batch_upload_documents`
- [ ] MCP tool: `get_batch_status`

**Implementation:**
```python
# Batch upload
batch_id = mcp.batch_upload_documents(files=[...], template="Invoices")

# Poll for completion
while True:
    status = mcp.get_batch_status(batch_id)
    if status.completed:
        break
```

---

### 5. **Authentication & Security** [CRITICAL FOR PRODUCTION]

**Problem:** No authentication. Anyone can access everything.

**Needed:**
- [ ] API key authentication
- [ ] User accounts and permissions
- [ ] Rate limiting per user/key
- [ ] Audit logging
- [ ] Document access control (who can see what)

**Implementation:**
```python
# FastAPI middleware
@app.middleware("http")
async def authenticate(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    user = validate_api_key(api_key)
    request.state.user = user
    return await call_next(request)
```

**Security Checklist:**
- [ ] API key management (create, revoke, rotate)
- [ ] HTTPS only (no HTTP)
- [ ] CORS restrictions (not allow_origins=["*"])
- [ ] Rate limiting (e.g., 100 req/min per key)
- [ ] Input validation and sanitization
- [ ] SQL injection prevention (use ORM)
- [ ] File upload size limits
- [ ] Virus scanning for uploads (ClamAV)

---

### 6. **RAG (Retrieval Augmented Generation)** [HIGH VALUE]

**Problem:** LLMs hallucinate. Need to ground answers in actual documents.

**Architecture:**
```
User Question → Vector Search → Top K Chunks
                                     ↓
                              LLM with Context
                                     ↓
                              Answer + Citations
```

**MCP Tool:**
```python
@mcp_tool
def rag_query(question: str, max_chunks: int = 5) -> dict:
    """
    Answer question using document corpus as context.

    Returns:
        - answer: LLM-generated answer
        - sources: List of document chunks used
        - confidence: How well sources support answer
    """
```

**Implementation:**
1. Vector search for relevant chunks
2. Rerank by relevance
3. Pass top K chunks to LLM with prompt
4. Extract answer and citations
5. Return structured response

---

### 7. **Production Infrastructure** [CRITICAL]

#### a. Monitoring & Logging
- [ ] Structured logging (JSON format)
- [ ] Application metrics (Prometheus)
- [ ] Error tracking (Sentry)
- [ ] Performance monitoring (OpenTelemetry)
- [ ] Dashboard (Grafana)

#### b. Scalability
- [ ] PostgreSQL instead of SQLite
- [ ] Redis for caching
- [ ] Background job queue (Celery)
- [ ] CDN for file serving
- [ ] Load balancing (multiple backend instances)
- [ ] Horizontal ES scaling

#### c. Reliability
- [ ] Health checks (`/health`)
- [ ] Database backups (automated)
- [ ] File storage backups (S3)
- [ ] Circuit breakers for external APIs
- [ ] Graceful degradation
- [ ] Retry logic with exponential backoff

#### d. Cost Optimization
- [ ] Query result caching (Redis)
- [ ] Embedding caching (don't re-embed)
- [ ] Parse result caching (already done ✅)
- [ ] Batch API calls to external services
- [ ] Monitor API usage and costs

---

### 8. **Advanced Features** [NICE TO HAVE]

#### a. Multi-Language Support
- [ ] Detect document language
- [ ] Language-specific models
- [ ] Translate queries/results

#### b. OCR for Scanned Documents
- [ ] Detect if document is scanned
- [ ] Run OCR (Reducto supports this)
- [ ] Store OCR confidence

#### c. Table Extraction
- [ ] Detect tables in documents
- [ ] Extract to structured format (CSV/JSON)
- [ ] MCP tool: `extract_tables`

#### d. Entity Extraction
- [ ] NER (Named Entity Recognition)
- [ ] Link entities across documents
- [ ] Build knowledge graph

#### e. Document Versioning
- [ ] Track document updates
- [ ] Compare versions
- [ ] Rollback capability

---

## Implementation Priority

### Phase 1: MVP for LLM Analysis (2-3 weeks)
**Goal:** LLMs can search, read, and analyze documents

1. ✅ Search and aggregations (DONE)
2. **Document content access** - 2 days
   - `get_document_content` endpoint
   - `get_document_page` endpoint
   - Add to MCP config
3. **Basic RAG** - 3 days
   - Document chunking
   - Embedding generation
   - Vector search
   - RAG query tool
4. **Testing** - 2 days
   - Integration tests
   - MCP client tests
   - Load testing

### Phase 2: Production Ready (2-3 weeks)
**Goal:** Can deploy for real users

1. **Authentication** - 3 days
   - API key system
   - User management
   - Rate limiting
2. **Batch Operations** - 3 days
   - Background jobs
   - Progress tracking
   - Webhooks
3. **Monitoring** - 2 days
   - Logging
   - Metrics
   - Alerting
4. **Security Hardening** - 2 days
   - HTTPS
   - Input validation
   - Access control

### Phase 3: Scale & Optimize (2-3 weeks)
**Goal:** Handle production load

1. **Database Migration** - 2 days
   - SQLite → PostgreSQL
   - Data migration
2. **Caching Layer** - 2 days
   - Redis setup
   - Query caching
   - Session storage
3. **Performance** - 3 days
   - Query optimization
   - Index tuning
   - Load balancing
4. **Cost Optimization** - 2 days
   - Embedding caching
   - API usage monitoring

### Phase 4: Advanced Features (ongoing)
**Goal:** Competitive differentiation

- Document comparison
- Multi-language support
- Advanced analytics
- Custom integrations

---

## Minimal Viable Product (Next 48 Hours)

**Goal:** LLM can search AND read documents via MCP

### Required Changes:

#### 1. Add Document Content Endpoints (4 hours)

**File:** `backend/app/api/mcp_search.py`

```python
@router.get("/document/{document_id}/content")
async def get_document_content_mcp(document_id: int):
    """Get full document text for LLM analysis"""
    elastic_service = ElasticsearchService()
    doc = await elastic_service.get_document(document_id)

    return {
        "success": True,
        "document_id": document_id,
        "filename": doc.get("filename"),
        "content": doc.get("full_text", ""),
        "metadata": {
            "uploaded_at": doc.get("uploaded_at"),
            "template": doc.get("_query_context", {}).get("template_name"),
            "status": doc.get("status")
        }
    }

@router.get("/document/{document_id}/chunks")
async def get_document_chunks_mcp(
    document_id: int,
    page: Optional[int] = None,
    chunk_size: int = 1000
):
    """Get document in chunks for processing long documents"""
    # Implementation: Split full_text into chunks
    # Return paginated chunks with metadata
```

#### 2. Update MCP Config (1 hour)

**File:** `mcp-server-config.json`

Add tools:
- `get_document_content`
- `get_document_chunks`
- `rag_query` (basic version)

#### 3. Basic RAG Implementation (8 hours)

**New File:** `backend/app/services/rag_service.py`

```python
class RAGService:
    def __init__(self):
        self.elastic_service = ElasticsearchService()
        self.claude_service = ClaudeService()

    async def answer_question(
        self,
        question: str,
        filters: Optional[dict] = None,
        max_chunks: int = 5
    ) -> dict:
        """Answer question using document corpus"""

        # 1. Search for relevant documents
        results = await self.elastic_service.search(
            query=question,
            filters=filters,
            size=max_chunks
        )

        # 2. Build context from top results
        context_chunks = []
        for doc in results["documents"]:
            chunk = {
                "text": doc["data"].get("full_text", "")[:2000],
                "source": doc["data"]["filename"],
                "doc_id": doc["id"]
            }
            context_chunks.append(chunk)

        # 3. Build prompt
        context_text = "\n\n---\n\n".join([
            f"Source: {c['source']}\n{c['text']}"
            for c in context_chunks
        ])

        prompt = f"""Answer the following question based ONLY on the provided documents.
If the documents don't contain relevant information, say so.

Documents:
{context_text}

Question: {question}

Answer:"""

        # 4. Get answer from Claude
        answer = await self.claude_service.get_completion(prompt)

        return {
            "question": question,
            "answer": answer,
            "sources": context_chunks,
            "num_sources": len(context_chunks)
        }
```

#### 4. MCP RAG Endpoint (2 hours)

**File:** `backend/app/api/mcp_search.py`

```python
@router.post("/rag/query")
async def rag_query_mcp(request: dict):
    """Answer question using document corpus (RAG)"""
    from app.services.rag_service import RAGService

    rag_service = RAGService()
    result = await rag_service.answer_question(
        question=request["question"],
        filters=request.get("filters"),
        max_chunks=request.get("max_chunks", 5)
    )

    return {
        "success": True,
        **result
    }
```

#### 5. Testing (2 hours)

Create `test_mcp_llm_analysis.py`:
```python
def test_llm_workflow():
    # 1. Search documents
    results = search_documents("contracts")

    # 2. Get content
    content = get_document_content(results[0].id)

    # 3. RAG query
    answer = rag_query("What is the contract value?")

    assert content["content"]
    assert answer["answer"]
```

---

## Cost Analysis

### Current Costs (per 1000 documents/month)
- Reducto parsing: $50-100 (depending on doc size)
- Claude for query optimization: $5-10 (only 20-30% of queries)
- Elasticsearch hosting: $50-200 (depends on provider)
- **Total: ~$100-300/month**

### With RAG Added
- Embeddings (one-time): $5-10
- Vector storage: +$20-50/month
- RAG queries: $10-20/month (depends on usage)
- **Total: ~$135-380/month**

### At Scale (100K documents/month)
- Reducto: $5,000-10,000
- Embeddings: $500-1,000
- Claude: $500-1,000
- Infrastructure: $500-2,000
- **Total: ~$6,500-14,000/month**

---

## Success Metrics

### MVP Success
- [ ] LLM can search 1000+ documents in <500ms
- [ ] LLM can retrieve full document content
- [ ] RAG answers questions with >80% accuracy
- [ ] MCP integration works in Claude Desktop

### Production Success
- [ ] 99.9% uptime
- [ ] <200ms p95 search latency
- [ ] <2s p95 RAG query latency
- [ ] Process 1000 docs/day
- [ ] Cost per document <$0.50

---

## Next Steps

### Immediate (Do This First)
1. Implement document content endpoints ← **START HERE**
2. Add RAG service (basic version)
3. Update MCP config with new tools
4. Test with Claude Desktop

### Short Term (This Week)
1. Add authentication
2. Improve RAG with vector search
3. Add batch upload
4. Write documentation

### Medium Term (This Month)
1. Migrate to PostgreSQL
2. Add monitoring
3. Implement caching
4. Security hardening

---

## Questions to Answer

1. **Who is the target user?**
   - Developers building LLM apps?
   - End users via Claude Desktop?
   - Enterprise teams?

2. **What's the main use case?**
   - Contract analysis?
   - Research papers?
   - General documents?

3. **What's the scale?**
   - Personal use (100s of docs)?
   - Team use (1,000s of docs)?
   - Enterprise (100,000s of docs)?

4. **Business model?**
   - Open source?
   - SaaS ($X/month)?
   - API ($X per 1000 queries)?
   - Self-hosted license?

---

## Summary

**You have a solid foundation but need 3 critical additions for LLM analysis:**

1. **Document content access** - LLMs can search but can't read ← **Most important**
2. **RAG capability** - Answer questions grounded in documents
3. **Authentication** - Production security

**The 48-hour MVP:**
- Add 2 MCP tools: `get_document_content`, `rag_query`
- Basic RAG implementation
- Test end-to-end workflow

**After that, the product is usable for LLM document analysis!**

Then layer on: auth, batching, vector search, monitoring, scaling.
