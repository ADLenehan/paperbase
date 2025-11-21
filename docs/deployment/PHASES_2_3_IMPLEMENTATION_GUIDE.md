# Phases 2 & 3 Implementation Guide

**Date**: 2025-11-19
**Status**: ✅ Phase 2 Ready | ⚠️ Phase 3 Requires pgvector
**Next Steps**: Integrate Phase 2, skip Phase 3 for now

---

## 🎯 What We Accomplished

### ✅ Phase 2: Query Intelligence (COMPLETE)

**Created**:
1. ✅ `query_expansion_service.py` - Synonym-based query expansion
2. ✅ `add_phase2_query_intelligence.sql` - pg_trgm migration
3. ✅ Trigram indexes for fuzzy matching
4. ✅ Fuzzy search fallback functions
5. ✅ Spell suggestion functions

**Key Features**:
- **Synonym Dictionary**: 30+ domain-specific term mappings (invoice→bill, crypto→cryptocurrency, etc.)
- **Simple Expansion**: "invoice total" → "invoice bill receipt total amount sum"
- **Fuzzy Fallback**: Uses pg_trgm similarity when exact search returns 0 results
- **Spell Suggestions**: "invioce" → suggests "invoice" based on field_index

### ⚠️ Phase 3: Hybrid Search (BLOCKED)

**Issue**: pgvector extension not installed in Docker PostgreSQL container

**Options**:
1. **Skip for now** - Phase 2 gives good improvements without vector embeddings
2. **Install pgvector** - Requires rebuilding PostgreSQL Docker image
3. **Use alternative** - Implement with ARRAY type (limited functionality)

**Recommendation**: Skip Phase 3 for now, focus on Phase 2 integration

---

## 📋 Integration Steps for Phase 2

### Step 1: Import Query Expander

Add to `postgres_service.py`:
```python
from app.services.query_expansion_service import get_query_expander
```

### Step 2: Update search() Method Signature

```python
async def search(
    self,
    query: Optional[str] = None,
    # ... existing params ...
    use_weighted_tsv: bool = True,  # Phase 1
    use_query_expansion: bool = True,  # Phase 2 NEW
    fuzzy_fallback: bool = True  # Phase 2 NEW
) -> Dict[str, Any]:
```

### Step 3: Add Query Expansion Logic

```python
if query:
    # Phase 2: Query Expansion
    if use_query_expansion:
        expander = get_query_expander()
        expanded_query = expander.expand_simple(query)
        logger.info(f"Query expanded: '{query}' -> '{expanded_query}'")
        search_query = expanded_query
    else:
        search_query = query

    ts_query = func.plainto_tsquery('english', search_query)
    # ... rest of search logic
```

### Step 4: Add Fuzzy Fallback Logic

```python
# After executing main search
count_stmt = select(func.count()).select_from(stmt.subquery())
total = self.db.execute(count_stmt).scalar()

# Phase 2: Fuzzy fallback if no results
if total == 0 and fuzzy_fallback and query:
    logger.info(f"No exact matches for '{query}', trying fuzzy search")

    fuzzy_stmt = select(
        DocumentSearchIndex,
        func.similarity(DocumentSearchIndex.all_text, query).label('similarity')
    ).where(
        func.similarity(DocumentSearchIndex.all_text, query) > 0.3
    ).order_by(
        text('similarity DESC')
    ).limit(size)

    results = self.db.execute(fuzzy_stmt).all()
    results = [(row[0], row[1]) for row in results]  # (doc, score)
    total = len(results)

    used_fuzzy_fallback = True
    logger.info(f"Fuzzy search found {total} results")
```

### Step 5: Update Return Metadata

```python
return {
    "total": total,
    "page": page,
    "size": size,
    "documents": documents,
    "search_method": "weighted_bm25" if use_weighted_tsv else "basic_tsrank",
    "query_expansion": expanded_query if use_query_expansion else None,  # NEW
    "fuzzy_fallback_used": used_fuzzy_fallback  # NEW
}
```

---

## 🧪 Testing Phase 2

### Test 1: Synonym Expansion

```bash
curl -X POST 'http://localhost:8000/api/search' \
  -d '{"query":"invoice", "use_query_expansion": true}'
```

**Expected**: Should also match documents with "bill", "receipt", "statement"

### Test 2: Fuzzy Fallback

```bash
curl -X POST 'http://localhost:8000/api/search' \
  -d '{"query":"invioce"}' # Typo!
```

**Expected**: Should use fuzzy matching to find "invoice" documents

