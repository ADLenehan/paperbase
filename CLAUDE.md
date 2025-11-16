# Paperbase - MVP

## Project Overview
A no-code document extraction platform that uses Reducto for parsing, Elasticsearch for storage/search, and Anthropic Claude for AI-powered schema generation and improvements.

**Status**: ✅ Multi-Template Extraction Complete (Backend Ready) | ✅ Complex Data Extraction (Backend Ready)

### Latest Update: Batch Audit Workflow (2025-11-02)
- ✅ **Phase 1** Inline audit modal - verify fields without losing chat context
- ✅ **Phase 2** Batch audit modal - verify multiple fields at once in table view
- ✅ **NEW** `POST /api/audit/bulk-verify-and-regenerate` endpoint
- ✅ **NEW** "Review All" button for bulk verification
- ✅ **NEW** Table view with inline editing
- ✅ **NEW** Batch operations: 1 API call for N fields
- 🎯 **Impact Phase 1**: <10 seconds per field (down from ~30s), 100% context preservation
- 🎯 **Impact Phase 2**: <20 seconds for 5 fields (vs ~50s), 70% cost reduction for batch

**See**: [INLINE_AUDIT_IMPLEMENTATION.md](./docs/implementation/INLINE_AUDIT_IMPLEMENTATION.md) | [BATCH_AUDIT_IMPLEMENTATION.md](./docs/implementation/BATCH_AUDIT_IMPLEMENTATION.md)

### Previous Update: Complex Data Extraction (2025-11-02)
- ✅ Support for arrays, tables, and array_of_objects field types
- ✅ Elasticsearch nested mappings with dynamic templates for variable columns
- ✅ Complexity assessment: 0-100 scoring with auto/assisted/manual tiers
- ✅ Claude self-assessment in schema generation
- ✅ Complexity warnings in bulk upload API
- ✅ Database migration for complex data support
- ⏳ Frontend components pending (table/array editors)

**See**: [docs/features/COMPLEX_TABLE_EXTRACTION.md](./docs/features/COMPLEX_TABLE_EXTRACTION.md) | [docs/ARRAY_FIELDS_AND_UI_STRATEGY.md](./docs/ARRAY_FIELDS_AND_UI_STRATEGY.md) | [docs/CLAUDE_AUTOMATION_COMPLEXITY_THRESHOLDS.md](./docs/CLAUDE_AUTOMATION_COMPLEXITY_THRESHOLDS.md)

### Multi-Template Extraction (2025-10-11)
- ✅ One file → Multiple extractions with different templates
- ✅ Automatic file deduplication (SHA256 hash-based)
- ✅ Virtual folder organization (no physical file duplication)
- ✅ Parse result caching for cost optimization
- ✅ Batch processing API
- ⏳ Frontend components pending

**See**: [MULTI_TEMPLATE_EXTRACTION.md](./docs/features/MULTI_TEMPLATE_EXTRACTION.md) | [Quick Start](./docs/features/MULTI_TEMPLATE_QUICKSTART.md)

### Elasticsearch Optimization (2025-10-23)
- ✅ Production-ready mapping with `dynamic: strict`
- ✅ Field limits to prevent mapping explosion (max 1000 fields)
- ✅ Keyword field protection with `ignore_above` (prevents indexing failures)
- ✅ Storage optimization: Removed redundant `.raw` sub-fields (-30% storage)
- ✅ Bulk indexing optimization helpers (20-30% faster)
- ✅ Index statistics monitoring API

**See**: [docs/features/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md](./docs/features/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)

## Feature Documentation

All major features are documented in [docs/features/](./docs/features/):

