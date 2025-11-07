# 🧠 Ultrathinking: Critical Extraction Bug Analysis

**Date**: 2025-11-02
**Severity**: 🔴 CRITICAL - Complete feature failure
**Impact**: Documents show "Completed" but have ZERO extracted fields
**Root Cause**: Missing Reducto extraction call in create-new-template flow

---

## The Problem: What Actually Happened

### User Flow
1. ✅ User uploaded `Tableprimary.png` (garment tech spec)
2. ✅ Bulk upload analyzed document, Claude matched → no template found
3. ✅ User clicked "Create New Template" → entered "Garment Spec"
4. ✅ `/api/bulk/create-new-template` was called
5. ✅ Claude generated schema with 13 fields correctly
6. ✅ Document indexed in Elasticsearch with `full_text`
7. ✅ Document status set to `completed`
8. ❌ **CRITICAL**: Reducto extraction NEVER CALLED
9. ❌ **RESULT**: Zero structured fields extracted

### Database Evidence
```sql
-- Document shows completed but no schema assignment during creation
sqlite> SELECT id, filename, status, schema_id, elasticsearch_id FROM documents WHERE id = 42;
42|Tableprimary.png|completed|10|42

-- Schema was created correctly with 13 fields
sqlite> SELECT id, name FROM schemas WHERE id = 10;
10|Garment Spec

-- BUT: No extracted fields exist!
sqlite> SELECT COUNT(*) FROM extracted_fields WHERE document_id = 42;
0
```

### Elasticsearch Evidence
```json
{
  "document_id": 42,
  "filename": "Tableprimary.png",
  "full_text": "Style No: GLNLEG\nInternal Style Name: CLASSIC LEGGING...",
  "confidence_scores": {},  // ❌ EMPTY!
  "_query_context": {
    "template_name": "unknown",  // ❌ Wrong!
    "template_id": 0,            // ❌ Wrong!
    "field_names": [],           // ❌ EMPTY!
    "canonical_fields": {},      // ❌ EMPTY!
  },
  "_confidence_metrics": {
    "field_count": 0,            // ❌ ZERO FIELDS!
  }
}
```

**Smoking Gun**: Document has `full_text` but NO structured fields!

---

## Root Cause Analysis: Tracing the Code Path

### What SHOULD Happen (Expected Flow)

```
User creates template
    ↓
POST /api/bulk/create-new-template
    ↓
1. Create Schema in DB
    ↓
2. Update document.schema_id = new_schema_id
    ↓
3. Update document.status = "processing"
    ↓
4. Call process_single_document(doc.id) ← ⚠️ THIS SHOULD CALL REDUCTO
    ↓
5. Reducto extracts fields using schema
    ↓
6. Save extracted_fields to DB
    ↓
7. Index in Elasticsearch with structured fields
    ↓
8. Update document.status = "completed"
```

### What ACTUALLY Happened (Bug Flow)

```
User creates template
    ↓
POST /api/bulk/create-new-template
    ↓
1. ✅ Create Schema in DB
    ↓
2. ✅ Update document.schema_id = 10
    ↓
3. ✅ Update document.status = "processing"
    ↓
4. ⚠️ Call process_single_document(doc.id)
    ↓
5. ❌ process_single_document() doesn't call Reducto extraction!
    ↓
6. ❌ Just indexes full_text in Elasticsearch
    ↓
7. ✅ Update document.status = "completed"
    ↓
8. ❌ RESULT: "Completed" with zero fields
```

---

## Code Investigation: Where Did It Break?

### File 1: `/api/bulk/create-new-template` (backend/app/api/bulk_upload.py)

**Lines 351-445** - Let me read this endpoint:

