# Multi-Tenancy Security Audit

**Status**: ⚠️ **CRITICAL - ACTION REQUIRED**
**Date**: 2025-11-15
**Priority**: **P0 - Security Critical**

## Executive Summary

The OAuth and organization management implementation adds multi-tenancy support to Paperbase. However, **existing queries do NOT filter by organization_id**, creating a **CRITICAL SECURITY VULNERABILITY** that allows users to access documents, templates, and files from other organizations.

**Impact**: **Cross-organization data leak** - Users can potentially access ALL documents in the database, regardless of organization membership.

**Required Action**: All queries listed below MUST be updated to filter by `organization_id` before deploying to production.

---

## Affected Models

The following models now have `organization_id` and REQUIRE organization filtering:

1. **Document** (`documents` table)
2. **Schema** (`schemas` table) - Templates
3. **PhysicalFile** (`physical_files` table)

## Vulnerability Details

### Current State (INSECURE)
```python
# ❌ VULNERABLE: Returns documents from ALL organizations
documents = db.query(Document).all()

# ❌ VULNERABLE: User can access any document by guessing IDs
document = db.query(Document).filter(Document.id == document_id).first()
```

### Required State (SECURE)
```python
# ✅ SECURE: Returns only documents from user's organization
documents = db.query(Document).filter(
    Document.organization_id == current_user.org_id
).all()

# ✅ SECURE: Returns document only if in user's organization
document = db.query(Document).filter(
    Document.id == document_id,
    Document.organization_id == current_user.org_id
).first()

# ✅ BEST: Use OrganizationContext helper
from app.utils.organization_context import get_organization_context

@router.get("/documents")
def get_documents(org_ctx: OrganizationContext = Depends(get_organization_context)):
    # Automatically filtered by organization
    documents = org_ctx.query(Document).all()
    return documents
```

---

## Files Requiring Updates

### 🔴 HIGH PRIORITY - User-Facing APIs

#### `app/api/documents.py` (20+ vulnerable queries)
**Risk**: Users can view/edit/delete documents from other organizations

```python
# Line ~45: Get documents by IDs
documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~78: Get single document
document = db.query(Document).filter(Document.id == document_id).first()
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~115: List all documents
query = db.query(Document).order_by(Document.uploaded_at.desc())
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~145: Get document for export
document = db.query(Document).filter(Document.id == document_id).first()
# FIX: Add .filter(Document.organization_id == current_user.org_id)
```

**Recommended Fix**:
```python
# Replace get_db dependency with OrganizationContext
from app.utils.organization_context import get_organization_context, OrganizationContext

@router.get("/{document_id}")
def get_document(
    document_id: int,
    org_ctx: OrganizationContext = Depends(get_organization_context)
):
    document = org_ctx.check_document_access(document_id)  # Raises 404 if not found or wrong org
    return document
```

#### `app/api/sharing.py` (3 vulnerable queries)
**Risk**: Users can share documents from other organizations

```python
# Line ~35: Get document to share
document = db.query(Document).filter(Document.id == document_id).first()
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Similar issues on lines ~65, ~95
```

#### `app/api/search.py` (4 vulnerable queries)
**Risk**: Users can search across all organizations

```python
# Line ~48: Get schema for filtering
schema = db.query(Schema).filter(Schema.id == schema_id).first()
# FIX: Add .filter(Schema.organization_id == current_user.org_id)

# Similar issues on lines ~78, ~112, ~145
```

#### `app/api/onboarding.py` (10+ vulnerable queries)
**Risk**: Users can access schemas/documents from other organizations during onboarding

```python
# Line ~55: Count documents by schema
document_count = db.query(Document).filter(Document.schema_id == schema_id).count()
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~82: Get schema by name
existing_schema = db.query(Schema).filter(Schema.name == schema_name).first()
# FIX: Add .filter(Schema.organization_id == current_user.org_id)

# Similar issues on lines ~105, ~130, ~168, ~195, ~220, ~248, ~275, ~302
```

#### `app/api/bulk_upload.py` (5 vulnerable queries)
**Risk**: File deduplication across organizations (security + cost issue)

```python
# Line ~78: Check for existing file by hash
existing_physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()
# FIX: Add .filter(PhysicalFile.organization_id == current_user.org_id)

# CRITICAL: Without org filter, files are deduplicated across orgs!
# This means Org A uploading a file prevents Org B from storing their own copy.
# Also, Org B could potentially access Org A's parse results.

# Similar issues on lines ~145, ~198, ~245, ~289
```

#### `app/api/analytics.py` (10+ vulnerable queries)
**Risk**: Analytics show data from all organizations

