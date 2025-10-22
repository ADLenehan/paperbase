# Audit UX Improvements

## Changes Made (2025-10-13)

### Issue 1: Better handling of 0% confidence
**Problem**: Showing "0%" confidence is misleading when a field simply wasn't extracted.

**Solution**:
- Show "not extracted" instead of "0%" when confidence is 0 or null
- Changed empty value display from "(empty)" to "(not extracted)"

### Issue 2: Clarify when bbox highlighting is unavailable
**Problem**: Users might not realize when location data is missing.

**Solution**:
- Added yellow warning banner when `source_bbox` is not available
- Message: "No location data available. You'll need to review the full document."

## Updated Files

### 1. Audit Page ([frontend/src/pages/Audit.jsx](frontend/src/pages/Audit.jsx))

**Before:**
```jsx
<p className="font-mono text-sm text-gray-900">
  {currentItem.field_value || '(empty)'}
</p>

<span className="text-sm font-medium text-gray-900">
  {Math.round(currentItem.confidence * 100)}%
</span>
```

**After:**
```jsx
<p className="font-mono text-sm text-gray-900">
  {currentItem.field_value || '(not extracted)'}
</p>

{currentItem.confidence === 0 || currentItem.confidence === null ? (
  <div className="text-sm text-gray-500 italic">
    Field not extracted
  </div>
) : (
  <span className="text-sm font-medium text-gray-900">
    {Math.round(currentItem.confidence * 100)}%
  </span>
)}

{/* New warning banner */}
{!currentItem.source_bbox && (
  <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
    <div className="text-xs text-yellow-700">
      No location data available. You'll need to review the full document.
    </div>
  </div>
)}
```

### 2. Documents Dashboard ([frontend/src/pages/DocumentsDashboard.jsx](frontend/src/pages/DocumentsDashboard.jsx))

**Before:**
```jsx
<span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${colorClass}`}>
  {doc.lowest_confidence_field.field_name}: {Math.round(doc.lowest_confidence_field.confidence * 100)}%
</span>
```

**After:**
```jsx
{doc.lowest_confidence_field.confidence === 0 || doc.lowest_confidence_field.confidence === null ? (
  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">
    {doc.lowest_confidence_field.field_name}: not extracted
  </span>
) : (
  <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${colorClass}`}>
    {doc.lowest_confidence_field.field_name}: {Math.round(doc.lowest_confidence_field.confidence * 100)}%
  </span>
)}
```

## Visual Changes

### Audit Page - Confidence Display

**Scenario 1: Normal confidence (e.g., 45%)**
```
Confidence:
[=========>         ] 45%
```

**Scenario 2: Field not extracted (0% or null)**
```
Confidence:
Field not extracted
```

### Audit Page - Missing Bbox Warning

When `source_bbox` is null/undefined:
```
┌────────────────────────────────────────────┐
│ ⚠️ No location data available. You'll need │
│    to review the full document.            │
└────────────────────────────────────────────┘
```

### Documents Dashboard - Lowest Field Column

**Scenario 1: Low confidence field**
```
⚠️ invoice_total: 45%  [yellow/red badge]
```

**Scenario 2: Field not extracted**
```
invoice_total: not extracted  [gray badge]
```

**Scenario 3: No fields**
```
—
```

## Bbox Highlighting Confirmation

The bbox highlighting **IS already implemented** and working:

```jsx
// In Audit.jsx
const highlights = currentItem.source_bbox ? [{
  bbox: currentItem.source_bbox,           // [x, y, width, height]
  color: currentItem.confidence < 0.4 ? 'red'
       : currentItem.confidence < 0.6 ? 'yellow'
       : 'green',
  label: currentItem.field_name,           // Shows field name on hover
  page: currentItem.source_page
}] : [];

// Passed to PDFViewer
<PDFViewer
  fileUrl={fileUrl}
  page={currentPage}
  highlights={highlights}  // ← Rendered as colored boxes over PDF
  ...
/>
```

**Rendering behavior:**
- Red box (border + 10% fill) for confidence <40%
- Yellow box for 40-60%
- Green box for ≥60%
- Label tooltip on hover showing field name
- Automatically jumps to correct page (`source_page`)

## Testing Checklist

### Scenario 1: Normal extraction with bbox
- [ ] Upload document, extract fields
- [ ] Navigate to Audit tab
- [ ] Verify colored box appears over PDF at extraction location
- [ ] Hover over box - should show field name
- [ ] Verify confidence shows percentage (e.g., "45%")

### Scenario 2: Extraction without bbox
- [ ] Find/create extraction with no bbox data
- [ ] Navigate to Audit tab
- [ ] Verify yellow warning banner appears
- [ ] Verify PDF shows full document (no highlighted boxes)

### Scenario 3: Field not extracted (0% confidence)
- [ ] Find/create field with 0 or null confidence
- [ ] Audit page should show "Field not extracted" instead of "0%"
- [ ] Documents dashboard should show "not extracted" in badge

### Scenario 4: Documents table
- [ ] View Documents dashboard
- [ ] Check "Lowest Field" column
- [ ] Verify confidence badges are color-coded correctly
- [ ] Verify "not extracted" shows for 0% fields

## Edge Cases Handled

1. **Null/undefined confidence**: Shows "Field not extracted"
2. **0 confidence**: Treated same as null (field not extracted)
3. **Missing bbox**: Warning banner + full PDF view
4. **Missing source_page**: Defaults to page 1
5. **Empty field_value**: Shows "(not extracted)" instead of "(empty)"

## Why These Changes Matter

### User Clarity
- "0%" implies a measurement was taken but resulted in zero confidence
- "not extracted" is more accurate - the field simply wasn't found/returned
- Removes confusion about what 0% means

### Better Context
- Warning banner sets expectations when bbox is unavailable
- Users know upfront they need to review the entire document
- Reduces frustration from expecting highlighting that doesn't appear

### Consistent Terminology
- Both Audit page and Documents dashboard use same language
- "not extracted" is clearer than "(empty)" or "0%"

## Related Documentation

- [AUDIT_TAB_IMPLEMENTATION.md](./AUDIT_TAB_IMPLEMENTATION.md) - Full implementation details
- [PDFViewer.jsx](./frontend/src/components/PDFViewer.jsx) - Bbox rendering logic
- [Audit.jsx](./frontend/src/pages/Audit.jsx) - Main audit interface

## Next Steps

If bbox data is consistently missing:
1. Verify Reducto API is returning bbox in responses
2. Check `_parse_extraction_with_bbox()` is correctly parsing the format
3. Add debug logging in extraction pipeline to trace bbox flow
4. Consider fallback strategies (e.g., text search highlighting)
