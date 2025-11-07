# SHA256 Deduplication - Debugging & Integration Guide

## Critical Integration Points

### 🔴 HIGH PRIORITY: Code Needs Updating

The following locations still reference legacy Document fields directly and need to be updated to use the new `actual_*` properties for full compatibility:

#### 1. **bulk_upload.py** - Template Matching Section

**Lines 242, 247** - Uses `representative_doc.reducto_parse_result` directly:
```python
# CURRENT (Line 242)
chunks = representative_doc.reducto_parse_result.get("chunks", []) if representative_doc.reducto_parse_result else []

# SHOULD BE
chunks = representative_doc.actual_parse_result.get("chunks", []) if representative_doc.actual_parse_result else []

# CURRENT (Line 247)
common_fields = extract_field_names_from_parse(representative_doc.reducto_parse_result) if representative_doc.reducto_parse_result else []

# SHOULD BE
common_fields = extract_field_names_from_parse(representative_doc.actual_parse_result) if representative_doc.actual_parse_result else []
```

**Why this matters**: After deduplication, Documents will rely on PhysicalFile for parse results. Direct access to `reducto_parse_result` may be `None`.

#### 2. **bulk_upload.py** - File Organization

**Lines 323, 330, 418, 422, 690, 694** - Uses `doc.file_path` directly:
```python
# CURRENT (Line 323, 418, 690)
old_path = doc.file_path
current_path = doc.file_path

# SHOULD BE
old_path = doc.actual_file_path
current_path = doc.actual_file_path

# CURRENT (Line 330, 422, 694)
doc.file_path = new_path

# ISSUE: This only updates legacy field, not PhysicalFile!
# SOLUTION: Update PhysicalFile.file_path instead
if doc.physical_file:
    doc.physical_file.file_path = new_path
else:
    doc.file_path = new_path  # Fallback for unmigrated docs
```

#### 3. **bulk_upload.py** - Schema Generation Functions

**Lines 535-546** (`quick-analyze` endpoint):
```python
# CURRENT
if doc.reducto_parse_result:
    parsed_doc = {
        "result": doc.reducto_parse_result,
        "job_id": doc.reducto_job_id
    }
else:
    parsed = await reducto_service.parse_document(doc.file_path)
    doc.reducto_job_id = parsed.get("job_id")
    doc.reducto_parse_result = parsed.get("result")

# SHOULD BE
if doc.actual_parse_result:
    parsed_doc = {
        "result": doc.actual_parse_result,
        "job_id": doc.actual_job_id
    }
else:
    parsed = await reducto_service.parse_document(doc.actual_file_path)
    # Update PhysicalFile if available
    if doc.physical_file:
        doc.physical_file.reducto_job_id = parsed.get("job_id")
        doc.physical_file.reducto_parse_result = parsed.get("result")
    else:
        # Fallback for unmigrated docs
        doc.reducto_job_id = parsed.get("job_id")
        doc.reducto_parse_result = parsed.get("result")
```

**Lines 619-630** (`create-new-template` endpoint) - Same pattern as above.

#### 4. **elastic_service.py** - Clustering Function

**Location**: `cluster_uploaded_documents` method
```python
# CURRENT
for doc in documents:
    if not doc.reducto_parse_result:
        logger.warning(f"Skipping document {doc.id} - no parse result")
        continue
    chunks = doc.reducto_parse_result.get("chunks", [])

# SHOULD BE
for doc in documents:
    parse_result = doc.actual_parse_result
    if not parse_result:
        logger.warning(f"Skipping document {doc.id} - no parse result")
        continue
    chunks = parse_result.get("chunks", [])
```

### 🟡 MEDIUM PRIORITY: Potential Issues

#### 1. **File Reorganization Logic**

**Problem**: When organizing files into template folders, we update `doc.file_path` but the physical file hasn't moved.

