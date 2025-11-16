# Inline Citations & Bounding Box Display Fix

**Date**: 2025-11-06
**Issue**: AI answers were displaying values without confidence indicators or bounding box highlights
**Status**: ✅ Fixed

## Problem

When users asked questions like "what is the back rise for size 2?", the AI would respond with:
```
Perfect! I found the tech spec for style GLNLEG (Classic Legging).

Back Rise for Size 2: 7 1/2 inches
```

**Missing**:
1. ❌ No confidence indicator showing the extraction confidence (e.g., 75%)
2. ❌ No bounding box highlighting in the PDF
3. ❌ No clickable citation to verify the data

## Root Cause

The answer generation flow was:
1. Backend: Search results → Claude → **Plain text answer**
2. Frontend: Display plain text
3. Audit items with confidence/bbox were shown **separately** below the answer

**The disconnect**: Answer text mentioned values, but had no inline references to the extracted fields with their confidence/bbox data.

## Solution Architecture

### Backend: Field Reference Markers

Modified Claude to include inline field references using markers:

**Format**: `[[FIELD:field_name:document_id]]`

**Example**:
```
The back rise for size 2 is 7 1/2 inches [[FIELD:back_rise_size_2:123]]
```

This allows the frontend to:
- Extract field references
- Match them to audit items (which contain confidence/bbox)
- Render inline confidence badges
- Link to PDF highlights

### Frontend: Citation Parsing & Rendering

Created a 3-component system:

1. **answerCitations.js** (utility)
   - `extractFieldReferences()` - Parse `[[FIELD:name:id]]` markers
   - `matchReferencesToAuditItems()` - Link markers to confidence/bbox data
   - `prepareAnswerWithCitations()` - Complete pipeline

2. **AnswerWithInlineCitations.jsx** (component)
   - Renders answer text with inline `CitationBadge` components
   - Each badge shows confidence score and links to PDF

3. **AnswerWithAudit.jsx** (enhanced)
   - Detects field references in answer
   - Uses inline citations when present
   - Falls back to plain text for legacy answers

## Implementation Details

### Backend Changes

#### [claude_service.py](./backend/app/services/claude_service.py)

**1. Updated system prompt** (lines 66-85):
```python
ANSWER_GENERATION_SYSTEM = """...
- **CRITICALLY IMPORTANT**: Cite specific field values with inline references:
  "The [field_name] is [value] [[FIELD:field_name:document_id]]"
  Example: "The back rise for size 2 is 7 1/2 inches [[FIELD:back_rise_size_2:123]]"
...
"""
```

**2. Enhanced answer prompt** (lines 1150-1175):
```python
Instructions:
2. **CRITICALLY IMPORTANT**: For EVERY specific value you mention, include an inline field reference:
   Format: "The [field] is [value] [[FIELD:field_name:document_id]]"
   Examples:
   - "The back rise for size 2 is 7 1/2 inches [[FIELD:back_rise_size_2:123]]"
   - "The invoice total is $1,234.56 [[FIELD:invoice_total:456]]"
```

### Frontend Changes

#### [answerCitations.js](./frontend/src/utils/answerCitations.js) (NEW)

Utility functions for parsing field references:

```javascript
// Extract [[FIELD:name:id]] markers from text
extractFieldReferences(answerText)
// Returns: [{fieldName, documentId, startIndex, endIndex, markerText}]

// Match markers to audit items (confidence/bbox data)
matchReferencesToAuditItems(fieldReferences, auditItems)
// Returns: Map of markerText -> auditItem

// Parse answer into segments (text + citations)
prepareAnswerWithCitations(answerText, auditItems)
// Returns: [{type: 'text', content}, {type: 'citation', data}]
```

#### [AnswerWithInlineCitations.jsx](./frontend/src/components/AnswerWithInlineCitations.jsx) (NEW)

Component that renders answer with inline badges:

```jsx
<AnswerWithInlineCitations
  answerText={answer}           // "The value is 123 [[FIELD:amount:456]]"
  auditItems={auditItems}       // [{field_name: "amount", confidence: 0.75, ...}]
  onCitationClick={handler}     // Opens inline audit modal
/>
```

