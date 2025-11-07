# Testing New Features Guide

**Date**: 2025-11-01
**Features to Test**: Extraction Preview + Enhanced Query Suggestions

---

## What We Just Built

### 1. **Extraction Preview in ProcessingModal** ✨
Shows live field extraction during document processing with confidence scores.

### 2. **Enhanced Query Suggestions UI** ✨
Beautiful category-aware suggestion chips with icons and color coding.

---

## Current Situation

Your uploaded documents (`Tableprimary.png`) are stuck at the **template assignment** stage. This is EXPECTED behavior in the bulk upload workflow.

**Database shows:**
```
id=40,41,42 | status=template_needed | progress=0%
```

**Why?** Documents are waiting for you to:
1. Review the template suggestions
2. Click "Process All" or assign templates individually
3. THEN extraction begins (and ProcessingModal preview activates)

---

## Step-by-Step Testing Guide

### Step 1: Navigate to Bulk Upload Page

1. Open browser to: **http://localhost:3002/**
2. You should see the BulkUpload page
3. It should show your 3 uploaded documents grouped by template

**Expected UI:**
```
Review & Process Documents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3 documents grouped into 1 template. Review and assign templates below.

┌──────────────────────────────────────────────────────────────┐
│ Documents     │ Template       │ Match │ Actions            │
├──────────────────────────────────────────────────────────────┤
│ 3 files       │ ✨ Table       │ 🟢 85%│ [Process]          │
│ Tableprimary…│                │ ⚡ Fast│                    │
└──────────────────────────────────────────────────────────────┘
```

---

### Step 2: Process Documents

**Option A: Process All (Recommended)**
1. Click **"Process All (3 docs)"** button in top-right
2. Backend will start extraction for all groups
3. **ProcessingModal opens automatically** ✅
4. Watch live extraction preview appear!

**Option B: Process Individual Group**
1. Click "Explore ▼" dropdown on a group
2. Select option (e.g., "Edit Template Fields")
3. Or just click "Process All"

---

### Step 3: Watch Extraction Preview (NEW FEATURE #1)

Once processing starts, you'll see:

```
Processing Documents
━━━━━━━━━━━━━━━━ 33%

📄 Tableprimary.png ⚠                    [████████░░] Processing...
   ├─ column_1: "Product Name"           92%
   ├─ column_2: "Price"                  88%
   ├─ column_3: "Quantity"               54% ⚠
   └─ + 5 more fields                    ▼

📄 Tableprimary.png                      [██████████] Complete
   ├─ column_1: "SKU"                    95%
   ├─ column_2: "Description"            91%
   └─ [8 fields extracted]               ▼
```

**What to observe:**
- ✅ Fields appear in real-time as extraction completes
- ✅ Confidence scores color-coded (green/yellow/red)
- ✅ Warning badge (⚠) for low-confidence docs
- ✅ Expandable field lists (click ▼ to see all)
- ✅ Smooth animations and progress updates

---

### Step 4: Test Enhanced Query Suggestions (NEW FEATURE #2)

After documents complete processing:

1. Navigate to: **http://localhost:3002/query** (or click "Ask AI" tab)
2. Look at the suggestion chips below the search bar

**Expected UI:**
```
✨ Smart suggestions for your documents

[📅 Show documents from last month]  [💰 Find invoices over $1000]
[⚠️ Show low confidence fields]      [🔍 Find vendor "ACME Corp"]
```

**What to observe:**
- ✅ Context indicator badge at top
- ✅ Category-aware icons (📅💰⚠️🔍)
- ✅ Color coding by category (blue=time, green=amount, yellow=quality, purple=search)
- ✅ Hover animations
- ✅ Click to auto-fill query

**Test interactions:**
1. **Hover** over chips - see subtle scale animation
2. **Click** a suggestion - it fills the search input
3. **Submit** the query - see AI-powered search results

---

## Alternative: Upload New Documents

If the current documents are stuck, you can also test with fresh uploads:

### Quick Test Upload

1. Go to **http://localhost:3002/** (BulkUpload page)
2. Click **"Upload & Analyze"** to reset
3. Drop 2-3 sample PDFs (invoices, receipts, etc.)
4. Wait for grouping/matching to complete
5. Click **"Process All"**
6. **ProcessingModal opens** - BOOM! See extraction preview live! ✨

---

## Troubleshooting

### If BulkUpload page shows no groups:

**Problem:** Previous analysis state is cached
**Solution:**
1. Refresh page (F5)
2. Or click "Upload & Analyze" again with new files

### If ProcessingModal doesn't show extraction preview:

**Problem:** Backend not returning `extracted_fields`
**Solution:**
1. Check backend logs: `docker-compose logs -f backend`
2. Verify `/api/documents?ids=X` returns `extracted_fields` array
3. Check database: `sqlite3 backend/app.db "SELECT id, status, has_low_confidence_fields FROM documents"`

### If Query Suggestions show generic queries:

**Problem:** No template context detected
**Expected:** This is fine! Generic suggestions are the fallback.
**To test template-aware suggestions:**
1. Upload documents with a specific template
2. Navigate to `/query?template_id=1`
3. Suggestions will be template-specific

---

## Success Criteria

### ✅ Extraction Preview Working When:
- [ ] ProcessingModal opens during document processing
- [ ] Fields appear incrementally with confidence scores
- [ ] Color coding works (green ≥80%, yellow 60-80%, red <60%)
- [ ] Low-confidence warning badge shows (⚠)
- [ ] Expand/collapse button works
- [ ] "Extracting fields..." shows for in-progress docs

### ✅ Query Suggestions Working When:
- [ ] Suggestion chips visible on ChatSearch page
- [ ] Context indicator shows at top
- [ ] Category icons display correctly
- [ ] Color coding matches category
- [ ] Hover animations smooth
- [ ] Click fills search input
- [ ] Template-specific suggestions when context available

---

## Next Steps After Testing

Once you've verified both features work:

1. **Documentation** - Update CLAUDE.md with new features (1 hour)
2. **Citation Modal** - Build the big swing feature (6-8 hours)
3. **ProcessingModal Enhancements** - Add inline editing, filtering (2-4 hours)

---

**Need help?** Check:
- [EXTRACTION_PREVIEW_FEATURE.md](./EXTRACTION_PREVIEW_FEATURE.md) - Complete extraction preview docs
- [QUERY_SUGGESTIONS_FEATURE.md](./QUERY_SUGGESTIONS_FEATURE.md) - Complete query suggestions docs
- [NEXT_STEPS_ANALYSIS.md](./NEXT_STEPS_ANALYSIS.md) - Strategic roadmap

**Status:** 🎯 Ready to test!