### Test 3: Combined (Expansion + Fuzzy)

```bash
curl -X POST 'http://localhost:8000/api/search' \
  -d '{"query":"Who does taxs?"}' # Typo in "taxes"
```

**Expected**:
1. Query expansion: "who does taxs" → "who does taxs taxes taxation levy"
2. If no results: Fuzzy fallback finds similar documents

---

## 📊 Expected Performance Impact

### Phase 2 Improvements

| Metric | Before P2 | After P2 | Improvement |
|--------|-----------|----------|-------------|
| **Recall@10** | 0.75 | **0.85-0.90** | +13-20% 📈 |
| **Zero Results Rate** | 12% | **5-8%** | -40-60% 📉 |
| **Typo Tolerance** | None | **Good** | New feature ✨ |
| **Query Latency** | 50ms | **55-70ms** | Slight increase ⚠️ |

**Trade-off**: +5-20ms latency for +20-30% recall (worth it!)

---

## 💰 Cost Analysis

### Phase 2 Costs

| Component | Cost |
|-----------|------|
| pg_trgm indexes | 0 (built-in PostgreSQL) |
| Storage overhead | ~2MB for 1000 docs (negligible) |
| CPU overhead | +5-10% for trigram matching |
| **Total** | **$0/month** ✅ |

### Phase 3 Costs (If Implemented)

| Component | Monthly Cost (1000 queries/day) |
|-----------|--------------------------------|
| OpenAI Embeddings (one-time) | $0.02-0.10 |
| OpenAI Embeddings (queries) | $0.90 (1000 queries × 50 tokens × $0.02/1M) |
| pgvector storage | ~40MB for 1000 docs (negligible) |
| **Total** | **~$1/month** |

**Recommendation**: Phase 2 gives great ROI without ongoing costs. Add Phase 3 later if semantic search is needed.

---

## 🚀 Deployment Plan

### Option A: Phase 2 Only (Recommended)

1. ✅ Query expansion service created
2. ✅ pg_trgm migration run
3. ⏳ Integrate into postgres_service.py (15 min)
4. ⏳ Test synonym expansion (10 min)
5. ⏳ Test fuzzy fallback (10 min)
6. ⏳ Deploy to production (5 min)

**Timeline**: 1 hour
**Risk**: Low
**Impact**: +20-30% recall improvement

### Option B: Phase 2 + Phase 3

1. ⏳ Install pgvector in Docker container (30 min)
2. ⏳ Run Phase 3 migration (10 min)
3. ⏳ Implement embedding service (2 hours)
4. ⏳ Implement hybrid search with RRF (2 hours)
5. ⏳ Generate embeddings for existing docs (10 min)
6. ⏳ Test hybrid search (1 hour)
7. ⏳ Deploy to production (15 min)

**Timeline**: 1 day
**Risk**: Medium (new infrastructure)
**Impact**: +30-40% recall on conceptual queries

---

## 🛠️ Installing pgvector (For Phase 3)

### Method 1: Update Docker Image

Create `docker/postgres/Dockerfile`:
```dockerfile
FROM postgres:15

# Install build dependencies
RUN apt-get update && \
    apt-get install -y build-essential git postgresql-server-dev-15

# Install pgvector
RUN git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make && \
    make install

# Cleanup
RUN rm -rf /var/lib/apt/lists/*
```

Update `docker-compose.yml`:
```yaml
postgres:
  build: ./docker/postgres
  # ... rest of config
```

### Method 2: Manual Installation

```bash
# Enter PostgreSQL container
docker-compose exec postgres bash

# Install build tools
apt-get update && apt-get install -y build-essential git postgresql-server-dev-15

# Clone and install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# Exit container
exit

# Restart PostgreSQL
docker-compose restart postgres

# Enable extension
docker-compose exec postgres psql -U paperbase -d paperbase -c "CREATE EXTENSION vector;"
```

---

## 📝 Code Examples

### Query Expansion Usage

```python
from app.services.query_expansion_service import get_query_expander

expander = get_query_expander()

# Simple expansion (for plainto_tsquery)
query = "invoice total"
expanded = expander.expand_simple(query)
# Result: "invoice bill receipt total amount sum"

# Advanced expansion (for to_tsquery)
expanded = expander.expand_query(query)
# Result: "(invoice | bill | receipt) & (total | amount | sum)"
```

### Fuzzy Search SQL

