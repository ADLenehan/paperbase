# Elasticsearch Mapping Migration Guide

## Migration to Optimized Mappings (v2)

This guide covers migrating from the old Elasticsearch mappings to the new optimized mappings with production-ready best practices.

---

## What Changed?

### Summary of Changes

| Change | Before | After | Impact |
|--------|--------|-------|--------|
| Dynamic mapping | `true` (default) | `strict` | Breaking: rejects unmapped fields |
| Keyword fields | No limit | `ignore_above: 256` | Non-breaking: graceful handling |
| Multi-field | text+keyword+raw | text+keyword | Storage: -30% |
| Field limits | None | 1000 max fields | Non-breaking: protection |
| Object fields | Dynamic | `enabled: false` | Non-breaking: optimization |
| Refresh interval | Default (1s) | 5s (configurable) | Performance: +20-30% bulk |

### Breaking Changes

**Only one breaking change:**
- `dynamic: strict` will **reject documents with unmapped fields**
- **Solution:** Ensure all fields are defined in schema before indexing

---

## Migration Options

### Option 1: Fresh Start (Recommended for Development)

**Best for:** Development environments, small datasets (<1000 docs)

```bash
# 1. Stop the application
docker-compose down

# 2. Delete old indices
curl -X DELETE "localhost:9200/documents"
curl -X DELETE "localhost:9200/template_signatures"

# 3. Update code (already done via git pull)

# 4. Restart application (will recreate indices with new mappings)
docker-compose up -d

# 5. Re-upload your documents
```

**Pros:**
- Clean slate
- No migration complexity
- Fastest approach

**Cons:**
- Lose existing data
- Need to re-upload documents

---

### Option 2: Reindex with Alias Swap (Recommended for Production)

**Best for:** Production environments, preserving data

#### Step 1: Backup Current Index

```bash
# Create snapshot repository (if not exists)
curl -X PUT "localhost:9200/_snapshot/backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/usr/share/elasticsearch/backup"
  }
}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/backup/pre-migration-$(date +%Y%m%d)" -H 'Content-Type: application/json' -d'
{
  "indices": "documents,template_signatures",
  "ignore_unavailable": true,
  "include_global_state": false
}'
```

#### Step 2: Create New Indices

```python
# Run this script to create new indices with v2 mappings
# File: scripts/create_v2_indices.py

import asyncio
from app.services.elastic_service import ElasticsearchService
from app.core.database import SessionLocal
from app.models.schema import Schema

async def create_v2_indices():
    db = SessionLocal()
    elastic = ElasticsearchService()

    try:
        # Get all schemas
        schemas = db.query(Schema).all()

        for schema in schemas:
            print(f"Creating index for schema: {schema.name}")

            # Create new index with v2 suffix
            elastic.index_name = f"documents_v2"
            await elastic.create_index(schema.to_dict())

        # Create template signatures v2
        elastic.template_signatures_index = "template_signatures_v2"
        await elastic.create_template_signatures_index()

        print("✅ New indices created successfully")

    finally:
        await elastic.close()
        db.close()

if __name__ == "__main__":
    asyncio.run(create_v2_indices())
```

```bash
# Run the script
cd backend
python scripts/create_v2_indices.py
```

#### Step 3: Reindex Data

```bash
# Reindex documents
curl -X POST "localhost:9200/_reindex" -H 'Content-Type: application/json' -d'
{
  "source": {
    "index": "documents"
  },
  "dest": {
    "index": "documents_v2"
  }
}'

# Reindex template signatures
curl -X POST "localhost:9200/_reindex" -H 'Content-Type: application/json' -d'
{
  "source": {
    "index": "template_signatures"
  },
  "dest": {
    "index": "template_signatures_v2"
  }
}'
```

**Note:** Reindexing may fail on some documents if they have unmapped fields. See "Handling Unmapped Fields" below.

#### Step 4: Create Aliases

```bash
# Remove old aliases (if any)
curl -X POST "localhost:9200/_aliases" -H 'Content-Type: application/json' -d'
{
  "actions": [
    { "remove": { "index": "documents", "alias": "documents_active" } },
    { "add": { "index": "documents_v2", "alias": "documents_active" } }
  ]
}'

# Update application to use alias
# In elastic_service.py, change:
# self.index_name = "documents_active"
```

