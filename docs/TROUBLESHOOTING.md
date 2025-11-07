# Paperbase Troubleshooting Guide

Common issues and their solutions for the Paperbase document extraction platform.

## 🔍 Quick Diagnostics

### Check System Health

```bash
# Backend health
curl http://localhost:8001/health

# Frontend accessible
curl -I http://localhost:3000

# Elasticsearch running
curl http://localhost:9200

# Database exists
ls -lh backend/paperbase.db

# Check running processes
ps aux | grep -E "uvicorn|vite|elasticsearch"
```

---

## 🚨 Common Issues

### 1. Backend Won't Start

**Symptom:**
```
ERROR: Address already in use
```

**Cause:** Port 8001 already in use

**Solution:**
```bash
# Find process using port
lsof -i :8001

# Kill the process
kill -9 <PID>

# Or use different port
uvicorn app.main:app --reload --port 8002
```

---

**Symptom:**
```
ModuleNotFoundError: No module named 'app'
```

**Cause:** Wrong directory or venv not activated

**Solution:**
```bash
# Make sure you're in backend directory
cd /Users/adlenehan/Projects/paperbase/backend

# Activate virtual environment
source venv/bin/activate

# Verify packages installed
pip list | grep -E "fastapi|reducto|anthropic"

# If missing, reinstall
pip install -r requirements.txt
```

---

**Symptom:**
```
sqlalchemy.exc.OperationalError: no such table: documents
```

**Cause:** Database not initialized

**Solution:**
```bash
# Delete old database
rm backend/paperbase.db

# Restart backend - tables will be created automatically
uvicorn app.main:app --reload
```

---

### 2. Frontend Issues

**Symptom:**
Frontend shows "Network Error" or can't connect to backend

**Cause:** Wrong API URL or backend not running

**Solution:**
```bash
# Check backend is running
curl http://localhost:8001/health

# Check frontend .env file
cat frontend/.env
# Should have: VITE_API_URL=http://localhost:8001

# If .env changed, restart frontend
cd frontend
npm run dev
```

---

**Symptom:**
```
npm ERR! Missing script: "dev"
```

**Cause:** Dependencies not installed

**Solution:**
```bash
cd frontend
npm install
npm run dev
```

---

### 3. Elasticsearch Issues

**Symptom:**
```
Connection refused to localhost:9200
```

**Cause:** Elasticsearch not running

**Solution:**
```bash
# Start Elasticsearch via Docker
docker-compose up elasticsearch

# Or start in background
docker-compose up -d elasticsearch

# Verify running
curl http://localhost:9200
```

---

**Symptom:**
```
Elasticsearch unhealthy: cluster_block_exception
```

**Cause:** Disk space or memory issues

**Solution:**
```bash
# Check disk space
df -h

# Check Elasticsearch logs
docker-compose logs elasticsearch | tail -50

# Increase Docker memory allocation
# Docker Desktop → Settings → Resources → Memory: 8GB

# Restart Elasticsearch
docker-compose restart elasticsearch
```

---

### 4. Document Upload Issues

**Symptom:**
Documents stuck in "analyzing" status

**Cause:** Reducto API call failed or processing crashed

**Diagnosis:**
```bash
# Check document status
sqlite3 backend/paperbase.db "
SELECT id, filename, status, error_message
FROM documents
WHERE status = 'analyzing'
ORDER BY uploaded_at DESC;
"

# Check logs for errors
tail -100 /tmp/paperbase_backend.log | grep ERROR
```

**Solution:**
```bash
# Reset stuck documents
sqlite3 backend/paperbase.db "
UPDATE documents
SET status = 'uploaded', error_message = NULL
WHERE status = 'analyzing';
"

# Trigger reprocessing
curl -X POST http://localhost:8001/api/documents/process \
  -H "Content-Type: application/json" \
  -d '[<document_id>]'
```

---

**Symptom:**
```
ReductoError: API key invalid
```

**Cause:** Missing or incorrect Reducto API key

**Solution:**
```bash
# Check .env file
cat backend/.env | grep REDUCTO

# If missing, add it
echo "REDUCTO_API_KEY=your_key_here" >> backend/.env

# Restart backend
# (Kill and restart uvicorn)
```

---

### 5. Extraction Issues

**Symptom:**
Extractions not showing in UI (all fields empty)

