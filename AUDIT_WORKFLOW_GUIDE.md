# Audit Workflow - Visual Guide

**Status**: ✅ Phases 1 & 2 Complete
**URL**: http://localhost:3004

---

## 🎯 Two Audit Modes Available

### Phase 1: Inline Audit Modal (Single Field)
**Best for:** Quick spot-checks, 1-3 fields

**How to Access:**
1. Go to `/query` (Ask AI tab)
2. Submit a natural language query
3. If answer has low-confidence fields, you'll see:
   - ⚠ Yellow warning banner
   - 🔍 "Fields Needing Review" section
   - Citation badges with confidence scores
4. **Click any citation badge** → Inline modal opens

**Features:**
- PDF viewer (left) + Field editor (right)
- Keyboard shortcuts: `1` = Correct, `2` = Fix, `3` = Not Found, `S` = Skip, `Esc` = Close
- Auto-advances to next field after verification
- Real-time answer regeneration
- Progress: "5 of 12 fields"

### Phase 2: Batch Audit Modal (Multiple Fields)
**Best for:** Systematic reviews, 5+ fields

**How to Access:**
1. Same as above - go to `/query` and submit a query
2. If answer has multiple low-confidence fields, you'll see:
   - 🔍 "Fields Needing Review (N)" section
   - **Blue "Review All" button** (top-right of section)
3. **Click "Review All" button** → Batch modal opens

**Features:**
- Table view with all fields grouped by document
- Inline editing for corrections
- Action buttons: `Correct` / `Fix` / `Not Found`
- Notes field for each row
- Real-time stats: "5 verified, 7 pending"
- Single submit for all verifications
- Keyboard shortcut: `Ctrl+Enter` = Submit all

---

## 📊 Visual Layout

### Inline Modal (Phase 1)
```
┌─────────────────────────────────────────────────────┐
│ Review Extraction          Progress: 1 of 5      [X]│
├──────────────────┬──────────────────────────────────┤
│ PDF Preview      │ Field: invoice_total             │
│                  │ Value: $2,100.00                 │
│ [Document]       │ Confidence: 58% ⚠                │
│ [with bbox      │                                   │
│  highlighted]    │ Is this correct?                 │
│                  │ [✓ Yes (1)] [✏ Fix (2)] [✗ No(3)]│
│ Zoom: [-][100%][+]│ [⏭ Skip (S)]                   │
└──────────────────┴──────────────────────────────────┘
```

