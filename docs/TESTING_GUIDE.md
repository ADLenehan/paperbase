# Paperbase Testing Guide

Complete guide for testing all features of the Paperbase document extraction platform.

## 🚀 Prerequisites

### 1. Start All Services

```bash
# Terminal 1: Start Elasticsearch (if not using Docker)
docker-compose up elasticsearch

# Terminal 2: Start Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Terminal 3: Start Frontend
cd frontend
npm run dev
```

### 2. Verify Services Running

```bash
# Check backend
curl http://localhost:8001/health

# Check frontend
curl http://localhost:3000

# Check Elasticsearch
curl http://localhost:9200
```

### 3. Check Environment Variables

Backend `.env` should have:
```
REDUCTO_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
ELASTICSEARCH_URL=http://localhost:9200
```

Frontend `.env` should have:
```
VITE_API_URL=http://localhost:8001
```

## 📋 Test Plan

### Test 1: Template Management

**Objective:** Verify all built-in templates are available

```bash
# Get all templates
curl http://localhost:8001/api/templates/ | jq

# Expected: 5 templates (Invoice, Receipt, Contract, Purchase Order, Generic)
```

**UI Test:**
1. Navigate to http://localhost:3000
2. Should see upload interface
3. Templates should be available in UI

**Success Criteria:**
- ✅ API returns 5 templates
- ✅ Each template has fields defined
- ✅ Categories are correct (invoice, receipt, contract, etc.)

---

### Test 2: Bulk Document Upload & Parsing

**Objective:** Upload documents and verify Reducto parsing with pipeline caching

**Steps:**
1. Create a test document:
```bash
cat > /tmp/test_contract.txt << 'EOF'
CONTRACT AGREEMENT

This agreement is entered into on January 15, 2025 between:

Party A: Acme Corporation
Party B: Supplier Inc.

Effective Date: January 15, 2025
Expiration Date: January 15, 2026

Total Contract Value: $50,000

Payment Terms: Net 30 days

Termination: Either party may terminate with 30 days notice.
EOF
```

2. Upload via API:
```bash
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@/tmp/test_contract.txt" \
  | jq
```

**Expected Response:**
```json
{
  "success": true,
  "total_documents": 1,
  "groups": [
    {
      "document_ids": [31],
      "filenames": ["test_contract.txt"],
      "template_match": {
        "template_id": 3,
        "template_name": "Contract",
        "confidence": 0.85
      }
    }
  ]
}
```

**Verify in Database:**
```bash
sqlite3 backend/paperbase.db "
SELECT id, filename, status, reducto_job_id
FROM documents
WHERE filename = 'test_contract.txt';
"
```

**Success Criteria:**
- ✅ Document uploaded successfully
- ✅ Status changes: uploaded → analyzing → template_matched
- ✅ `reducto_job_id` is populated (pipeline cache)
- ✅ Template matched correctly
- ✅ Confidence score provided

---

### Test 3: Template Confirmation & Pipelined Extraction

**Objective:** Confirm template and verify pipeline optimization

**Steps:**
1. Confirm template for the uploaded document:
```bash
curl -X POST http://localhost:8001/api/bulk/confirm-template \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": [31],
    "template_id": 3
  }' | jq
```

2. Monitor logs for pipeline usage:
```bash
tail -f /tmp/paperbase_backend.log | grep -E "pipeline|jobid://"
```

**Expected in Logs:**
```
INFO - Using pipelined extraction with job_id: <uuid>
INFO - Extracting 8 fields using pipeline (jobid://<uuid>)
INFO - Using cached parse result for ES indexing
```

**Verify Extractions:**
```bash
sqlite3 backend/paperbase.db "
SELECT field_name, field_value, confidence_score
FROM extracted_fields
WHERE document_id = 31;
"
```

**Success Criteria:**
- ✅ Pipeline used (logs show `jobid://`)
- ✅ No re-upload or re-parse (only 1 parse API call)
- ✅ Fields extracted correctly
- ✅ Confidence scores assigned
- ✅ Document status: processing → completed
- ✅ File organized into /uploads/contract/ folder

