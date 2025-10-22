# Project Implementation Plan

**Status**: MVP Development  
**Target Launch**: 4-6 weeks  
**Last Updated**: 2025-01-XX

## MVP Scope

### In Scope ✅
- Sample document analysis with Claude
- Visual schema editor
- Bulk document processing via Reducto
- Elasticsearch storage and search
- HITL verification for low-confidence extractions
- Basic analytics dashboard

### Out of Scope ❌
- Multi-user/authentication
- Template library
- Advanced analytics
- Mobile optimization
- Scheduled AI improvements
- External integrations (webhooks, API)

---

## Phase 1: Foundation & Setup

### TODO 1.1: Project Initialization
**Priority**: P0 (Blocker)  
**Estimated Time**: 2 hours  
**Dependencies**: None

- [ ] Create project directory structure
- [ ] Set up Docker Compose configuration
- [ ] Create `.env.example` with all required variables
- [ ] Initialize git repository with proper `.gitignore`
- [ ] Create `requirements.txt` for backend
- [ ] Create `package.json` for frontend
- [ ] Write initial README.md

**Acceptance Criteria**:
- `docker-compose up` starts Elasticsearch successfully
- Directory structure matches CLAUDE.md
- All placeholder env vars documented

---

### TODO 1.2: Backend Foundation
**Priority**: P0 (Blocker)  
**Estimated Time**: 4 hours  
**Dependencies**: 1.1

- [ ] Set up FastAPI application in `backend/app/main.py`
- [ ] Create database configuration (`app/core/database.py`)
- [ ] Create settings management (`app/core/config.py`)
- [ ] Add health check endpoint (`/health`)
- [ ] Configure CORS for local development
- [ ] Create database models:
  - [ ] Schema model (`app/models/schema.py`)
  - [ ] Document model (`app/models/document.py`)
  - [ ] ExtractedField model (`app/models/document.py`)
  - [ ] Verification models (`app/models/verification.py`)
- [ ] Initialize database tables on startup
- [ ] Add basic logging configuration

**Acceptance Criteria**:
- Backend starts without errors
- `/health` endpoint returns 200 OK
- Database tables created automatically
- API docs available at `/docs`

**Testing**:
```bash
# Start backend
cd backend && uvicorn app.main:app --reload

# Test health endpoint
curl http://localhost:8000/health

# Check API docs
open http://localhost:8000/docs
```

---

### TODO 1.3: Frontend Foundation
**Priority**: P0 (Blocker)  
**Estimated Time**: 3 hours  
**Dependencies**: 1.1

- [ ] Initialize Vite React app
- [ ] Install dependencies (React Router, TailwindCSS, axios)
- [ ] Configure TailwindCSS
- [ ] Set up React Router with pages:
  - [ ] `/onboarding` - Onboarding wizard
  - [ ] `/documents` - Document management
  - [ ] `/search` - Search interface
  - [ ] `/verify` - HITL verification
- [ ] Create basic layout component with navigation
- [ ] Set up API client with axios
- [ ] Add environment variable support

**Acceptance Criteria**:
- Frontend starts on port 3000
- All routes render placeholder pages
- Navigation between pages works
- Can make test API call to backend

**Testing**:
```bash
# Start frontend
cd frontend && npm run dev

# Verify routes
open http://localhost:3000/onboarding
open http://localhost:3000/documents
```

---

## Phase 2: Core Services

### TODO 2.1: Reducto Service
**Priority**: P0 (Blocker)  
**Estimated Time**: 6 hours  
**Dependencies**: 1.2

- [ ] Create `app/services/reducto_service.py`
- [ ] Implement `parse_document()` method
  - [ ] Handle file upload
  - [ ] Parse with Reducto API
  - [ ] Extract confidence scores from blocks
  - [ ] Handle URL-based results if response too large
- [ ] Implement `extract_structured()` method for schema-based extraction
- [ ] Implement `get_job_status()` for async jobs
- [ ] Add error handling and retries
- [ ] Create helper methods:
  - [ ] `extract_confidence_from_block()`
  - [ ] `get_confidence_label()` (High/Medium/Low)
  - [ ] `extract_field_from_chunks()` using hints