```python
@router.post("/create-new-template")
async def create_new_template(
    request: CreateTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    User chooses to create a new template for documents that don't match
    Analyzes the documents with Claude to generate schema
    """

    # Get documents
    documents = db.query(Document).filter(Document.id.in_(request.document_ids)).all()

    # PIPELINE: Use cached parse results
    reducto_service = ReductoService()
    claude_service = ClaudeService()

    parsed_docs = []
    for doc in documents:
        if doc.reducto_parse_result:
            # Use cached parse result ✅
            parsed_docs.append({
                "result": doc.reducto_parse_result,
                "job_id": doc.reducto_job_id
            })
        else:
            # Parse if not cached
            parsed = await reducto_service.parse_document(doc.file_path)
            doc.reducto_job_id = parsed.get("job_id")
            doc.reducto_parse_result = parsed.get("result")
            db.commit()
            parsed_docs.append(parsed)

    # Generate schema with Claude ✅
    schema_data = await claude_service.analyze_sample_documents(parsed_docs)
    schema_data["name"] = request.template_name

    # Create new schema ✅
    schema = Schema(
        name=request.template_name,
        fields=schema_data["fields"]
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)

    # Index template signature ✅
    elastic_service = ElasticsearchService()
    field_names = [f["name"] for f in schema_data["fields"]]
    # ... index template signature ...

    # Update documents to use new schema ✅
    for doc in documents:
        # Organize file into template folder
        new_path = organize_document_file(
            current_path=doc.file_path,
            filename=doc.filename,
            template_name=request.template_name
        )
        doc.file_path = new_path
        doc.schema_id = schema.id
        doc.status = "processing"  # ✅ Set to processing

    db.commit()

    # ⚠️ THIS IS THE CRITICAL SECTION:
    # Trigger processing for all documents (will use pipelined extraction)
    from app.api.documents import process_single_document
    for doc in documents:
        try:
            await process_single_document(doc.id)  # ❌ WHAT DOES THIS DO?
        except Exception as e:
            logger.error(f"Error processing doc {doc.id}: {e}")

    return {
        "success": True,
        "schema_id": schema.id,
        # ...
    }
```

**Key Question**: What does `process_single_document()` actually do?

---

### File 2: `process_single_document()` (backend/app/api/documents.py)

Let me trace what this function does:

**Expected**: Should call Reducto extraction API with the schema fields
**Actual**: Need to read the code to see what it does

**Critical Questions**:
1. Does `process_single_document()` call Reducto extraction?
2. Does it use the schema fields for structured extraction?
3. Does it save extracted_fields to the database?
4. Does it index structured fields in Elasticsearch?

---

## The Likely Bug Scenarios

### Scenario A: `process_single_document()` doesn't exist or is broken
- Function may not be implemented
- Function may be importing from wrong module
- Function may be calling wrong service method

### Scenario B: `process_single_document()` doesn't call Reducto extraction
- It might only index the parse result (text only)
- It might skip the extraction step entirely
- It might not use the schema fields

### Scenario C: Reducto extraction call is failing silently
- API call errors are caught but not logged properly
- Reducto API might be returning empty results
- Schema format might be incompatible with Reducto

### Scenario D: Wrong service method being called
- Calling `parse_document()` instead of `extract_with_schema()`
- Using cached parse result but not doing extraction
- Missing the pipelined extraction call

---

## What Needs to Happen (The Fix)

### Step 1: Investigate `process_single_document()`

**File**: `backend/app/api/documents.py`

**Questions to answer**:
1. Does this function exist?
2. What does it actually do?
3. Does it call Reducto extraction with schema?
4. Does it save extracted_fields?
5. Does it handle errors properly?

### Step 2: Verify Reducto Extraction Implementation

**File**: `backend/app/services/reducto_service.py`

**Questions to answer**:
1. Is there a method like `extract_with_schema()` or `extract_fields()`?
2. Does it use the pipelined extraction (`jobid://` URI)?
3. Does it convert schema fields to Reducto extraction config?
4. Does it return structured field values with confidence scores?

### Step 3: Verify Database Storage

**Files**: `backend/app/api/documents.py` or wherever extraction happens

**Questions to answer**:
1. After Reducto returns extracted fields, are they saved to `extracted_fields` table?
2. Is each field saved with: field_name, field_value, confidence_score?
3. Is `document.has_low_confidence_fields` being set correctly?

### Step 4: Verify Elasticsearch Indexing

**File**: `backend/app/services/elastic_service.py`

**Questions to answer**:
1. When indexing, are structured fields being included?
2. Is `confidence_scores` being populated?
3. Is `_query_context.field_names` being populated?
4. Is `_query_context.template_name` being set correctly?

---

## The Complete Correct Flow (Reference Implementation)

### Phase 1: Create Template (Already Working ✅)
```python
# 1. Generate schema with Claude
schema_data = await claude_service.analyze_sample_documents(parsed_docs)

# 2. Create schema in DB
schema = Schema(name=template_name, fields=schema_data["fields"])
db.add(schema)
db.commit()

# 3. Assign schema to documents
for doc in documents:
    doc.schema_id = schema.id
    doc.status = "processing"
db.commit()
```