---

### Test 4: Bulk Confirmation UI

**Objective:** Review and edit extractions in the UI

**Steps:**
1. Navigate to bulk confirmation page:
   ```
   http://localhost:3000/confirm?schema_id=4
   ```

2. Check table displays:
   - Document filename in first column
   - Field columns (CONTRACT TITLE, EFFECTIVE DATE, etc.)
   - Extracted values in cells
   - Confidence badges (85%)
   - Color coding (green = high confidence)

3. Edit a field:
   - Click in a cell
   - Change value
   - Verify edited state is tracked

4. Click "Confirm All & Continue"

**Expected Behavior:**
- Table loads with vertical layout (docs as rows, fields as cols)
- Values are pre-filled from extractions
- Confidence scores show as badges
- Color coding: green (≥80%), yellow (60-80%), red (<60%)
- Stats show: High/Medium/Low confidence field counts
- Inline editing works
- Save button submits verifications

**Success Criteria:**
- ✅ Table displays correctly
- ✅ All extracted values visible
- ✅ Confidence scores shown
- ✅ Color coding works
- ✅ Inline editing functional
- ✅ Stats calculated correctly

---

### Test 5: Document Search

**Objective:** Search for documents using Elasticsearch

**Steps:**
1. Search via API:
```bash
curl -X POST http://localhost:8001/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contract",
    "page": 1,
    "size": 10
  }' | jq
```

**Expected Response:**
```json
{
  "total": 1,
  "results": [
    {
      "document_id": 31,
      "filename": "test_contract.txt",
      "score": 0.85,
      "extracted_fields": { ... }
    }
  ]
}
```

**Success Criteria:**
- ✅ Search returns relevant documents
- ✅ Full-text search works
- ✅ Extracted fields included in results

---

### Test 6: Natural Language Search

**Objective:** Test Claude-powered NL search

**Steps:**
1. Ask a natural language question:
```bash
curl -X POST http://localhost:8001/api/search/nl \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me all contracts with Acme Corporation",
    "schema_id": 4
  }' | jq
```

**Expected Response:**
```json
{
  "query": "Show me all contracts with Acme Corporation",
  "answer": "I found 1 contract involving Acme Corporation...",
  "explanation": "I searched for documents where party_a or party_b contains 'Acme Corporation'",
  "results": [ ... ],
  "total": 1,
  "elasticsearch_query": { ... }
}
```

**UI Test:**
1. Navigate to http://localhost:3000/search
2. Type: "Show me contracts expiring in 2026"
3. Press Enter

**Success Criteria:**
- ✅ Claude converts NL to ES query
- ✅ Query executes successfully
- ✅ Results returned with explanation
- ✅ Natural language answer generated
- ✅ UI shows results clearly

---

### Test 7: Pipeline Cost Optimization

**Objective:** Verify cost savings from pipelining

**Method:**
Count API calls in logs for a single document workflow:

```bash
# Upload & Parse (Initial)
grep "POST https://platform.reducto.ai" /tmp/paperbase_backend.log | wc -l

# Expected: 2 calls total
# 1. Upload endpoint
# 2. Parse endpoint

# Extract (Pipelined - should NOT have upload/parse)
grep "jobid://" /tmp/paperbase_backend.log

# Expected: Uses jobid:// - no additional upload/parse
```

