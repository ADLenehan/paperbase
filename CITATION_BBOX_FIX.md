# Citation & Bounding Box Fix

## Problem
PDF viewer in Audit page showed "No location data available" for all fields because `source_bbox` and `source_page` were `null`.

## Root Cause
Using **legacy Reducto API format** for citations:
- Old parameter: `generate_citations=True`
- Old response: Separate `citations` array at top level
- Result: Bbox data not being returned or parsed correctly

## Solution Applied

### 1. Updated API Parameter (Line 189)
```python
# OLD (legacy):
extract_kwargs = {
    "generate_citations": True
}

# NEW (current v3 format):
extract_kwargs = {
    "settings": {
        "citations": {
            "enabled": True
        }
    }
}
```

### 2. Updated Response Parsing (Lines 662-697)
Now correctly parses v3 format where citations are embedded in each field:

```python
# V3 Format:
{
    "field_name": {
        "value": "extracted text",
        "citations": [
            {
                "bbox": {
                    "left": 0.254,
                    "top": 0.234,
                    "width": 0.025,
                    "height": 0.006,
                    "page": 2
                },
                "confidence": "high",
                "content": "AWS",
                "type": "Text"
            }
        ]
    }
}
```

### 3. Added Debug Logging
Comprehensive logging to track:
- Citation availability check
- Bbox extraction per field
- Fields with/without bbox data

## Testing

### For New Documents
1. Upload a new PDF via Bulk Upload
2. Check backend logs for: `Field 'field_name' v3 citation: conf=high→0.9, page=2, bbox_keys=[...]`
3. Navigate to Audit page
4. Verify PDF highlights appear at correct locations

### For Existing Documents (Missing Bbox)
Existing documents like `2025.10.07_Pinecone BYOC Services Addendum.pdf` will **still have null bbox** because they were extracted with the old API.

**To get bbox data for these:**
1. **Option A - Re-extract:** Delete and re-upload the document
2. **Option B - Rematch:** Use the rematch endpoint to re-extract with new settings
3. **Option C - Accept:** Leave existing documents without bbox, new uploads will have it

## Verification Commands

```bash
# Check if new extractions have bbox
sqlite3 backend/paperbase.db "SELECT field_name, source_page, source_bbox FROM extracted_fields WHERE created_at > datetime('now', '-1 hour') LIMIT 5;"

# Check backend logs for citation parsing
docker logs paperbase_backend --tail 100 | grep "citation"
```

## Next Steps

1. **Test with new upload** - Upload a PDF and verify bbox appears
2. **Monitor logs** - Check for warnings about missing bbox
3. **Update existing docs** - Decide whether to re-extract documents without bbox
4. **Update requirements.txt** - Add comment about v3 API usage

## Files Modified
- `backend/app/services/reducto_service.py` - Lines 189-194, 662-697
- `docker-compose.yml` - Line 32 (volume mount fix)
- `backend/requirements.txt` - Line 22 (email-validator)

---

**Date**: 2025-11-06
**Status**: ✅ Applied, awaiting testing with new uploads
**Impact**: All future document uploads will have bbox/page data for PDF highlighting
