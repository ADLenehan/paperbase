# Permissions System - Quick Start Guide

This guide will help you get started with the Paperbase permissions system.

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**New dependencies added:**
- `pyjwt==2.8.0` - JWT token handling
- `passlib[bcrypt]==1.7.4` - Password hashing
- `python-jose[cryptography]==3.3.0` - Additional JWT support

### 2. Database Setup

The permissions system adds several new tables. You'll need to run a migration (script to be created):

```bash
# Option A: Using Alembic (recommended for production)
alembic upgrade head

# Option B: Manual initialization (for development)
# The tables will be created automatically when you start the app
# and run the initialize endpoint
```

### 3. Initialize Default Permissions & Roles

Start your backend server:

```bash
uvicorn app.main:app --reload
```

Then initialize the system (one-time setup):

```bash
curl -X POST http://localhost:8000/api/roles/initialize
```

This creates:
- **17 default permissions** (read:documents, write:templates, etc.)
- **3 system roles** (Admin, Editor, Viewer)

### 4. Assign Admin Role to Default User

```bash
curl -X POST http://localhost:8000/api/users/1/roles \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": 1,
    "scope": "global"
  }'
```

---

## 📚 Core Concepts

### Roles

**System Roles** (cannot be modified):
- **Admin** - Full system access, all permissions
- **Editor** - Can create/edit documents and templates
- **Viewer** - Read-only access

**Custom Roles** - Create your own with specific permissions

### Permissions

Permissions are granular actions:
- `read:documents` - View documents
- `write:documents` - Create/edit documents
- `delete:documents` - Delete documents
- `share:documents` - Share documents with others
- `manage:roles` - Manage roles and assignments
- `admin` - Superuser access (all permissions)

### Scopes

Permissions can be scoped to different levels:
- **Global** - Applies everywhere
- **Organization** - Applies to specific org
- **Folder** - Applies to specific folder and optionally subfolders
- **Document** - Applies to specific document

---

## 🎯 Common Use Cases

### Use Case 1: Create a New User

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@company.com",
    "name": "John Doe",
    "org_id": 1,
    "is_admin": false
  }'
```

### Use Case 2: Assign Editor Role

```bash
# Make John an Editor
curl -X POST http://localhost:8000/api/users/2/roles \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": 2,
    "scope": "global"
  }'
```

### Use Case 3: Share a Document

```bash
# Share document 123 with user 2
curl -X POST http://localhost:8000/api/sharing/documents/123/share \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": [2],
    "can_read": true,
    "can_write": false,
    "expires_in_days": 30,
    "notes": "Q1 report review"
  }'
```

### Use Case 4: Create a Share Link

```bash
# Create a shareable link that expires in 7 days
curl -X POST http://localhost:8000/api/sharing/documents/123/links \
  -H "Content-Type: application/json" \
  -d '{
    "access_level": "read",
    "expires_in_days": 7,
    "max_accesses": 100
  }'

# Response includes the share URL:
# {
#   "url": "http://localhost:5173/share/abc123xyz..."
# }
```

### Use Case 5: Check User Permissions

```bash
# See what permissions a user has
curl http://localhost:8000/api/users/2/permissions

# Response:
# {
#   "permissions": [
#     {"action": "read:documents", "name": "Read Documents"},
#     {"action": "write:documents", "name": "Write Documents"},
#     ...
#   ],
#   "roles": [...]
# }
```

### Use Case 6: Create a Custom Role

```bash
# Create a "Contract Reviewer" role
curl -X POST http://localhost:8000/api/roles \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Contract Reviewer",
    "slug": "contract-reviewer",
    "description": "Can review and approve contracts",
    "permission_ids": [1, 2, 5]
  }'
```

### Use Case 7: Share a Folder

```bash
# Share entire folder with a team
curl -X POST http://localhost:8000/api/sharing/folders/contracts/2024/share \
  -H "Content-Type: application/json" \
  -d '{
    "user_ids": [2, 3, 4],
    "can_read": true,
    "inherit_to_subfolders": true
  }'
```

### Use Case 8: View Document Access

```bash
# See who has access to a document
curl http://localhost:8000/api/sharing/documents/123/permissions

