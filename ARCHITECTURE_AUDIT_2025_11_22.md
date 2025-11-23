# Architecture Audit: Elasticsearch → PostgreSQL Migration

**Date**: 2025-11-22
**Status**: 🔴 **CRITICAL INCONSISTENCIES FOUND**
**Migration Status**: Partially Complete (Code migrated, docs outdated)

## Executive Summary

Paperbase has migrated from **Elasticsearch** to **PostgreSQL** for search/indexing, but:
1. ✅ **Code is mostly migrated** (PostgresService in use)
2. ❌ **Documentation still references Elasticsearch** (CLAUDE.md, Railway docs)
3. 🐛 **2 critical bugs found** (incorrect variable references)
4. ⚠️ **Hybrid architecture** (both services exist, only PostgreSQL used)

---

## Current Architecture (ACTUAL)

### Tech Stack - REALITY
```
Frontend (React) → Backend (FastAPI) → Services (Reducto, PostgreSQL, Claude)
                                     ↓
                              PostgreSQL (metadata + full-text search)
```

**Database**: PostgreSQL 16
- Full-text search via `tsvector` and `ts_rank`
- Aggregations via SQL `GROUP BY`, `SUM`, `AVG`, `COUNT`
- Template similarity via `pg_trgm` extension
- Document indexing in `document_search_index` table

**Migration**: Completed ~Nov 2025 (see POSTGRES_MIGRATION_README.md)

### Services Breakdown

| Service | File | Status | Purpose |
|---------|------|--------|---------|
| **PostgresService** | `app/services/postgres_service.py` | ✅ **ACTIVE** | Search, indexing, aggregations |
| **ElasticsearchService** | `app/services/elastic_service.py` | ⚠️ **LEGACY** | Deprecated but still exists |
| ReductoService | `app/services/reducto_service.py` | ✅ ACTIVE | Document parsing |
| ClaudeService | `app/services/claude_service.py` | ✅ ACTIVE | NL queries, schema gen |

---

## Bugs Found 🐛

