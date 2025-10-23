# Paperbase - MVP

## Project Overview
A no-code document extraction platform that uses Reducto for parsing, Elasticsearch for storage/search, and Anthropic Claude for AI-powered schema generation and improvements.

**Status**: ✅ Multi-Template Extraction Complete (Backend Ready)

### Latest Update: Multi-Template Extraction (2025-10-11)
- ✅ One file → Multiple extractions with different templates
- ✅ Automatic file deduplication (SHA256 hash-based)
- ✅ Virtual folder organization (no physical file duplication)
- ✅ Parse result caching for cost optimization
- ✅ Batch processing API
- ⏳ Frontend components pending

**See**: [MULTI_TEMPLATE_EXTRACTION.md](./MULTI_TEMPLATE_EXTRACTION.md) | [Quick Start](./MULTI_TEMPLATE_QUICKSTART.md)

### Elasticsearch Optimization (2025-10-23)
- ✅ Production-ready mapping with `dynamic: strict`
- ✅ Field limits to prevent mapping explosion (max 1000 fields)
- ✅ Keyword field protection with `ignore_above` (prevents indexing failures)
- ✅ Storage optimization: Removed redundant `.raw` sub-fields (-30% storage)
- ✅ Bulk indexing optimization helpers (20-30% faster)
- ✅ Index statistics monitoring API

**See**: [docs/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md](./docs/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)

## Core Value Proposition (NEW)
Users upload documents → AI auto-matches templates → Bulk confirmation → Natural language search

**Key Innovation**: Bulk-first workflow with intelligent template matching - SIMPLE and POWERFUL

## Tech Stack
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy, SQLite
- **Frontend**: React 18, TailwindCSS, Vite
- **Document Processing**: Reducto API (provides confidence scores)
- **Search**: Elasticsearch 8.x (open source, self-hosted)
- **AI**: Anthropic Claude Sonnet 4.5
- **Deployment**: Docker Compose

## Architecture Pattern
```
Frontend (React) → Backend (FastAPI) → Services (Reducto, Elastic, Claude)
                                     ↓
                              SQLite (metadata + parse cache)

Reducto Pipeline Flow (Optimized):
Upload → Parse (job_id) → Template Match → Extract (jobid://) → Index
         ↓ cache                          ↑ reuse (no re-upload!)
```

## Key Design Decisions

### Cost Optimization Strategy
- **Claude**: Used ONLY for:
  1. Template matching (once per upload batch)
  2. Schema generation (once per new template)
  3. NL search query conversion (per search, cached)
  4. Weekly improvements from verifications
- **Reducto**: Does all document parsing and extraction
  - **Pipeline Optimization**: Uses `jobid://` to reuse parse results
  - **Savings**: 50-75% fewer API calls, ~60% cost reduction per document
- **Elasticsearch**: Handles all structured queries (no LLM per-query)
- **Target**: <$2 per upload batch (down from $3), ~$15-20 per 1000 docs/month

### Confidence Scores
- **Source**: Reducto provides `logprobs_confidence` (0.0-1.0) for each extraction
- **Labels**: High (≥0.8), Medium (0.6-0.8), Low (<0.6)
- **HITL Trigger**: Fields below threshold automatically flagged for review

### Schema-Driven Extraction
1. Claude analyzes sample docs → generates schema + extraction rules
2. Rules stored as JSON config
3. Reducto applies rules to all subsequent docs (no LLM per-doc)
4. User verifications create training examples for improvement

### Elasticsearch Best Practices (NEW)
- **Explicit Mapping**: `dynamic: strict` prevents unexpected schema changes
- **Field Protection**: `ignore_above: 256` on keyword fields prevents indexing failures
- **Storage Optimization**: Text fields use text+keyword (not text+keyword+raw) for 30% savings
- **Mapping Explosion Prevention**: Hard limits on total fields (1000), depth (20), nested (50)
- **Bulk Indexing**: Temporary refresh disabling for 20-30% faster bulk operations
- **Production Ready**: Settings optimized for reliability and performance at scale

## Project Structure
```
paperbase/
├── CLAUDE.md                    # ← You are here
├── PROJECT_PLAN.md              # Feature roadmap with TODOs
├── .claude/                     # Claude Code configuration
│   ├── settings.json
│   ├── commands/                # Slash commands
│   │   ├── setup.md
│   │   ├── test.md
│   │   ├── review.md
│   │   └── deploy.md
│   └── hooks/                   # Git hooks
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── api/                 # API routes
│   │   ├── services/            # Business logic
│   │   ├── models/              # SQLAlchemy models
│   │   └── core/                # Config, DB
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── pages/               # Page components
│   │   └── App.jsx
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## Key Files to Understand

### Backend (NEW Architecture)
- `app/main.py` - FastAPI application entry point
- `app/api/settings.py` - **NEW** Settings management API with hierarchy
- `app/api/audit.py` - **UPDATED** HITL audit with dynamic thresholds
- `app/api/bulk_upload.py` - **OPTIMIZED** Bulk upload with pipeline & folder organization
- `app/services/settings_service.py` - **NEW** Hierarchical settings resolution
- `app/services/claude_service.py` - **UPDATED** Template matching + NL search
- `app/services/reducto_service.py` - **OPTIMIZED** Pipeline support with `jobid://`
- `app/services/elastic_service.py` - **UPDATED** Custom query support
- `app/models/settings.py` - **NEW** Settings, Organization, User models
- `app/models/document.py` - **UPDATED** Parse caching & template fields
- `app/utils/file_organization.py` - **NEW** Template-based folder structure
- `app/models/schema.py` - Schema database models
- `app/models/verification.py` - HITL verification tracking

