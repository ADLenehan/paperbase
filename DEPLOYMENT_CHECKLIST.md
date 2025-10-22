# Multi-Template Extraction - Deployment Checklist

## 🚀 Pre-Deployment

### 1. Backup Current System
- [ ] Backup database: `cp backend/paperbase.db backend/paperbase.db.backup`
- [ ] Backup uploads folder: `tar -czf uploads_backup.tar.gz backend/uploads/`
- [ ] Document current system state (document count, templates, etc.)
- [ ] Export current stats for comparison

### 2. Verify Requirements
- [ ] Python 3.11+ installed
- [ ] All dependencies in `requirements.txt` installed
- [ ] Backend running successfully on `http://localhost:8000`
- [ ] Elasticsearch running and healthy
- [ ] At least 2 templates configured in system

### 3. Code Verification
- [ ] All new files created:
  - [ ] `backend/app/models/physical_file.py`
  - [ ] `backend/app/models/extraction.py`
  - [ ] `backend/app/models/batch.py`
  - [ ] `backend/app/services/file_service.py`
  - [ ] `backend/app/services/extraction_service.py`
  - [ ] `backend/app/services/folder_service.py`
  - [ ] `backend/app/api/extractions.py`
  - [ ] `backend/app/api/folders.py`
  - [ ] `backend/app/utils/hashing.py`
  - [ ] `backend/app/migrations/migrate_to_extractions.py`

- [ ] Modified files updated:
  - [ ] `backend/app/models/document.py` (ExtractedField supports extraction_id)
  - [ ] `backend/app/main.py` (new routers registered)

## 🔄 Migration Process

### Step 1: Create Tables
```bash
cd backend
python -m app.migrations.migrate_to_extractions --create-tables
```

**Verify:**
- [ ] No errors in output
- [ ] Tables created: `physical_files`, `extractions`, `batches`, `batch_extractions`

### Step 2: Dry Run Migration
```bash
python -m app.migrations.migrate_to_extractions --dry-run
```

**Verify:**
- [ ] Shows count of documents to migrate
- [ ] No errors reported
- [ ] Sample output shows correct mapping

### Step 3: Run Migration
```bash
python -m app.migrations.migrate_to_extractions
```

**Expected Output:**
```
Found X documents to migrate
Created PhysicalFile: filename.pdf (hash: abc12345...)
✓ Migrated Document #1 → Extraction #1 (5 fields) - Template/2025-10-11/filename.pdf
...
Migration complete!
  Migrated: X
  Skipped:  0
  Errors:   0
```

**Verify:**
- [ ] Migrated count matches document count
- [ ] Zero errors
- [ ] All files accounted for

### Step 4: Verify Migration
```bash
# Check record counts
sqlite3 backend/paperbase.db << 'EOF'
.headers on
.mode column
SELECT 'physical_files' as table_name, COUNT(*) as count FROM physical_files
UNION ALL
SELECT 'extractions', COUNT(*) FROM extractions
UNION ALL
SELECT 'extracted_fields (new)', COUNT(*) FROM extracted_fields WHERE extraction_id IS NOT NULL
UNION ALL
SELECT 'extracted_fields (old)', COUNT(*) FROM extracted_fields WHERE document_id IS NOT NULL;
EOF
```

**Expected:**
- [ ] `physical_files` count ≤ original document count (due to deduplication)
- [ ] `extractions` count = original document count
- [ ] `extracted_fields (new)` count = total extracted fields
- [ ] `extracted_fields (old)` count = 0 (all migrated)

### Step 5: Test New Endpoints
```bash
# Test extraction endpoints
curl http://localhost:8000/api/extractions/stats | jq

# Test folder endpoints
curl http://localhost:8000/api/folders/browse | jq

# Test folder tree
curl http://localhost:8000/api/folders/tree | jq
```

**Verify:**
- [ ] `/api/extractions/stats` returns valid statistics
- [ ] `/api/folders/browse` shows folder structure
- [ ] `/api/folders/tree` shows complete tree
- [ ] No 404 or 500 errors

## ✅ Post-Migration Validation