### Bug 1: rematch.py - Undefined `elastic_service`
**File**: [`backend/app/api/rematch.py:77`](backend/app/api/rematch.py#L77)

```python
# Line 52: Correct initialization
postgres_service = PostgresService(db)

# Line 77: BUG - references non-existent elastic_service
match_result = await hybrid_match_document(
    document=doc,
    elastic_service=elastic_service,  # ❌ UNDEFINED!
    claude_service=claude_service,
    available_templates=template_data,
    db=db
)
```

**Fix**: Change `elastic_service` → `postgres_service`

**Impact**: 🔴 **CRITICAL** - Rematch endpoint will crash with `NameError`

---

### Bug 2: nl_query.py - Undefined `elastic_service`
**File**: [`backend/app/api/nl_query.py:168`](backend/app/api/nl_query.py#L168)

```python
# Line 56: Correct initialization
postgres_service = PostgresService(db)

# Line 168: BUG - references non-existent elastic_service
aggregations = await _handle_aggregation_query(
    parsed_query, elastic_service, results  # ❌ UNDEFINED!
)
```

**Fix**: Change `elastic_service` → `postgres_service`

**Impact**: 🟡 **MODERATE** - Aggregation queries will crash (but search works)

---

## Documentation Inconsistencies

### CLAUDE.md - OUTDATED

**Line 111**: Says Elasticsearch ❌
```markdown
- **Search**: Elasticsearch 8.x (open source, self-hosted)
```

**Should say**: PostgreSQL ✅
```markdown
- **Search**: PostgreSQL 16 (full-text search with tsvector)
```

**Additional Issues**:
- Line 144: "Elasticsearch handles all structured queries" - should be PostgreSQL
- Line 181-186: "Elasticsearch Clustering" section - outdated
- Line 190-196: "Elasticsearch Best Practices" - no longer relevant
- Line 476: Deployment says "Self-hosted Elasticsearch" - should be PostgreSQL
- Line 535-538: "Elasticsearch won't start" troubleshooting - remove
- Line 790: Points to Elasticsearch docs - should point to PostgreSQL docs

---

### RAILWAY_DEPLOYMENT.md - OUTDATED

**Lines 7-8**: Lists Elasticsearch as required service ❌
```markdown
2. **Frontend** (React/Vite)
3. **Elasticsearch** (search engine)  # ❌ NOT NEEDED
```

**Should say**: Only 2 services ✅
```markdown
2. **Frontend** (React/Vite)
# PostgreSQL is the only database needed
```

**Additional Issues**:
- Lines 31-36: Instructions for "Create Elasticsearch Service" - DELETE
- Line 25: `ELASTICSEARCH_URL=http://elasticsearch:9200` - DELETE
- Line 60: "Backend → Elasticsearch: Use internal URL" - DELETE

---

### docker-compose.yml - CORRECT ✅

**Current setup**: PostgreSQL only (correct!)
```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5434:5432"]
    # ✅ This is correct

  backend:
    environment:
      - DATABASE_URL=postgresql://paperbase:paperbase@postgres:5432/paperbase
      # ✅ No Elasticsearch URL - correct!
```

**Status**: ✅ **CORRECT** - No changes needed

---

## Files That Reference Elasticsearch

### Active Code (needs fixing)
1. ❌ `backend/app/api/rematch.py:77` - Bug #1
2. ❌ `backend/app/api/nl_query.py:168` - Bug #2
3. ⚠️ `backend/app/api/nl_query.py:150` - Comment says "Elasticsearch query" (misleading but harmless)

### Legacy/Migration Files (can ignore)
- `backend/migrations/migrate_es_to_postgres.py` - Migration script (keep for reference)
- `backend/fix_document_75.py` - Old utility script (can delete)
- `backend/app/services/elastic_service.py` - Legacy service file (can delete after verification)

### Documentation (needs updating)
1. ❌ `CLAUDE.md` - Multiple outdated sections
2. ❌ `RAILWAY_DEPLOYMENT.md` - Outdated deployment guide
3. ⚠️ `docs/features/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md` - Legacy feature doc (archive?)

### Exception Classes (keep for now)
- `backend/app/core/exceptions.py` - Defines `ElasticsearchError` (still referenced in comments)

---

## Verification Checklist

### Code Verification ✅
- [x] PostgresService is the primary search service
- [x] docker-compose.yml uses PostgreSQL only
- [x] backend/requirements.txt has PostgreSQL drivers
- [x] No ELASTICSEARCH_URL in active configs
- [x] PostgreSQL migrations exist and are complete

### Bugs to Fix 🐛
- [ ] Fix `rematch.py:77` - change `elastic_service` → `postgres_service`
- [ ] Fix `nl_query.py:168` - change `elastic_service` → `postgres_service`
- [ ] Test rematch endpoint after fix
- [ ] Test aggregation queries after fix

### Documentation to Update 📝
- [ ] Update CLAUDE.md Tech Stack section
- [ ] Update CLAUDE.md Architecture Pattern
- [ ] Remove Elasticsearch sections from CLAUDE.md
- [ ] Update RAILWAY_DEPLOYMENT.md (remove Elasticsearch service)
- [ ] Update Railway config if needed
- [ ] Add note about PostgreSQL migration completion

---

## Recommended Actions (Priority Order)

### 🔴 **CRITICAL** - Fix Bugs (15 min)
1. Fix `rematch.py:77` - variable name bug
2. Fix `nl_query.py:168` - variable name bug
3. Test both endpoints
4. Commit fixes

### 🟡 **HIGH** - Update Core Documentation (30 min)
1. Update CLAUDE.md:
   - Tech Stack section
   - Architecture Pattern diagram
   - Remove Elasticsearch sections
   - Add PostgreSQL details
2. Update RAILWAY_DEPLOYMENT.md:
   - Remove Elasticsearch service steps
   - Update to 2-service architecture
   - Fix environment variables

### 🟢 **MEDIUM** - Cleanup (45 min)
1. Archive legacy docs:
   - Move ELASTICSEARCH_MAPPING_IMPROVEMENTS.md to `docs/archive/`
   - Add README explaining migration
2. Delete legacy files:
   - `backend/fix_document_75.py`
   - Consider removing `elastic_service.py` (after full verification)
3. Update PROJECT_INDEX.json

### 🔵 **LOW** - Nice to Have
1. Add PostgreSQL tuning guide
2. Document full-text search capabilities
3. Add performance comparison (ES vs PG)
4. Update README.md if it exists

---

## PostgreSQL Feature Parity

### What PostgreSQL Provides ✅
- ✅ Full-text search (tsvector, ts_rank)
- ✅ Aggregations (SQL GROUP BY, SUM, AVG, COUNT, percentiles)
- ✅ Range queries (date ranges, numeric ranges)
- ✅ Fuzzy matching (pg_trgm extension)
- ✅ Template similarity (Jaccard via pg_trgm)
- ✅ Field filtering (JSONB queries)
- ✅ Nested data (JSONB with GIN indexes)

### What Was Lost (if anything) ❌
- ❌ Distributed scaling (but not needed at current scale)
- ❌ Elasticsearch-specific analyzers (replaced with PostgreSQL equivalents)

### Net Result 📊
**Better**: Simpler, single database, better for structured data, correct aggregations
**Cost**: -$50-100/month (no Elasticsearch cluster)
**Performance**: Similar for current scale (<100k docs)

---

## Migration History

**When**: ~November 2025
**Why**:
1. Fix broken aggregations (ES returned wrong totals)
2. Simplify architecture (one database vs two)
3. Better for structured document data
4. Reduce costs

**Migration Docs**:
- `POSTGRES_MIGRATION_README.md` - Main migration guide
- `backend/migrations/migrate_es_to_postgres.py` - Data migration script
- `backend/migrations/create_postgres_search_tables.py` - Table creation

**Status**: ✅ Code migration complete, ❌ Docs not updated

---

## Conclusion

**Current State**: The system is **functionally using PostgreSQL** but documentation and 2 bugs indicate incomplete migration cleanup.

**Action Required**:
1. Fix 2 critical bugs (10 min)
2. Update CLAUDE.md and RAILWAY_DEPLOYMENT.md (30 min)
3. Test deployment flows

**Risk Level**: 🟡 **MODERATE**
- System works but specific endpoints (rematch, aggregations) will crash
- Deployment docs will mislead new users
- Developers will be confused about architecture

**Next Steps**: See "Recommended Actions" above