# Response shows:
# - Direct user permissions
# - Role-based permissions
# - Active share links
# - Total users with access
```

### Use Case 9: Revoke Access

```bash
# Revoke user's access to document
curl -X DELETE http://localhost:8000/api/sharing/documents/123/permissions/2

# Revoke a share link
curl -X DELETE http://localhost:8000/api/sharing/links/5
```

### Use Case 10: List Available Permissions

```bash
# See all permissions that can be assigned
curl http://localhost:8000/api/roles/permissions

# Filter by resource type
curl "http://localhost:8000/api/roles/permissions?resource_type=document"
```

---

## 🔐 Permission Checking Logic

### Document Access Resolution

When checking if a user can access a document, the system checks in this order:

1. **Is user the document owner?** → Full access
2. **Is user an admin?** → Full access
3. **Is document public and user in same org?** → Read access
4. **Does user have direct DocumentPermission?** → Check permission level
5. **Does user have FolderPermission for document's folder?** → Check permission level
6. **Does user have permission via role?** → Check role permissions

### Role Permission Resolution

Users can have multiple roles with different scopes:

```
User John:
  - Editor (global scope)
  - Viewer (folder: /confidential)
  - Custom Role (organization: 1)
```

Permissions are **additive** - if any role grants permission, user has it.

### Admin Bypass

Users with `is_admin=true` or the `admin` permission **bypass all checks**.

---

## 🧪 Testing Permissions

### Test Admin Access

```python
# Python test
from app.services.permission_service import PermissionService
from app.models.permissions import PermissionAction

permission_service = PermissionService(db)

# Should return True for admin
has_access = permission_service.check_permission(
    user_id=1,
    action=PermissionAction.ADMIN
)
```

### Test Document Access

```python
# Check if user can read document
can_read = permission_service.check_document_access(
    user_id=2,
    document_id=123,
    required_permission="read"
)

# Check if user can share document
can_share = permission_service.check_document_access(
    user_id=2,
    document_id=123,
    required_permission="share"
)
```

### Test Permission Enforcement

```python
# This will raise PermissionDeniedError if user lacks permission
permission_service.require_permission(
    user_id=2,
    action=PermissionAction.DELETE_DOCUMENTS
)
```

---

## 🎨 Frontend Integration (Coming Soon)

Once the frontend components are built, you'll be able to:

### Permissions Dashboard
- View all users and their roles
- Assign/revoke roles with drag-and-drop
- See permission matrix
- Filter and search users

### Document Sharing Modal
- Click "Share" button on any document
- Select users or roles from dropdown
- Set permission levels with checkboxes
- Set expiration date
- Generate shareable links

### Audit Log Viewer
- Timeline view of all permission changes
- Filter by user, action, date
- See who shared what with whom
- Export audit reports

---

## 🤖 MCP Integration (Coming Soon)

Once MCP tools are implemented, you'll be able to use natural language:

```
User: "Give john@company.com access to document 123"
Claude: [Uses grant_document_access MCP tool]
Claude: "I've granted john@company.com read access to document 123"

User: "Who can see document 456?"
Claude: [Uses list_document_permissions MCP tool]
Claude: "Document 456 is accessible by:
- Jane Doe (Editor role, can read/write)
- Mike Smith (Direct permission, can read)
- Public share link (read-only, expires in 3 days)"

User: "Make Sarah an admin"
Claude: [Uses assign_user_role MCP tool]
Claude: "I've assigned the Administrator role to sarah@company.com"
```

---

## 🔍 Natural Language Queries (Coming Soon)

Once the NL interface is integrated:

```
"Show me all invoices that John Smith can access"
→ Filters search results by user permissions

"Create a share link for Q1-report.pdf that expires tomorrow"
→ Generates shareable link with 1-day expiration

"Who changed permissions on document 789 last week?"
→ Queries audit log and shows permission changes