### Batch Modal (Phase 2)
```
┌──────────────────────────────────────────────────────────────┐
│ Batch Review - 5 Fields              5 verified  0 pending [X]│
├──────────────────────────────────────────────────────────────┤
│ 📄 invoice_001.pdf (3 fields)                                │
│ ┌────────────┬─────────────┬────────┬──────────┬──────────┐ │
│ │ Field      │ Value       │ Conf   │ Actions  │ Notes    │ │
│ ├────────────┼─────────────┼────────┼──────────┼──────────┤ │
│ │ total      │ $2,100.00   │ 58% ⚠ │ [✓][✏][✗]│ [......] │ │
│ │ date       │ 2025-01-15  │ 62% ⚠ │ [✓][✏][✗]│ [......] │ │
│ │ vendor     │ Acme Corp   │ 55% ⚠ │ [✓][✏][✗]│ [......] │ │
│ └────────────┴─────────────┴────────┴──────────┴──────────┘ │
│                                                                │
│ 📄 invoice_002.pdf (2 fields)                                │
│ [Similar table...]                                            │
├──────────────────────────────────────────────────────────────┤
│ 5 of 5 fields reviewed    [Cancel] [Submit (5) Ctrl+Enter]  │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎨 Testing the UI

### Test Scenario 1: See the Warning Banner
1. Navigate to `/query`
2. Make sure you have documents with low-confidence extractions
3. Submit a query like: "Show me all invoices"
4. Look for:
   - ⚠ Yellow warning banner at top of answer
   - "This answer uses X fields with low confidence scores"
   - "Show fields needing review →" link

### Test Scenario 2: Try Inline Modal
1. In the "Fields Needing Review" section, find a field
2. Click the citation badge (shows: `field_name: value [58%] ⚠`)
3. Modal should open with:
   - PDF on left (if available)
   - Field details on right
   - Three action buttons
4. Try keyboard shortcuts:
   - Press `1` to mark correct
   - Should auto-advance to next field

### Test Scenario 3: Try Batch Modal
1. Click the **blue "Review All" button** (top-right of Fields section)
2. Batch modal should open with table view
3. Try actions:
   - Click "Correct" on a field → Row turns green
   - Click "Fix" on a field → Inline editor appears → Type new value
   - Click "Not Found" on a field → Row turns red
4. Add notes if desired
5. Click "Submit" or press `Ctrl+Enter`
6. Modal should close, answer should update

### Test Scenario 4: Verified Badges
1. After verifying fields, look for:
   - ✓ Verified badges on completed fields (green)
   - Updated answer with "🔄 Answer updated..." banner
   - Verified count in stats

---

## 🔧 Current System State

### Services Running
- ✅ Backend: http://localhost:8000
- ✅ Frontend: http://localhost:3004
- ✅ Elasticsearch: http://localhost:9200

### Endpoints Available
- `POST /api/audit/verify-and-regenerate` - Single field (Phase 1)
- `POST /api/audit/bulk-verify-and-regenerate` - Batch (Phase 2)

### Components Created
- `PDFExcerpt.jsx` - Lightweight PDF viewer
- `InlineAuditModal.jsx` - Single field modal
- `BatchAuditModal.jsx` - Batch table modal
- Enhanced: `AnswerWithAudit.jsx`, `ChatSearch.jsx`

---

## ⚠️ Current Limitation

**No test data in audit queue!**

The current database has 45 documents but 0 unverified low-confidence fields. To test the modals, you need to:

### Option 1: Upload New Documents
1. Go to `/` (Bulk Upload)
2. Upload sample documents (invoices, contracts, etc.)
3. Process with templates
4. Run natural language search
5. Look for low-confidence warnings

### Option 2: Lower Threshold (Quick Test)
```bash
# Temporarily lower confidence threshold to 0.9
curl -X PUT http://localhost:8000/api/settings/audit_confidence_threshold \
  -H "Content-Type: application/json" \
  -d '{"value": 0.9, "level": "system"}'

# Now check audit queue
curl http://localhost:8000/api/audit/queue

# Reset when done
curl -X PUT http://localhost:8000/api/settings/audit_confidence_threshold \
  -H "Content-Type: application/json" \
  -d '{"value": 0.6, "level": "system"}'
```

### Option 3: Modify Database
```bash
# Mark a field as unverified with low confidence
sqlite3 backend/paperbase.db "UPDATE extracted_fields SET verified=0, confidence_score=0.55 WHERE id=34;"

# Check it appears in queue
curl http://localhost:8000/api/audit/queue
```

---

## 🎯 What's Next?

Now that Phases 1 & 2 are complete, here are potential next steps:

### Immediate: Fix Project Index Hook Error
The post-edit hook is failing because the index update script is missing. This is a minor issue but should be fixed.

### Phase 3: Analytics Dashboard
- Audit statistics page
- Most corrected fields chart
- Template quality scores
- Verification velocity graphs
- User performance metrics

### Phase 4: Smart Prioritization
- ML-based error prediction
- Sort fields by likely errors
- Auto-suggest common corrections
- Pattern recognition for repetitive fixes

### Phase 5: MCP Integration
- Enhanced MCP audit tools
- Batch export for MCP
- Claude Desktop integration
- External verification workflows

### Phase 6: Session Tracking
- Resume interrupted audits
- Save progress across sessions
- Audit session history
- Recovery from crashes

### Alternative: Polish & UX Improvements
- Add field filtering in batch modal
- Add undo/redo functionality
- Improve loading states
- Add animations and transitions
- Mobile responsive design
- Accessibility improvements (ARIA, screen readers)

---

## 📚 Documentation

- [INLINE_AUDIT_IMPLEMENTATION.md](./INLINE_AUDIT_IMPLEMENTATION.md) - Phase 1 details
- [BATCH_AUDIT_IMPLEMENTATION.md](./BATCH_AUDIT_IMPLEMENTATION.md) - Phase 2 details
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Overall summary
- [TESTING_INLINE_AUDIT.md](./TESTING_INLINE_AUDIT.md) - Testing guide

---

**Last Updated**: 2025-11-02
**Phases Complete**: 1 (Inline) + 2 (Batch)
**Status**: ✅ Ready for Testing
**Browser**: http://localhost:3004