### Frontend (NEW Architecture)
- `src/pages/Settings.jsx` - **NEW** Configurable thresholds with sliders
- `src/pages/Audit.jsx` - **PRIMARY** HITL audit interface with PDF viewer
- `src/pages/BulkUpload.jsx` - **NEW** Main entry point - upload & template matching
- `src/pages/BulkConfirmation.jsx` - **NEW** Bulk table view for verification
- `src/pages/DocumentsDashboard.jsx` - **NEW** Status dashboard
- `src/pages/ChatSearch.jsx` - **NEW** Natural language search interface
- `src/pages/Onboarding.jsx` - (Legacy) Sample upload & schema generation
- `src/pages/Verify.jsx` - **DEPRECATED** - Use Audit.jsx instead

## Development Workflow

### Starting Development
```bash
# Start all services
docker-compose up

# Backend only (for development)
cd backend && uvicorn app.main:app --reload

# Frontend only (for development)
cd frontend && npm run dev
```

### Making Changes
1. Always update tests when changing logic
2. Run `npm run lint` (frontend) or `ruff check .` (backend) before committing
3. Test with sample documents in `test_documents/` folder
4. Update CLAUDE.md if architecture changes

### Environment Variables
Required in `.env`:
- `REDUCTO_API_KEY` - Get from https://reducto.ai
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com

## Common Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Check types
mypy app/

# Lint
ruff check app/
```

### Frontend
```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Docker
```bash
# Build and start
docker-compose up --build

# Rebuild specific service
docker-compose up --build backend

# View logs
docker-compose logs -f backend

# Reset everything
docker-compose down -v
```



## API Endpoints

### NEW: Settings Management (Hierarchical Configuration)
- `GET /api/settings/` - Get all settings with hierarchy resolution
- `GET /api/settings/{key}` - Get specific setting value
- `PUT /api/settings/{key}?level={system|organization|user}` - Update setting
- `DELETE /api/settings/{key}?level={level}` - Reset to fallback value
- `POST /api/settings/initialize` - Initialize system defaults
- `GET /api/settings/categories/list` - Get available categories
- `GET /api/settings/category/{category}` - Get settings by category

**Configurable Settings:**
- `template_matching_threshold` - Claude fallback threshold (0.0-1.0, default: 0.70)
- `audit_confidence_threshold` - Max confidence for audit queue (0.0-1.0, default: 0.6)
- `confidence_threshold_high` - High confidence label (0.0-1.0, default: 0.8)
- `confidence_threshold_medium` - Medium confidence label (0.0-1.0, default: 0.6)
- `enable_claude_fallback` - Enable Claude fallback (bool, default: true)
- `batch_size` - Parallel processing limit (1-50, default: 10)

### NEW: Audit (HITL Review - Primary Interface)
- `GET /api/audit/queue` - Get low-confidence fields (uses dynamic threshold)
- `GET /api/audit/document/{document_id}` - Get audit fields for document
- `POST /api/audit/verify` - Verify field extraction
- `GET /api/audit/stats` - Statistics with dynamic confidence thresholds

### NEW: Bulk Upload Flow (Primary)
- `POST /api/bulk/upload-and-analyze` - Upload, parse, group, match templates
- `POST /api/bulk/confirm-template` - Confirm template & start processing
- `POST /api/bulk/create-new-template` - Create schema for unmatched docs
- `POST /api/bulk/verify` - Bulk verification of extracted fields

### NEW: Natural Language Search
- `POST /api/search/nl` - Natural language query → ES query + answer

### Templates
- `GET /api/templates` - List all templates
- `GET /api/templates/{id}` - Get template details
- `GET /api/templates/category/{category}` - Filter by category

### Document Processing
- `POST /api/documents/upload` - Upload documents (old flow)
- `POST /api/documents/process` - Trigger Reducto processing
- `GET /api/documents/{id}` - Get document + extractions
- `GET /api/documents` - List all documents with status

### Search (Traditional)
- `POST /api/search` - Search with filters
- `GET /api/search/filters` - Get available facets

