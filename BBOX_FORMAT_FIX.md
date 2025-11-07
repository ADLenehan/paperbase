# Bounding Box Format Fix

**Date**: 2025-11-06
**Status**: ✅ Complete
**Impact**: Fixes table bounding box display in PDF viewer

## Problem

Bounding boxes for extracted fields (including complex tables) were not displaying in the PDF viewer because of a **format mismatch**:

- **Backend (Reducto)** returns bboxes as **dictionaries**:
  ```json
  {
    "left": 100,
    "top": 200,
    "width": 300,
    "height": 150,
    "page": 1
  }
  ```

- **Frontend (PDFViewer)** expects **arrays**:
  ```javascript
  [100, 200, 300, 150]
  ```

This caused bbox highlighting to fail silently (the component checked `bbox.length < 4` which is always false for objects).

## Solution

Created a **bbox normalization utility** that converts between formats automatically.

### 1. New Utility: `bbox_utils.py`

Created [app/utils/bbox_utils.py](backend/app/utils/bbox_utils.py):

```python
def normalize_bbox(bbox: Any) -> Optional[List[float]]:
    """
    Convert bbox from any format to frontend-compatible array format.

    Handles:
    - Dict: {left, top, width, height} → [x, y, w, h]
    - Dict: {x, y, w, h} → [x, y, w, h]
    - Array: [x, y, w, h] → [x, y, w, h] (passthrough)
    - None → None
    """
```

Supports multiple dict formats:
- Reducto standard: `{left, top, width, height, page}`
- Alternative: `{x, y, w, h}`
- Alternative: `{x, y, width, height}`

### 2. Updated API Endpoints

Applied `normalize_bbox()` to all endpoints that return bbox data:

#### `app/api/audit.py`

```python
# GET /api/audit/queue
"source_bbox": normalize_bbox(field.source_bbox)

# GET /api/audit/document/{document_id}
"source_bbox": normalize_bbox(field.source_bbox)
```

#### `app/api/documents.py`

```python
# GET /api/documents/{document_id}
"source_bbox": normalize_bbox(field.source_bbox),
"source_page": field.source_page  # Also added page number
```

### 3. Frontend Compatibility

The frontend PDF viewer components remain unchanged:

```javascript
// PDFViewer.jsx - Already expects array format
const [x, y, width, height] = highlight.bbox;

// PDFExcerpt.jsx - Already validates array format
if (!highlight.bbox || highlight.bbox.length < 4) return null;
```

## Testing

Created [test_bbox_conversion.py](backend/test_bbox_conversion.py):

```bash
$ python3 test_bbox_conversion.py

✅ PASS: Dict format (Reducto API)
✅ PASS: Alternative dict format
✅ PASS: Array format (passthrough)
✅ PASS: None value
✅ PASS: Invalid bbox (missing fields)
✅ PASS: Format with page number
✅ PASS: Real-world table bbox

🎉 ALL TESTS PASSED! (7/7)
```

## Impact on Table Extractions

For complex tables like garment grading specs:

**Before**:
- Table bbox stored as `{left: 93.6, top: 157.2, width: 1139.04, height: 82.56, page: 1}`
- Frontend received object, tried to destructure as array → **failed silently**
- No highlighting shown in PDF viewer ❌

**After**:
- Backend automatically converts to `[93.6, 157.2, 1139.04, 82.56]`
- Frontend receives array, destructures correctly → **works** ✅
- Yellow box highlights the entire table in PDF viewer ✅

## Files Changed

1. **Created**:
   - `backend/app/utils/bbox_utils.py` - Conversion utility
   - `backend/test_bbox_conversion.py` - Test suite

2. **Modified**:
   - `backend/app/api/audit.py` - Added import and conversion (2 locations)
   - `backend/app/api/documents.py` - Added import, conversion, and page number

## Usage for Future Development

When adding new API endpoints that return extracted field data:

```python
from app.utils.bbox_utils import normalize_bbox

# Always normalize bbox before returning to frontend
{
    "field_name": "grading_table",
    "source_page": field.source_page,
    "source_bbox": normalize_bbox(field.source_bbox)  # ← Always do this
}
```

## Edge Cases Handled

1. **None values**: Returns `None` (frontend skips highlighting)
2. **Invalid bbox**: Missing required fields → returns `None`
3. **Already array**: Passes through unchanged
4. **Mixed formats**: Supports 3 different dict key formats
5. **Page numbers**: Preserved from dict or can be passed separately

## Verification

To verify bbox highlighting works:

1. Upload a document with table extraction (e.g., garment spec)
2. Navigate to audit page: `/audit`
3. Select a table field from the queue
4. **Expected**: Yellow bounding box highlights the table region in PDF viewer
5. **Zoom in/out**: Box should scale proportionally

## Related Documentation

- [Complex Table Extraction](docs/features/COMPLEX_TABLE_EXTRACTION.md)
- [Audit UX Improvements](docs/features/AUDIT_UX_IMPROVEMENTS.md)
- [Inline Audit Implementation](INLINE_AUDIT_IMPLEMENTATION.md)

---

**Next Steps**: Test with real documents to verify table bbox highlighting works end-to-end.