**Diagnosis:**
```bash
# Check if fields extracted
sqlite3 backend/paperbase.db "
SELECT COUNT(*) as field_count
FROM extracted_fields
WHERE document_id = <id>;
"

# If 0, check document status
sqlite3 backend/paperbase.db "
SELECT status, error_message
FROM documents
WHERE id = <id>;
"

# Check logs
grep "document <id>" /tmp/paperbase_backend.log
```

**Solution:**
```bash
# If status = error, check error_message
sqlite3 backend/paperbase.db "
SELECT id, filename, error_message
FROM documents
WHERE status = 'error';
"

# If format issue, verify fix is applied
grep "isinstance(extractions, list)" backend/app/api/documents.py

# Reset and reprocess
sqlite3 backend/paperbase.db "
UPDATE documents
SET status = 'processing', error_message = NULL
WHERE id = <id>;
"

curl -X POST http://localhost:8001/api/documents/process \
  -H "Content-Type: application/json" \
  -d '[<id>]'
```

---

**Symptom:**
```
'list' object has no attribute 'items'
```

**Cause:** Old version of documents.py without list handling fix

**Solution:**
This should be fixed. Verify the fix is in place:
```bash
grep -A5 "isinstance(extractions, list)" backend/app/api/documents.py
```

Should show:
```python
if isinstance(extractions, list):
    if len(extractions) > 0 and isinstance(extractions[0], dict):
        extractions = extractions[0]
```

If not present, the code needs to be updated.

---

### 6. Pipeline Optimization Not Working

**Symptom:**
Logs don't show "Using pipelined extraction"

**Diagnosis:**
```bash
# Check for pipeline logs
grep "pipeline\|jobid://" /tmp/paperbase_backend.log

# Check if job_id cached
sqlite3 backend/paperbase.db "
SELECT filename, reducto_job_id
FROM documents
WHERE reducto_job_id IS NOT NULL;
"
```

**Possible Causes:**
1. Document uploaded before pipeline implementation
2. job_id not saved during parse
3. Reducto SDK version doesn't support jobid://

**Solution:**
```bash
# Upload new document to test
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@test_documents/invoice_001.txt"

# Check logs for:
# - "Parsed: filename.pdf (job_id: xxx)"
# - "Using pipelined extraction with job_id: xxx"
# - "jobid://xxx"

# If still not working, check Reducto SDK version
cd backend
pip show reducto | grep Version
```

---

### 7. Template Matching Issues

**Symptom:**
All documents match "Generic Document" template

**Cause:** Claude not getting enough context or API key issue

**Diagnosis:**
```bash
# Check Claude API key
cat backend/.env | grep ANTHROPIC

# Check logs for Claude errors
grep "claude" /tmp/paperbase_backend.log -i | grep -i error
```

**Solution:**
```bash
# Verify API key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'

# Should return JSON response, not error

# If key invalid, update .env
echo "ANTHROPIC_API_KEY=your_key_here" >> backend/.env

# Restart backend
```

---

### 8. Search Not Working

**Symptom:**
Search returns no results even though documents exist

**Cause:** Documents not indexed in Elasticsearch

**Diagnosis:**
```bash
# Check Elasticsearch index
curl http://localhost:9200/documents/_search?pretty

# Check if documents have elasticsearch_id
sqlite3 backend/paperbase.db "
SELECT COUNT(*) as indexed_docs
FROM documents
WHERE elasticsearch_id IS NOT NULL;
"
```

**Solution:**
```bash
# Re-index all completed documents
sqlite3 backend/paperbase.db "
UPDATE documents
SET status = 'processing'
WHERE status = 'completed';
"

# Get document IDs
sqlite3 backend/paperbase.db "
SELECT id FROM documents WHERE status = 'processing';
" | while read id; do
  curl -X POST http://localhost:8001/api/documents/process \
    -H "Content-Type: application/json" \
    -d "[$id]"
done
```

---

### 9. High Memory Usage

**Symptom:**
Backend using excessive memory or crashing with OOM

**Possible Causes:**
1. Large PDF files
2. Memory leak in parsing
3. Too many documents processed simultaneously