- [ ] Add comprehensive logging
- [ ] Write unit tests with mocked Reducto API

**Implementation Notes**:
- Reducto provides `logprobs_confidence` (0.0-1.0) in each block
- Use async/await for all API calls
- Set timeout to 300 seconds for large documents
- Cache parsed results to avoid re-processing

**Acceptance Criteria**:
- Can parse a sample PDF successfully
- Confidence scores extracted correctly
- Handles both inline and URL responses
- Tests pass with 80%+ coverage

**Testing**:
```python
# Test with sample document
from app.services.reducto_service import ReductoService
service = ReductoService()
result = await service.parse_document("test.pdf")
assert "result" in result
assert "chunks" in result["result"]
```

---

### TODO 2.2: Claude Service
**Priority**: P0 (Blocker)  
**Estimated Time**: 8 hours  
**Dependencies**: 1.2, 2.1

- [ ] Create `app/services/claude_service.py`
- [ ] Implement `analyze_sample_documents()` method
  - [ ] Accept list of Reducto parsed results
  - [ ] Build prompt with document content
  - [ ] Request schema generation from Claude
  - [ ] Parse Claude's JSON response
  - [ ] Validate schema structure
- [ ] Implement `generate_reducto_config()` method
  - [ ] Convert schema to Reducto extraction rules
  - [ ] Create chunking strategy
  - [ ] Generate system prompt for extraction
- [ ] Implement `improve_extraction_rules()` method (for future use)
- [ ] Add retry logic with exponential backoff
- [ ] Write comprehensive tests

**Schema Format** (Claude should output):
```json
{
  "name": "Service Agreements",
  "fields": [
    {
      "name": "effective_date",
      "type": "date",
      "required": true,
      "extraction_hints": ["Effective Date:", "Dated:", "As of"],
      "confidence_threshold": 0.75,
      "description": "Contract effective date"
    }
  ]
}
```

**Acceptance Criteria**:
- Claude generates valid schema from samples
- Schema includes all key fields from documents
- Extraction hints are specific and useful
- Reducto config is properly formatted

**Testing**:
```python
# Test schema generation
service = ClaudeService()
schema = await service.analyze_sample_documents([doc1, doc2, doc3])
assert "fields" in schema
assert len(schema["fields"]) > 0
```

---

### TODO 2.3: Elasticsearch Service
**Priority**: P0 (Blocker)  
**Estimated Time**: 6 hours  
**Dependencies**: 1.2

- [ ] Create `app/services/elastic_service.py`
- [ ] Implement `create_index()` with dynamic mapping
- [ ] Implement `index_document()` method
  - [ ] Store full document content
  - [ ] Store extracted field metadata
  - [ ] Store confidence scores
  - [ ] Generate vector embeddings (optional for MVP)
- [ ] Implement `search()` method
  - [ ] Keyword search
  - [ ] Metadata filters
  - [ ] Confidence-based filtering
  - [ ] Pagination
- [ ] Implement `get_document()` by ID
- [ ] Implement `update_document()` after verification
- [ ] Implement `get_aggregations()` for analytics
- [ ] Add connection health checks
- [ ] Write tests with Elasticsearch test container

**Acceptance Criteria**:
- Index created with correct mapping
- Documents indexed successfully
- Search returns relevant results
- Filters work correctly
- Tests pass

---

## Phase 3: Onboarding Flow

### TODO 3.1: Sample Upload API
**Priority**: P0 (Blocker)  
**Estimated Time**: 4 hours  
**Dependencies**: 2.1, 2.2

- [ ] Create `app/api/onboarding.py` router
- [ ] Implement `POST /api/onboarding/analyze-samples`
  - [ ] Accept file uploads (3-5 PDFs)
  - [ ] Validate file types and sizes
  - [ ] Save files temporarily
  - [ ] Parse each with Reducto
  - [ ] Analyze with Claude
  - [ ] Generate schema
  - [ ] Store schema in database
  - [ ] Return schema to frontend
- [ ] Add progress tracking for long operations
- [ ] Implement error handling
- [ ] Write integration tests