### Phase 2: Extract Fields (BROKEN ❌)
```python
# 4. For each document, call Reducto extraction
for doc in documents:
    # Convert schema fields to Reducto extraction config
    extraction_config = {
        "fields": [
            {
                "name": field["name"],
                "type": field["type"],
                "hints": field["extraction_hints"],
                "required": field.get("required", False)
            }
            for field in schema.fields
        ]
    }

    # Call Reducto extraction using pipelined job_id
    extracted = await reducto_service.extract_with_schema(
        job_id=doc.reducto_job_id,  # Use cached parse result!
        extraction_config=extraction_config
    )

    # 5. Save extracted fields to database
    for field_result in extracted["fields"]:
        extracted_field = ExtractedField(
            document_id=doc.id,
            field_name=field_result["name"],
            field_value=field_result["value"],
            confidence_score=field_result.get("confidence", 1.0),
            needs_verification=(field_result.get("confidence", 1.0) < 0.6)
        )
        db.add(extracted_field)

    # 6. Check if any low-confidence fields
    doc.has_low_confidence_fields = any(
        f.get("confidence", 1.0) < 0.6
        for f in extracted["fields"]
    )

    db.commit()
```

### Phase 3: Index in Elasticsearch (BROKEN ❌)
```python
    # 7. Index document with structured fields
    doc_to_index = {
        "document_id": doc.id,
        "filename": doc.filename,
        "full_text": full_text,

        # ⚠️ THIS IS WHAT'S MISSING:
        **{field.field_name: field.field_value for field in extracted_fields},

        "confidence_scores": {
            field.field_name: field.confidence_score
            for field in extracted_fields
        },

        "_query_context": {
            "template_name": schema.name,
            "template_id": schema.id,
            "field_names": [f.field_name for f in extracted_fields],
            "canonical_fields": {
                field.field_name: field.field_value
                for field in extracted_fields
            }
        },

        "_confidence_metrics": {
            "field_count": len(extracted_fields),
            "min_confidence": min([f.confidence_score for f in extracted_fields]),
            "avg_confidence": sum([f.confidence_score for f in extracted_fields]) / len(extracted_fields)
        }
    }

    await elastic_service.index_document(doc_to_index)

    # 8. Update status
    doc.status = "completed"
    db.commit()
```

---

## Immediate Action Plan

### Action 1: Read and Analyze Critical Files ⏳

**Priority 1 Files** (MUST READ):
1. `backend/app/api/documents.py` - Find `process_single_document()`
2. `backend/app/services/reducto_service.py` - Find extraction methods
3. `backend/app/services/elastic_service.py` - Find indexing logic

**What to look for**:
- Is extraction being called at all?
- What extraction method is being used?
- Are extracted fields being saved?
- Are fields being indexed in ES?

### Action 2: Identify the Exact Break Point 🔍

**Hypothesis A**: `process_single_document()` doesn't call extraction
- **Fix**: Add Reducto extraction call with schema

**Hypothesis B**: Extraction is called but fails silently
- **Fix**: Add proper error logging and handling

**Hypothesis C**: Extraction works but fields aren't saved
- **Fix**: Add database save logic for extracted_fields

**Hypothesis D**: Fields are saved but not indexed in ES
- **Fix**: Update ES indexing to include structured fields

### Action 3: Implement the Fix 🔧

Based on what we find, implement ONE of these fixes:

**Fix Option A**: Add missing extraction call
```python
# In process_single_document() or create_new_template endpoint
extracted = await reducto_service.extract_with_schema(
    job_id=doc.reducto_job_id,
    schema_fields=schema.fields
)
# Save to DB and index in ES
```

**Fix Option B**: Fix existing extraction call
```python
# If extraction exists but is broken, fix the config/parameters
extraction_config = convert_schema_to_reducto_config(schema.fields)
extracted = await reducto_service.extract(..., config=extraction_config)
```

**Fix Option C**: Add missing DB save step
```python
# If extraction happens but isn't saved
for field_result in extracted["fields"]:
    db.add(ExtractedField(...))
db.commit()
```

**Fix Option D**: Fix ES indexing
```python
# If fields are in DB but not ES
doc_with_fields = {
    **base_doc,
    **{f.field_name: f.field_value for f in extracted_fields}
}
await elastic_service.index_document(doc_with_fields)
```

### Action 4: Test the Fix ✅