**Renders**:
```
The value is 123 [75%]
                 ^^^^^
                 Clickable badge showing confidence
                 Opens PDF with bbox highlighted
```

#### [AnswerWithAudit.jsx](./frontend/src/components/AnswerWithAudit.jsx) (MODIFIED)

Enhanced to use inline citations:

```jsx
// Check if answer has field references
const hasFieldReferences = extractFieldReferences(answer).length > 0;

// Render with inline citations if present
{hasFieldReferences ? (
  <AnswerWithInlineCitations
    answerText={answer}
    auditItems={auditItems}
    onCitationClick={handleInlineCitationClick}
  />
) : (
  // Fallback to plain text for legacy answers
  <p>{answer}</p>
)}
```

## User Experience Improvements

### Before
```
Q: What is the back rise for size 2?
A: The back rise for size 2 is 7 1/2 inches.

[Separately below]
📋 Fields Needing Review (3)
  - back_rise_size_2: 7 1/2 inches [75%] → Click to audit
```

**Problems**:
- Value and confidence are disconnected
- No direct link from answer to audit
- No bounding box visible

### After
```
Q: What is the back rise for size 2?
A: The back rise for size 2 is 7 1/2 inches [75%].
                                              ^^^^^
                                     Inline confidence badge
                                     Click → Opens PDF with bbox highlight

[Still shown below for bulk review]
📋 Fields Needing Review (3)
  - back_rise_size_2: 7 1/2 inches [75%]
  - tolerance_size_2: -1/4" to +1/4" [68%]
  - pom_code: B510 [82%]
```