**Acceptance Criteria**:
- Can upload 5 sample PDFs
- Schema generated within 3 minutes
- Schema stored in database
- Proper error messages returned

---

### TODO 3.2: Onboarding Frontend
**Priority**: P0 (Blocker)  
**Estimated Time**: 6 hours  
**Dependencies**: 3.1

- [ ] Create `src/components/Onboarding/SampleUpload.jsx`
  - [ ] Drag-and-drop file upload
  - [ ] File list with preview
  - [ ] Upload progress indicator
  - [ ] Error handling
- [ ] Create `src/components/Onboarding/SchemaPreview.jsx`
  - [ ] Display generated schema fields
  - [ ] Show examples from documents
  - [ ] Confidence indicators
  - [ ] Edit/remove field buttons
- [ ] Create `src/pages/Onboarding.jsx`
  - [ ] Multi-step wizard (Upload → Preview → Confirm)
  - [ ] Progress indicator
  - [ ] Navigation controls
- [ ] Add loading states
- [ ] Add error states
- [ ] Make responsive

**Acceptance Criteria**:
- Users can upload sample documents
- Schema displays with examples
- UI is intuitive and responsive
- Error handling is clear

---

### TODO 3.3: Schema Editor
**Priority**: P1 (Important)  
**Estimated Time**: 8 hours  
**Dependencies**: 3.2

- [ ] Create `src/components/Onboarding/SchemaEditor.jsx`
- [ ] Implement field list with drag-to-reorder
- [ ] Implement field editor modal:
  - [ ] Edit field name
  - [ ] Change field type (dropdown)
  - [ ] Edit extraction hints (tag input)
  - [ ] Set confidence threshold (slider)
  - [ ] Toggle required flag
- [ ] Add natural language field addition
  - [ ] Text input: "Add a field for..."
  - [ ] Send to Claude for suggestions
  - [ ] Show suggested config
- [ ] Implement "Test on Samples" feature
  - [ ] Re-extract using current schema
  - [ ] Show extraction results
  - [ ] Highlight in PDF preview
- [ ] Add save/cancel functionality
- [ ] Create `PUT /api/onboarding/schema` endpoint

**Acceptance Criteria**:
- Can add/edit/remove fields visually
- Natural language addition works
- Testing shows real extraction results
- Changes persist to database

---

## Phase 4: Document Processing

### TODO 4.1: Document Upload & Processing
**Priority**: P0 (Blocker)  
**Estimated Time**: 6 hours  
**Dependencies**: 2.1, 2.3

- [ ] Create `app/api/documents.py` router
- [ ] Implement `POST /api/documents/upload`
  - [ ] Accept file uploads
  - [ ] Validate against schema
  - [ ] Store file metadata in DB
  - [ ] Save files to disk
  - [ ] Return document IDs
- [ ] Implement `POST /api/documents/process`
  - [ ] Get documents by IDs
  - [ ] Process with Reducto using schema config
  - [ ] Extract fields with confidence
  - [ ] Store in Elasticsearch
  - [ ] Update DB with results
  - [ ] Flag low-confidence fields for review
- [ ] Implement `GET /api/documents`
  - [ ] List all documents
  - [ ] Filter by status
  - [ ] Pagination
- [ ] Implement `GET /api/documents/{id}`
  - [ ] Return document + all extractions
  - [ ] Include confidence scores

**Acceptance Criteria**:
- Can upload bulk documents (100+)
- Processing completes successfully
- Extractions stored correctly
- Low-confidence items flagged

---

### TODO 4.2: Document Management Frontend
**Priority**: P1 (Important)  
**Estimated Time**: 6 hours  
**Dependencies**: 4.1

- [ ] Create `src/components/Documents/Upload.jsx`
  - [ ] Bulk file upload (drag-drop)
  - [ ] Upload queue with progress
  - [ ] Error handling per file
- [ ] Create `src/components/Documents/DocumentList.jsx`
  - [ ] Table view with key fields
  - [ ] Status indicators
  - [ ] Confidence badges
  - [ ] Click to view details
  - [ ] Bulk actions (future)
- [ ] Create `src/pages/Documents.jsx`
  - [ ] Upload area
  - [ ] Document list
  - [ ] Filters (status, confidence)
  - [ ] Search within documents