"Give the Finance team read access to all invoices"
→ Shares all invoice documents with Finance role
```

---

## 📊 API Endpoint Reference

### User Management
- `POST /api/users` - Create user
- `GET /api/users` - List users
- `GET /api/users/{id}` - Get user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Deactivate user
- `POST /api/users/{id}/roles` - Assign role
- `DELETE /api/users/{id}/roles/{role_id}` - Revoke role
- `GET /api/users/{id}/permissions` - Get permissions

### Roles & Permissions
- `GET /api/roles/permissions` - List permissions
- `GET /api/roles` - List roles
- `GET /api/roles/{id}` - Get role
- `POST /api/roles` - Create custom role
- `PUT /api/roles/{id}` - Update role
- `DELETE /api/roles/{id}` - Delete role
- `POST /api/roles/{id}/permissions` - Add permissions
- `DELETE /api/roles/{id}/permissions/{perm_id}` - Remove permission
- `POST /api/roles/initialize` - Initialize system

### Sharing
- `POST /api/sharing/documents/{id}/share` - Share document
- `GET /api/sharing/documents/{id}/permissions` - List access
- `DELETE /api/sharing/documents/{id}/permissions/{user_id}` - Revoke access
- `POST /api/sharing/documents/{id}/links` - Create share link
- `DELETE /api/sharing/links/{link_id}` - Revoke link
- `POST /api/sharing/folders/{path}/share` - Share folder
- `GET /api/sharing/folders/{path}/permissions` - Get folder permissions

---

## 🛠️ Troubleshooting

### Issue: "Permission denied" errors

**Solution**: Check user's roles and permissions:
```bash
curl http://localhost:8000/api/users/{user_id}/permissions
```

### Issue: Can't share document

**Cause**: User needs `share:documents` permission or document ownership

**Solution**:
```bash
# Assign Editor role (includes share permission)
curl -X POST http://localhost:8000/api/users/{user_id}/roles \
  -d '{"role_id": 2, "scope": "global"}'
```

### Issue: System roles not found

**Cause**: System not initialized

**Solution**:
```bash
curl -X POST http://localhost:8000/api/roles/initialize
```

### Issue: Share link not working

**Check**:
1. Is link expired? Check `expires_at`
2. Has it reached max accesses? Check `current_accesses` vs `max_accesses`
3. Is it revoked? Check `is_active`

---

## 📝 Best Practices

### 1. Use Roles for Team Permissions
Don't assign direct permissions to many users. Create roles:
```
❌ Bad: Assign read permission to 50 users individually
✅ Good: Create "Finance Team" role, assign to role
```

### 2. Set Expiration on Temporary Access
Always set expiration for guest/contractor access:
```javascript
{
  "expires_in_days": 30,  // Access expires after 30 days
  "notes": "Q1 audit - expires end of March"
}
```

### 3. Use Folder Permissions for Organization
Share folders instead of individual documents:
```
❌ Bad: Share 100 contract documents individually
✅ Good: Share /contracts folder with inherit_to_subfolders
```

### 4. Regular Audit Reviews
Periodically review who has access:
```bash
# Check document access
GET /api/sharing/documents/{id}/permissions

# Check user permissions
GET /api/users/{id}/permissions
```

### 5. Use Share Links for External Sharing
For external stakeholders, use share links instead of creating accounts:
```javascript
{
  "access_level": "read",
  "expires_in_days": 7,
  "password": "optional-password",
  "max_accesses": 10
}
```

---

## 🔐 Security Notes

- Admins have unrestricted access - assign carefully
- Share links should be treated as sensitive (contain access token)
- Set reasonable expiration times on temporary access
- Review audit logs regularly
- Password-protect sensitive share links
- Revoke access when users leave organization

---

## 🚀 Next Steps

1. **Complete MCP Integration** - Enable natural language permission management
2. **Build Frontend Components** - Visual permission management
3. **Add Authentication** - JWT tokens for API security
4. **Row-Level Security** - Filter Elasticsearch queries by permissions
5. **Advanced Audit** - Track document access attempts
6. **Email Notifications** - Notify users when documents are shared

---

## 📖 Additional Documentation

- [PERMISSIONS_IMPLEMENTATION_STATUS.md](./PERMISSIONS_IMPLEMENTATION_STATUS.md) - Full implementation status
- [API.md](./API.md) - Complete API reference (to be updated)
- [RBAC_ARCHITECTURE.md](./RBAC_ARCHITECTURE.md) - Technical architecture (to be created)

---

**Questions?** Check the implementation status doc or ask in the project chat!

**Last Updated**: 2025-10-28