```python
# Line ~25: Total documents count
total_documents = db.query(Document).count()
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~32: Get all schemas
schemas = db.query(Schema).all()
# FIX: Add .filter(Schema.organization_id == current_user.org_id)

# Similar issues on lines ~48, ~65, ~82, ~110, ~135, ~160, ~185, ~210, ~235
```

#### `app/api/rematch.py` (2 vulnerable queries)
**Risk**: Users can rematch templates for other organizations' documents

```python
# Line ~35: Get unmatched documents
unmatched_docs = db.query(Document).filter(...)
# FIX: Add .filter(Document.organization_id == current_user.org_id)

# Line ~68: Get document for rematching
doc = db.query(Document).filter(Document.id == document_id).first()
# FIX: Add .filter(Document.organization_id == current_user.org_id)
```

---

### 🟡 MEDIUM PRIORITY - Service Layer

#### `app/services/file_service.py` (4 vulnerable queries)
**Risk**: File operations across organizations

```python
# Line ~45: Get file by hash
existing = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()
# FIX: Add .filter(PhysicalFile.organization_id == organization_id)

# Line ~78: Get file by ID
return db.query(PhysicalFile).get(file_id)
# FIX: Add .filter(PhysicalFile.organization_id == organization_id)

# Similar issues on lines ~102, ~130
```

---

### 🟢 LOW PRIORITY - MCP/Internal Tools

#### `app/api/mcp_search.py` (1 query)
**Risk**: MCP server can search across organizations

```python
# Line ~55: Get all templates
templates = db.query(Schema).all()
# FIX: Add organization_id parameter to MCP requests
```

---

## Migration Strategy

### Phase 1: Immediate Security Fix (Before ANY Production Use)

**Option A: Use OrganizationContext (Recommended)**

1. Import the helper:
   ```python
   from app.utils.organization_context import get_organization_context, OrganizationContext
   ```

2. Replace `get_db` dependency:
   ```python
   # OLD
   def endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
       documents = db.query(Document).all()

   # NEW
   def endpoint(org_ctx: OrganizationContext = Depends(get_organization_context)):
       documents = org_ctx.query(Document).all()
   ```

3. Use helper methods for common operations:
   ```python
   document = org_ctx.check_document_access(document_id)  # Auto-validates org membership
   schema = org_ctx.check_schema_access(schema_id)
   ```

**Option B: Manual Filtering**

1. Add organization_id to every query:
   ```python
   documents = db.query(Document).filter(
       Document.organization_id == current_user.org_id
   ).all()
   ```

2. Always validate on single-entity lookups:
   ```python
   document = db.query(Document).filter(
       Document.id == document_id,
       Document.organization_id == current_user.org_id
   ).first()

   if not document:
       raise HTTPException(status_code=404, detail="Document not found")
   ```

### Phase 2: Automated Testing

Create tests to verify organization isolation:

```python
def test_document_isolation():
    """Test that users cannot access documents from other organizations"""
    # Create two organizations with one document each
    org1 = create_organization("Org 1")
    org2 = create_organization("Org 2")

    user1 = create_user("user1@org1.com", org_id=org1.id)
    user2 = create_user("user2@org2.com", org_id=org2.id)

    doc1 = create_document("doc1.pdf", organization_id=org1.id)
    doc2 = create_document("doc2.pdf", organization_id=org2.id)

    # User 1 should only see their doc
    with client_as_user(user1):
        response = client.get("/api/documents")
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == doc1.id

        # User 1 should NOT be able to access doc2
        response = client.get(f"/api/documents/{doc2.id}")
        assert response.status_code == 404

    # User 2 should only see their doc
    with client_as_user(user2):
        response = client.get("/api/documents")
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == doc2.id
```

### Phase 3: Database Constraints (Future)

Add database-level constraints to enforce organization_id:

```sql
-- Ensure documents always have organization_id
ALTER TABLE documents ALTER COLUMN organization_id SET NOT NULL;

-- Add check constraint (if needed)
ALTER TABLE documents ADD CONSTRAINT check_org_id CHECK (organization_id IS NOT NULL);
```

**WARNING**: Cannot add NOT NULL constraint until all existing queries are fixed!

---

## Testing Checklist

Before deploying to production:

- [ ] **Run migration** (`python migrations/add_oauth_and_organizations.py`)
- [ ] **Update all queries** in files listed above
- [ ] **Test organization isolation**:
  - [ ] Create 2 organizations
  - [ ] Create 1 document in each org
  - [ ] Verify user A cannot see user B's documents
  - [ ] Verify user A cannot access user B's document by ID
  - [ ] Verify analytics show only org-scoped data
  - [ ] Verify search returns only org-scoped results
  - [ ] Verify file deduplication works within organization
  - [ ] Verify PhysicalFile isolation (same hash, different orgs)
- [ ] **Test edge cases**:
  - [ ] User with no organization (should get 400 error)
  - [ ] User switches organizations (future feature)
  - [ ] Superadmin access (if applicable)
