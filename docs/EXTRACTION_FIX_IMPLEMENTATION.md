# Extraction Fix Implementation

**Date**: 2025-11-01
**Bug**: Reducto extraction returns zero fields
**Root Cause**: Schema format doesn't include extraction hints

---

## Root Cause Identified ✅

### The Smoking Gun

Backend logs show:
```
2025-11-01 20:51:55,206 - Using pipelined extraction with job_id: a5a49f40...
2025-11-01 20:51:55,206 - Extracted 0 fields from document 42
```

**Reducto was called successfully** but returned **empty extractions**.

### Why Extraction Failed

Current code builds schema like this:

```python
reducto_schema = {
    "type": "object",
    "properties": {
        "style_number": {
            "type": "string",
            "description": "Product style identifier code"
        },
        "season": {
            "type": "string",
            "description": "Product season and year"
        }
        # ... etc
    }
}
```

**Problem**: Our database schema has rich `extraction_hints` but we're **NOT passing them to Reducto**!

Database schema field:
```json
{
  "name": "style_number",
  "type": "text",
  "required": true,
  "extraction_hints": [  // ← WE'RE IGNORING THESE!
    "Style No:",
    "Style No",
    "GLNLEG"
  ],
  "confidence_threshold": 0.9,
  "description": "Product style identifier code"
}
```

### Reducto API Expected Format

Based on Reducto docs, the extraction schema should include hints about WHERE to find values:

```python
# What we SHOULD send:
reducto_schema = {
    "type": "object",
    "properties": {
        "style_number": {
            "type": "string",
            "description": "Product style identifier code. Look for 'Style No:' or 'Style No' labels.",
            #  ↑ Include extraction hints in description!
        }
    }
}
```

OR use Reducto's prompt-based extraction:
```python
{
    "style_number": "Extract the style number (look for 'Style No:' or similar labels)"
}
```

---

## The Fix

### Option 1: Include Hints in Description (RECOMMENDED)

