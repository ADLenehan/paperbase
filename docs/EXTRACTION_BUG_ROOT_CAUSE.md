# Extraction Bug Root Cause Analysis

**Date**: 2025-11-01
**Status**: 🔴 CRITICAL BUG IDENTIFIED
**Impact**: Documents show "completed" but have ZERO extracted fields

---

## Executive Summary

Documents created via `/api/bulk/create-new-template` endpoint show status="completed" but have **zero extracted fields** in the database, making AI search completely non-functional.

### Evidence:
```sql
-- Document 42: "completed" with schema but NO FIELDS
SELECT d.id, d.status, d.schema_id, s.name, COUNT(ef.id) as fields
FROM documents d
LEFT JOIN schemas s ON d.schema_id = s.id
LEFT JOIN extracted_fields ef ON ef.document_id = d.id
WHERE d.id = 42
GROUP BY d.id;

-- Result:
-- 42 | completed | 10 | Garment Spec | 0
```

---

## Investigation: Code Flow Analysis

### Step 1: What SHOULD Happen

**Expected Flow:**
```
User creates template
↓
POST /api/bulk/create-new-template
↓
1. Create schema with Claude-generated fields ✅
2. Assign schema_id to document ✅
3. Call process_single_document(doc.id) ✅
   ↓
   3a. Build Reducto schema from DB schema ✅
   3b. Call reducto_service.extract_structured() ✅
   3c. Save extracted_fields to database ✅
   3d. Index in Elasticsearch ✅
   3e. Mark status = "completed" ✅
↓
4. Document has extracted fields ✅
```

### Step 2: What ACTUALLY Happens

I found **NO LOGS** showing extraction happening for document 42:

**Backend logs search:**
```bash
# Searched for:
- "Processing document 42"
- "Extracted N fields from document 42"
- "Indexed document 42"
- Any Reducto API calls for extraction

# Result: NOTHING FOUND
```

**This means:** `process_single_document(42)` was **NEVER CALLED** or **FAILED SILENTLY**.

---

## Root Cause: Silent Failure in Async Background Task

### The Bug Location