- [ ] **Code review** all query changes
- [ ] **Run automated security tests**

---

## Risk Assessment

### Pre-Fix Risk Level: **CRITICAL** 🔴

- **Confidentiality**: Full breach - users can access all data
- **Integrity**: High - users can modify other orgs' data
- **Availability**: Medium - users can delete other orgs' documents
- **GDPR/Compliance**: Severe violation - customer data mixing

### Post-Fix Risk Level: **LOW** 🟢 (if all queries updated)

- Organization isolation enforced at application layer
- Row-level security prevents cross-org access
- Automated tests verify isolation

---

## Estimated Effort

- **Option A (OrganizationContext)**: 4-6 hours
  - Update ~40 endpoints
  - Replace `get_db` with `get_organization_context`
  - Test all affected endpoints

- **Option B (Manual Filtering)**: 8-12 hours
  - Update ~60 queries manually
  - Add filters to each query
  - Higher risk of missing queries
  - More verbose code

**Recommendation**: **Use Option A** (OrganizationContext helper)
- Less error-prone
- More maintainable
- Enforces pattern across codebase
- Easier to audit

---

## Long-Term Recommendations

1. **Mandatory Code Review**: All queries touching multi-tenant models must be reviewed for org filtering

2. **Linting Rule**: Add custom linter to detect queries without organization_id
   ```python
   # Example: Detect db.query(Document) without organization_id
   ```

3. **Database Views**: Create org-scoped views for each multi-tenant table
   ```sql
   CREATE VIEW user_documents AS
   SELECT * FROM documents WHERE organization_id = current_setting('app.current_org_id')::integer;
   ```

4. **Row-Level Security (Postgres)**: If migrating to Postgres, use RLS
   ```sql
   ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
   CREATE POLICY org_isolation ON documents
   USING (organization_id = current_setting('app.current_org_id')::integer);
   ```

5. **Monitoring**: Log and alert on cross-org access attempts
   ```python
   if requested_org_id != current_user.org_id:
       logger.security_alert(f"User {user.id} attempted cross-org access")
   ```

---

## Developer Guidelines

### DO ✅

```python
# Use OrganizationContext
from app.utils.organization_context import OrganizationContext, get_organization_context

@router.get("/documents")
def get_documents(org_ctx: OrganizationContext = Depends(get_organization_context)):
    documents = org_ctx.query(Document).all()  # Automatically filtered
    return documents

# Set organization_id when creating
@router.post("/documents")
def create_document(
    data: DocumentCreate,
    org_ctx: OrganizationContext = Depends(get_organization_context)
):
    document = Document(**data.dict())
    document.organization_id = org_ctx.organization_id  # CRITICAL
    org_ctx.db.add(document)
    org_ctx.db.commit()
    return document

# Validate access with helper
document = org_ctx.check_document_access(document_id)  # Raises 404 if wrong org
```

### DON'T ❌

```python
# DON'T: Query without organization filter
documents = db.query(Document).all()  # ❌ Returns ALL documents

# DON'T: Get by ID without checking org
document = db.query(Document).filter(Document.id == id).first()  # ❌ Cross-org access

# DON'T: Forget to set organization_id on create
document = Document(filename="test.pdf")
db.add(document)  # ❌ organization_id = NULL!

# DON'T: Filter after fetching
all_docs = db.query(Document).all()
user_docs = [d for d in all_docs if d.organization_id == org_id]  # ❌ Inefficient + insecure
```

---

## Immediate Action Items

**FOR THE DEVELOPER**:

1. ⚠️ **DO NOT DEPLOY TO PRODUCTION** until queries are fixed
2. 📋 **Review this document** with your team
3. 🔧 **Choose fix strategy** (Option A recommended)
4. 🧪 **Create test cases** for organization isolation
5. 🔨 **Update queries** systematically (use file list above)
6. ✅ **Test thoroughly** before deploying
7. 📝 **Document** which endpoints have been secured
8. 🔍 **Code review** all changes
9. 🚨 **Add monitoring** for cross-org access attempts

**Timeline**: **Complete before ANY production deployment** (P0 priority)

---

## Questions?

If you need help:
1. Review `app/utils/organization_context.py` for helper utilities
2. Check `OAUTH_IMPLEMENTATION.md` for OAuth setup
3. Test in development with 2 separate organizations
4. Run security tests to verify isolation

**DO NOT SKIP THIS FIX** - Multi-tenancy without organization filtering is a **CRITICAL SECURITY VULNERABILITY**.

---

**Last Updated**: 2025-11-15
**Review Status**: ⚠️ Requires Immediate Action
**Security Risk**: 🔴 Critical (Pre-Fix) → 🟢 Low (Post-Fix)