**Calculate Savings:**
- **Without Pipeline:** Upload + Parse + Upload + Extract + Parse = 5 calls
- **With Pipeline:** Upload + Parse + Extract(jobid://) = 2 calls
- **Savings:** 60% reduction

**Verify Cache:**
```bash
sqlite3 backend/paperbase.db "
SELECT
  filename,
  reducto_job_id IS NOT NULL as has_job_id,
  reducto_parse_result IS NOT NULL as has_cache
FROM documents
WHERE status = 'completed';
"
```

**Success Criteria:**
- ✅ Only 2 Reducto API calls per document
- ✅ Logs show "Using pipelined extraction"
- ✅ Logs show "Using cached parse result"
- ✅ Database has job_id and parse_result cached

---

### Test 8: File Organization

**Objective:** Verify template-based folder structure

**Steps:**
1. Check folder structure:
```bash
find backend/uploads -type d
```

**Expected:**
```
backend/uploads/
backend/uploads/contract/
backend/uploads/invoice/
backend/uploads/unmatched/
```

2. Verify file locations:
```bash
ls -la backend/uploads/contract/
```

**Expected:** Contract documents should be in contract folder

3. Test organization function:
```bash
sqlite3 backend/paperbase.db "
SELECT filename, file_path
FROM documents
WHERE schema_id = 4;
"
```

**Success Criteria:**
- ✅ Template folders created
- ✅ Documents organized by template
- ✅ File paths updated in database
- ✅ Unmatched docs in /unmatched/

---

### Test 9: Error Handling

**Objective:** Test error scenarios and recovery

**Test Cases:**

**A. Invalid file upload:**
```bash
echo "corrupted" > /tmp/bad.pdf
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@/tmp/bad.pdf"
```
Expected: Error message, document marked as error

**B. Missing API key:**
```bash
# Temporarily unset key
unset REDUCTO_API_KEY
# Restart backend
# Try upload
```
Expected: Clear error message

**C. Elasticsearch down:**
```bash
# Stop Elasticsearch
docker-compose stop elasticsearch
# Try search
```
Expected: Graceful degradation, warning in logs

**Success Criteria:**
- ✅ Errors are caught and logged
- ✅ User-friendly error messages
- ✅ System doesn't crash
- ✅ Documents marked with error status
- ✅ Error messages stored in database

---

### Test 10: End-to-End Workflow

**Objective:** Complete bulk upload workflow from start to finish

**Steps:**

1. **Upload multiple documents:**
```bash
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@test_documents/invoice_001.txt" \
  -F "files=@test_documents/invoice_002.txt" \
  -F "files=@test_documents/receipt_001.txt"
```

2. **Review grouping:**
- Check that similar docs are grouped
- Verify template suggestions

3. **Confirm templates:**
```bash
curl -X POST http://localhost:8001/api/bulk/confirm-template \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": [32, 33],
    "template_id": 1
  }'
```

4. **Review in UI:**
- Navigate to confirmation page
- Check all fields populated
- Verify confidence scores

5. **Edit and verify:**
- Make corrections in UI
- Click "Confirm All"

6. **Search documents:**
- Try full-text search
- Try NL search
- Verify results

**Success Criteria:**
- ✅ All documents upload successfully
- ✅ Grouping makes sense
- ✅ Templates matched correctly
- ✅ Extractions accurate
- ✅ UI displays properly
- ✅ Verifications saved
- ✅ Search returns correct results
- ✅ Pipeline optimization used throughout

---

## 🧪 Performance Testing

### Load Test: Multiple Documents

```bash
# Create 10 test documents
for i in {1..10}; do
  cat > /tmp/contract_$i.txt << EOF
CONTRACT AGREEMENT $i
Effective Date: 2025-0$i-01
Party A: Company $i
Party B: Client $i
Value: \$$(($i * 1000))
EOF
done

# Upload all at once
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  $(for i in {1..10}; do echo -n "-F files=@/tmp/contract_$i.txt "; done)
```

**Metrics to Monitor:**
- Upload time
- Parse time per document
- Total processing time
- Memory usage
- API call count

**Expected:**
- Upload: <2 seconds
- Parse per doc: 4-6 seconds
- Total for 10 docs: <60 seconds
- Memory: Stable, no leaks

---

## 🐛 Common Issues & Solutions

### Issue 1: Port Already in Use
```
ERROR: Address already in use
```
**Solution:**
```bash
# Find process on port 8001
lsof -i :8001
# Kill it
kill -9 <PID>
```

### Issue 2: Elasticsearch Not Running
```
Connection refused to localhost:9200
```
**Solution:**
```bash
docker-compose up elasticsearch
```

### Issue 3: Frontend Can't Connect to Backend
**Solution:**
Check `.env` file has correct URL:
```
VITE_API_URL=http://localhost:8001
```
Restart frontend after changing.

### Issue 4: Extractions Not Showing
**Solution:**
1. Check document status: `sqlite3 backend/paperbase.db "SELECT * FROM documents WHERE id=X;"`
2. Check for errors: Look at `error_message` field
3. Check logs: `tail -f /tmp/paperbase_backend.log`
4. Verify API returns extracted_fields in response

### Issue 5: Pipeline Not Working
**Solution:**
1. Check logs for "Using pipelined extraction"
2. Verify `reducto_job_id` is populated
3. Check Reducto API status
4. Verify SDK version supports jobid://

---

## 📊 Test Results Template

Use this template to track your test results:

```
Date: ___________
Tester: ___________

[ ] Test 1: Template Management - PASS / FAIL
[ ] Test 2: Bulk Upload - PASS / FAIL
[ ] Test 3: Pipeline Extraction - PASS / FAIL
[ ] Test 4: Bulk Confirmation UI - PASS / FAIL
[ ] Test 5: Document Search - PASS / FAIL
[ ] Test 6: NL Search - PASS / FAIL
[ ] Test 7: Cost Optimization - PASS / FAIL
[ ] Test 8: File Organization - PASS / FAIL
[ ] Test 9: Error Handling - PASS / FAIL
[ ] Test 10: E2E Workflow - PASS / FAIL

Notes:
_________________________________
_________________________________
_________________________________
```

---

## 🎯 Acceptance Criteria

System is ready for demo/production when:

- [ ] All 10 tests pass
- [ ] No errors in logs during normal operation
- [ ] Pipeline optimization confirmed (60% API reduction)
- [ ] UI responsive and intuitive
- [ ] Search returns accurate results
- [ ] File organization working correctly
- [ ] Error handling graceful
- [ ] Documentation complete
- [ ] Performance acceptable (<15s per document)
- [ ] Cost targets met (<$2 per batch)

---

## 📝 Test Data

### Sample Documents

Create these test files for comprehensive testing:

**invoice_test.txt:**
```
INVOICE

Invoice #: INV-2025-001
Date: January 15, 2025
Due Date: February 15, 2025

Bill To: Acme Corp
From: Services Inc

Item: Consulting Services
Quantity: 10 hours
Rate: $150/hour
Subtotal: $1,500.00
Tax: $150.00
Total: $1,650.00
```

**receipt_test.txt:**
```
RECEIPT

Store: Coffee Shop
Date: January 15, 2025
Receipt #: 12345

Items:
- Coffee: $4.50
- Muffin: $3.00

Total: $7.50
Payment: Credit Card
```

**contract_test.txt:**
```
CONTRACT AGREEMENT

This agreement dated January 15, 2025

Party A: ABC Company
Party B: XYZ Services

Effective: January 15, 2025
Expires: December 31, 2025

Contract Value: $100,000
Payment Terms: Net 30
Termination: 60 days notice required
```

---

## 🔍 Debugging Tips

### Check Document Status
```bash
sqlite3 backend/paperbase.db "
SELECT id, filename, status, error_message
FROM documents
ORDER BY id DESC
LIMIT 10;
"
```

### View Recent Logs
```bash
tail -100 /tmp/paperbase_backend.log | grep ERROR
```

### Check Extracted Fields
```bash
sqlite3 backend/paperbase.db "
SELECT d.filename, ef.field_name, ef.field_value, ef.confidence_score
FROM documents d
JOIN extracted_fields ef ON d.id = ef.document_id
WHERE d.id = <document_id>;
"
```

### Monitor API Calls
```bash
tail -f /tmp/paperbase_backend.log | grep "HTTP Request"
```

### Check Pipeline Usage
```bash
grep -c "jobid://" /tmp/paperbase_backend.log
```

---

## 📚 Related Documentation

- `SYSTEM_STATUS.md` - Current system health
- `CLAUDE.md` - Project overview and architecture
- `PIPELINE_OPTIMIZATION.md` - Pipeline implementation details
- `TROUBLESHOOTING.md` - Common issues and solutions
- `README.md` - Setup instructions

---

**Last Updated:** 2025-10-10
**Version:** 2.0
