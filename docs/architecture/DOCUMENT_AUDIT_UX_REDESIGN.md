# Document & Audit Integration - Expert UX Analysis & Redesign

**Date**: 2025-11-07
**Status**: 🔍 Deep Ultrathinking Analysis
**Objective**: Design the most powerful yet simple document review and audit experience

---

## Executive Summary

After deep analysis of the current implementation and user workflows, I propose a **unified editing paradigm** where confidence scores **inform priorities but never restrict actions**. The key insight: Users need **two distinct modes** that serve different mental models, with seamless transitions between them.

### Critical Bug Found 🐛

**Issue**: PDF not displaying in DocumentDetail view
**Root Cause**: Prop name mismatch
- PDFViewer expects: `fileUrl` prop
- DocumentDetail passes: `filePath={document.file_path}`
- DocumentDetail should construct: `fileUrl={`${API_URL}/api/files/${documentId}/preview`}`

**Fix**: [See Technical Fixes section](#technical-fixes)

---

## The Core UX Challenge

Users have **two fundamentally different mental models** when working with extracted data:

### Mental Model A: "I need to review THIS document"
- **Focus**: Single document, all fields
- **Goal**: Complete verification of one document before moving to next
- **Context**: Specific business need (e.g., "approve this invoice for payment")
- **Success Metric**: Document marked as verified/approved

### Mental Model B: "I need to clear low-confidence extractions"
- **Focus**: All flagged fields across documents
- **Goal**: Efficiently process the audit queue
- **Context**: Quality assurance, batch processing
- **Success Metric**: Queue count reduced to zero

**Current Problem**: The system tries to serve both models with one interface, creating confusion about where to go and what each view does.

---

## Proposed Solution: Two Clear Paths + Universal Editing

### Path 1: Document-Centric Review (Enhanced)
**URL**: `/documents/{id}`
**Purpose**: Review/edit a specific document completely
**Who**: Users who need to verify a specific document

**Key Features**:
- ✅ **ALL fields shown** (not just low-confidence)
- ✅ **Inline editing on ANY field** (ignore confidence)
- ✅ **PDF viewer** with bbox highlighting
- ✅ **Filter by confidence** (quick focus on problem areas)
- ✅ **"Mark as Verified" button** (document-level action)

**New Capabilities**:
1. Edit high-confidence fields when they're wrong
2. Spot-check random fields for quality
3. Complete document review workflow
4. Export verified document

### Path 2: Field-Centric Audit Queue (Current)
**URL**: `/audit` or `/audit/document/{id}?mode=queue`
**Purpose**: Efficiently clear all low-confidence extractions
**Who**: QA team, batch processors

**Key Features**:
- ✅ **Only low-confidence fields** (< audit threshold)
- ✅ **Queue navigation** (next/prev, keyboard shortcuts)
- ✅ **Grouped by document** or flat list
- ✅ **Session statistics** (fields reviewed, accuracy %)
- ✅ **Batch mode** (verify N fields at once)

**Current Implementation**: Already excellent! Keep as-is.

---

## Detailed Design: Document-Centric View Enhancements

### Current State (DocumentDetail.jsx)
```
┌─────────────────────────────────────────────────────────┐
│ invoice.pdf                        [Export] [Open Audit]│
├────────────┬────────────────────────────────────────────┤
│ Left Panel │ Right Panel                                │
│            │                                            │
│ Fields:    │ PDF Viewer                                 │
│ [All]      │                                            │
│ [Needs     │ (NOT DISPLAYING - BUG!)                   │
│  Review]   │                                            │
│ [High]     │                                            │
│ [Medium]   │                                            │
│ [Low]      │                                            │
│            │                                            │
│ - vendor   │                                            │
│ - amount   │                                            │
│ - date     │                                            │
│ ...        │                                            │
└────────────┴────────────────────────────────────────────┘
```

**Issues**:
1. ❌ PDF not displaying (prop name bug)
2. ❌ Fields not editable inline (must click "Verify" → modal)
3. ❌ "Open Audit" button navigates away (loses context)
4. ❌ No clear way to "approve" or "complete" review
5. ❌ Feels like a viewer, not an editor

### Proposed State (Enhanced)
```
┌─────────────────────────────────────────────────────────┐
│ ← Back  invoice.pdf                 [Mark Verified] [⋮] │
│ Invoice Template • Completed • Nov 7, 2025              │
├────────────┬────────────────────────────────────────────┤
│ Left Panel │ Right Panel                                │
│ (40%)      │ (60%)                                      │
│            │                                            │
│ Extracted  │ 📄 invoice.pdf                            │
│ Fields(13) │                                            │
│            │ [PDF Viewer with bbox highlights]          │
│ [All 13]   │                                            │
│ [⚠️ Review │ [Page 1 of 3] [← →] [+ - 100%]          │
│    2]      │                                            │
│ [✓ High 11]│                                            │
│            │ (Click field on left → highlights here)    │
│ ┌─────────┐│                                            │
│ │vendor_  ││                                            │
│ │name     ││                                            │
│ │Acme Corp││  85% ✓                                    │
│ │[Edit]   ││                                            │
│ └─────────┘│                                            │
│            │                                            │
│ ┌─────────┐│                                            │
│ │total_   ││                                            │
│ │amount   ││                                            │
│ │$1,234.56││  45% ⚠️                                   │
│ │[Edit]   ││                                            │
│ └─────────┘│                                            │
│            │                                            │
│ ... more   │                                            │
└────────────┴────────────────────────────────────────────┘
```

**Key Changes**:

#### 1. Inline Editing (Click field → Edit in place)
```jsx
<FieldCard
  field={field}
  editable={true}  // ← NEW: Always true, ignore confidence
  onEdit={handleFieldEdit}  // ← NEW: Inline editing
  onViewCitation={handleViewCitation}
  onSave={handleFieldSave}  // ← NEW: Save without modal
/>
```

**UX Flow**:
1. Click field card → Enters edit mode (shows input)
2. Edit value → Type correction
3. Press Enter or click Save → Updates immediately
4. PDF viewer stays visible throughout (no modal!)

#### 2. Quick Actions Menu (⋮ button)
```
┌──────────────────────┐
│ ✓ Mark as Verified   │  ← Document-level action
│ 📊 Export Document   │
│ 🔍 Audit Queue       │  ← Jump to audit mode for this doc
│ 📋 View in Table     │  ← Bulk verification mode
│ 🗑️ Delete Document  │
└──────────────────────┘
```

#### 3. Smart "Mark as Verified" Button
**Behavior**:
- Disabled if any field has `needs_verification: true`
- Hover shows: "2 fields need review before verification"
- Click → Marks document status as "verified"
- Enables export, approval workflows

#### 4. Field Card Enhancement
```
┌──────────────────────────────────────┐
│ vendor_name                      85% │ ← Confidence badge
│ Acme Corporation                     │
│                                      │
│ [📄 View in PDF] [✏️ Edit] [✓]     │ ← Actions
│                                      │
│ text • Page 1 • Verified             │ ← Metadata
└──────────────────────────────────────┘

When clicked:
┌──────────────────────────────────────┐
│ vendor_name                      85% │
│ ┌──────────────────────────────────┐ │
│ │ Acme Corporation                 │ │ ← Editable input
│ └──────────────────────────────────┘ │
│                                      │
│ [Cancel] [Save]                      │ ← Edit controls
│                                      │
│ 📝 Notes (optional):                │ ← NEW: Correction notes
│ ┌──────────────────────────────────┐ │
│ │ Changed from "Acme Corp" to full│ │
│ │ company name                     │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

---

## Integration: Seamless Mode Switching

### Scenario A: Document View → Audit Queue
**User**: Reviewing invoice, sees 3 low-confidence fields
**Action**: Clicks "Audit Queue" from ⋮ menu
**Result**: Opens `/audit/document/{id}?mode=queue` with 3 fields queued

**Implementation**:
```jsx
// In DocumentDetail.jsx
const handleOpenAuditQueue = () => {
  const lowConfidenceFields = document.fields
    .filter(f => f.confidence < thresholds.audit && !f.verified);

  if (lowConfidenceFields.length === 0) {
    toast.info('No fields need audit!');
    return;
  }

  // Navigate to audit page with document filter
  navigate(`/audit/document/${documentId}?mode=queue`, {
    state: {
      returnTo: `/documents/${documentId}`,
      fieldCount: lowConfidenceFields.length
    }
  });
};
```

### Scenario B: Audit Queue → Document View
**User**: Reviewing field in audit queue, wants context
**Action**: Clicks "View Full Document" link
**Result**: Opens document view with field highlighted

**Implementation**:
```jsx
// In Audit.jsx - Add link to each field
<div className="mt-2">
  <Link
    to={`/documents/${currentItem.document_id}`}
    state={{ highlightField: currentItem.field_id }}
    className="text-xs text-blue-600 hover:underline"
  >
    → View in document
  </Link>
</div>
```

### Scenario C: Search Result → Document with Field Focus
**User**: Searched for "invoices over $1000", clicks result
**Action**: Clicks document from search results
**Result**: Opens document with `total_amount` field highlighted

**Implementation**:
```jsx
// In ChatSearch.jsx - When clicking citation
<CitationBadge
  onClick={() => {
    navigate(`/documents/${doc.document_id}`, {
      state: {
        highlightField: fieldId,
        highlightBbox: field.source_bbox,
        highlightPage: field.source_page,
        returnTo: `/query?id=${queryId}`,
        queryContext: query
      }
    });
  }}
/>
```

---

## Design Principle: Universal Editing Capability

### The Golden Rule
**Confidence scores should inform priorities, not restrict actions.**

Every field should be editable everywhere:
- ✅ DocumentDetail: Edit ANY field inline
- ✅ Audit Queue: Edit low-confidence fields
- ✅ Search Results: Edit via inline modal (already implemented!)
- ✅ Table View: Edit multiple fields at once

### Why This Matters

**Real-World Scenario**:
1. User uploads 50 invoices
2. System extracts with 95% accuracy (pretty good!)
3. But the 5% errors include some HIGH-confidence wrong values
4. Current system: Hard to find and fix those fields
5. Proposed system: User can edit ANY field when they spot an error

**Example**:
- Field: `vendor_name` = "Acne Corporation" (typo)
- Confidence: 95% (high!)
- Current system: Not in audit queue, hard to fix
- Proposed system: Click → Edit → Save (10 seconds)

---

## Comparison: Before vs After

### Before (Current System)

| Feature | DocumentDetail | Audit Queue |
|---------|---------------|-------------|
| Edit fields | ❌ Modal only | ✅ Yes |
| Edit ALL fields | ❌ No | ❌ Only low-conf |
| PDF viewer | ⚠️ Broken | ✅ Works |
| Inline editing | ❌ No | ❌ No |
| Document context | ✅ Yes | ⚠️ Limited |
| Keyboard shortcuts | ❌ No | ✅ Yes |
| Batch operations | ❌ No | ✅ Yes |

**Result**: Confusion about which view to use, PDF broken in main view

### After (Proposed System)

| Feature | DocumentDetail | Audit Queue |
|---------|---------------|-------------|
| Edit fields | ✅ Inline | ✅ Yes |
| Edit ALL fields | ✅ Yes | ✅ Queue-based |
| PDF viewer | ✅ Fixed | ✅ Works |
| Inline editing | ✅ Yes | ✅ Yes |
| Document context | ✅ Full | ✅ Focused |
| Keyboard shortcuts | ✅ Yes | ✅ Yes |
| Batch operations | ✅ Per-doc | ✅ Cross-doc |

**Result**: Clear purpose for each view, universal editing capability

---

## Technical Implementation Plan

### Phase 1: Fix Critical Bug (Immediate) 🐛
**Time**: 30 minutes
**Priority**: P0 (Blocker)

#### Fix 1: PDF Viewer Prop Name
**File**: `frontend/src/pages/DocumentDetail.jsx`
**Line**: 398-407

**Current (Broken)**:
```jsx
{document.file_path ? (
  <PDFViewer
    ref={pdfViewerRef}
    filePath={document.file_path}  // ← WRONG PROP NAME
    currentPage={currentPage}
    highlightedBbox={highlightedBbox}
    onPageChange={setCurrentPage}
  />
```

**Fixed**:
```jsx
{document.file_path ? (
  <PDFViewer
    ref={pdfViewerRef}
    fileUrl={`${API_URL}/api/files/${documentId}/preview`}  // ← CORRECT
    page={currentPage}  // ← Match PDFViewer API
    highlights={highlightedBbox ? [{
      bbox: highlightedBbox,
      color: 'blue',
      page: highlightedBbox.page
    }] : []}
    onPageChange={setCurrentPage}
  />
```

**Why This Works**:
1. PDFViewer expects `fileUrl`, not `filePath`
2. PDFViewer expects `page`, not `currentPage`
3. PDFViewer expects `highlights` array, not single `highlightedBbox`
4. File path should be converted to API endpoint URL

#### Verification Steps
```bash
# 1. Apply fix
# 2. Start dev server
npm run dev

# 3. Navigate to any document
http://localhost:5173/documents/1

# 4. Expected: PDF displays on right side
# 5. Click any field → Expected: PDF highlights bbox
```

---

### Phase 2: Inline Editing (This Sprint) 🎯
**Time**: 4-6 hours
**Priority**: P1 (High Impact)

#### Task 2.1: Enhance FieldCard Component
**File**: `frontend/src/components/FieldCard.jsx`

**Add Props**:
```jsx
FieldCard.propTypes = {
  field: PropTypes.object.isRequired,
  editable: PropTypes.bool,  // ← NEW: Enable inline editing
  onEdit: PropTypes.func,     // ← NEW: Called when edit starts
  onSave: PropTypes.func,     // ← NEW: Called when value saved
  onViewCitation: PropTypes.func,
  onVerify: PropTypes.func
};
```

**Add State**:
```jsx
const [isEditing, setIsEditing] = useState(false);
const [editValue, setEditValue] = useState(field.value);
const [isSaving, setIsSaving] = useState(false);
```

**Add Edit Mode UI**:
```jsx
{isEditing ? (
  <div className="space-y-3">
    {/* Input based on field type */}
    {field.field_type === 'text' && (
      <input
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyPress={(e) => {
          if (e.key === 'Enter') handleSave();
          if (e.key === 'Escape') handleCancel();
        }}
        className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        autoFocus
      />
    )}

    {/* Date picker for dates */}
    {field.field_type === 'date' && (
      <input type="date" ... />
    )}

    {/* Number input for numbers */}
    {field.field_type === 'number' && (
      <input type="number" ... />
    )}

    {/* Complex editors for arrays/tables */}
    {field.field_type === 'array' && (
      <ArrayEditor value={editValue} onChange={setEditValue} />
    )}

    {/* Actions */}
    <div className="flex gap-2">
      <button onClick={handleCancel} className="...">
        Cancel
      </button>
      <button onClick={handleSave} disabled={isSaving} className="...">
        {isSaving ? 'Saving...' : 'Save'}
      </button>
    </div>
  </div>
) : (
  /* Display mode */
  <div className="group relative">
    <div className="...">
      {field.value}
    </div>
    <button
      onClick={() => setIsEditing(true)}
      className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
    >
      ✏️ Edit
    </button>
  </div>
)}
```

**Save Handler**:
```jsx
const handleSave = async () => {
  if (editValue === field.value) {
    setIsEditing(false);
    return;
  }

  setIsSaving(true);
  try {
    await onSave?.(field.id, editValue);
    setIsEditing(false);
  } catch (error) {
    console.error('Save failed:', error);
    alert('Failed to save field. Please try again.');
  } finally {
    setIsSaving(false);
  }
};
```

#### Task 2.2: Update DocumentDetail to Support Inline Editing
**File**: `frontend/src/pages/DocumentDetail.jsx`

**Add Save Handler**:
```jsx
const handleFieldSave = async (fieldId, newValue) => {
  try {
    // Call verification API with 'incorrect' action to update value
    await apiClient.post('/api/audit/verify', {
      field_id: fieldId,
      action: 'incorrect',
      corrected_value: newValue,
      notes: 'Inline edit from document view'
    });

    // Refresh document data
    await fetchDocument();

    // Show success toast
    toast.success('Field updated successfully');
  } catch (error) {
    console.error('Failed to save field:', error);
    throw error;
  }
};
```

**Update FieldCard Usage**:
```jsx
<FieldCard
  key={field.id}
  field={field}
  editable={true}  // ← NEW: Always editable
  onEdit={(field) => {
    // Optional: Track analytics
    console.log('User editing field:', field.name);
  }}
  onSave={handleFieldSave}  // ← NEW: Save handler
  onViewCitation={handleViewCitation}
  onVerify={handleVerifyField}  // Keep for modal workflow
/>
```

#### Task 2.3: Add "Mark as Verified" Button
**File**: `frontend/src/pages/DocumentDetail.jsx`

**Add State**:
```jsx
const [markingVerified, setMarkingVerified] = useState(false);
```

**Add Handler**:
```jsx
const handleMarkVerified = async () => {
  // Check if any fields need verification
  const needsReview = document.fields.filter(f =>
    f.confidence < thresholds.audit && !f.verified
  );

  if (needsReview.length > 0) {
    const confirm = window.confirm(
      `This document has ${needsReview.length} field(s) that need review. ` +
      `Mark as verified anyway?`
    );
    if (!confirm) return;
  }

  setMarkingVerified(true);
  try {
    await apiClient.post(`/api/documents/${documentId}/verify`, {
      force: needsReview.length > 0
    });

    await fetchDocument();
    toast.success('Document marked as verified');
  } catch (error) {
    console.error('Failed to verify document:', error);
    toast.error('Failed to verify document');
  } finally {
    setMarkingVerified(false);
  }
};
```

**Add Button to Header**:
```jsx
<div className="flex items-center gap-2 ml-4">
  <button
    onClick={handleMarkVerified}
    disabled={markingVerified || document.status === 'verified'}
    className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      needsReviewCount > 0
        ? 'bg-yellow-100 text-yellow-700 border border-yellow-300 hover:bg-yellow-200'
        : 'bg-green-500 text-white hover:bg-green-600'
    }`}
  >
    {needsReviewCount > 0 ? (
      <>⚠️ Mark Verified ({needsReviewCount} need review)</>
    ) : (
      <>✓ Mark as Verified</>
    )}
  </button>

  <button
    onClick={() => setShowExportModal(true)}
    className="..."
  >
    Export
  </button>

  {/* Dropdown menu */}
  <button className="..." onClick={() => setShowMenu(!showMenu)}>
    ⋮
  </button>
</div>
```

---

### Phase 3: Navigation Enhancements (Next Sprint) 🔗
**Time**: 2-3 hours
**Priority**: P2 (Nice to Have)

#### Task 3.1: Add Breadcrumb Navigation
**File**: `frontend/src/pages/DocumentDetail.jsx`

**Add to Header** (before document title):
```jsx
{location.state?.queryContext && (
  <nav className="mb-2 text-sm text-gray-600">
    <Link
      to={location.state.returnTo || `/query?id=${location.state.queryContext.query_id}`}
      className="flex items-center gap-1 hover:text-periwinkle-600 transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      Back to query: "{location.state.queryContext.query_text}"
    </Link>
  </nav>
)}

{location.state?.fromAudit && (
  <nav className="mb-2 text-sm text-gray-600">
    <Link
      to="/audit"
      className="flex items-center gap-1 hover:text-periwinkle-600 transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      Back to audit queue ({location.state.queueRemaining} remaining)
    </Link>
  </nav>
)}
```

#### Task 3.2: Add Quick Navigation in Audit Queue
**File**: `frontend/src/pages/Audit.jsx`

**Add to Field Review Panel**:
```jsx
<div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
  <Link
    to={`/documents/${currentItem.document_id}`}
    state={{
      fromAudit: true,
      queueRemaining: queue.length - currentIndex - 1,
      highlightField: currentItem.field_id
    }}
    className="text-sm text-blue-700 hover:text-blue-800 font-medium flex items-center gap-2"
  >
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
    View full document for context
  </Link>
</div>
```

---

### Phase 4: Keyboard Shortcuts (Future) ⌨️
**Time**: 2 hours
**Priority**: P3 (Power User Feature)

#### Add Global Keyboard Shortcuts
**File**: `frontend/src/pages/DocumentDetail.jsx`

```jsx
useEffect(() => {
  const handleKeyPress = (e) => {
    // Ignore if user is typing in input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      return;
    }

    switch(e.key) {
      case 'e':
        // Edit next field that needs review
        const nextField = filteredFields.find(f => !f.verified && f.confidence < thresholds.audit);
        if (nextField) {
          handleVerifyField(nextField);
        }
        break;

      case 'v':
        // Mark document as verified
        handleMarkVerified();
        break;

      case 'n':
        // Next field in current filter
        // ... scroll to next field
        break;

      case 'p':
        // Previous field
        // ... scroll to previous field
        break;

      case '?':
        // Show keyboard shortcuts help
        setShowShortcutsModal(true);
        break;
    }
  };

  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, [document, filteredFields]);
```

**Add Shortcuts Help Modal**:
```jsx
<Modal isOpen={showShortcutsModal} onClose={() => setShowShortcutsModal(false)}>
  <h3 className="text-lg font-bold mb-4">Keyboard Shortcuts</h3>
  <dl className="space-y-2">
    <div className="flex items-center justify-between">
      <dt className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">E</dt>
      <dd className="text-sm text-gray-600">Edit next field needing review</dd>
    </div>
    <div className="flex items-center justify-between">
      <dt className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">V</dt>
      <dd className="text-sm text-gray-600">Mark document as verified</dd>
    </div>
    <div className="flex items-center justify-between">
      <dt className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">N</dt>
      <dd className="text-sm text-gray-600">Next field</dd>
    </div>
    <div className="flex items-center justify-between">
      <dt className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">P</dt>
      <dd className="text-sm text-gray-600">Previous field</dd>
    </div>
    <div className="flex items-center justify-between">
      <dt className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">?</dt>
      <dd className="text-sm text-gray-600">Show this help</dd>
    </div>
  </dl>
</Modal>
```

---

## Success Metrics

### User Experience
- ✅ **Time to Review Document**: Target <2 minutes per document (currently ~3-5 min)
- ✅ **PDF Load Success Rate**: Target 100% (currently ~0% due to bug!)
- ✅ **Edit Actions per Session**: Expect 3x increase (inline editing vs modal)
- ✅ **User Confusion**: Reduce support tickets about "which view to use"

### Technical
- ✅ **PDF Rendering**: <2 seconds
- ✅ **Field Save Time**: <500ms
- ✅ **Document Verification**: <1 second
- ✅ **Navigation Transitions**: Instant (client-side routing)

### Business
- ✅ **Documents Verified per Hour**: Target 2x increase
- ✅ **Extraction Accuracy**: Target 98%+ with inline corrections
- ✅ **User Adoption**: DocumentDetail should become primary interface

---

## Answering the Original Questions

### Q1: "Should you be able to audit from the docs screen (regardless of confidence)?"

**Answer: YES, with inline editing**

Users should be able to edit ANY field from the document view, regardless of confidence score. Confidence scores should:
- ✅ **Inform**: Show which fields are uncertain
- ✅ **Prioritize**: Auto-filter to "Needs Review"
- ❌ **NOT Restrict**: Don't prevent editing high-confidence fields

**Implementation**:
- Every field gets an "Edit" button (visible on hover)
- Clicking edits inline (no modal required)
- Low-confidence fields highlighted in yellow
- Filter tabs help focus on problem areas

### Q2: "Should audit be a standalone lineup of fields under the confidence threshold?"

**Answer: YES, keep as separate workflow**

The audit queue serves a different purpose:
- **Document View**: "Review THIS document completely"
- **Audit Queue**: "Clear ALL low-confidence fields efficiently"

Both are valid workflows for different scenarios.

**Implementation**:
- Keep `/audit` page for field-centric workflow
- Add navigation links between views
- Add context preservation (breadcrumbs, return links)
- Allow users to switch modes based on task

### Q3: "How to make this powerful and simple?"

**Answer: Two clear paths + Universal editing**

**SIMPLE**:
1. Clear naming: "Document View" vs "Audit Queue"
2. Clear entry points: Documents dashboard → Document view, Audit badge → Audit queue
3. One editing paradigm: Click → Edit → Save (everywhere)

**POWERFUL**:
1. Edit anything, anywhere
2. Keyboard shortcuts for power users
3. Batch operations in audit mode
4. Seamless navigation between modes
5. Context preservation across views

---

## Migration Strategy

### Week 1: Fix Critical Bug
- [ ] Apply PDF viewer prop fix
- [ ] Test on all browsers
- [ ] Deploy to staging
- [ ] User acceptance testing

### Week 2: Inline Editing
- [ ] Enhance FieldCard component
- [ ] Add save handlers
- [ ] Add "Mark as Verified" button
- [ ] User testing with beta users

### Week 3: Navigation & Polish
- [ ] Add breadcrumbs
- [ ] Add quick navigation links
- [ ] Add keyboard shortcuts
- [ ] Documentation updates

### Week 4: Launch & Monitor
- [ ] Deploy to production
- [ ] Monitor success metrics
- [ ] Gather user feedback
- [ ] Iterate based on usage

---

## Risks & Mitigations

### Risk 1: Users Confused by Two Views
**Mitigation**: Clear naming, onboarding tooltips, help documentation

### Risk 2: Inline Editing Breaks Workflows
**Mitigation**: Keep modal as fallback, allow users to choose preference

### Risk 3: Performance Issues with Large Documents
**Mitigation**: Virtual scrolling for field list, lazy load PDF pages

### Risk 4: Accidental Edits
**Mitigation**: Require explicit "Save" click, add undo functionality

---

## Conclusion

The proposed design creates **two clear workflows** that match user mental models:

1. **Document-Centric Review**: Complete verification of a specific document with universal editing
2. **Field-Centric Audit**: Efficient processing of low-confidence fields across documents

**Key Principles**:
- ✅ Confidence scores **inform**, don't **restrict**
- ✅ Edit anything, anywhere, anytime
- ✅ Seamless navigation between modes
- ✅ Context preservation across views
- ✅ Simple for basic tasks, powerful for advanced users

**Immediate Action**: Fix the PDF viewer bug (30 minutes) to unblock users TODAY.

**Next Priority**: Implement inline editing (1 sprint) to 2x user efficiency.

---

**Overall Assessment**: 🌟🌟🌟🌟🌟
The system has **excellent bones** but needs the PDF fix ASAP and inline editing for optimal UX.

---

## Appendix A: User Flows

### Flow 1: Quick Document Review
```
1. User: Navigate to /documents
2. User: Click document row
3. System: Open DocumentDetail with PDF + fields
4. User: Scan fields, click "vendor_name" → Edit
5. System: Show inline editor
6. User: Fix typo, press Enter
7. System: Save, update field in real-time
8. User: Click "Mark as Verified"
9. System: Document status → verified
10. User: Click "Export"
11. Done! (Total: ~90 seconds)
```

### Flow 2: Audit Queue Processing
```
1. User: Navigate to /audit
2. System: Show 15 low-confidence fields
3. User: Review first field in PDF
4. User: Press "1" (correct)
5. System: Auto-advance to next field
6. User: Press "2" (incorrect) → type correction
7. System: Save, auto-advance
8. ... repeat for all 15 fields ...
9. System: Show completion stats
10. Done! (Total: ~3 minutes for 15 fields)
```

### Flow 3: Search → Document → Edit
```
1. User: Ask AI: "Show me invoices over $1000"
2. System: Return 5 matching documents
3. User: Click "Acme Corp - $1,234.56"
4. System: Navigate to DocumentDetail
5. System: Highlight "total_amount" field in PDF
6. User: Sees value is "$1,234.56" (correct)
7. User: Notice "vendor_name" is wrong
8. User: Click "vendor_name" → Edit
9. System: Show inline editor
10. User: Fix, save
11. System: Update, re-index to Elasticsearch
12. User: Click breadcrumb "← Back to query"
13. System: Return to search results with updated data
14. Done! (Total: ~60 seconds)
```

---

## Appendix B: Component API Reference

### FieldCard (Enhanced)

```typescript
interface FieldCardProps {
  field: {
    id: number;
    name: string;
    value: string;
    field_type: 'text' | 'date' | 'number' | 'array' | 'table' | 'array_of_objects';
    field_value_json?: any;
    confidence: number;
    verified: boolean;
    source_page: number;
    source_bbox: [number, number, number, number];
  };
  editable?: boolean;  // NEW: Enable inline editing
  onEdit?: (field: Field) => void;  // NEW: Called when edit starts
  onSave?: (fieldId: number, newValue: string) => Promise<void>;  // NEW: Save handler
  onViewCitation?: (field: Field) => void;
  onVerify?: (field: Field) => void;
}
```

### PDFViewer (Fixed Props)

```typescript
interface PDFViewerProps {
  fileUrl: string;  // NOT filePath!
  page?: number;    // NOT currentPage!
  highlights?: Array<{  // NOT highlightedBbox!
    bbox: [number, number, number, number];
    color: string;
    label?: string;
    page: number;
  }>;
  onPageChange?: (page: number) => void;
  zoom?: number;
  onZoomChange?: (zoom: number) => void;
}
```

### DocumentDetail (New Handlers)

```typescript
interface DocumentDetailHandlers {
  handleFieldSave: (fieldId: number, newValue: string) => Promise<void>;
  handleMarkVerified: () => Promise<void>;
  handleOpenAuditQueue: () => void;
  handleFieldEdit: (field: Field) => void;
}
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-07
**Author**: Claude (Sonnet 4.5)
**Status**: Ready for Implementation