### HITL Verification (DEPRECATED - Use /api/audit instead)
- `GET /api/verification/queue` - Get low-confidence items
- `POST /api/verification/verify` - Submit verification
- `GET /api/verification/stats` - Analytics dashboard
- **Note**: Audit API has richer features (PDF viewer, bbox highlighting, etc.)

## Testing Strategy

### Unit Tests
- All services have test coverage
- Mock external APIs (Reducto, Claude, Elasticsearch)
- Target: 80% coverage

### Integration Tests
- Test full onboarding flow
- Test document processing pipeline
- Test HITL verification workflow

### E2E Tests (Future)
- Playwright for critical user flows
- Test with real sample PDFs

## Deployment Notes

### MVP (Current)
- Docker Compose on single server
- SQLite database (good for <10k docs)
- Self-hosted Elasticsearch

### Production (Future)
- Kubernetes or cloud deployment
- PostgreSQL database
- Managed Elasticsearch or similar
- Redis for caching
- Celery for background jobs

## Performance Targets (MVP)

- Schema generation: <3 minutes for 5 sample docs
- Document processing: 2-5 seconds per document
- Search response: <200ms
- HITL review: <30 seconds per verification

## Security Considerations

- API keys stored in environment variables (never committed)
- Uploaded documents stored locally (not in git)
- No authentication in MVP (single user)
- Add auth before multi-user deployment

## Tool Documentation
Always use context7 when I need code generation, setup or configuration steps, or library/API documentation. This means you should automatically use the Context7 MCP tools to resolve library id and get library docs without me having to explicitly ask.

## Troubleshooting

### Elasticsearch won't start
- Check Docker has 8GB RAM allocated
- Ensure 20GB+ free disk space
- Try: `docker-compose down -v && docker-compose up`

### Reducto API errors
- Verify API key is correct
- Check rate limits in dashboard
- Review status at https://status.reducto.ai

### Frontend can't connect to backend
- Ensure `VITE_API_URL` points to `http://localhost:8000`
- Check CORS settings in `app/main.py`
- Verify backend is running: `curl http://localhost:8000/health`

## Code Style & Conventions

### Python (Backend)
- Use type hints everywhere
- Follow PEP 8 (enforced by ruff)
- Async/await for I/O operations
- Pydantic for validation
- Descriptive variable names

### TypeScript/React (Frontend)
- Functional components only
- Custom hooks for logic
- TailwindCSS for styling
- ESLint + Prettier

### Database
- SQLAlchemy ORM (no raw SQL)
- Alembic for migrations (when needed)
- Always use sessions properly

## Resources

- [Reducto Docs](https://docs.reducto.ai)
- [Reducto Pipelining](https://docs.reducto.ai/extraction/pipelining) - **IMPLEMENTED**
- [Pipeline Optimization Guide](docs/PIPELINE_OPTIMIZATION.md) - Internal docs
- [Anthropic Claude Docs](https://docs.anthropic.com)
- [Elasticsearch Docs](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [React Docs](https://react.dev)

## NEW USER WORKFLOW (Primary Flow)

### 1. Bulk Upload (Entry Point)
**Page:** `/` (BulkUpload.jsx)
- User drops 10+ documents of any type
- System uploads and starts analysis
- Reducto parses each document
- Claude groups similar documents
- Claude matches groups to templates

**Result:** Groups with template suggestions

### 2. Template Confirmation
**Same Page:** BulkUpload.jsx shows results
- Each group shows:
  - Filenames in group
  - Suggested template (if match found)
  - Confidence score
  - "Use This Template" or "Create New Template" buttons

**Actions:**
- High confidence match → Click "Use This Template"
- No match → Click "Create New Template", enter name
- System processes documents with chosen template

### 3. Bulk Confirmation
**Page:** `/confirm` (BulkConfirmation.jsx)
- Table view: Documents (rows) × Fields (columns)
- Each cell shows extracted value + confidence
- Color-coded: Green (high), Yellow (medium), Red (low)
- Inline editing for corrections
- Click "Confirm All & Continue"

**Result:** All verifications saved to ES + DB

### 4. Document Dashboard
**Page:** `/documents` (DocumentsDashboard.jsx)
- See all documents with status
- Filter by: uploaded, analyzing, matched, processing, completed
- Click stats to filter
- Quick actions on each document

### 5. Search & Discovery
**Keyword Search:** Search bar in top header
- Type filename or keywords
- Instant dropdown with results
- Click to open document in audit view
- Uses `/api/folders/search` endpoint

**Natural Language Search:** `/query` (Ask AI tab)
- Ask: "Show me all invoices over $1000"
- Claude converts to ES query
- Results shown with explanation
- Follow-up questions supported

## Current Sprint

See `NEW_ARCHITECTURE.md` for complete implementation details.
See `PROJECT_PLAN.md` for future feature roadmap.

---

**Last Updated**: 2025-10-07
**Architecture Version**: 2.0 (Bulk-First)
**Claude Code Version**: Recommended v1.0.18+
**Primary Contact**: See README.md
