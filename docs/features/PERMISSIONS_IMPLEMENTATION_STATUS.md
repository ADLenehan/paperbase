# Permissions System Implementation Status

**Date**: 2025-10-28
**Status**: Phase 1-3 Complete (Core Backend), Phases 4-7 In Progress

## Overview

We're implementing a comprehensive Role-Based Access Control (RBAC) system for Paperbase with full functionality accessible through both MCP tools and the AskAI natural language interface.

---

## ✅ Completed Components

### Phase 1: Database Models & Core System (COMPLETE)

#### 1. Permission Models ✅
**File**: `backend/app/models/permissions.py`

**Created Models:**
- `Role` - Role definitions (Admin, Editor, Viewer, Custom)
- `Permission` - Granular permissions (17 default permissions)
- `UserRole` - User-to-role assignments with scope
- `DocumentPermission` - Document-level access control
- `FolderPermission` - Folder-level access control
- `ShareLink` - Shareable links with expiration
- `ShareLinkAccessLog` - Track share link usage
- `PermissionAuditLog` - Comprehensive audit trail

**Permission Scopes:**
- Global - System-wide permissions
- Organization - Org-specific permissions
- Folder - Folder-level permissions
- Document - Document-specific permissions

**Default Roles:**
- **Admin**: Full system access (all permissions)
- **Editor**: Create/edit documents and templates
- **Viewer**: Read-only access

**Default Permissions (17 total):**
- Document: read, write, delete, share
- Template: read, write, delete
- User: read, write, delete
- Role: manage
- Organization: manage
- Settings: manage
- Search: all
- Export: data
- Audit: view
- System: admin

#### 2. Model Updates ✅
**Files Updated:**
- `backend/app/models/settings.py` - Added permission relationships to User and Organization
- `backend/app/models/document.py` - Added ownership and sharing fields

#### 3. PermissionService ✅
**File**: `backend/app/services/permission_service.py`

**Key Methods:**
- `check_permission()` - Verify user has a permission
- `check_document_access()` - Check document-level access
- `check_folder_access()` - Check folder-level access
- `require_permission()` - Enforce permission or raise error
- `get_user_permissions()` - Get all user permissions
- `get_user_roles()` - Get all user roles
- `grant_document_access()` - Share document with user
- `revoke_document_access()` - Revoke document access
- `assign_role()` - Assign role to user
- `revoke_role()` - Revoke role from user
- `create_share_link()` - Generate shareable link
- `revoke_share_link()` - Revoke share link
- `initialize_default_permissions()` - Setup system defaults

**Permission Resolution Order:**
1. Admin bypass (admins have all permissions)
2. Direct resource permissions (DocumentPermission, FolderPermission)
3. Role-based permissions (via UserRole)
4. Organization-level permissions
5. Public access (if resource is public)

### Phase 2: API Endpoints (COMPLETE)

#### 1. User Management API ✅
**File**: `backend/app/api/users.py`

**Endpoints:**
- `POST /api/users` - Create new user
- `GET /api/users` - List users with filters
- `GET /api/users/{id}` - Get user details
- `PUT /api/users/{id}` - Update user profile
- `DELETE /api/users/{id}` - Deactivate user
- `POST /api/users/{id}/roles` - Assign role to user
- `DELETE /api/users/{id}/roles/{role_id}` - Revoke role
- `GET /api/users/{id}/permissions` - Get user permissions

**Features:**
- Search by name/email
- Filter by organization and active status
- Pagination support
- Users can update own profile
- Comprehensive permission views

#### 2. Role & Permission API ✅
**File**: `backend/app/api/roles.py`

**Endpoints:**
- `GET /api/roles/permissions` - List all available permissions
- `GET /api/roles` - List all roles
- `GET /api/roles/{id}` - Get role details
- `POST /api/roles` - Create custom role
- `PUT /api/roles/{id}` - Update role
- `DELETE /api/roles/{id}` - Delete role (soft delete)
- `POST /api/roles/{id}/permissions` - Add permissions to role
- `DELETE /api/roles/{id}/permissions/{perm_id}` - Remove permission
- `POST /api/roles/initialize` - Initialize system defaults

**Features:**
- System roles protected from modification
- Custom role creation with specific permissions
- User count per role
- Org-specific roles support
- Filter by role type

#### 3. Document Sharing API ✅
**File**: `backend/app/api/sharing.py`

**Endpoints:**
- `POST /api/sharing/documents/{id}/share` - Share document
- `GET /api/sharing/documents/{id}/permissions` - List who has access
- `DELETE /api/sharing/documents/{id}/permissions/{user_id}` - Revoke access
- `POST /api/sharing/documents/{id}/links` - Create share link
- `DELETE /api/sharing/links/{link_id}` - Revoke share link
- `POST /api/sharing/folders/{path}/share` - Share folder
- `GET /api/sharing/folders/{path}/permissions` - Get folder permissions