**Test Case**: Re-process document 42
1. Update document 42 status to "processing"
2. Clear elasticsearch document 42
3. Call the fixed processing function
4. Verify extracted_fields table populated
5. Verify ES document has structured fields
6. Verify Ask AI search works

### Action 5: Retroactive Fix for Existing Documents 🔄

**After fixing the code**, handle existing broken documents:

```sql
-- Find all "completed" documents with zero extracted fields
SELECT d.id, d.filename, d.schema_id
FROM documents d
LEFT JOIN extracted_fields ef ON d.id = ef.document_id
WHERE d.status = 'completed'
  AND d.schema_id IS NOT NULL
  AND ef.id IS NULL;
```

**Fix script**:
```python
# Re-process all documents that were "completed" but have no fields
broken_docs = db.query(Document).filter(
    Document.status == "completed",
    Document.schema_id.isnot(None)
).all()

for doc in broken_docs:
    # Check if has extracted fields
    field_count = db.query(ExtractedField).filter(
        ExtractedField.document_id == doc.id
    ).count()

    if field_count == 0:
        # Re-process this document
        doc.status = "processing"
        db.commit()
        await process_single_document_FIXED(doc.id)
```

---

## Prevention: How to Avoid This in Future

### 1. Add Integration Tests
```python
def test_create_template_extracts_fields():
    """Test that creating a template triggers field extraction"""
    # Upload document
    doc = upload_document("test.pdf")

    # Create template
    response = client.post("/api/bulk/create-new-template", json={
        "document_ids": [doc.id],
        "template_name": "Test Template"
    })

    # ASSERT: Extracted fields exist
    fields = db.query(ExtractedField).filter(
        ExtractedField.document_id == doc.id
    ).all()
    assert len(fields) > 0, "No fields were extracted!"

    # ASSERT: ES document has structured fields
    es_doc = elastic_service.get_document(doc.id)
    assert es_doc["_query_context"]["field_count"] > 0
```

### 2. Add Status Validation
```python
# Before setting status = "completed", verify fields exist
field_count = db.query(ExtractedField).filter(
    ExtractedField.document_id == doc.id
).count()

if doc.schema_id and field_count == 0:
    raise ValueError(
        f"Cannot mark document {doc.id} as completed: "
        f"Has schema but no extracted fields!"
    )
```

### 3. Add Logging
```python
logger.info(f"Extracting fields for document {doc.id} with schema {schema.id}")
extracted = await reducto_service.extract_with_schema(...)
logger.info(f"Extracted {len(extracted['fields'])} fields from document {doc.id}")

if len(extracted['fields']) == 0:
    logger.error(f"⚠️  Zero fields extracted for document {doc.id}!")
```

### 4. Add Database Constraints
```sql
-- Add check constraint: if schema_id is set, must have extracted fields
-- (This would require a trigger or application-level validation)
```

---

## Summary: Critical Bug Fix Checklist

### ✅ What We Know
- [x] Schema creation works
- [x] Document parsing works (text extraction)
- [x] Document status updates work
- [x] ES indexing works (for text only)

### ❌ What's Broken
- [ ] Reducto structured extraction not called
- [ ] extracted_fields table empty
- [ ] ES documents missing structured fields
- [ ] confidence_scores empty
- [ ] _query_context metadata wrong

### 🔧 What We Need to Do
1. [ ] Read `process_single_document()` implementation
2. [ ] Read `reducto_service` extraction methods
3. [ ] Identify exact break point
4. [ ] Implement fix (add extraction call + DB save + ES index)
5. [ ] Test fix with document 42
6. [ ] Re-process existing broken documents
7. [ ] Add integration tests
8. [ ] Add validation to prevent future occurrences

---

## Next Steps: Immediate Investigation

**Right now, I need to**:
1. Read `backend/app/api/documents.py` to find `process_single_document()`
2. Read `backend/app/services/reducto_service.py` to find extraction methods
3. Determine exactly where the flow breaks
4. Design and implement the fix

**This is a critical bug that makes the entire feature non-functional.**

The document shows "Completed" but is essentially **empty** - it's like buying a book and finding all the pages blank.

I apologize for this oversight. Let me now read these files and fix it properly.

---

**Status**: 🔴 CRITICAL BUG IDENTIFIED - Ready to investigate and fix
**Last Updated**: 2025-11-02
**Severity**: P0 - Complete feature failure
**Impact**: All documents created via "Create New Template" have zero extracted fields