- [ ] Add processing status polling

**Acceptance Criteria**:
- Smooth bulk upload experience
- Real-time progress updates
- Clear status indicators
- Responsive design

---

## Phase 5: Search Interface

### TODO 5.1: Search API
**Priority**: P1 (Important)  
**Estimated Time**: 4 hours  
**Dependencies**: 2.3

- [ ] Create `app/api/search.py` router
- [ ] Implement `POST /api/search`
  - [ ] Accept search query
  - [ ] Accept filters (field values, confidence ranges)
  - [ ] Query Elasticsearch
  - [ ] Return results with highlights
  - [ ] Include aggregations/facets
- [ ] Implement `GET /api/search/filters`
  - [ ] Return available filter options
  - [ ] Return value distributions
- [ ] Add query caching (optional)
- [ ] Write tests

**Acceptance Criteria**:
- Search returns relevant documents
- Filters work correctly
- Fast response times (<200ms)
- Proper pagination

---

### TODO 5.2: Search Frontend
**Priority**: P1 (Important)  
**Estimated Time**: 6 hours  
**Dependencies**: 5.1

- [ ] Create `src/components/Search/SearchBar.jsx`
  - [ ] Text input with autocomplete
  - [ ] Advanced filters toggle
  - [ ] Search suggestions
- [ ] Create `src/components/Search/Results.jsx`
  - [ ] Result cards with key fields
  - [ ] Confidence indicators
  - [ ] Click to view full document
  - [ ] Pagination controls
  - [ ] Sort options
- [ ] Create `src/components/Search/Filters.jsx`
  - [ ] Filter by field values
  - [ ] Filter by confidence
  - [ ] Filter by date ranges
  - [ ] Clear filters button
- [ ] Create `src/pages/Search.jsx`
  - [ ] Combine all components
  - [ ] Handle search state
  - [ ] URL-based search (shareable links)

**Acceptance Criteria**:
- Intuitive search experience
- Filters work smoothly
- Results load quickly
- Can view document details

---

## Phase 6: HITL Verification

### TODO 6.1: Verification Queue API
**Priority**: P0 (Blocker)  
**Estimated Time**: 6 hours  
**Dependencies**: 4.1

- [ ] Create `app/api/verification.py` router
- [ ] Implement `GET /api/verification/queue`
  - [ ] Get fields below confidence threshold
  - [ ] Group by document or field
  - [ ] Sort by priority
  - [ ] Pagination
  - [ ] Include document context
- [ ] Implement `POST /api/verification/verify`
  - [ ] Accept verification data
  - [ ] Update ExtractedField in DB
  - [ ] Update Elasticsearch document
  - [ ] Create training example
  - [ ] Return next item
- [ ] Implement `GET /api/verification/stats`
  - [ ] Count items in queue
  - [ ] Verification progress
  - [ ] Accuracy improvements
- [ ] Track verification sessions
- [ ] Write tests

**Acceptance Criteria**:
- Queue returns low-confidence items
- Verifications update correctly
- Training examples created
- Stats are accurate

---

### TODO 6.2: Verification Frontend
**Priority**: P0 (Blocker)  
**Estimated Time**: 10 hours  
**Dependencies**: 6.1

- [ ] Create `src/components/Verification/ReviewQueue.jsx`
  - [ ] Show queue summary
  - [ ] Filter/group options
  - [ ] Start review button
- [ ] Create `src/components/Verification/ReviewItem.jsx`
  - [ ] Side-by-side layout (PDF + form)
  - [ ] PDF viewer with highlights
  - [ ] Extraction preview
  - [ ] Verification form (radio + custom input)
  - [ ] Skip/Next buttons
  - [ ] Keyboard shortcuts
- [ ] Create `src/components/Verification/PDFViewer.jsx`
  - [ ] Render PDF page
  - [ ] Highlight extracted regions
  - [ ] Color-code by confidence
  - [ ] Navigation controls
- [ ] Create `src/pages/Verify.jsx`
  - [ ] Queue dashboard
  - [ ] Review interface
  - [ ] Progress tracking
  - [ ] Session summary