**Features:**
- Share with users or roles
- Multiple permission levels (read, write, delete, share)
- Optional expiration
- Shareable links with:
  - Optional password protection
  - Access limits
  - Expiration dates
  - Usage tracking
- Folder-level permissions with inheritance

---

## 🚧 In Progress / Remaining Components

### Phase 3: MCP Tools (NOT STARTED)

#### Files to Create:
1. `backend/mcp_server/tools/permissions.py` - MCP permission tools
2. `backend/mcp_server/resources/permissions.py` - MCP permission resources

#### MCP Tools to Implement:
```python
@mcp.tool()
async def list_users_with_permissions(org_id: Optional[int] = None)

@mcp.tool()
async def grant_document_access(document_id: int, user_id: int, permission: str = "read")

@mcp.tool()
async def revoke_document_access(document_id: int, user_id: int)

@mcp.tool()
async def assign_user_role(user_id: int, role_name: str, scope: str = "global")

@mcp.tool()
async def list_document_permissions(document_id: int)

@mcp.tool()
async def create_share_link(document_id: int, expires_in_days: int = 7)

@mcp.tool()
async def audit_permission_changes(user_id: Optional[int] = None, days: int = 30)
```

#### MCP Resources to Implement:
```
paperbase://permissions/users/{user_id}
paperbase://permissions/roles
paperbase://permissions/audit
paperbase://permissions/documents/{doc_id}
```

### Phase 4: Natural Language Interface (NOT STARTED)

#### Files to Create:
1. `backend/app/services/claude_service.py` - Extend with permission parsing
2. `backend/app/api/nl_permissions.py` - NL permission API
3. Update `backend/app/api/nl_query.py` - Add permission intent detection

#### Natural Language Commands to Support:

**Grant Access:**
- "Give john@company.com read access to document 123"
- "Make Sarah an editor for the Invoices folder"
- "Share all Q4 reports with the Finance team"

**Revoke Access:**
- "Remove Mike's access to confidential documents"
- "Revoke editor role from user@example.com"

**Query Permissions:**
- "Who can see document 456?"
- "What documents can John access?"
- "Show me all admins"
- "List everyone with write access to Contracts"

**Audit & Reports:**
- "Show permission changes from last week"
- "Who accessed sensitive documents yesterday?"
- "Generate access report for John Smith"

**Share Links:**
- "Create a share link for invoice_2024.pdf that expires in 3 days"
- "Generate public link for presentation.pdf"

### Phase 5: Frontend Components (NOT STARTED)

#### Files to Create:
1. `frontend/src/pages/Permissions.jsx` - Permissions dashboard
2. `frontend/src/components/ShareDocument.jsx` - Document sharing modal
3. `frontend/src/pages/AuditLog.jsx` - Audit log viewer
4. Update `frontend/src/pages/NaturalLanguageQuery.jsx` - Add permission UI

#### UI Components Needed:
- User management table
- Role assignment interface
- Permission matrix visualization
- Document sharing modal with:
  - User/role selection
  - Permission level checkboxes
  - Expiration date picker
  - Share link generator
- Audit log timeline with filters
- Permission change confirmations

### Phase 6: Security & Middleware (NOT STARTED)

#### Files to Create:
1. `backend/app/core/auth.py` - Authentication middleware
2. `backend/app/core/exceptions.py` - Update with permission exceptions

#### Tasks:
- Implement JWT authentication
- Create `get_current_user()` dependency
- Add `require_permission()` decorator
- Update all existing API endpoints with permission checks
- Implement row-level security in Elasticsearch queries

#### Endpoints to Update:
- All document APIs → Add ownership/permission checks
- All template APIs → Add permission checks
- All search APIs → Filter by user access
- All MCP tools → Add permission validation

### Phase 7: Database Migration & Setup (NOT STARTED)

#### Files to Create:
1. `backend/alembic/versions/xxx_add_permissions.py` - Migration script
2. Update `backend/requirements.txt` - Add dependencies

#### Required Dependencies:
```
pyjwt==2.8.0           # JWT tokens
python-multipart==0.0.6 # File upload with auth
passlib[bcrypt]==1.7.4  # Password hashing (already exists)
```

#### Migration Tasks:
- Create all permission tables
- Add owner/sharing fields to documents
- Create indexes for permission queries
- Initialize default permissions and roles
- Create default admin user

### Phase 8: Documentation (NOT STARTED)

#### Files to Create:
1. `docs/PERMISSIONS_GUIDE.md` - User guide
2. `docs/RBAC_ARCHITECTURE.md` - Technical architecture
3. `docs/MCP_PERMISSIONS.md` - MCP tool docs
4. `docs/NL_PERMISSIONS_EXAMPLES.md` - Natural language examples
5. `docs/PERMISSIONS_API.md` - API reference

