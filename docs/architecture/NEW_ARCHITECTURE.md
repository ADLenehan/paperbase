# New Paperbase Architecture - Option A Implementation

## Overview
Complete rebuild of Paperbase following the "SIMPLE and POWERFUL" philosophy with bulk-first workflow.

## Key Changes from Original Design

### 1. **Bulk Upload First** (New Entry Point)
**Old Flow:** Templates → Samples → Schema → Upload
**New Flow:** Upload → Auto-match Templates → Confirm → Process

**Implementation:**
- `POST /api/bulk/upload-and-analyze` - Upload docs, analyze with Claude, suggest templates
- Documents start with `status="uploaded"` and no schema
- Claude groups similar documents automatically
- Template matching with confidence scores

### 2. **Auto-Template Matching**
**How it works:**
1. User uploads multiple documents (any type)
2. Reducto parses each document (extract text)
3. Claude analyzes and groups similar documents
4. Claude matches each group to existing templates
5. High confidence (≥0.7) = auto-suggest, Low = create new template

**Backend:**
- `ClaudeService.analyze_documents_for_grouping()` - Groups docs by similarity
- `ClaudeService.match_document_to_template()` - Matches to templates
- Document model updated with `suggested_template_id`, `template_confidence`

**Frontend:**
- `BulkUpload.jsx` - Main upload page (now at `/`)
- Shows grouped documents with template suggestions
- "Use This Template" or "Create New Template" options per group

### 3. **Bulk Confirmation UI**
**Row-based extraction view** - See all docs × fields in a table

**Features:**
- Table: Documents (rows) × Fields (columns)
- Inline editing for corrections
- Confidence color-coding (green/yellow/red backgrounds)
- Bulk "Confirm All & Continue" button
- Stats showing high/medium/low confidence counts

**Implementation:**
- `BulkConfirmation.jsx` - Table view with editable cells
- `POST /api/bulk/verify` - Batch verification endpoint
- Updates Elasticsearch and database in one call

### 4. **Document Status Dashboard**
**See all documents with processing status**

**Status Flow:**
```
uploaded → analyzing → template_matched → processing → completed → verified
         ↘ template_needed (if no match)
         ↘ error (if failed)
```

**Features:**
- Filterable table showing all documents
- Status badges with color coding
- Quick stats cards (Total, Analyzing, Matched, Processing, Completed)
- Click stats to filter documents

**Implementation:**
- `DocumentsDashboard.jsx` - Replaces old Documents page
- Uses updated Document model with new statuses

### 5. **Natural Language Search**
**Chat interface for document search**

**How it works:**
1. User asks: "Show me all invoices over $1000"
2. Claude converts to Elasticsearch query
3. ES executes search
4. Claude generates natural language answer
5. Shows results with explanation

**Backend:**
- `ClaudeService.natural_language_search()` - Query conversion
- `ClaudeService.answer_question_about_results()` - Answer generation
- `POST /api/search/nl` - NL search endpoint
- `ElasticsearchService.search()` updated to accept `custom_query`

**Frontend:**
- `ChatSearch.jsx` - Chat interface (now at `/search`)
- Conversation history for context
- Example queries to get started
- Shows answer + matching documents

## New API Endpoints

### Bulk Upload Flow
```
POST /api/bulk/upload-and-analyze
- Upload files
- Parse with Reducto
- Group with Claude
- Match to templates
- Returns: groups with template suggestions

POST /api/bulk/confirm-template
- Confirm template for document group
- Creates/gets schema from template
- Triggers processing
- Returns: schema_id

POST /api/bulk/create-new-template
- Create new template for unmatched docs
- Analyzes with Claude
- Creates schema
- Returns: schema with fields

POST /api/bulk/verify
- Bulk verification of extracted fields
- Updates all documents at once
- Syncs to Elasticsearch
- Returns: verification session
```

### Natural Language Search
```
POST /api/search/nl
- Natural language query
- Conversation history for context
- Returns: answer, explanation, results, ES query
```

## Updated Models

### Document Model
```python
# New fields:
suggested_template_id = ForeignKey(SchemaTemplate)
template_confidence = Float  # 0.0-1.0

# New statuses:
uploaded, analyzing, template_matched, template_needed,
ready_to_process, processing, completed, verified, error
```

### Schema Model
- No changes needed (already supports templates via `is_template` and `template_id`)

## Frontend Routes

```
/              → BulkUpload (new entry point)
/upload        → BulkUpload
/confirm       → BulkConfirmation
/documents     → DocumentsDashboard (status dashboard)
/search        → ChatSearch (natural language)
/verify        → Verify (individual field review)
/analytics     → Analytics

# Old routes preserved for reference:
/documents-old → Documents (old upload flow)
/search-old    → Search (old keyword search)
/onboarding    → Onboarding (sample-based)
```