**Current flow**:
```python
# organize_document_file moves the physical file
new_path = organize_document_file(current_path, filename, template_name)
doc.file_path = new_path  # Update Document

# But with deduplication:
# - Multiple Documents may share one PhysicalFile
# - Moving the physical file affects ALL Documents sharing it!
```

**Solution Options**:

**Option A: Don't move physical files (recommended)**
```python
# Keep physical files in single location (uploads/)
# Use virtual paths for organization (metadata only)
doc.organized_path = f"{template_name}/{filename}"  # Virtual path
# Physical file stays at doc.physical_file.file_path
```

**Option B: Copy on reorganize**
```python
# When reorganizing, create new PhysicalFile (break sharing)
if doc.physical_file and doc.physical_file.documents.count() > 1:
    # Multiple docs share this file - copy it
    new_physical_file = PhysicalFile(
        filename=doc.physical_file.filename,
        file_hash=doc.physical_file.file_hash,  # Same hash!
        file_path=new_path,  # New location
        # Copy parse cache
        reducto_job_id=doc.physical_file.reducto_job_id,
        reducto_parse_result=doc.physical_file.reducto_parse_result
    )
    doc.physical_file = new_physical_file
else:
    # Only this doc uses the file - safe to move
    os.rename(doc.physical_file.file_path, new_path)
    doc.physical_file.file_path = new_path
```

#### 2. **Extraction Service Compatibility**

Check if `ExtractionService` (from multi-template extraction) works with the new structure:

```python
# In extraction_service.py, does it expect Document.file_path?
# Or can it use Document.actual_file_path?

# Search for:
grep -n "document.file_path" backend/app/services/extraction_service.py
```

### 🟢 LOW PRIORITY: Enhancements

#### 1. **Add Index on physical_file_id**

Already added in model, verify in database:
```sql
-- Check index exists
SELECT name FROM sqlite_master
WHERE type='index' AND tbl_name='documents';

-- Should show: ix_documents_physical_file_id
```

#### 2. **Add Cascade Delete Logic**

Consider: Should PhysicalFile be deleted when last Document is deleted?

```python
# Option 1: Keep PhysicalFile (allows future dedup)
# Current: No cascade delete

# Option 2: Cleanup orphaned PhysicalFiles (save storage)
# Add periodic cleanup job:
DELETE FROM physical_files
WHERE id NOT IN (SELECT DISTINCT physical_file_id FROM documents WHERE physical_file_id IS NOT NULL)
  AND id NOT IN (SELECT DISTINCT physical_file_id FROM extractions WHERE physical_file_id IS NOT NULL);
```

## Testing Scenarios

### Test 1: Upload Same File Twice (Basic Dedup)

```python
# Test script
import requests

# Upload invoice.pdf first time
with open("invoice.pdf", "rb") as f:
    response1 = requests.post(
        "http://localhost:8000/api/bulk/upload-and-analyze",
        files={"files": f}
    )

# Upload same invoice.pdf again
with open("invoice.pdf", "rb") as f:
    response2 = requests.post(
        "http://localhost:8000/api/bulk/upload-and-analyze",
        files={"files": f}
    )

# Check deduplication
assert response2.json()["parse_calls_saved"] == 1
assert response2.json()["unique_files"] == 1
assert response2.json()["total_documents"] == 1

# Verify database
# - 1 PhysicalFile
# - 2 Documents (both pointing to same PhysicalFile)
```

**Expected logs**:
```
[Upload 1] Starting bulk upload of 1 files
[Upload 1] Dedup analysis: 1 files → 1 unique hashes (0 duplicates in batch, 0 with cached parse)
[Upload 1] Created PhysicalFile #1: abc12345_invoice.pdf
[Upload 1] Parsing new file: invoice.pdf
[Upload 1] Parsed invoice.pdf → job_id: job_xyz

[Upload 2] Starting bulk upload of 1 files
[Upload 2] Dedup analysis: 1 files → 1 unique hashes (0 duplicates in batch, 1 with cached parse)  ← SAVED!
[Upload 2] Reusing PhysicalFile #1 for 1 files (hash: abc12345...)
[Upload 2] Using cached parse for invoice.pdf (job_id: job_xyz)  ← NO PARSE!
```