- [ ] Implement keyboard shortcuts
  - [ ] 1-9 for options
  - [ ] Enter to confirm
  - [ ] S to skip
  - [ ] N for "not found"
- [ ] Add pattern detection suggestions

**Acceptance Criteria**:
- Efficient review workflow
- Clear visual feedback
- Keyboard shortcuts work
- Progress is tracked
- Can complete 20+ items/10min

---

## Phase 7: Analytics & Polish

### TODO 7.1: Analytics Dashboard
**Priority**: P2 (Nice to have)  
**Estimated Time**: 4 hours  
**Dependencies**: 4.1, 6.1

- [ ] Create `app/api/analytics.py` router
- [ ] Implement dashboard metrics:
  - [ ] Total documents processed
  - [ ] Average confidence by field
  - [ ] Items in verification queue
  - [ ] Processing time stats
  - [ ] Error rates
- [ ] Create simple charts (recharts)
- [ ] Add to frontend

**Acceptance Criteria**:
- Dashboard shows key metrics
- Charts are readable
- Updates in real-time

---

### TODO 7.2: Error Handling & Logging
**Priority**: P1 (Important)  
**Estimated Time**: 4 hours  
**Dependencies**: All previous

- [ ] Add structured logging throughout
- [ ] Create error handler middleware
- [ ] Add user-friendly error messages
- [ ] Create error reporting mechanism
- [ ] Add Sentry integration (optional)

**Acceptance Criteria**:
- Errors logged with context
- Users see helpful messages
- Stack traces captured

---

### TODO 7.3: Documentation & Testing
**Priority**: P1 (Important)  
**Estimated Time**: 6 hours  
**Dependencies**: All previous

- [ ] Write API documentation
- [ ] Create user guide
- [ ] Add inline code documentation
- [ ] Achieve 80% test coverage
- [ ] Create test document set
- [ ] Write deployment guide

**Acceptance Criteria**:
- All endpoints documented
- User guide covers main flows
- Tests pass consistently
- Deployment guide works

---

## Testing Checklist

### Integration Tests
- [ ] Full onboarding flow (upload → schema → confirm)
- [ ] Document processing pipeline
- [ ] Search with various filters
- [ ] HITL verification workflow
- [ ] Error handling scenarios

### Performance Tests
- [ ] Upload 100 documents
- [ ] Search with 10k+ documents
- [ ] Verify responsiveness under load

### User Acceptance Tests
- [ ] Non-technical user can complete onboarding
- [ ] Can find documents easily
- [ ] Verification is intuitive
- [ ] No major bugs

---

## Success Criteria

### Functional
- ✅ Can onboard new document type in <30 minutes
- ✅ Processes documents at 2-5 seconds each
- ✅ Search responds in <200ms
- ✅ HITL verification <30 seconds per item
- ✅ >90% extraction accuracy after initial feedback

### Technical
- ✅ 80%+ test coverage
- ✅ All endpoints documented
- ✅ Docker deployment works
- ✅ Handles 1000+ documents smoothly

### Business
- ✅ Onboarding cost: <$5
- ✅ Processing cost: $25-35 per 1000 docs
- ✅ User can get value in first session
- ✅ Platform is self-service

---

## Future Enhancements (Post-MVP)

1. **Multi-user Support**
   - Authentication & authorization
   - User management
   - Team collaboration

2. **Template Library**
   - Pre-built schemas
   - Community templates
   - Quick start options

3. **Advanced Features**
   - Scheduled AI improvements
   - Batch operations
   - Export integrations
   - Webhook notifications

4. **Scale & Performance**
   - PostgreSQL migration
   - Celery background jobs
   - Redis caching
   - Kubernetes deployment

---

## Notes for Claude Code

When working on this project:
1. **Always read the relevant TODO section before starting**
2. **Update checkboxes as you complete items**
3. **Add implementation notes if you deviate from plan**
4. **Run tests after each major change**
5. **Update CLAUDE.md if architecture changes**
6. **Ask for clarification if requirements unclear**

For new features not in this plan:
1. Create a new TODO section
2. Estimate time and dependencies
3. Define acceptance criteria
4. Get approval before implementing