## Key Design Decisions

### 1. **Simplicity**
- Single upload endpoint does everything
- Auto-suggest templates (no manual selection upfront)
- Bulk operations (not one-by-one)
- Natural language search (no complex filters)

### 2. **Power**
- Claude for intelligence (grouping, matching, NL search)
- Elasticsearch for speed (all structured queries)
- Confidence-driven UX (auto vs manual review)
- Learning loop ready (verifications → improvements)

### 3. **Cost Optimization**
- Claude used only for:
  1. Template matching (once per upload batch)
  2. Schema generation (once per new template)
  3. NL search query conversion (per search)
  4. Answer generation (per search)
- Reducto does all extraction (no per-doc LLM)
- Elasticsearch handles all data queries (no per-query LLM)

## User Flow

### Happy Path
1. **Upload** → Drop 10 invoices on homepage
2. **Auto-match** → System: "These look like invoices (95% confidence)"
3. **Confirm** → User clicks "Use This Template"
4. **Review** → Table shows all 10 docs × fields with confidence colors
5. **Fix** → Edit 2 low-confidence fields inline
6. **Confirm** → Click "Confirm All & Continue"
7. **Search** → Ask "Show me invoices over $500"
8. **Results** → Get answer + matching documents

### New Template Path
1. **Upload** → Drop 5 contracts (new type)
2. **Auto-match** → System: "No good template match - create new?"
3. **Create** → User enters "Service Contracts", clicks "Create & Continue"
4. **Generated** → Claude analyzes and suggests schema with 12 fields
5. **Edit** → User tweaks field names/types if needed
6. **Confirm** → Schema saved, processing starts
7. **Review** → Same bulk confirmation flow

## Testing Checklist

### Backend
- [ ] Test bulk upload with mixed document types
- [ ] Verify template matching accuracy
- [ ] Test schema generation from samples
- [ ] Verify bulk verification updates ES correctly
- [ ] Test NL search query conversion
- [ ] Test conversation history in NL search

### Frontend
- [ ] Test drag-and-drop upload
- [ ] Verify template suggestions display
- [ ] Test table editing in bulk confirmation
- [ ] Verify confidence color coding
- [ ] Test document status dashboard filters
- [ ] Test chat search interface

### Integration
- [ ] Complete flow: Upload → Match → Confirm → Review → Search
- [ ] New template flow: Upload → Create → Generate → Review
- [ ] Verify ES indexing after processing
- [ ] Test verification syncing to ES

## Migration Notes

### For Users
- New entry point is simpler (just upload, no setup)
- Old onboarding flow still available at `/onboarding`
- Old search still available at `/search-old`

### For Developers
- Main changes in:
  - `backend/app/api/bulk_upload.py` (new)
  - `backend/app/services/claude_service.py` (added methods)
  - `backend/app/models/document.py` (updated)
  - `frontend/src/pages/BulkUpload.jsx` (new)
  - `frontend/src/pages/BulkConfirmation.jsx` (new)
  - `frontend/src/pages/DocumentsDashboard.jsx` (new)
  - `frontend/src/pages/ChatSearch.jsx` (new)

### Database Migration
Run migration to add new columns to Document table:
```sql
ALTER TABLE documents ADD COLUMN suggested_template_id INTEGER;
ALTER TABLE documents ADD COLUMN template_confidence FLOAT;
ALTER TABLE documents MODIFY COLUMN schema_id INTEGER NULL;
```

## Performance Targets

- **Upload & Analysis:** <2 min for 10 documents
- **Template Matching:** <5 seconds per group
- **Bulk Confirmation:** <500ms to save all verifications
- **NL Search:** <3 seconds (Claude + ES)
- **Chat Response:** <2 seconds for answer generation

## Future Enhancements

1. **Smart Defaults:** Pre-fill high-confidence fields as "confirmed"
2. **Anomaly Detection:** Flag unusual values automatically
3. **Learning Loop:** Weekly schema improvements from verifications
4. **Batch Actions:** Process/delete/export multiple doc groups
5. **Advanced Chat:** Follow-up questions, aggregations, comparisons
6. **Export:** Bulk export to CSV/Excel with filters

## Security Considerations

- File upload size limits (enforced)
- API rate limiting for Claude calls
- Input validation on all endpoints
- Elasticsearch query injection prevention
- User authentication (TODO for multi-user)

---

**Built with:** FastAPI, React, Claude Sonnet 4.5, Reducto, Elasticsearch
**Status:** ✅ Complete - Ready for Testing
**Next Steps:** End-to-end testing, refinement based on user feedback