### Test 2: Batch Upload with Duplicates

```python
# Upload 5 files: [invoice.pdf, invoice.pdf, contract.pdf, invoice.pdf, receipt.pdf]
# Expected:
# - 3 unique hashes (invoice, contract, receipt)
# - 2 duplicates in batch (invoice appears 3 times)
# - 3 parse calls (one per unique file)
# - parse_calls_saved = 2 (invoice parsed once, reused 2x)

response = requests.post(
    "http://localhost:8000/api/bulk/upload-and-analyze",
    files=[
        ("files", open("invoice.pdf", "rb")),
        ("files", open("invoice.pdf", "rb")),  # Dup 1
        ("files", open("contract.pdf", "rb")),
        ("files", open("invoice.pdf", "rb")),  # Dup 2
        ("files", open("receipt.pdf", "rb"))
    ]
)

assert response.json()["total_documents"] == 5
assert response.json()["unique_files"] == 3
assert response.json()["exact_duplicates_in_batch"] == 2
assert response.json()["parse_calls_saved"] == 2
```

### Test 3: Migration Script

```bash
# Backup first
cp backend/paperbase.db backend/paperbase.db.backup

# Dry run
cd backend
python -m migrations.link_documents_to_physical_files --dry-run

# Expected output:
# Found X documents without physical_file_id
# Processing Document #1: invoice.pdf
#   Hash: abc12345...
#   [DRY RUN] Would create PhysicalFile
#   [DRY RUN] Would link Document → PhysicalFile

# Actual migration
python -m migrations.link_documents_to_physical_files

# Verify
sqlite3 paperbase.db "SELECT COUNT(*) FROM documents WHERE physical_file_id IS NULL"
# Should be 0 after migration
```

### Test 4: ES Clustering with Deduped Docs

```python
# Upload 3 different invoices (different content, same structure)
response = requests.post(
    "http://localhost:8000/api/bulk/upload-and-analyze",
    files=[
        ("files", open("invoice_jan.pdf", "rb")),
        ("files", open("invoice_feb.pdf", "rb")),
        ("files", open("invoice_mar.pdf", "rb"))
    ]
)

# Expected:
# - 3 unique files
# - 3 parse calls
# - 1 cluster (similar content)
# - 1 template suggestion (Invoice)

assert response.json()["unique_files"] == 3
assert len(response.json()["groups"]) == 1  # One cluster
assert response.json()["groups"][0]["document_ids"] == [1, 2, 3]  # All in one group
```

### Test 5: Backwards Compatibility

```python
# Test with unmigrated Document (no physical_file_id)

# 1. Create old-style document directly
from app.models.document import Document
doc = Document(
    filename="legacy.pdf",
    file_path="/path/to/legacy.pdf",
    reducto_parse_result={"chunks": [...]},
    status="completed"
)
db.add(doc)
db.commit()

# 2. Try to use it
assert doc.actual_file_path == "/path/to/legacy.pdf"  # Falls back to legacy
assert doc.actual_parse_result == {"chunks": [...]}  # Falls back to legacy

# 3. Upload same file again (should still dedup)
# New upload will create PhysicalFile and deduplicate
```

## Debugging Checklist

### When uploads fail:

- [ ] Check logs for "Dedup analysis" line - shows hash detection
- [ ] Verify PhysicalFile was created (`SELECT * FROM physical_files ORDER BY id DESC LIMIT 1`)
- [ ] Check if parse was cached (`reducto_parse_result IS NOT NULL`)
- [ ] Verify Document links to PhysicalFile (`SELECT id, physical_file_id FROM documents WHERE id = ?`)

