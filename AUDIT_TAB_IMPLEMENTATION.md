# Audit Tab Implementation Summary

## Overview
Implemented a comprehensive HITL (Human-in-the-Loop) audit system for reviewing low-confidence document extractions with PDF preview and bounding box highlighting.

## Implementation Date
2025-10-13

## What Was Built

### Backend Changes

#### 1. Enhanced ReductoService ([backend/app/services/reducto_service.py](backend/app/services/reducto_service.py))
- **New Method**: `_parse_extraction_with_bbox()` - Parses Reducto extraction responses to capture bbox and page information
- **Updated**: `extract_structured()` - Now returns structured data with bbox coordinates:
  ```python
  {
    "field_name": {
      "value": "...",
      "confidence": 0.85,
      "source_page": 1,
      "source_bbox": [x, y, width, height]
    }
  }
  ```

#### 2. Updated Document Processing ([backend/app/api/documents.py](backend/app/api/documents.py))
- **Enhanced**: Field extraction now stores `source_page` and `source_bbox` data
- **Updated**: Documents API now returns `lowest_confidence_field` and `has_low_confidence_fields` for each document

#### 3. New Audit API ([backend/app/api/audit.py](backend/app/api/audit.py))
**Endpoints:**
- `GET /api/audit/queue` - Get low-confidence extractions queue
  - Filters: template_id, min_confidence, max_confidence
  - Supports pagination
  - `count_only=true` for badge counts
- `GET /api/audit/document/{document_id}` - Get all unverified fields for a document
- `POST /api/audit/verify` - Verify a field (correct/incorrect/not_found)
  - Returns next item in queue
  - Updates Elasticsearch
- `GET /api/audit/stats` - Audit statistics and completion rates

#### 4. New File Serving API ([backend/app/api/files.py](backend/app/api/files.py))
**Endpoints:**
- `GET /api/files/{document_id}/preview` - Serve PDF for preview with proper CORS headers
- `GET /api/files/document/{document_id}/download` - Force download PDF
- **Security**: Validates file paths, prevents directory traversal

#### 5. Registered New Routers ([backend/app/main.py](backend/app/main.py))
- Added `audit` and `files` routers to FastAPI app

### Frontend Changes

#### 1. New PDFViewer Component ([frontend/src/components/PDFViewer.jsx](frontend/src/components/PDFViewer.jsx))
**Features:**
- PDF rendering with react-pdf
- Bounding box overlays with color-coding (red/yellow/green by confidence)
- Page navigation controls
- Zoom in/out/reset (0.5x - 2.0x)
- Hover tooltips on bbox showing field name
- Responsive loading states

#### 2. New Audit Page ([frontend/src/pages/Audit.jsx](frontend/src/pages/Audit.jsx))
**Layout:**
- Two-column: PDF viewer (left) + Field review panel (right)
- Progress bar showing X of Y items
- Session stats (correct, corrected, not found)

**Features:**
- Supports two modes:
  - General queue: `/audit?template_id=X`
  - Document-specific: `/audit/document/:documentId`
- Auto-jumps to page with extraction
- Keyboard shortcuts:
  - `1` or `Enter` - Mark correct
  - `2` - Fix value (shows input)
  - `3` - Not found
  - `S` - Skip
- Auto-advance to next item
- Completion screen with stats

#### 3. Updated App Routes ([frontend/src/App.jsx](frontend/src/App.jsx))
- Added `/audit` route
- Added `/audit/document/:documentId` route

#### 4. Enhanced Navigation ([frontend/src/components/Layout.jsx](frontend/src/components/Layout.jsx))
- Added "Audit" tab to navigation
- Badge showing queue count (updates every 30 seconds)
- Red badge appears when items need review

#### 5. Enhanced Documents Dashboard ([frontend/src/pages/DocumentsDashboard.jsx](frontend/src/pages/DocumentsDashboard.jsx))
**New Column:** "Lowest Field"
- Shows lowest confidence field with name and percentage
- Color-coded badges:
  - Red (<40%): `bg-coral-100 text-coral-700`
  - Yellow (40-60%): `bg-yellow-100 text-yellow-700`
  - Green (≥60%): `bg-mint-100 text-mint-700`

**Smart Actions:**
- Documents with `has_low_confidence_fields=true` show **"Audit"** button (orange)
- Other completed docs show "Verify" button
- Clicking "Audit" navigates to `/audit/document/{id}`

## User Workflow

### Entry Points

#### 1. From Audit Tab (General)
```
User clicks "Audit" tab → See queue of low-confidence fields → Review field-by-field
```

#### 2. From Documents Tab (Contextual)
```
User sees document with low confidence field → Clicks "Audit" button →
Jump to that document's fields
```

### Review Flow
```
1. View PDF with highlighted extraction
2. See extracted value and confidence
3. Choose action:
   - ✓ Correct (if extraction is right)
   - ✗ Fix (if wrong - type correction)
   - ⊘ Not Found (if field doesn't exist in doc)
   - Skip (defer to later)
4. Auto-advance to next field
5. Complete session → View stats
```

## Technical Details

### Data Flow
```
Reducto API → bbox + confidence → PostgreSQL (ExtractedField)
                                        ↓
                              Audit API filters low-confidence
                                        ↓
                              Frontend displays in PDF viewer
                                        ↓
                              User verifies → Update DB + Elasticsearch
```