### 1. Data Integrity
```bash
# Check for orphaned records
sqlite3 backend/paperbase.db << 'EOF'
-- Should return 0
SELECT COUNT(*) as orphaned_extractions
FROM extractions e
LEFT JOIN physical_files pf ON e.physical_file_id = pf.id
WHERE pf.id IS NULL;

-- Should return 0
SELECT COUNT(*) as orphaned_fields
FROM extracted_fields ef
LEFT JOIN extractions e ON ef.extraction_id = e.id
WHERE ef.extraction_id IS NOT NULL AND e.id IS NULL;
EOF
```

**Verify:**
- [ ] Zero orphaned extractions
- [ ] Zero orphaned fields

### 2. File Deduplication
```bash
# Check for potential duplicates
sqlite3 backend/paperbase.db << 'EOF'
SELECT file_hash, COUNT(*) as count
FROM physical_files
GROUP BY file_hash
HAVING count > 1;
EOF
```

**Verify:**
- [ ] No duplicate file_hash values (should return empty)

### 3. Folder Organization
```bash
# Check organized paths
curl http://localhost:8000/api/folders/templates | jq '.folders'
```

**Verify:**
- [ ] All template folders present
- [ ] File counts match expected

## 🧪 Functional Testing

### Test 1: Upload with Multiple Templates
```bash
# Upload test file with 2 templates
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@test_documents/invoice_sample.pdf" \
  -F "template_ids=1" \
  -F "template_ids=2" | jq
```

**Verify:**
- [ ] Response shows 1 physical file
- [ ] Response shows 2 extractions
- [ ] Both extractions reference same physical_file_id

### Test 2: File Deduplication
```bash
# Upload same file again
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@test_documents/invoice_sample.pdf" \
  -F "template_ids=1" | jq
```

**Verify:**
- [ ] Response shows `duplicates_found: 1`
- [ ] Response shows `is_new: false`
- [ ] Uses existing physical file

### Test 3: Batch Extraction
```bash
# Get file IDs
FILE_IDS=$(curl -s http://localhost:8000/api/folders/browse | jq -r '.files[].physical_file_id' | head -3 | tr '\n' ',' | sed 's/,$//')

# Batch extract
curl -X POST http://localhost:8000/api/extractions/batch-extract \
  -H "Content-Type: application/json" \
  -d "{
    \"physical_file_ids\": [$FILE_IDS],
    \"template_id\": 1,
    \"batch_name\": \"Test Batch\"
  }" | jq
```

**Verify:**
- [ ] Batch created successfully
- [ ] All files processed
- [ ] Status shows "completed"

### Test 4: Folder Browsing
```bash
# Browse root
curl http://localhost:8000/api/folders/browse | jq

# Browse specific folder
curl http://localhost:8000/api/folders/browse?path=Invoice | jq
```

**Verify:**
- [ ] Folders listed correctly
- [ ] Files shown with correct metadata
- [ ] Counts accurate

### Test 5: Folder Reorganization
```bash
# Get extraction IDs
EXT_IDS=$(curl -s "http://localhost:8000/api/folders/browse?path=Invoice" | jq -r '.files[].extraction_id' | head -2 | jq -s .)

# Reorganize
curl -X POST http://localhost:8000/api/folders/reorganize \
  -H "Content-Type: application/json" \
  -d "{
    \"extraction_ids\": $EXT_IDS,
    \"target_path\": \"Test/Archive\"
  }" | jq
```

**Verify:**
- [ ] Files moved successfully
- [ ] Browse Test/Archive shows files
- [ ] Original folder no longer contains files

## 📊 Performance Testing

### 1. API Response Times
```bash
# Test extraction stats endpoint
time curl -s http://localhost:8000/api/extractions/stats > /dev/null

# Test folder browsing
time curl -s "http://localhost:8000/api/folders/browse?path=Invoice" > /dev/null

# Test folder tree
time curl -s http://localhost:8000/api/folders/tree > /dev/null
```

**Verify:**
- [ ] All endpoints respond < 1 second
- [ ] No timeouts

### 2. Database Indexes
```bash
sqlite3 backend/paperbase.db << 'EOF'
.indexes physical_files
.indexes extractions
.indexes extracted_fields
EOF
```