### When clustering fails:

- [ ] Check if `actual_parse_result` returns data for all Documents
- [ ] Verify ES can access parse results (not `None`)
- [ ] Check logs for "Skipping document X - no parse result"

### When extraction fails:

- [ ] Verify `jobid://` still works with cached parse
- [ ] Check if PhysicalFile has `reducto_job_id` set
- [ ] Test: Can we extract with `jobid://{physical_file.reducto_job_id}`?

### When file organization fails:

- [ ] Check if moving physical file breaks dedup (multiple docs share it)
- [ ] Verify `organize_document_file` doesn't delete shared files
- [ ] Consider: Should we move files at all? Or use virtual paths?

## SQL Queries for Debugging

```sql
-- Show deduplication effectiveness
SELECT
    pf.file_hash,
    pf.filename,
    COUNT(d.id) as document_count,
    pf.reducto_job_id IS NOT NULL as has_cached_parse
FROM physical_files pf
LEFT JOIN documents d ON d.physical_file_id = pf.id
GROUP BY pf.id
HAVING document_count > 1
ORDER BY document_count DESC;

-- Find documents without PhysicalFile (need migration)
SELECT id, filename, file_path
FROM documents
WHERE physical_file_id IS NULL
LIMIT 10;

-- Show parse cache sharing
SELECT
    pf.id as pf_id,
    pf.filename,
    pf.file_hash,
    d.id as doc_id,
    d.filename as doc_filename,
    pf.reducto_parse_result IS NOT NULL as pf_has_parse,
    d.reducto_parse_result IS NOT NULL as doc_has_parse
FROM physical_files pf
JOIN documents d ON d.physical_file_id = pf.id
WHERE pf.reducto_parse_result IS NOT NULL
ORDER BY pf.id;

-- Cost savings calculation
SELECT
    COUNT(DISTINCT pf.id) as unique_files,
    COUNT(d.id) as total_documents,
    (COUNT(d.id) - COUNT(DISTINCT pf.id)) as duplicates,
    ROUND((COUNT(d.id) - COUNT(DISTINCT pf.id)) * 0.02, 2) as cost_saved_usd
FROM documents d
JOIN physical_files pf ON d.physical_file_id = pf.id;
```

## Code Update Priority

**Phase 1: Critical (Do First)**
1. Update `elastic_service.py` clustering to use `actual_parse_result`
2. Update `bulk_upload.py` lines 242, 247 to use `actual_parse_result`
3. Test basic deduplication workflow

**Phase 2: Important (Do Soon)**
4. Update file organization logic (lines 323, 330, 418, 422, 690, 694)
5. Update schema generation functions (lines 535-546, 619-630)
6. Run migration script on dev database

**Phase 3: Polish (Do Later)**
7. Add monitoring queries to admin dashboard
8. Add dedup stats to API responses
9. Update frontend to show dedup savings

## Next Steps

1. **Create update script**:
   ```python
   # backend/scripts/update_for_deduplication.py
   # Automatically updates all doc.reducto_parse_result → doc.actual_parse_result
   ```

2. **Add comprehensive tests**:
   ```python
   # backend/tests/test_deduplication.py
   # Test all scenarios above
   ```

3. **Monitor in production**:
   ```sql
   -- Daily dedup report
   SELECT
       DATE(uploaded_at) as date,
       COUNT(DISTINCT physical_file_id) as unique_files,
       COUNT(*) as total_uploads,
       ROUND((COUNT(*) - COUNT(DISTINCT physical_file_id)) * 0.02, 2) as savings_usd
   FROM documents
   WHERE physical_file_id IS NOT NULL
   GROUP BY DATE(uploaded_at)
   ORDER BY date DESC;
   ```

---

**Status**: Implementation complete, integration updates needed
**Priority**: Update ES clustering first (breaks without it)
**Timeline**: 1-2 hours for critical updates, 1 day for full integration