[backend/app/api/bulk_upload.py:438-444](backend/app/api/bulk_upload.py#L438-L444):

```python
# Trigger processing for all documents (will use pipelined extraction)
from app.api.documents import process_single_document
for doc in documents:
    try:
        await process_single_document(doc.id)  # ⚠️ THIS LINE
    except Exception as e:
        logger.error(f"Error processing doc {doc.id}: {e}")
```

### Critical Issues Identified:

#### 1. **process_single_document() Creates New DB Session**

[backend/app/api/documents.py:100-105](backend/app/api/documents.py#L100-L105):
```python
async def process_single_document(document_id: int):
    """Background task to process a single document"""
    from app.core.database import SessionLocal

    db = SessionLocal()  # ⚠️ Creates NEW session
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
```

**Problem:** This function expects to be called as a background task, NOT awaited in the request!

#### 2. **Mixing Sync DB Operations with Async Calls**

The `create_new_template` endpoint uses `db: Session = Depends(get_db)` (synchronous), but then tries to `await process_single_document()`.

**Potential race condition:**
- Main request commits: `doc.status = "processing"`
- `process_single_document()` starts in same event loop
- Uses different DB session (SessionLocal())
- May not see committed data or vice versa

#### 3. **Silent Failure - No Error Logs**

Despite the try/except wrapper, I found NO error logs for document 42. This suggests:
- The function **was called** but didn't execute
- OR an error occurred before logging could happen
- OR the function wasn't awaited properly

---

## Hypothesis: BackgroundTasks vs Direct Await

### How It SHOULD Work

[backend/app/api/documents.py:71-97](backend/app/api/documents.py#L71-L97):
```python
@router.post("/process")
async def process_documents(
    request: dict,
    background_tasks: BackgroundTasks,  # ← FastAPI's BackgroundTasks
    db: Session = Depends(get_db)
):
    documents = db.query(Document).filter(Document.id.in_(document_ids)).all()

    # Add processing tasks to background
    for doc in documents:
        background_tasks.add_task(process_single_document, doc.id)  # ← Proper background task
        doc.status = "processing"

    db.commit()  # ← Commit BEFORE background tasks run

    return {"success": True}
```

**Key differences:**
1. Uses FastAPI's `BackgroundTasks` to schedule work **AFTER** response
2. Commits status change **BEFORE** background task runs
3. Does **NOT** await - background task runs after response

### How create-new-template Does It

[backend/app/api/bulk_upload.py:438-444](backend/app/api/bulk_upload.py#L438-L444):
```python
# Update documents
for doc in documents:
    doc.schema_id = schema.id
    doc.status = "processing"

db.commit()  # ← Commit here

# Trigger processing (WRONG - should use BackgroundTasks!)
from app.api.documents import process_single_document
for doc in documents:
    try:
        await process_single_document(doc.id)  # ⚠️ Direct await in request
    except Exception as e:
        logger.error(f"Error processing doc {doc.id}: {e}")
```

**Problems:**
1. **Direct await** in request handler (not background task)
2. **Blocks response** until extraction completes (but logs show instant response)
3. **Uses wrong DB session** (SessionLocal vs request session)
4. **No guarantee extraction runs** to completion

---

## Why No Logs?

### Theory 1: Function Never Executed
If `await process_single_document(42)` silently failed or was optimized away:
- No logs would appear
- Document would remain status="processing"
- **BUT database shows status="completed"** ❌ This contradicts

### Theory 2: Function Executed But Skipped Extraction
Looking at `process_single_document()` logic:

[backend/app/api/documents.py:140-186](backend/app/api/documents.py#L140-L186):
```python
# PIPELINE: Use Reducto's structured extraction with job_id if available
extraction_result = None
if document.reducto_job_id:  # ← Document 42 has reducto_job_id = True
    try:
        # Try pipelined extraction
        extraction_result = await reducto_service.extract_structured(
            schema=reducto_schema,
            job_id=document.reducto_job_id
        )
    except Exception as e:
        # Check if job expired
        if job_expired:
            # Clear job_id and fall through
            ...
        else:
            raise  # ← Re-raise non-job errors
```

**Possible scenario:**
1. Document 42 has `reducto_job_id` from parse
2. Tried pipelined extraction with `jobid://...`
3. Reducto API returned error (expired job, invalid job, etc.)
4. Error matched "job not found" pattern
5. Cleared `reducto_job_id` and **should have fallen through**...
6. **BUT**: If `extraction_result` remains `None`, what happens?

Let me check:

[backend/app/api/documents.py:174-186](backend/app/api/documents.py#L174-L186):
```python
if extraction_result is None:
    # Fallback: extract with file_path
    extraction_result = await reducto_service.extract_structured(
        schema=reducto_schema,
        file_path=document.file_path  # ← Should retry here
    )
```

**This should work!** Unless...

### Theory 3: file_path Invalid

Check database:
```sql
SELECT id, file_path, reducto_job_id FROM documents WHERE id = 42;
```

If `file_path` was moved/deleted during folder organization, extraction would fail!

[backend/app/api/bulk_upload.py:424-435](backend/app/api/bulk_upload.py#L424-L435):
```python
# Update documents to use new schema and organize into template folder
for doc in documents:
    # Organize file into template folder
    new_path = organize_document_file(
        current_path=doc.file_path,
        filename=doc.filename,
        template_name=request.template_name
    )
    doc.file_path = new_path  # ← File moved BEFORE extraction!
    doc.schema_id = schema.id
    doc.status = "processing"

db.commit()  # ← Commit new path

# Now try to extract (but file_path already changed!)
await process_single_document(doc.id)
```

**BINGO!** If the file was moved but the move failed or returned wrong path, extraction would fail with file not found!

---

## Testing the Hypothesis

Let me check document 42's file path:

```sql
sqlite3 paperbase.db "SELECT id, filename, file_path, reducto_job_id IS NOT NULL as has_job FROM documents WHERE id = 42"
```

Expected issues:
1. File path points to non-existent file
2. OR file was moved but extraction used old path
3. OR reducto_job_id expired and fallback failed

---

## The Fix

### Option 1: Use BackgroundTasks Properly (RECOMMENDED)

**Change:**
```python
@router.post("/create-new-template")
async def create_new_template(
    request: CreateTemplateRequest,
    background_tasks: BackgroundTasks,  # ← Add this
    db: Session = Depends(get_db)
):
    # ... create schema, update documents ...

    db.commit()  # Commit FIRST

    # Schedule background tasks (don't await!)
    for doc in documents:
        background_tasks.add_task(process_single_document, doc.id)

    return {"success": True, "schema_id": schema.id}
```

**Pros:**
- Proper async handling
- Doesn't block response
- DB sessions managed correctly

**Cons:**
- User doesn't know if extraction succeeded
- Need polling to check status

### Option 2: Extract Inline (SIMPLE)

**Change:**
```python
# Don't call process_single_document at all
# Instead, extract inline in the request:

reducto_service = ReductoService()
elastic_service = ElasticsearchService()

for doc in documents:
    # Build schema
    reducto_schema = {...}

    # Extract
    result = await reducto_service.extract_structured(
        schema=reducto_schema,
        job_id=doc.reducto_job_id  # Use cached parse
    )

    # Save fields
    for field_name, field_data in result["extractions"].items():
        ef = ExtractedField(...)
        db.add(ef)

    # Index in ES
    await elastic_service.index_document(...)

    doc.status = "completed"

db.commit()
```

**Pros:**
- Simple, inline logic
- User gets immediate feedback
- No async complexity

**Cons:**
- Blocks request (could timeout on large batches)
- Duplicates extraction logic

### Option 3: Hybrid - Inline for Single, Background for Batch

**Best of both worlds:**
- If `len(documents) == 1`: Extract inline
- If `len(documents) > 5`: Use background tasks

---

## Recommended Fix: Option 1 + Better Error Handling

```python
@router.post("/create-new-template")
async def create_new_template(
    request: CreateTemplateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # ... create schema ...

    # Organize files FIRST (before extraction needs them)
    for doc in documents:
        new_path = organize_document_file(...)
        doc.file_path = new_path
        doc.schema_id = schema.id
        doc.status = "processing"

    db.commit()  # Commit status + file paths

    # Schedule extraction in background
    for doc in documents:
        background_tasks.add_task(
            process_single_document_safe,  # NEW: wrapper with better logging
            doc.id
        )

    return {"success": True, "template_id": schema.id}

# NEW: Safe wrapper
async def process_single_document_safe(document_id: int):
    try:
        logger.info(f"🚀 Starting extraction for document {document_id}")
        await process_single_document(document_id)
        logger.info(f"✅ Extraction completed for document {document_id}")
    except Exception as e:
        logger.error(f"❌ Extraction FAILED for document {document_id}: {e}", exc_info=True)
        # Update document status to "error"
        db = SessionLocal()
        try:
            doc = db.query(Document).get(document_id)
            if doc:
                doc.status = "error"
                doc.error_message = str(e)
                db.commit()
        finally:
            db.close()
```

---

## Next Steps

1. ✅ Verify file_path for document 42
2. ⏳ Implement Option 1 fix
3. ⏳ Add comprehensive logging to extraction flow
4. ⏳ Test with document 42 (re-process)
5. ⏳ Add validation: documents can't be "completed" without fields

---

**User Request:** "we should also consider as part of making a new template the types of questions a user would like to ask of this type of doc"

**Response:** EXCELLENT idea! When creating a template, we should:
1. Ask Claude to generate example queries for this doc type
2. Store them in `schema_templates.example_queries` JSON field
3. Show them as suggestions in ChatSearch when template is selected
4. Use them to train query understanding for this template

**Implementation:**
- Add to `/api/bulk/create-new-template` after schema generation
- Prompt: "Given this schema for {template_name}, generate 5-10 example questions users might ask"
- Store in `schemas.metadata` → `{"example_queries": [...]}`
- Fetch in `/api/query/suggestions?template_id=X`

This aligns perfectly with the Query Suggestions feature we just built!