### Phase 9: Testing (NOT STARTED)

#### Test Files to Create:
1. `backend/tests/test_permission_service.py`
2. `backend/tests/test_api_users.py`
3. `backend/tests/test_api_roles.py`
4. `backend/tests/test_api_sharing.py`
5. `backend/tests/test_mcp_permissions.py`
6. `backend/tests/test_nl_permissions.py`

---

## 📊 Progress Summary

**Total Phases**: 9
**Completed**: 2 (Database Models, API Endpoints)
**In Progress**: 0
**Not Started**: 7

**Overall Progress**: ~25% complete

### By Component:
- ✅ **Backend Core**: 100% (Models + Service + APIs)
- ⏳ **MCP Integration**: 0%
- ⏳ **Natural Language**: 0%
- ⏳ **Frontend**: 0%
- ⏳ **Security**: 0%
- ⏳ **Migration**: 0%
- ⏳ **Documentation**: 0%
- ⏳ **Testing**: 0%

---

## 🎯 Next Steps (Priority Order)

### Immediate (Critical Path):

1. **Update requirements.txt** ✅ (5 min)
   - Add JWT, passlib dependencies

2. **Create Database Migration** (30 min)
   - Alembic migration script
   - Initialize permissions on startup

3. **Create Authentication Middleware** (1 hour)
   - JWT token validation
   - get_current_user() helper
   - Update all APIs

4. **Create Audit Log API** (1 hour)
   - `backend/app/api/audit_log.py`
   - Query audit logs with filters

### High Priority (Core Functionality):

5. **Create MCP Permission Tools** (2-3 hours)
   - Implement 7 core MCP tools
   - Add permission resources
   - Test with Claude Desktop

6. **Extend ClaudeService for NL Permissions** (2 hours)
   - Parse permission commands
   - Extract entities (users, documents, actions)
   - Map to API calls

7. **Create NL Permission API** (2 hours)
   - Route permission queries
   - Execute actions
   - Return user-friendly responses

### Medium Priority (User Experience):

8. **Create Permissions Dashboard UI** (3-4 hours)
   - User management interface
   - Role assignment UI
   - Permission matrix

9. **Create Document Sharing Modal** (2 hours)
   - Share with users/roles
   - Generate share links
   - Set expiration

10. **Update NL Query Interface** (1-2 hours)
    - Add permission command UI
    - Permission change confirmations
    - Visual feedback

### Lower Priority (Polish):

11. **Create Audit Log Viewer** (2 hours)
12. **Write Documentation** (3-4 hours)
13. **Write Tests** (4-5 hours)

---

## 💡 Quick Start Guide

### To Initialize Permissions:

```bash
# 1. Run database migration (once created)
cd backend
alembic upgrade head

# 2. Initialize default permissions and roles
curl -X POST http://localhost:8000/api/roles/initialize

# 3. Assign admin role to default user
curl -X POST http://localhost:8000/api/users/1/roles \
  -H "Content-Type: application/json" \
  -d '{"role_id": 1, "scope": "global"}'
```

### To Test Permissions:

```python
# Check if user can read document
GET /api/users/1/permissions

# Share document
POST /api/sharing/documents/123/share
{
  "user_ids": [2],
  "can_read": true,
  "can_write": false
}

# Create share link
POST /api/sharing/documents/123/links
{
  "access_level": "read",
  "expires_in_days": 7
}
```

### To Use MCP (Once Implemented):

```
User: "Give john@example.com access to document 123"
Claude: [Uses grant_document_access MCP tool]
Claude: "I've granted john@example.com read access to document 123"
```

---

## 🚀 Estimated Time to Complete

- **MCP Tools**: 2-3 days
- **NL Interface**: 2-3 days
- **Frontend**: 3-4 days
- **Security & Migration**: 1-2 days
- **Testing & Docs**: 2-3 days

**Total Remaining**: ~10-15 days

---

## 📝 Notes

### Architecture Highlights:

1. **Hierarchical Permissions**: Global → Org → Folder → Document
2. **Role-Based + Direct**: Flexible permission assignment
3. **Audit Trail**: Complete history of all permission changes
4. **Share Links**: Secure, time-limited public sharing
5. **MCP + NL**: Dual interface for maximum usability

### Key Design Decisions:

- System roles (Admin, Editor, Viewer) are protected
- Document owners always have full access
- Admin role bypasses all permission checks
- Permissions are additive (more roles = more access)
- Folder permissions cascade to documents
- Share links use secure random tokens
- All permission changes are audited

### Security Considerations:

- JWT tokens for API authentication
- Password hashing with bcrypt
- Rate limiting on share link access
- Audit logging for compliance
- Row-level security in queries
- No permission escalation possible

---

**Last Updated**: 2025-10-28
**Next Update**: After Phase 3 (MCP Tools) completion