#### Step 5: Test and Verify

```bash
# Test search
curl "localhost:9200/documents_v2/_search?size=5"

# Check index stats via API
curl "localhost:8000/api/search/index-stats"

# Compare document counts
curl "localhost:9200/documents/_count"
curl "localhost:9200/documents_v2/_count"
```

#### Step 6: Cleanup (After 24-48 Hours)

```bash
# Delete old indices
curl -X DELETE "localhost:9200/documents"
curl -X DELETE "localhost:9200/template_signatures"
```

---

### Option 3: In-Place Update (Limited)

**Best for:** Adding new fields only (not changing existing mappings)

**Warning:** You **cannot** change existing field mappings or add `dynamic: strict` in-place.

```python
# Only works for adding NEW fields
# Cannot change dynamic mapping or existing field types

await elastic_service.client.indices.put_mapping(
    index="documents",
    body={
        "properties": {
            "new_field": {"type": "keyword", "ignore_above": 256}
        }
    }
)
```

**Not recommended** - use Option 1 or 2 instead.

---

## Handling Unmapped Fields

If reindexing fails due to unmapped fields:

### Step 1: Identify Unmapped Fields

```bash
# Get a sample document with all fields
curl "localhost:9200/documents/_search?size=1&pretty"

# Compare against schema
curl "localhost:9200/documents/_mapping?pretty"
```

### Step 2: Update Schema to Include All Fields

```python
# Add missing fields to schema definition
# In your schema JSON:
{
  "fields": [
    # ... existing fields ...
    {
      "name": "previously_unmapped_field",
      "type": "text",
      "description": "Field that was dynamically added"
    }
  ]
}
```

### Step 3: Recreate Index with Updated Schema

```bash
# Delete v2 index
curl -X DELETE "localhost:9200/documents_v2"

# Recreate with updated schema (run create_v2_indices.py again)
python scripts/create_v2_indices.py

# Retry reindex
curl -X POST "localhost:9200/_reindex" ...
```

---

## Testing the Migration

### Functional Tests

```bash
# 1. Test document upload
curl -X POST "localhost:8000/api/documents/upload" \
  -F "file=@test_invoice.pdf" \
  -F "schema_id=1"

# 2. Test search
curl "localhost:8000/api/search?query=invoice"

# 3. Test index stats
curl "localhost:8000/api/search/index-stats"

# 4. Test with unmapped field (should fail)
curl -X POST "localhost:9200/documents/_doc" -H 'Content-Type: application/json' -d'
{
  "unmapped_field": "should_fail"
}'
# Expected: 400 error with "strict_dynamic_mapping_exception"
```

### Performance Comparison

```python
# Benchmark script: scripts/benchmark_migration.py
import time
import asyncio
from app.services.elastic_service import ElasticsearchService

async def benchmark():
    elastic = ElasticsearchService()

    # Test bulk indexing speed
    documents = [...]  # 100 test documents

    start = time.time()
    for doc in documents:
        await elastic.index_document(...)
    end = time.time()

    print(f"Indexing speed: {len(documents)/(end-start):.2f} docs/sec")

    # Test storage size
    stats = await elastic.get_index_stats()
    print(f"Storage size: {stats['storage_size_mb']} MB")
    print(f"Avg per doc: {stats['storage_size_mb']/stats['document_count']:.2f} MB")

asyncio.run(benchmark())
```

---

## Rollback Plan

If migration fails or causes issues:

### Quick Rollback (Alias Swap)

```bash
# Swap back to old index
curl -X POST "localhost:9200/_aliases" -H 'Content-Type: application/json' -d'
{
  "actions": [
    { "remove": { "index": "documents_v2", "alias": "documents_active" } },
    { "add": { "index": "documents", "alias": "documents_active" } }
  ]
}'

# Restart application
docker-compose restart backend
```

### Full Rollback (Code Revert)

```bash
# Revert code changes
git revert <commit-hash>

# Delete new indices
curl -X DELETE "localhost:9200/documents_v2"
curl -X DELETE "localhost:9200/template_signatures_v2"

# Restart
docker-compose restart
```

