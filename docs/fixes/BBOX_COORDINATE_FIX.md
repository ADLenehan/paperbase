# Bbox Coordinate Scaling Fix

## Problem
Bbox highlights appeared in the wrong location - "first_name" highlight showed at the top of the page instead of where "Andrew" actually appears in the middle.

## Root Cause
Frontend was treating Reducto bbox coordinates as **pixels**, but they're actually **normalized [0-1] coordinates**!

### Reducto Bbox Format
```json
{
  "left": 0.254,    // 25.4% from left edge
  "top": 0.234,     // 23.4% from top edge
  "width": 0.025,   // 2.5% of page width
  "height": 0.006   // 0.6% of page height
}
```

### Frontend Bug
```javascript
// ❌ WRONG - treating as pixels
style={{ left: `${x}px` }}

// ✅ CORRECT - scale by page dimensions
style={{ left: `${x * pageWidth}px` }}
```

## Solution Applied

### Files Modified
1. `frontend/src/components/DocumentViewer.jsx`
2. `frontend/src/components/PDFViewer.jsx`

### Changes Made

#### 1. Added Page Height State
```javascript
const [pageHeight, setPageHeight] = useState(800);
```

#### 2. Capture Actual Page Dimensions on Load
```javascript
<Page
  onLoadSuccess={(pageData) => {
    const viewport = pageData.getViewport({ scale: 1 });
    setPageWidth(viewport.width);
    setPageHeight(viewport.height);
  }}
/>
```

#### 3. Scale Normalized Coordinates to Pixels
```javascript
// Bbox from Reducto: [0.254, 0.234, 0.025, 0.006] (normalized)
const pixelX = x * pageWidth;      // 0.254 * 612 = 155px
const pixelY = y * pageHeight;     // 0.234 * 792 = 185px
const pixelWidth = width * pageWidth;   // 0.025 * 612 = 15px
const pixelHeight = height * pageHeight; // 0.006 * 792 = 5px
```

#### 4. Pass Both Dimensions to BBoxOverlays
```javascript
<BBoxOverlays
  highlights={highlights}
  pageWidth={pageWidth * zoom}
  pageHeight={pageHeight * zoom}  // ← NEW
  currentPage={page}
  zoom={zoom}
/>
```

## Testing

### Current Document
The document you're viewing was extracted with the OLD api (before citation fix), so it has `bbox: null`. You won't see highlights for it.

### Testing with New Upload

1. **Upload a new PDF** (will use v3 citation API)
2. **Backend should log**:
   ```
   Field 'first_name' v3 citation: conf=high→0.9, page=1, bbox_keys=['left', 'top', 'width', 'height', 'page']
   ```
3. **Navigate to Audit page**
4. **Bbox should now appear at correct location!**

### Verify in Console
```javascript
// In browser console on Audit page
// Check if bbox values look normalized (0-1 range)
console.log(highlight.bbox)
// Should see: [0.254, 0.234, 0.025, 0.006]
```

## Expected Result

- ✅ "first_name" highlight appears around the actual name "Andrew"
- ✅ Highlight scales with zoom
- ✅ Highlight position matches text location on page
- ✅ Multiple highlights on same page don't overlap incorrectly

## Rollback if Needed

If this breaks existing documents with pixel coordinates (unlikely), we can detect the format:

```javascript
// Auto-detect if coordinates are normalized or pixels
const isNormalized = x <= 1 && y <= 1;
const pixelX = isNormalized ? x * pageWidth : x;
```

---

**Date**: 2025-11-06
**Status**: ✅ Fixed - Ready for testing
**Impact**: All future uploads with v3 citations will have correctly positioned bbox highlights