**Solution:**
```bash
# Monitor memory
ps aux | grep uvicorn

# Limit file size in upload
# Add to backend/app/api/bulk_upload.py:
# max_file_size = 50 * 1024 * 1024  # 50MB

# Process documents sequentially instead of parallel
# (Already implemented in bulk_upload.py)

# Restart backend regularly in development
pkill -f uvicorn
uvicorn app.main:app --reload
```

---

### 10. Slow Processing

**Symptom:**
Documents taking >30 seconds to process

**Diagnosis:**
```bash
# Check processing times in logs
grep "Processing document" /tmp/paperbase_backend.log | \
  grep "Successfully processed"

# Should show ~10-15 seconds per document
```

**Possible Causes:**
1. Reducto API rate limiting
2. Network latency
3. Large documents
4. Elasticsearch indexing slow

**Solution:**
```bash
# Check Reducto API status
curl https://status.reducto.ai

# Monitor network latency
ping platform.reducto.ai

# Check Elasticsearch performance
curl http://localhost:9200/_cat/indices?v

# Optimize Elasticsearch (if too many documents)
curl -X POST "http://localhost:9200/documents/_forcemerge?max_num_segments=1"
```

---

## 🛠️ Advanced Debugging

### Enable Debug Logging

Add to `backend/app/main.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Database Inspection

```bash
# Open database in SQLite
sqlite3 backend/paperbase.db

# Useful queries:
sqlite> .tables
sqlite> .schema documents
sqlite> SELECT * FROM documents LIMIT 5;
sqlite> SELECT * FROM extracted_fields LIMIT 5;
sqlite> .exit
```

### Monitor API Calls

```bash
# Watch all HTTP requests
tail -f /tmp/paperbase_backend.log | grep "HTTP Request"

# Count Reducto API calls
grep "platform.reducto.ai" /tmp/paperbase_backend.log | wc -l

# See rate limiting
grep -i "rate limit" /tmp/paperbase_backend.log
```

### Network Debugging

```bash
# Check all services are accessible
curl -v http://localhost:8001/health
curl -v http://localhost:3000
curl -v http://localhost:9200

# Check DNS resolution
nslookup platform.reducto.ai
nslookup api.anthropic.com
```

---

## 📋 Diagnostic Checklist

When something isn't working, go through this checklist:

```
[ ] Is backend running? (curl http://localhost:8001/health)
[ ] Is frontend running? (curl http://localhost:3000)
[ ] Is Elasticsearch running? (curl http://localhost:9200)
[ ] Are environment variables set? (cat backend/.env)
[ ] Is virtual environment activated? (which python)
[ ] Are dependencies installed? (pip list)
[ ] Is database initialized? (ls backend/paperbase.db)
[ ] Are there errors in logs? (tail /tmp/paperbase_backend.log)
[ ] Is disk space available? (df -h)
[ ] Is port available? (lsof -i :8001)
```

---

## 🔧 Reset Everything

If all else fails, nuclear option:

```bash
# Stop all services
pkill -f uvicorn
pkill -f vite
docker-compose down

# Clean everything
rm backend/paperbase.db
rm -rf backend/uploads/*
docker volume prune -f

# Reinstall dependencies
cd backend
pip install -r requirements.txt

cd ../frontend
npm install

# Restart services
docker-compose up -d elasticsearch
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

---

## 📞 Getting Help

### Check Logs First
```bash
# Backend logs
tail -100 /tmp/paperbase_backend.log

# Frontend logs
# Check browser console (F12)

# Docker logs
docker-compose logs elasticsearch
```

### Gather Debug Info
```bash
# System info
uname -a
python --version
node --version
docker --version

# Service status
curl http://localhost:8001/health
curl http://localhost:9200

# Document count
sqlite3 backend/paperbase.db "SELECT status, COUNT(*) FROM documents GROUP BY status;"

# Recent errors
grep ERROR /tmp/paperbase_backend.log | tail -20
```

### Report Issues
Include:
1. Error message (full stack trace)
2. Steps to reproduce
3. System info (OS, Python version, etc.)
4. Relevant logs
5. Database state

---

## 📚 Related Documentation

- `TESTING_GUIDE.md` - How to test each feature
- `SYSTEM_STATUS.md` - Current system health
- `CLAUDE.md` - Architecture overview
- `README.md` - Setup instructions

---

**Last Updated:** 2025-10-10
**Version:** 1.0