**Verify:**
- [ ] Index on `physical_files.file_hash`
- [ ] Index on `extractions.physical_file_id`
- [ ] Index on `extractions.organized_path`
- [ ] Index on `extracted_fields.extraction_id`

## 🔒 Security & Cleanup

### 1. Environment Variables
- [ ] `REDUCTO_API_KEY` set correctly
- [ ] `ANTHROPIC_API_KEY` set correctly
- [ ] No sensitive data in logs

### 2. File Permissions
```bash
# Check upload directory permissions
ls -la backend/uploads/
```

**Verify:**
- [ ] Uploads directory writable
- [ ] No world-readable sensitive files

### 3. Cleanup Old Data (Optional)
```bash
# After 1 week of stable operation, optionally archive old documents table
# DO NOT DO THIS IMMEDIATELY - wait for production validation

# Archive old documents (keep as backup)
sqlite3 backend/paperbase.db << 'EOF'
ALTER TABLE documents RENAME TO documents_legacy;
EOF
```

## 📈 Monitoring

### 1. Setup Monitoring Endpoints
- [ ] Add `/api/extractions/stats` to monitoring
- [ ] Track deduplication rate
- [ ] Monitor extraction success rate
- [ ] Track API response times

### 2. Log Monitoring
```bash
# Monitor logs for errors
tail -f backend/logs/app.log | grep -i error
```

**Watch for:**
- [ ] No migration-related errors
- [ ] No foreign key constraint failures
- [ ] No file not found errors

## 🎉 Go Live

### Final Checks
- [ ] All tests passing
- [ ] No errors in logs
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Team trained on new features

### Communication
- [ ] Notify team of new capabilities
- [ ] Share documentation links:
  - [ ] [MULTI_TEMPLATE_EXTRACTION.md](./MULTI_TEMPLATE_EXTRACTION.md)
  - [ ] [MULTI_TEMPLATE_QUICKSTART.md](./MULTI_TEMPLATE_QUICKSTART.md)
  - [ ] [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)

### Rollback Plan (If Issues)
```bash
# 1. Stop backend
# 2. Restore database backup
cp backend/paperbase.db.backup backend/paperbase.db

# 3. Restore uploads folder
tar -xzf uploads_backup.tar.gz

# 4. Restart backend

# OR use migration rollback
python -m app.migrations.migrate_to_extractions --rollback
```

## 📋 Post-Deployment Tasks

### Week 1
- [ ] Monitor deduplication statistics daily
- [ ] Check extraction success rates
- [ ] Gather user feedback
- [ ] Document any issues

### Week 2
- [ ] Analyze cost savings from parse caching
- [ ] Review folder organization patterns
- [ ] Optimize based on usage data

### Month 1
- [ ] Consider archiving legacy documents table
- [ ] Plan frontend component implementation
- [ ] Evaluate additional features

## ✨ Success Metrics

Track these metrics to validate success:

- [ ] **Deduplication Rate**: `duplicates_avoided / total_extractions * 100%`
  - Target: >10% for typical usage

- [ ] **Parse Caching Effectiveness**: `reused_parses / total_extractions * 100%`
  - Target: >50% for multi-template scenarios

- [ ] **Cost Savings**: Compare before/after API costs
  - Target: 30-60% reduction

- [ ] **Storage Efficiency**: `physical_files / extractions ratio`
  - Target: <0.5 (meaning 2+ extractions per file on average)

- [ ] **API Performance**: Response time for folder browsing
  - Target: <500ms for typical folders

---

## 🆘 Support

If you encounter issues:

1. Check logs: `tail -f backend/logs/app.log`
2. Verify migration: `python -m app.migrations.migrate_to_extractions --dry-run`
3. Review documentation: [MULTI_TEMPLATE_EXTRACTION.md](./MULTI_TEMPLATE_EXTRACTION.md)
4. Rollback if needed (see Rollback Plan above)

**Emergency Contact**: [Add your contact info]

---

**Deployment Date**: _____________
**Deployed By**: _____________
**Status**: ⏳ Pending → ✅ Complete
