# Bbox Coordinate Scaling Fix - Verification Status

## ✅ Fixes Completed

### 1. Frontend Coordinate Scaling (COMPLETE)
**Files Modified:**
- `frontend/src/components/DocumentViewer.jsx`
- `frontend/src/components/PDFViewer.jsx`

**Changes:**
- Added `pageHeight` state variable to track actual PDF dimensions
- Capture real page dimensions on PDF load: `viewport.getViewport({ scale: 1 })`
- Scale normalized [0-1] coordinates to pixels:
  ```javascript
  const pixelX = x * pageWidth;      // 0.318 × 612 = 194px
  const pixelY = y * pageHeight;     // 0.388 × 792 = 307px
  const pixelWidth = width * pageWidth;
  const pixelHeight = height * pageHeight;
  ```

### 2. Backend Citation API v3 (COMPLETE)
**File:** `backend/app/services/reducto_service.py`

**Changes:**
- Updated to parse v3 embedded citations (lines 662-697)
- Handles new format: `{"value": "...", "citations": [...]}`
- Extracts bbox from nested citation structure
- Falls back to legacy format for backwards compatibility

## 📊 Database Verification

**Document 74** - "(9) Andrew Lenehan _ LinkedIn.pdf"
- **Status**: Has bbox data ✅
- **Format**: Normalized coordinates (correct!)
- **Example Fields**:
  ```json
  {
    "field_name": "first_name",
    "value": "Andrew",
    "source_page": 1,
    "source_bbox": {
      "left": 0.31774848398536143,   // 31.8% from left
      "top": 0.3880651137408088,      // 38.8% from top (MIDDLE of page!)
      "width": 0.05687744448883364,   // 5.7% width
      "height": 0.01589033338758683,  // 1.6% height
      "page": 1
    }
  }
  ```

## 🎯 Expected Behavior

With a standard PDF page (612×792 pixels):
- **Normalized**: `left: 0.318, top: 0.388`
- **Scaled to Pixels**: `left: 194px, top: 307px`
- **Visual Position**: About 1/3 from left, 2/5 down page (middle area) ✅

This matches the user's description: "Andrew in the middle of the page"

## 🧪 Testing Checklist

### Before Testing
- [ ] Start backend: `cd backend && uvicorn app.main:app --reload`
- [ ] Start frontend: `cd frontend && npm run dev`
- [ ] Verify backend health: `curl http://localhost:8000/health`

### Test Document 74 (Has Bbox Data)
- [ ] Navigate to: http://localhost:3000/audit?document_id=74
- [ ] Verify PDF loads without "Failed to load document" error
- [ ] Check "first_name" field highlight appears at ~38% down page (middle)
- [ ] Verify highlight is NOT at top of page
- [ ] Test zoom in/out - highlight should scale correctly
- [ ] Hover over highlight - should show label "first_name"

### Test New Upload (V3 Citations)
- [ ] Upload new PDF via bulk upload
- [ ] Check backend logs for: `Field 'X' v3 citation: conf=high→0.9, page=1, bbox_keys=['left', 'top', 'width', 'height', 'page']`
- [ ] Navigate to audit page for new document
- [ ] Verify all bbox highlights appear at correct locations
- [ ] Test with multi-page document - verify page filtering works

## 🐛 Known Issues / Edge Cases

1. **Old Documents (Pre-V3 API)**
   - Documents extracted before v3 API changes have `source_bbox: null`
   - Will show "No location data available" - expected behavior
   - Solution: Re-upload or re-extract these documents

2. **Backend Not Running**
   - Current status: Backend process stopped (connection refused)
   - Need to restart: `cd backend && uvicorn app.main:app --reload`

3. **Confidence Threshold Filtering**
   - Document 74 has fields with ~46% confidence
   - These appear in audit queue because threshold is 60%
   - This is correct behavior for low-confidence fields

## 📝 Technical Details

### Coordinate System
- **Reducto Output**: Normalized [0-1] relative to page dimensions
- **Frontend Display**: Absolute pixels relative to rendered PDF
- **Conversion**: `pixel = normalized × dimension`

### Page Dimensions
- Captured from PDF.js viewport: `pageData.getViewport({ scale: 1 })`
- Standard US Letter: 612×792 pixels (8.5×11 inches at 72 DPI)
- Dimensions vary by PDF page size

### Zoom Handling
- `pageWidth * zoom` and `pageHeight * zoom` passed to BBoxOverlays
- Scaling calculation already includes zoom
- No additional zoom adjustment needed in bbox rendering

## ✅ Completion Status

- [x] Frontend coordinate scaling implemented
- [x] Backend v3 citation parsing implemented
- [x] Database verification shows correct bbox data
- [x] Documentation created
- [ ] **Testing needed** (backend currently not running)

## 🚀 Next Steps

1. **Restart Backend** - `cd backend && uvicorn app.main:app --reload`
2. **Test Document 74** - Verify highlights appear at correct locations
3. **Test New Upload** - Confirm v3 citations work end-to-end
4. **Clear Old Documents** - Optionally re-extract pre-v3 documents

---

**Date**: 2025-11-06
**Fix Status**: ✅ Code Complete, ⏳ Testing Pending
**Related Files**: [BBOX_COORDINATE_FIX.md](./BBOX_COORDINATE_FIX.md)