### 🚀 Production Features
- **[Pipeline Optimization](docs/features/PIPELINE_OPTIMIZATION.md)** - Reducto `jobid://` reuse for 60% cost savings
- **[Elasticsearch Mappings](docs/features/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)** - Production-ready strict mappings
- **[Permissions & Auth](docs/features/PERMISSIONS_ARCHITECTURE.md)** - RBAC with JWT and API keys (backend complete)
- **[Audit Links](docs/features/LOW_CONFIDENCE_AUDIT_LINKS.md)** - Deep-linking to low-confidence fields in PDFs
- **[Query Field Lineage](docs/features/QUERY_FIELD_LINEAGE_IMPLEMENTATION.md)** - Track field usage in searches

### 🔨 In Development
- **[Complex Table Extraction](docs/features/COMPLEX_TABLE_EXTRACTION.md)** - Advanced table parsing (backend ready)
- **[Extraction Preview](docs/features/EXTRACTION_PREVIEW_FEATURE.md)** - Preview before indexing
- **[Query Suggestions](docs/features/QUERY_SUGGESTIONS_FEATURE.md)** - AI-powered search suggestions
- **[UX Improvements](docs/features/UX_AND_CITATION_IMPROVEMENTS.md)** - Enhanced citations & audit interface

**See**: [docs/features/README.md](./docs/features/README.md) for complete feature catalog

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