---

## Post-Migration Monitoring

### Week 1: Watch for Issues

```bash
# Monitor error logs
docker-compose logs -f backend | grep -i "elasticsearch"

# Check index health daily
curl "localhost:8000/api/search/index-stats"

# Monitor field count growth
watch -n 3600 'curl -s localhost:8000/api/search/index-stats | jq .field_count'
```

### Week 2-4: Performance Analysis

1. **Compare storage:**
   - Old index size vs new index size
   - Expected: 20-30% reduction

2. **Compare indexing speed:**
   - Bulk upload 100 documents before/after
   - Expected: 20-30% faster with refresh optimization

3. **Search latency:**
   - Should be unchanged or slightly faster
   - Monitor via application metrics

---

## Common Issues & Solutions

### Issue 1: Reindexing Fails with "strict_dynamic_mapping_exception"

**Cause:** Documents have fields not in schema

**Solution:**
```bash
# Option A: Update schema to include all fields
# Option B: Filter during reindex
curl -X POST "localhost:9200/_reindex" -H 'Content-Type: application/json' -d'
{
  "source": {
    "index": "documents",
    "_source": ["field1", "field2", "field3"]  # Only known fields
  },
  "dest": {
    "index": "documents_v2"
  }
}'
```

### Issue 2: Keyword Field Too Long

**Symptom:** Warning logs about ignored fields

**Expected:** This is normal! Fields longer than 256 chars are stored but not indexed as keywords.

**Action:** No action needed unless you need to search/aggregate on long text.

### Issue 3: Field Limit Exceeded

**Symptom:** `illegal_argument_exception: Limit of total fields [1000] has been exceeded`

**Solution:**
```bash
# Increase limit temporarily
curl -X PUT "localhost:9200/documents_v2/_settings" -H 'Content-Type: application/json' -d'
{
  "index.mapping.total_fields.limit": 2000
}'

# Long-term: Review and consolidate schemas
```

### Issue 4: Slower Aggregations

**Cause:** Removed `eager_global_ordinals` from some fields

**Solution:**
```python
# Add to frequently aggregated fields
"template_name": {
    "type": "keyword",
    "ignore_above": 256,
    "eager_global_ordinals": True
}
```

---

## FAQ

### Q: Do I need to re-upload all documents?

**A:** No, if you use Option 2 (reindex). Use Option 1 only if starting fresh.

### Q: Will this break my existing searches?

**A:** No, search queries remain compatible. Only indexing behavior changes.

### Q: Can I migrate one schema at a time?

**A:** No, mappings are index-level. You must migrate the entire index.

### Q: What if I have custom fields?

**A:** Add them to your schema definitions before migration. The new `dynamic: strict` will reject unmapped fields.

### Q: How long does migration take?

**A:**
- <1,000 docs: 1-2 minutes
- 10,000 docs: 5-10 minutes
- 100,000 docs: 30-60 minutes

### Q: Is downtime required?

**A:** No, if using Option 2 with alias swap. Application can stay up during reindex.

---

## Migration Checklist

### Pre-Migration
- [ ] Backup database and Elasticsearch indices
- [ ] Document current index stats (size, doc count, field count)
- [ ] Review schemas for unmapped fields
- [ ] Schedule maintenance window (recommended but not required)

### Migration
- [ ] Create new indices with v2 mappings
- [ ] Reindex documents (or fresh upload)
- [ ] Verify document counts match
- [ ] Test critical search queries
- [ ] Update application configuration (if using aliases)

### Post-Migration
- [ ] Monitor logs for 24 hours
- [ ] Compare performance metrics
- [ ] Verify storage reduction (~30%)
- [ ] Delete old indices after 48 hours
- [ ] Update team documentation

---

## Support

If you encounter issues during migration:

1. Check logs: `docker-compose logs backend`
2. Check Elasticsearch logs: `docker-compose logs elasticsearch`
3. Review this guide's "Common Issues" section
4. Check index stats: `curl localhost:8000/api/search/index-stats`

---

**Last Updated:** 2025-10-23
**Applies to:** Paperbase v2.0+ with optimized ES mappings
**Estimated Migration Time:** 30 minutes - 2 hours (depending on data size)