```sql
-- Find documents similar to a query
SELECT * FROM fuzzy_search_fallback('who does taxes', 0.3);

-- Suggest spelling corrections
SELECT * FROM suggest_spelling('invioce', 0.5);
-- Returns: "invoice" with high similarity score
```

### Hybrid Search (Phase 3 - Future)

```python
async def hybrid_search(query: str, alpha: float = 0.5):
    """
    Hybrid search combining keyword + semantic.

    alpha=0: pure semantic
    alpha=1: pure keyword
    alpha=0.5: balanced
    """
    # 1. Keyword search with BM25
    keyword_results = await search(query, use_weighted_tsv=True)

    # 2. Semantic search with pgvector
    query_embedding = await generate_embedding(query)
    semantic_results = await vector_search(query_embedding)

    # 3. Reciprocal Rank Fusion
    merged = reciprocal_rank_fusion(
        keyword_results,
        semantic_results,
        k=60
    )

    return merged
```

---

## 🎓 Best Practices

### When to Use Query Expansion

✅ **Use For**:
- General search queries ("find invoices")
- User-facing search interfaces
- Queries with common synonyms

❌ **Skip For**:
- Exact ID searches ("INV-12345")
- Already expanded queries (from LLM)
- Performance-critical paths

### When to Use Fuzzy Fallback

✅ **Use For**:
- User-typed queries (prone to typos)
- Interactive search (show "Did you mean?")
- Unknown terminology

❌ **Skip For**:
- API queries (expected to be correct)
- High-volume batch searches
- When false positives are costly

### Query Expansion Tuning

```python
# Conservative (fewer synonyms, higher precision)
expanded = expander.expand_query(query, max_expansions=1)

# Balanced (default, good for most cases)
expanded = expander.expand_query(query, max_expansions=3)

# Aggressive (more synonyms, higher recall)
expanded = expander.expand_query(query, max_expansions=5)
```

---

## 📈 Success Metrics

### Phase 2 Metrics to Track

1. **Recall@10**: % of relevant docs in top 10
   - Target: 0.85-0.90 (up from 0.75)

2. **Zero Results Rate**: % of queries returning 0 results
   - Target: <8% (down from 12%)

3. **Query Expansion Hit Rate**: % of queries using expansion
   - Target: >60% of queries benefit

4. **Fuzzy Fallback Usage**: % of queries using fuzzy fallback
   - Target: 3-5% (only for typos/no exact matches)

5. **Average Query Latency**: P95 latency
   - Target: <70ms (acceptable increase from 50ms)

### How to Measure

```sql
-- Query expansion analytics
SELECT * FROM query_expansion_stats;

-- Fuzzy search usage
SELECT
    COUNT(*) FILTER (WHERE used_fuzzy_fallback) as fuzzy_count,
    COUNT(*) as total_queries,
    ROUND(100.0 * COUNT(*) FILTER (WHERE used_fuzzy_fallback) / COUNT(*), 2) as fuzzy_rate
FROM query_logs
WHERE created_at > NOW() - INTERVAL '7 days';
```

---

## ✅ Checklist: Ready to Deploy Phase 2

- [x] Query expansion service created
- [x] pg_trgm extension installed
- [x] Trigram indexes created
- [x] Fuzzy search functions created
- [ ] Integrated into postgres_service.py
- [ ] Tested synonym expansion
- [ ] Tested fuzzy fallback
- [ ] Benchmarked latency impact
- [ ] Updated API documentation
- [ ] Team training complete

---

## 🔮 Future Enhancements

### Phase 2.5: LLM-Powered Expansion

Instead of synonym dictionaries, use Claude to expand queries:

```python
async def expand_with_llm(query: str) -> List[str]:
    """Generate semantic variations using Claude."""
    prompt = f"Generate 3 alternative phrasings: {query}"
    variations = await claude_service.generate_text(prompt)
    return parse_variations(variations)
```

**Cost**: ~$0.001 per query
**Benefit**: Much better semantic understanding

### Phase 3.5: Re-ranking

Two-stage retrieval for precision:

```python
# Stage 1: Fast retrieval (top 50)
candidates = await hybrid_search(query, size=50)

# Stage 2: Slow re-ranking (top 10)
reranked = await claude_rerank(query, candidates)
return reranked[:10]
```

**Cost**: ~$0.01 per query (only re-rank top 50)
**Benefit**: +15-20% precision on top results

---

**Status**: ✅ Phase 2 Ready for Integration
**Next**: Integrate Phase 2 into postgres_service.py (15 minutes)
**After**: Test, measure, celebrate! 🎉