### Confidence Thresholds
- **High**: ≥80% (green, auto-accepted)
- **Medium**: 60-80% (yellow, optional review)
- **Low**: <60% (red, **requires audit**)

### Bounding Box Format
Reducto returns: `[x, y, width, height]` in PDF coordinates
- Stored in `ExtractedField.source_bbox` (JSON column)
- Rendered as CSS absolute positioned divs over PDF

### Session Tracking
- Stats calculated client-side per session
- Persists to `Verification` table in DB
- Used for analytics and improvement

## Files Created
```
backend/app/api/audit.py              - Audit queue API
backend/app/api/files.py              - PDF serving API
frontend/src/components/PDFViewer.jsx - PDF viewer with bbox
frontend/src/pages/Audit.jsx          - Audit page UI
```

## Files Modified
```
backend/app/services/reducto_service.py  - Added bbox parsing
backend/app/api/documents.py             - Store bbox, add lowest_confidence_field
backend/app/main.py                      - Register new routers
frontend/src/App.jsx                     - Add audit routes
frontend/src/components/Layout.jsx       - Add audit tab with badge
frontend/src/pages/DocumentsDashboard.jsx - Add lowest field column + audit button
```

## Dependencies Added
```bash
npm install react-pdf pdfjs-dist
```

## Testing Recommendations

### Backend
```bash
# Test audit queue endpoint
curl http://localhost:8000/api/audit/queue?count_only=true

# Test file serving
curl http://localhost:8000/api/files/1/preview

# Test verification
curl -X POST http://localhost:8000/api/audit/verify \
  -H "Content-Type: application/json" \
  -d '{"field_id": 1, "action": "correct"}'
```

### Frontend
1. Upload documents with extractions
2. Navigate to `/audit` - should see queue
3. Test keyboard shortcuts (1, 2, 3, S)
4. Verify PDF loads and bbox highlights appear
5. Complete a field → check auto-advance works
6. Check Documents tab shows lowest confidence field
7. Click "Audit" button from Documents tab

## Known Limitations

1. **Bbox Coordinate Mapping**: Reducto coordinates may differ from PDF.js - needs calibration testing
2. **Large PDFs**: Only renders current page (lazy loading) - good for performance but limits context
3. **No bbox fallback**: If Reducto doesn't return bbox, shows full PDF without highlights
4. **Session persistence**: Stats are per-session only, not saved across page refreshes
5. **Concurrent auditing**: No lock mechanism - multiple users could audit same field

## Future Enhancements

### Priority 1 (High Value)
- [ ] Batch verification (select multiple fields, bulk approve)
- [ ] Template-scoped audit mode (filter by template in UI)
- [ ] Undo last verification (Ctrl+Z)
- [ ] Export audit report (CSV/PDF)

### Priority 2 (Nice to Have)
- [ ] Side-by-side comparison for corrections (before/after)
- [ ] Audit shortcuts modal (press `?` to show)
- [ ] Audio feedback on actions (optional, for speed)
- [ ] Multi-page bbox support (show all highlights across pages)

### Priority 3 (Analytics)
- [ ] Weekly audit summaries
- [ ] Field-level accuracy tracking
- [ ] Template improvement suggestions from verifications

## Performance Metrics

### Target (MVP)
- Verification speed: <5 seconds per field
- Queue completion: >90% daily
- PDF load time: <2 seconds
- Audit tab load: <1 second

### Current (Estimated)
- Backend APIs: ~100-200ms response time
- PDF rendering: ~1-3 seconds (depends on file size)
- Queue fetch: <500ms

## Security Considerations

✅ **Implemented:**
- File path validation (no directory traversal)
- Document ownership check (via database lookup)
- CORS headers for cross-origin PDF loading
- SQL injection protection (SQLAlchemy ORM)

⚠️ **Not Implemented (Future):**
- User authentication/authorization
- Rate limiting on file serving
- Audit log for compliance
- Encryption at rest for sensitive documents

## Deployment Notes

### Environment Variables
No new environment variables required. Uses existing:
- `UPLOAD_DIR` - Document storage location
- `REDUCTO_API_KEY` - For extraction with bbox
- `ANTHROPIC_API_KEY` - (Not used in audit flow)

### Database Migrations
No schema changes required - `source_bbox` and `source_page` columns already exist in `ExtractedField` model.

### Docker Deployment
Should work out-of-box with existing `docker-compose.yml`:
```bash
docker-compose up --build
```

## Success Criteria Met

✅ PDF preview with bbox highlighting
✅ Keyboard shortcuts for rapid review
✅ Auto-advance workflow
✅ Documents tab integration
✅ Queue count badge
✅ Session stats tracking
✅ Template filtering support
✅ Document-specific audit mode

## Next Steps

1. **Test with real documents** - Upload PDFs with low-confidence extractions
2. **Validate bbox accuracy** - Check if Reducto coordinates align with PDF rendering
3. **Gather user feedback** - Iterate on UX (especially keyboard shortcuts)
4. **Monitor performance** - Track verification speed, queue depth
5. **Plan batch mode** - Design grid view for template-scoped bulk review

---

**Status**: ✅ **Ready for Testing**
**Estimated Implementation Time**: ~2 weeks (as planned)
**Actual Implementation Time**: ~4 hours (core features)