Reducto Pipeline Flow (Optimized + Deduped):
Upload → SHA256 Hash → Existing? → Reuse PhysicalFile + Parse Cache ✓
         ↓ new hash
         Parse (job_id) → PhysicalFile (cached parse)
         ↓
         ES Cluster (by content similarity) → Template Match
         ↓
         Extract (jobid://) → Index
         ↑ reuse (no re-upload, no re-parse!)
```

## Key Design Decisions

### Cost Optimization Strategy
- **Claude**: Used ONLY for:
  1. Template matching (once per upload batch)
  2. Schema generation (once per new template)
  3. NL search query conversion (per search, cached)
  4. Weekly improvements from verifications
- **Reducto**: Does all document parsing and extraction
  - **SHA256 Deduplication**: Exact file match → reuse cached parse (NEW!)
  - **Pipeline Optimization**: Uses `jobid://` to reuse parse results
  - **Savings**: 50-75% fewer API calls + 20-70% parse dedup, ~70% total cost reduction
- **Elasticsearch**: Handles all structured queries (no LLM per-query)
  - **Content Clustering**: Groups similar docs for template matching (not for dedup!)
- **Target**: <$1.50 per upload batch (down from $3), ~$10-15 per 1000 docs/month

### Confidence Scores
- **Source**: Reducto provides `logprobs_confidence` (0.0-1.0) for each extraction
- **Labels**: High (≥0.8), Medium (0.6-0.8), Low (<0.6)
- **HITL Trigger**: Fields below threshold automatically flagged for review

### Schema-Driven Extraction
1. Claude analyzes sample docs → generates schema + extraction rules
2. Rules stored as JSON config
3. Reducto applies rules to all subsequent docs (no LLM per-doc)
4. User verifications create training examples for improvement

### Complex Data Extraction (NEW)
- **Field Types**: text, date, number, boolean, array, table, array_of_objects
- **Array Support**: Simple arrays (colors, tags) and structured arrays (line items)
- **Table Support**: Multi-cell tables with dynamic columns (e.g., garment grading specs)
- **Complexity Scoring**: 0-100+ scale based on field count, nesting, tables, domain specificity
- **Three-Tier System**:
  - **Auto (≤50)**: Simple documents - Claude generates schema automatically (confidence 0.8-0.95)
  - **Assisted (51-80)**: Medium complexity - Claude suggests schema, user reviews (confidence 0.6-0.75)
  - **Manual (81+)**: High complexity - User must define schema manually (confidence 0.3-0.5)
- **Examples**:
  - Auto: Basic invoices (8 text/number fields)
  - Assisted: Contracts with line items table
  - Manual: Financial statements with charts, garment specs with complex grading tables

### Two-Tier Deduplication Strategy (NEW)
- **Tier 1: SHA256 Hash (File Identity)**
  - Purpose: Avoid parsing the exact same file twice
  - When: BEFORE parsing (during upload)
  - Groups: Byte-identical files
  - Example: `invoice.pdf` uploaded 3 times → Parse once, save $0.04
  - Savings: 20-70% of parse costs (depending on duplicate rate)

- **Tier 2: Elasticsearch Clustering (Content Similarity)**
  - Purpose: Group similar documents for template matching
  - When: AFTER parsing (needs content)
  - Groups: Structurally similar documents (same fields)
  - Example: `invoice_jan.pdf`, `invoice_feb.pdf`, `invoice_mar.pdf` → 1 template
  - Benefit: Better UX (auto-template selection), not cost savings

**Key Insight**: SHA256 prevents redundant API calls, ES improves user experience.

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
- `app/core/auth.py` - **NEW** JWT + API key authentication (dual auth support)
- `app/api/auth.py` - **NEW** Login, logout, API key management endpoints
- `app/api/users.py` - **NEW** User management (requires authentication)
- `app/api/roles.py` - **NEW** Role & permission management (requires authentication)
- `app/api/sharing.py` - **NEW** Document sharing & access control (requires authentication)
- `app/api/settings.py` - Settings management API with hierarchy
- `app/api/audit.py` - HITL audit with dynamic thresholds
- `app/api/bulk_upload.py` - Bulk upload with **SHA256 deduplication** + pipeline & folder organization
- `app/services/settings_service.py` - Hierarchical settings resolution
- `app/services/permission_service.py` - **NEW** RBAC permission checking
- `app/services/file_service.py` - **NEW** File upload with hash-based deduplication
- `app/services/claude_service.py` - Template matching + NL search + **complexity assessment**
- `app/services/reducto_service.py` - Pipeline support with `jobid://` + **complex data extraction**
- `app/services/elastic_service.py` - Content clustering + custom query support + **nested/array mappings**
- `app/models/settings.py` - Settings, Organization, User models
- `app/models/permissions.py` - **NEW** Roles, Permissions, APIKey models
- `app/models/physical_file.py` - **NEW** Physical file storage with SHA256 deduplication
- `app/models/document.py` - **NEW** Links to PhysicalFile + template fields + **complex data support**
- `app/models/schema.py` - Schema database models + **complexity tracking** (ComplexityOverride)
- `app/utils/file_organization.py` - Template-based folder structure
- `app/utils/hashing.py` - **NEW** SHA256 hash calculation for deduplication
- `app/models/verification.py` - HITL verification tracking
- `backend/migrations/add_complex_data_support.py` - Database migration for complex types
- `backend/migrations/link_documents_to_physical_files.py` - **NEW** Migration for deduplication support

### Frontend (NEW Architecture)

#### Pages
- `src/pages/Settings.jsx` - Configurable thresholds with sliders
- `src/pages/Audit.jsx` - **PRIMARY** HITL audit interface with PDF viewer
- `src/pages/BulkUpload.jsx` - Main entry point - upload & template matching
- `src/pages/BulkConfirmation.jsx` - Bulk table view for verification
- `src/pages/DocumentsDashboard.jsx` - Status dashboard
- `src/pages/ChatSearch.jsx` - Natural language search interface with **inline audit**
- `src/pages/Onboarding.jsx` - (Legacy) Sample upload & schema generation
- `src/pages/Verify.jsx` - **DEPRECATED** - Use Audit.jsx instead

#### Components (Audit & Verification)
- `src/components/InlineAuditModal.jsx` - **NEW** Inline verification modal with PDF viewer
- `src/components/PDFExcerpt.jsx` - **NEW** Lightweight PDF viewer for modals
- `src/components/AnswerWithAudit.jsx` - Answer display with audit metadata & inline modal
- `src/components/CitationBadge.jsx` - Confidence indicators with click-to-audit
- `src/components/PDFViewer.jsx` - Full PDF viewer with bbox highlights

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

### NEW: Authentication & User Management (2025-10-29)
**All endpoints below require authentication via JWT token or API key**

#### Authentication
- `POST /api/auth/login` - Login with email/password → JWT token
- `POST /api/auth/logout` - Logout (client discards token)
- `GET /api/auth/me` - Get current user information
- `POST /api/auth/change-password` - Change password

#### API Key Management
- `POST /api/auth/api-keys` - Create API key (for MCP/scripts)
- `GET /api/auth/api-keys` - List user's API keys
- `DELETE /api/auth/api-keys/{key_id}` - Revoke API key
- `POST /api/auth/users/{user_id}/api-keys` - Admin: Create key for user
- `GET /api/auth/users/{user_id}/api-keys` - Admin: List user's keys

#### User Management
- `POST /api/users/` - Create new user (requires WRITE_USERS)
- `GET /api/users/` - List users with filters (requires READ_USERS)
- `GET /api/users/{user_id}` - Get user details (requires READ_USERS)
- `PUT /api/users/{user_id}` - Update user (requires WRITE_USERS or self)
- `DELETE /api/users/{user_id}` - Deactivate user (requires DELETE_USERS)
- `POST /api/users/{user_id}/roles` - Assign role (requires MANAGE_ROLES)
- `DELETE /api/users/{user_id}/roles/{role_id}` - Revoke role (requires MANAGE_ROLES)
- `GET /api/users/{user_id}/permissions` - Get user permissions

#### Role & Permission Management
- `GET /api/roles/permissions` - List all available permissions
- `GET /api/roles/` - List all roles with permissions
- `GET /api/roles/{role_id}` - Get role details
- `POST /api/roles/` - Create custom role (requires MANAGE_ROLES)
- `PUT /api/roles/{role_id}` - Update role (requires MANAGE_ROLES)
- `DELETE /api/roles/{role_id}` - Delete role (requires MANAGE_ROLES)
- `POST /api/roles/{role_id}/permissions` - Add permissions to role
- `DELETE /api/roles/{role_id}/permissions/{permission_id}` - Remove permission
- `POST /api/roles/initialize` - Initialize default roles & permissions

#### Document Sharing
- `POST /api/sharing/documents/{doc_id}/users` - Share with user
- `GET /api/sharing/documents/{doc_id}/access` - List who has access
- `DELETE /api/sharing/documents/{doc_id}/users/{user_id}` - Revoke access
- `POST /api/sharing/links` - Create shareable link
- `GET /api/sharing/links/{token}` - Get share link details
- `DELETE /api/sharing/links/{link_id}` - Delete share link

**See**: [AUTHENTICATION_IMPLEMENTATION.md](./docs/features/AUTHENTICATION_IMPLEMENTATION.md) for complete auth details

### Settings Management (Hierarchical Configuration)
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
- `POST /api/audit/verify-and-regenerate` - **NEW** Verify field + regenerate answer atomically
- `POST /api/audit/bulk-verify` - Bulk verify multiple fields at once
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
- HITL review: <10 seconds per verification (**improved from ~30s** with inline audit)
- Answer regeneration: <3 seconds (after verification)

## Security Considerations

### Authentication & Authorization (IMPLEMENTED 2025-10-29) ✅
- **JWT Tokens**: 24-hour expiry, HS256 signing with SECRET_KEY
- **API Keys**: bcrypt hashed, `pb_` prefix, optional expiration
- **Dual Authentication**: Single endpoint validates both JWT and API keys
- **Password Security**: bcrypt hashing with salt
- **Permission System**: RBAC with 16 granular permissions
- **Role Hierarchy**: Admin (all), Editor (read/write docs), Viewer (read-only)
- **Audit Trail**: All permission changes logged with user_id + timestamp

### Data Protection
- External API keys (Reducto, Claude) stored in environment variables (never committed)
- Uploaded documents stored locally (not in git)
- User passwords hashed with bcrypt (never stored plain)
- API keys hashed before storage (plain key shown only once)
- Soft deletes preserve audit trail (is_active flag)

### Access Control
- All endpoints require authentication (except /health, /login)
- Permission checks on every request via `get_current_user()` dependency
- Document-level permissions (share with specific users)
- Folder-level permissions (organize by template/category)
- Share links with optional expiration and access levels

### TODO: Additional Security Hardening
- [ ] Add rate limiting on login endpoint (prevent brute-force)
- [ ] Add token blacklist for true logout (currently client-side only)
- [ ] Add 2FA/MFA support for admin accounts
- [ ] Add password complexity requirements (min 8 chars currently)
- [ ] Add password reset flow via email
- [ ] Store SECRET_KEY in .env (currently auto-generated)
- [ ] Add HTTPS enforcement in production
- [ ] Add CSRF protection for state-changing operations
- [ ] Add security headers (HSTS, CSP, X-Frame-Options)
- [ ] Add input sanitization for SQL injection prevention

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

## Integration Best Practices (CRITICAL)

**Lesson Learned**: SHA256 Deduplication (2025-11-02) - Found 8 compatibility issues after initial implementation

### When Adding New Model Properties or Refactoring Data Storage

#### 1. **Use Accessor Properties for Backwards Compatibility**

When moving data from one model to another (e.g., Document → PhysicalFile), ALWAYS create accessor properties:

```python
# ✅ CORRECT: Backwards-compatible property
@property
def actual_file_path(self) -> str:
    """Get actual file path, preferring PhysicalFile over legacy field."""
    if self.physical_file:
        return self.physical_file.file_path
    return self.file_path  # Fallback to legacy

# ❌ WRONG: Direct access breaks when relationship changes
file_path = document.file_path  # May be None if using PhysicalFile!
```

**Why**: Allows gradual migration, supports mixed environments, prevents breaking changes

#### 2. **Mandatory Compatibility Audit Checklist**

Before marking ANY data refactoring "complete", run this checklist:

- [ ] **Search deprecated fields**: `grep -r "\.old_field" backend/app/`
- [ ] **Check all API endpoints**: Do they read/write the data?
- [ ] **Check all services**: elastic_service, reducto_service, claude_service
- [ ] **Check API responses**: Does frontend receive correct data?
- [ ] **Check file operations**: Any file paths, uploads, downloads?
- [ ] **Check background jobs**: Any async processing affected?
- [ ] **Update ALL usages**: Don't just update "main" code path

**Example from SHA256 Dedup**:
- ✅ Updated: bulk_upload.py (5 sections)
- ✅ Updated: documents.py (2 sections)
- ✅ Updated: audit.py (4 locations)
- ✅ Updated: files.py (2 locations)
- ✅ Updated: elastic_service.py (1 section)

#### 3. **Write Pattern for Shared Resources**

When multiple entities share the same resource (PhysicalFile, cached data, etc.):

```python
# ✅ CORRECT: Check relationship first, fall back to legacy
if doc.physical_file:
    # Write to shared resource
    doc.physical_file.reducto_job_id = new_job_id
    doc.physical_file.reducto_parse_result = result
else:
    # Fall back to legacy fields for unmigrated docs
    doc.reducto_job_id = new_job_id
    doc.reducto_parse_result = result

# ❌ WRONG: Always writing to Document breaks sharing
doc.reducto_job_id = new_job_id  # Other docs won't see this!
```

#### 4. **File Organization with Shared Resources**

When files are shared between entities, NEVER move - COPY instead:

```python
# ✅ CORRECT: Copy when sharing, move when not
if doc.physical_file:
    # Copy file (preserve original for other docs)
    new_path = organize_document_file_copy(doc.actual_file_path, ...)
    # Create new PhysicalFile for the copy
    new_physical_file = PhysicalFile(...)
    doc.physical_file_id = new_physical_file.id
else:
    # Move file (legacy, no sharing)
    new_path = organize_document_file(doc.file_path, ...)
    doc.file_path = new_path

# ❌ WRONG: Moving shared files breaks other entities
shutil.move(doc.physical_file.file_path, new_path)  # BREAKS OTHER DOCS!
```

#### 5. **Integration Testing Strategy**

After ANY model refactoring:

1. **Unit Tests**: Test property fallback logic
2. **Integration Tests**: Test each API endpoint end-to-end
3. **Compatibility Tests**: Test with both old and new data models
4. **File Operation Tests**: Upload, download, serve, organize
5. **UI Tests**: Verify frontend displays correct data

**Create a compatibility audit document** (see: [docs/fixes/SHA256_DEDUP_COMPLETE_COMPATIBILITY_AUDIT.md](./docs/fixes/SHA256_DEDUP_COMPLETE_COMPATIBILITY_AUDIT.md))

#### 6. **Common Pitfalls to Avoid**

❌ **Pitfall 1: Only updating "main" code path**
```python
# Fixed bulk_upload.py but forgot documents.py
# Result: Background processing fails
```

❌ **Pitfall 2: Forgetting API responses**
```python
# Fixed backend logic but forgot audit.py API response
# Result: Frontend gets None for file paths
```

❌ **Pitfall 3: Not testing file serving**
```python
# Fixed data model but forgot files.py endpoint
# Result: PDFs fail to load in viewer
```

❌ **Pitfall 4: Direct field access in loops**
```python
# Using doc.reducto_parse_result in 100 places
# Result: Need to fix 100 locations when refactoring
```

❌ **Pitfall 5: Moving shared files**
```python
# shutil.move() when multiple docs share PhysicalFile
# Result: Other documents can't find their files
```

#### 7. **Deprecation Pattern**

When deprecating fields:

```python
# 1. Add new relationship/property
physical_file_id = Column(Integer, ForeignKey("physical_files.id"), nullable=True)

# 2. Keep old field with comment
file_path = Column(String, nullable=True)  # DEPRECATED: Use actual_file_path

# 3. Create accessor property
@property
def actual_file_path(self) -> str:
    if self.physical_file:
        return self.physical_file.file_path
    return self.file_path

# 4. Update all code to use accessor
# 5. Create migration script
# 6. After migration complete, remove old field (major version only)
```

#### 8. **Documentation Requirements**

Every data refactoring MUST include:

1. **Implementation Doc**: What changed, why, how it works
2. **Integration Fixes Doc**: What broke, what was fixed
3. **Compatibility Audit**: Comprehensive review of all affected code
4. **Migration Guide**: How to migrate existing data
5. **Testing Checklist**: What to test before deployment

**Examples**:
- [SHA256_DEDUPLICATION_IMPLEMENTATION.md](./docs/implementation/SHA256_DEDUPLICATION_IMPLEMENTATION.md)
- [DEDUPLICATION_INTEGRATION_FIXES.md](./docs/fixes/DEDUPLICATION_INTEGRATION_FIXES.md)
- [SHA256_DEDUP_COMPLETE_COMPATIBILITY_AUDIT.md](./docs/fixes/SHA256_DEDUP_COMPLETE_COMPATIBILITY_AUDIT.md)

#### 9. **Code Review Checklist for Data Refactoring PRs**

Reviewers must verify:

- [ ] Accessor properties implemented for backwards compatibility
- [ ] All grep results for old field access addressed
- [ ] API responses updated (especially audit, files endpoints)
- [ ] File operations handle shared resources correctly
- [ ] Background jobs and async processing updated
- [ ] Integration tests added
- [ ] Migration script included and tested
- [ ] Documentation complete (implementation + fixes + audit)

#### 10. **When in Doubt: Ultrathink First**

Before implementing ANY data model change:

1. **Map all data flows**: Where is this data read? Written? Displayed?
2. **Identify all consumers**: API endpoints, services, background jobs, frontend
3. **Plan compatibility**: How will old data work? Mixed environment?
4. **Design accessor pattern**: Properties, fallbacks, migrations
5. **Create test plan**: What could break? How to test?

**Remember**: Finding 8 issues AFTER implementation is expensive. Finding 0 issues through ultrathinking is cheap.

### Real-World Example: SHA256 Deduplication

**Initial Implementation**: Added PhysicalFile model, updated bulk_upload.py (5 sections)

**Compatibility Audit Found**:
1. elastic_service.py - ES clustering using old field
2. documents.py - Background processing using old fields
3. audit.py - API responses returning None for file paths
4. files.py - File serving endpoint using old field
5. Multiple template matching sections

**Cost**: 3 hours of fixes, documentation updates, comprehensive testing

**Lesson**: If we had searched for ALL usages first, would have found all 8 issues in 30 minutes

**Takeaway**: ALWAYS run the compatibility audit checklist BEFORE marking work complete

## Resources

### Internal Documentation
- **[Feature Catalog](docs/features/README.md)** - Complete feature documentation
- **[Project Plan](PROJECT_PLAN.md)** - Roadmap and future features
- **[Authentication Guide](docs/features/AUTHENTICATION_IMPLEMENTATION.md)** - Auth implementation details
- **[Pipeline Optimization](docs/features/PIPELINE_OPTIMIZATION.md)** - Reducto cost optimization

### External Resources
- [Reducto Docs](https://docs.reducto.ai)
- [Reducto Pipelining](https://docs.reducto.ai/extraction/pipelining) - **IMPLEMENTED**
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

### ✅ Latest: SHA256 File Deduplication (2025-11-02)
- **Complete**: Two-tier deduplication strategy implemented
- SHA256 hash-based exact file matching (before parsing)
- PhysicalFile model with parse cache sharing
- Document model updated with PhysicalFile relationship
- Migration script for linking existing documents
- ES clustering for content similarity (after parsing)
- 🎯 **Impact**: 20-70% parse cost reduction, ~$0.02 saved per duplicate
- **Savings Example**: 100 files with 30 duplicates → $0.60 saved per batch

### ✅ Previous: Inline Audit Workflow (2025-11-02)
- **Phase 1 Complete**: Inline audit modal with real-time answer updates
- 2 new components: `InlineAuditModal.jsx`, `PDFExcerpt.jsx`
- 1 new endpoint: `POST /api/audit/verify-and-regenerate`
- Keyboard shortcuts for rapid verification (1/2/3/S/Esc)
- 3x faster verification workflow (<10s vs ~30s)
- 100% context preservation (no navigation)

### ✅ Backend Authentication (2025-10-29)
- JWT + API key authentication system
- User management with RBAC permissions
- 8 new auth endpoints, 24 endpoints secured
- **Status**: Backend complete, frontend pending

### Documentation
- **[Inline Audit Guide](docs/implementation/INLINE_AUDIT_IMPLEMENTATION.md)** - NEW audit workflow (Phase 1)
- [AUTHENTICATION_IMPLEMENTATION.md](./docs/features/AUTHENTICATION_IMPLEMENTATION.md) - Complete auth guide
- [PERMISSIONS_ARCHITECTURE.md](./docs/features/PERMISSIONS_ARCHITECTURE.md) - RBAC design
- [NEW_ARCHITECTURE.md](./docs/architecture/NEW_ARCHITECTURE.md) - Complete implementation details
- [PROJECT_PLAN.md](./PROJECT_PLAN.md) - Future feature roadmap
- [docs/features/](./docs/features/) - Complete feature catalog

---

**Last Updated**: 2025-11-02
**Architecture Version**: 2.2 (Bulk-First + Authentication + Inline Audit)
**Authentication**: ✅ Backend Complete, ⏳ Frontend Pending
**Inline Audit**: ✅ Phase 1 Complete (Ready for Testing)
**Claude Code Version**: Recommended v1.0.18+
**Primary Contact**: See README.md