**Improvements**:
- ✅ Confidence shown inline with value
- ✅ Single click to verify in PDF
- ✅ Bounding box automatically highlighted
- ✅ Context preserved (no navigation away from answer)

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Query: "What is the back rise for size 2?"         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Backend: Claude generates answer with field references  │
│    "The back rise for size 2 is 7 1/2 inches               │
│     [[FIELD:back_rise_size_2:123]]"                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend: Returns both:                                   │
│    - answer: "... [[FIELD:back_rise_size_2:123]]"          │
│    - audit_items: [{field_id, confidence: 0.75, bbox, ...}]│
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Frontend: Parse [[FIELD:...]] markers                   │
│    extractFieldReferences(answer)                           │
│    → [{fieldName: "back_rise_size_2", documentId: 123}]    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Frontend: Match to audit items                          │
│    matchReferencesToAuditItems(refs, auditItems)           │
│    → Map {                                                  │
│        "[[FIELD:back_rise_size_2:123]]" => {               │
│          confidence: 0.75,                                  │
│          source_bbox: [100, 200, 50, 20],                  │
│          source_page: 1,                                    │
│          file_path: "/uploads/techspec.pdf"                │
│        }                                                    │
│      }                                                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Frontend: Render inline citations                       │
│    <AnswerWithInlineCitations />                            │
│    → "The back rise for size 2 is 7 1/2 inches [75%]"     │
│                                                 ^^^^^       │
│                                            CitationBadge    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼ (User clicks badge)
┌─────────────────────────────────────────────────────────────┐
│ 7. Frontend: Open inline audit modal                       │
│    <InlineAuditModal field={...} />                         │
│    → Shows PDF with bbox [100, 200, 50, 20] highlighted   │
│    → User can verify/correct value                         │
│    → Answer auto-updates after verification                │
└─────────────────────────────────────────────────────────────┘
```

## Backward Compatibility

The implementation is fully backward compatible:

1. **Legacy answers without field references**:
   - Frontend detects no `[[FIELD:...]]` markers
   - Falls back to plain text rendering
   - Audit items still shown separately below

2. **Existing audit items**:
   - Still fetched from database with confidence/bbox
   - Still available for separate review
   - No data migration needed

3. **Gradual rollout**:
   - New queries will have inline citations
   - Old queries in history remain readable
   - No breaking changes

## Testing Checklist

- [ ] Query with simple text field: "What is the invoice number?"
  - Should show: "The invoice number is INV-123 [85%]"
- [ ] Query with numeric field: "What is the total amount?"
  - Should show: "The total amount is $1,234.56 [92%]"
- [ ] Query with low-confidence field: "What is the PO number?"
  - Should show: "The PO number is PO-456 [58%]" (yellow badge)
- [ ] Click inline citation badge
  - Should open inline audit modal
  - Should show PDF with bounding box highlighted
  - Should allow verification
- [ ] Verify a field via inline modal
  - Answer should update with new confidence
  - Badge should change color if threshold crossed
- [ ] Query without field extraction (general search)
  - Should fall back to plain text answer
  - No broken markers visible

## Performance Impact

**Minimal overhead**:
- Backend: No additional API calls (Claude already called for answer)
- Frontend: Lightweight parsing (regex + string manipulation)
- Rendering: CitationBadge components already optimized

**Estimated overhead**:
- Parse time: <1ms per answer (typical: 2-5 field references)
- Render time: <5ms per citation badge
- Memory: <1KB per answer with citations

## Future Enhancements

### Phase 2: Enhanced Bounding Box Display
- [ ] Show bbox preview on hover (tooltip with mini PDF screenshot)
- [ ] Multi-field highlighting (highlight all cited fields simultaneously)
- [ ] Bbox confidence visualization (color intensity based on confidence)

### Phase 3: Smart Citation Fallback
- [ ] If field reference missing, auto-detect value in answer text
- [ ] Fuzzy match answer values to audit items
- [ ] Example: "7 1/2 inches" → search audit_items for matching value

### Phase 4: Citation Analytics
- [ ] Track which fields users click most
- [ ] Identify patterns in low-confidence citations
- [ ] Auto-suggest schema improvements based on citation patterns

## Related Issues

- [INLINE_AUDIT_IMPLEMENTATION.md](./INLINE_AUDIT_IMPLEMENTATION.md) - Inline audit modal (Phase 1)
- [BATCH_AUDIT_IMPLEMENTATION.md](./BATCH_AUDIT_IMPLEMENTATION.md) - Batch verification (Phase 2)
- [docs/features/LOW_CONFIDENCE_AUDIT_LINKS.md](./docs/features/LOW_CONFIDENCE_AUDIT_LINKS.md) - Audit deep linking

## Deployment Notes

1. **No database migration needed** - Uses existing `ExtractedField.source_bbox` column
2. **No environment variables needed** - Uses existing confidence thresholds
3. **No breaking API changes** - Answer format enhanced, not changed
4. **Safe to deploy incrementally**:
   - Deploy backend first → answers get field references
   - Deploy frontend next → field references render as badges
   - If only backend deployed: markers visible in text (minor UX issue)
   - If only frontend deployed: falls back to plain text (safe)

## Files Modified

### Backend
- [backend/app/services/claude_service.py](./backend/app/services/claude_service.py) - Added field reference instructions to prompts

### Frontend (New Files)
- [frontend/src/utils/answerCitations.js](./frontend/src/utils/answerCitations.js) - Citation parsing utilities
- [frontend/src/components/AnswerWithInlineCitations.jsx](./frontend/src/components/AnswerWithInlineCitations.jsx) - Inline citation renderer

### Frontend (Modified Files)
- [frontend/src/components/AnswerWithAudit.jsx](./frontend/src/components/AnswerWithAudit.jsx) - Integrated inline citations

## Success Metrics

Track these metrics to measure impact:

1. **User Engagement**:
   - % of answers with field references (target: >80%)
   - Click-through rate on inline citations (target: >40%)
   - Time from question to verification (target: <10 seconds)

2. **Data Quality**:
   - % of low-confidence fields verified via inline citations (target: >60%)
   - Verification accuracy (accept vs. reject rate)
   - Time to complete verification (target: <5 seconds per field)

3. **Technical Metrics**:
   - Citation parsing success rate (target: 100%)
   - Citation-to-audit-item match rate (target: >95%)
   - Bbox highlighting success rate (target: >98%)

---

**Status**: ✅ Ready for testing
**Next Steps**: Test with sample queries, verify bbox highlighting, collect user feedback