Modify [backend/app/api/documents.py:117-138](backend/app/api/documents.py#L117-L138):

```python
# Build Reducto schema from our schema fields
reducto_schema = {
    "type": "object",
    "properties": {}
}

for field_def in schema.fields:
    field_name = field_def["name"]
    field_type = field_def.get("type", "string")

    json_type = {
        "text": "string",
        "date": "string",
        "number": "number",
        "boolean": "boolean"
    }.get(field_type, "string")

    # Build rich description with extraction hints
    description = field_def.get("description", "")
    extraction_hints = field_def.get("extraction_hints", [])

    if extraction_hints:
        hints_text = ", ".join(f'"{hint}"' for hint in extraction_hints[:3])
        description = f"{description}. Look for labels like: {hints_text}"

    reducto_schema["properties"][field_name] = {
        "type": json_type,
        "description": description
    }
```

**Result:**
```json
{
  "style_number": {
    "type": "string",
    "description": "Product style identifier code. Look for labels like: \"Style No:\", \"Style No\", \"GLNLEG\""
  }
}
```

### Option 2: Use Reducto's Prompt Format

Check if Reducto supports a simpler prompt-based format:

```python
reducto_schema = {}
for field_def in schema.fields:
    field_name = field_def["name"]
    description = field_def.get("description", "")
    hints = field_def.get("extraction_hints", [])

    prompt = f"{description}"
    if hints:
        prompt += f" (look for: {', '.join(hints[:2])})"

    reducto_schema[field_name] = prompt
```

**Need to verify**: Does Reducto accept both JSON Schema AND simple dict format?

---

## Implementation Plan

### Step 1: Fix Schema Building Logic

**File**: [backend/app/api/documents.py](backend/app/api/documents.py#L117-L138)

**Change**:
```python
for field_def in schema.fields:
    field_name = field_def["name"]
    field_type = field_def.get("type", "string")
    description = field_def.get("description", "")
    extraction_hints = field_def.get("extraction_hints", [])

    # Map types
    json_type = {
        "text": "string",
        "date": "string",
        "number": "number",
        "boolean": "boolean"
    }.get(field_type, "string")

    # Enhance description with extraction hints
    if extraction_hints:
        # Add first 3 hints to description
        hints_text = ", ".join(f'"{hint}"' for hint in extraction_hints[:3])
        enhanced_description = f"{description}. Look for labels or patterns like: {hints_text}"
    else:
        enhanced_description = description

    reducto_schema["properties"][field_name] = {
        "type": json_type,
        "description": enhanced_description
    }

    logger.debug(f"Field '{field_name}': {enhanced_description}")
```

### Step 2: Add Debug Logging

**Add before extraction call**:
```python
logger.info(f"Extraction schema for {document.filename}:")
logger.info(f"  Fields: {list(reducto_schema['properties'].keys())}")
logger.info(f"  Sample field: {list(reducto_schema['properties'].values())[0]}")
```

### Step 3: Test with Document 42

1. Re-trigger processing: `POST /api/documents/process {"document_ids": [42]}`
2. Check logs for schema details
3. Verify extraction returns fields
4. Check database: `SELECT COUNT(*) FROM extracted_fields WHERE document_id = 42`

### Step 4: Handle Empty Results

**Add validation** [after extraction, line ~190](backend/app/api/documents.py#L190):

```python
extractions = extraction_result.get("extractions", {})

if not extractions or len(extractions) == 0:
    logger.warning(
        f"⚠️  Reducto returned ZERO fields for {document.filename}. "
        f"Schema had {len(reducto_schema['properties'])} fields. "
        f"This may indicate schema format issues or document content mismatch."
    )

    # Log full schema for debugging
    logger.debug(f"Schema sent to Reducto: {json.dumps(reducto_schema, indent=2)}")

    # Still mark as completed but flag for review
    document.status = "completed"
    document.error_message = "Extraction returned zero fields - manual review needed"
else:
    logger.info(f"✅ Extracted {len(extractions)} fields from {document.filename}")
```

---

## Testing Protocol

### 1. Add Detailed Logging

Modify [backend/app/services/reducto_service.py:166-186](backend/app/services/reducto_service.py#L166-L186):

```python
# Extract using the document URL
logger.info(f"Calling Reducto extract with schema: {list(schema.get('properties', {}).keys())}")

extract_response = await asyncio.to_thread(
    self.client.extract.run,
    document_url=document_url,
    schema=schema
)

result = extract_response.result if hasattr(extract_response, 'result') else extract_response
raw_extractions = result if isinstance(result, list) else result.get("extractions", {})

logger.info(f"Reducto response type: {type(raw_extractions)}")
logger.info(f"Reducto response length: {len(raw_extractions) if isinstance(raw_extractions, (list, dict)) else 0}")

if raw_extractions:
    logger.debug(f"First extraction: {list(raw_extractions.items())[0] if isinstance(raw_extractions, dict) else raw_extractions[0]}")
else:
    logger.warning(f"⚠️  Reducto returned empty extractions for schema with {num_fields} fields")
```

### 2. Manual Test Script

Create test script to isolate issue:

```python
# test_extraction.py
import asyncio
from app.services.reducto_service import ReductoService
from app.models.document import Document
from app.core.database import SessionLocal

async def test_doc_42():
    db = SessionLocal()
    doc = db.query(Document).get(42)

    # Test schema
    schema = {
        "type": "object",
        "properties": {
            "style_number": {
                "type": "string",
                "description": "Product style identifier. Look for 'Style No:', 'Style No', or codes like 'GLNLEG'"
            },
            "season": {
                "type": "string",
                "description": "Product season and year. Look for 'Season', patterns like 'SPRING 2024'"
            }
        }
    }

    reducto = ReductoService()
    result = await reducto.extract_structured(
        schema=schema,
        job_id=doc.reducto_job_id
    )

    print(f"Extractions: {result['extractions']}")
    print(f"Field count: {len(result['extractions'])}")

if __name__ == "__main__":
    asyncio.run(test_doc_42())
```

### 3. Verify Fix

```bash
# Run test
cd backend
source venv/bin/activate
python test_extraction.py

# Expected output:
# Extractions: {'style_number': {'value': 'GLNLEG', 'confidence': 0.95, ...}, ...}
# Field count: 2
```

---

## Alternative: Check Reducto API Format

If hints in description don't work, we may need to check Reducto's actual API format:

### Hypothesis 1: Reducto Uses Different Schema Format

From Reducto SDK source, check if they expect:
- OpenAPI/JSON Schema format (what we're using)
- Custom format with explicit `hints` field
- Prompt-based string format

### Hypothesis 2: Field Names Must Match Document Text

Maybe Reducto expects field names to match actual text labels?

**Test**: Try renaming fields to match hints:
```python
{
    "Style No": "string",  # ← Use label as field name
    "Season": "string"
}
```

---

## User Request: Template-Specific Queries

> "we should also consider as part of making a new template the types of questions a user would like to ask of this type of doc"

**Implementation**:

1. **Generate Example Queries** in `/api/bulk/create-new-template`:

```python
# After schema creation
example_queries = await claude_service.generate_example_queries(
    template_name=request.template_name,
    fields=schema_data["fields"],
    sample_text=doc_text
)

# Store in schema metadata
schema.metadata = {
    "example_queries": example_queries,
    "created_from_documents": [doc.id for doc in documents],
    "field_count": len(schema_data["fields"])
}
db.commit()
```

2. **Claude Prompt**:

```python
async def generate_example_queries(self, template_name: str, fields: List[Dict], sample_text: str) -> List[str]:
    """Generate example queries users might ask for this template"""

    field_names = [f["name"] for f in fields]

    prompt = f'''Given a document template called "{template_name}" with these fields:
{json.dumps(field_names, indent=2)}

Generate 8-10 example natural language questions users might ask when searching these documents.

Examples should cover:
- Finding specific field values ("Show me garments with style GLNLEG")
- Filtering by ranges ("Find all Spring 2024 products")
- Aggregations ("How many carryover vs new products?")
- Comparisons ("Which designers have the most adopted styles?")
- Status queries ("Show me all documents pending review")

Return as JSON array of strings.'''

    response = await self._call_claude(prompt, max_tokens=800)
    return json.loads(response)["queries"]
```

3. **Return in `/api/query/suggestions`**:

```python
@router.get("/suggestions")
async def get_query_suggestions(
    template_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    if template_id:
        schema = db.query(Schema).get(template_id)
        if schema and schema.metadata:
            return schema.metadata.get("example_queries", [])

    # Generic fallback
    return [
        "Show documents from last month",
        "Find high confidence extractions",
        ...
    ]
```

---

## Next Actions

1. ✅ Root cause identified: Missing extraction hints in Reducto schema
2. ⏳ Implement schema building fix
3. ⏳ Add comprehensive logging
4. ⏳ Test with document 42
5. ⏳ Verify fields are extracted
6. ⏳ Implement example query generation
7. ⏳ Update documentation

**Priority**: P0 - Blocks all extraction functionality
**Estimated Time**: 30 minutes to fix + test
