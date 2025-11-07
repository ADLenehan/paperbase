# Permissions System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PAPERBASE PERMISSIONS                        │
│                     Role-Based Access Control (RBAC)                 │
└─────────────────────────────────────────────────────────────────────┘

                               ┌─────────────┐
                               │   User      │
                               │  (Actor)    │
                               └──────┬──────┘
                                      │
                          ┌───────────┴───────────┐
                          │                       │
                    ┌─────▼─────┐         ┌──────▼──────┐
                    │ UserRoles │         │   Direct    │
                    │           │         │ Permissions │
                    └─────┬─────┘         └──────┬──────┘
                          │                      │
                    ┌─────▼─────┐               │
                    │   Roles   │               │
                    │           │               │
                    └─────┬─────┘               │
                          │                     │
                    ┌─────▼─────┐              │
                    │Permissions│◄─────────────┘
                    │  (Actions)│
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │ Resources │
                    │ Documents │
                    │  Folders  │
                    │ Templates │
                    └───────────┘
```

---

## Database Schema

### Core Models

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                              │
└─────────────────────────────────────────────────────────────────────┘

organizations                users                     roles
┌──────────────┐          ┌──────────────┐         ┌──────────────┐
│ id           │◄─────────│ id           │         │ id           │
│ name         │          │ org_id       │────┐    │ org_id       │
│ slug         │          │ email        │    │    │ name         │
│ created_at   │          │ name         │    │    │ slug         │
└──────────────┘          │ is_admin     │    │    │ role_type    │
                          │ is_active    │    │    │ is_system    │
                          └───────┬──────┘    │    └──────┬───────┘
                                  │           │           │
                    ┌─────────────┴───────┐   │    ┌──────┴────────┐
                    │                     │   │    │               │
              user_roles            ┌─────▼───▼────▼────┐   role_permissions
            ┌──────────────┐        │                   │   ┌──────────────┐
            │ id           │        │   permissions     │   │ role_id      │
            │ user_id      │────┐   │                   │   │ permission_id│
            │ role_id      │────┼───│ id                │◄──└──────────────┘
            │ scope        │    │   │ action            │
            │ scope_org_id │    │   │ name              │
            │ scope_folder │    │   │ resource_type     │
            │ expires_at   │    │   └───────────────────┘
            └──────────────┘    │
                                │
                    ┌───────────┴────────────┐
                    │                        │
         document_permissions      folder_permissions
        ┌──────────────┐          ┌──────────────┐
        │ id           │          │ id           │
        │ document_id  │          │ folder_path  │
        │ user_id      │          │ user_id      │
        │ role_id      │          │ role_id      │
        │ can_read     │          │ can_read     │
        │ can_write    │          │ can_write    │
        │ can_delete   │          │ can_delete   │
        │ can_share    │          │ can_share    │
        │ expires_at   │          │ inherit      │
        └──────────────┘          └──────────────┘

              share_links              permission_audit_logs
        ┌──────────────┐          ┌──────────────────┐
        │ id           │          │ id               │
        │ document_id  │          │ user_id          │
        │ token        │          │ action           │
        │ access_level │          │ resource_type    │
        │ password_hash│          │ resource_id      │
        │ max_accesses │          │ target_user_id   │
        │ expires_at   │          │ details (JSON)   │
        │ is_active    │          │ timestamp        │
        └──────────────┘          └──────────────────┘
```

---

## Permission Resolution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   PERMISSION CHECK ALGORITHM                         │
└─────────────────────────────────────────────────────────────────────┘

    User requests access to Resource
                │
                ▼
    ┌───────────────────────┐
    │ Is user Admin?        │──Yes──► ✅ GRANT ACCESS (bypass all)
    └───────────┬───────────┘
                │ No
                ▼
    ┌───────────────────────┐
    │ Is user Owner?        │──Yes──► ✅ GRANT ACCESS (full access)
    └───────────┬───────────┘
                │ No
                ▼
    ┌───────────────────────┐
    │ Is resource Public?   │──Yes──► ✅ GRANT READ ACCESS
    └───────────┬───────────┘          (if same org)
                │ No
                ▼
    ┌───────────────────────┐
    │ Direct Permission?    │──Yes──► Check permission level
    │ (DocumentPermission)  │          ├─ can_read?
    └───────────┬───────────┘          ├─ can_write?
                │ No                   ├─ can_delete?
                ▼                      └─ can_share?
    ┌───────────────────────┐                │
    │ Folder Permission?    │──Yes───────────┤
    │ (FolderPermission)    │                │
    └───────────┬───────────┘                │
                │ No                         │
                ▼                            │
    ┌───────────────────────┐                │
    │ Role Permission?      │──Yes───────────┤
    │ (via UserRole)        │                │
    └───────────┬───────────┘                │
                │ No                         │
                ▼                            ▼
         ❌ DENY ACCESS            ✅ GRANT with level
```

---

## API Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYERS                                  │
└─────────────────────────────────────────────────────────────────────┘

    Frontend / MCP Client / Natural Language
           │
           │ HTTP/JSON
           ▼
    ┌─────────────────┐
    │  FastAPI Routes │
    │                 │
    │ ├─ /api/users   │──► User Management
    │ ├─ /api/roles   │──► Role Management
    │ ├─ /api/sharing │──► Document Sharing
    │ └─ /api/audit   │──► Audit Logs (TODO)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Permission      │
    │ Service         │
    │                 │
    │ ├─ check()      │──► Validate permissions
    │ ├─ grant()      │──► Share resources
    │ ├─ revoke()     │──► Remove access
    │ └─ audit()      │──► Log changes
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  SQLAlchemy     │
    │  ORM Layer      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  SQLite/        │
    │  PostgreSQL     │
    └─────────────────┘
```

---

## Permission Scopes

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PERMISSION SCOPES                               │
└─────────────────────────────────────────────────────────────────────┘

GLOBAL SCOPE
├── User has permission everywhere
├── Example: "Make Sarah a global admin"
└── UserRole: scope="global", scope_org_id=null, scope_folder=null

ORGANIZATION SCOPE
├── User has permission within specific organization
├── Example: "Make John an editor in Org 1"
└── UserRole: scope="organization", scope_org_id=1, scope_folder=null

FOLDER SCOPE
├── User has permission within specific folder
├── Example: "Give Mike access to /contracts folder"
├── Optionally inherits to subfolders
└── UserRole: scope="folder", scope_org_id=1, scope_folder="/contracts"

DOCUMENT SCOPE
├── User has permission for specific document
├── Example: "Share document 123 with Jane"
└── DocumentPermission: document_id=123, user_id=2
```

---

## User Journey: Sharing a Document

```
┌─────────────────────────────────────────────────────────────────────┐
│              DOCUMENT SHARING FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘

1. User clicks "Share" on document
              │
              ▼
2. Frontend shows Share Modal
   ├─ Select users/roles
   ├─ Set permission levels (read/write/delete/share)
   ├─ Set expiration (optional)
   └─ Add notes (optional)
              │
              ▼
3. POST /api/sharing/documents/{id}/share
   {
     "user_ids": [2, 3],
     "can_read": true,
     "can_write": false,
     "expires_in_days": 30
   }
              │
              ▼
4. Permission Service validates:
   ├─ Does user have "share" permission?
   ├─ Do target users exist?
   └─ Is document accessible?
              │
              ▼
5. Create DocumentPermission records
   ├─ One for each user
   └─ Or one for role (shared by all role members)
              │
              ▼
6. Log to PermissionAuditLog
   ├─ Who shared (user_id=1)
   ├─ What (document_id=123)
   ├─ With whom (target_user_id=2,3)
   └─ When (timestamp)
              │
              ▼
7. Return success + send notifications (TODO)
              │
              ▼
8. Target users can now access document
```

---

## Share Link Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                   SHARE LINK LIFECYCLE                               │
└─────────────────────────────────────────────────────────────────────┘

1. Create Share Link
   POST /api/sharing/documents/123/links
   {
     "access_level": "read",
     "expires_in_days": 7,
     "password": "optional123"
   }
              │
              ▼
2. System generates secure token
   token = secrets.token_urlsafe(32)
              │
              ▼
3. Store ShareLink record
   ├─ document_id: 123
   ├─ token: "abc123xyz..."
   ├─ expires_at: 7 days from now
   ├─ password_hash: bcrypt("optional123")
   └─ is_active: true
              │
              ▼
4. Return URL to user
   https://app.paperbase.com/share/abc123xyz...
              │
              ▼
5. User shares URL with external party
              │
              ▼
6. External party visits URL
   GET /share/abc123xyz...
              │
              ▼
7. System validates:
   ├─ Is token valid?
   ├─ Is link active?
   ├─ Is link expired?
   ├─ Has max accesses been reached?
   └─ Is password correct (if set)?
              │
              ▼
8. If valid:
   ├─ Show document
   ├─ Increment access count
   ├─ Log access to ShareLinkAccessLog
   └─ Track IP/user-agent
              │
              ▼
9. Owner can revoke anytime
   DELETE /api/sharing/links/{id}
```

---

## Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DEFAULT ROLES                                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ ADMIN (System Role)                                              │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ ✓ ALL PERMISSIONS (bypass all checks)                       │ │
│ │ ✓ Manage users                                               │ │
│ │ ✓ Manage roles                                               │ │
│ │ ✓ Manage organization                                        │ │
│ │ ✓ View audit logs                                            │ │
│ │ ✓ Full document access                                       │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ EDITOR (System Role)                                             │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ ✓ Read documents                                             │ │
│ │ ✓ Write documents                                            │ │
│ │ ✓ Share documents                                            │ │
│ │ ✓ Read templates                                             │ │
│ │ ✓ Write templates                                            │ │
│ │ ✓ Search all                                                 │ │
│ │ ✓ Export data                                                │ │
│ │ ✗ Delete documents                                           │ │
│ │ ✗ Manage users                                               │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ VIEWER (System Role)                                             │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ ✓ Read documents                                             │ │
│ │ ✓ Read templates                                             │ │
│ │ ✓ Search all                                                 │ │
│ │ ✗ Write documents                                            │ │
│ │ ✗ Delete documents                                           │ │
│ │ ✗ Share documents                                            │ │
│ │ ✗ Manage users                                               │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ CUSTOM ROLES (User-defined)                                     │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ Examples:                                                    │ │
│ │ • Contract Reviewer (read + comment only)                   │ │
│ │ • Finance Team (read + export)                              │ │
│ │ • Guest (temporary read access)                             │ │
│ │ • Department Lead (read + write + share in folder)          │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## Integration Points

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYSTEM INTEGRATIONS                               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   MCP Tools     │ ◄─── Natural Language Commands
│   (TODO)        │      "Give John access to doc 123"
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Permission APIs │ ◄─── REST API Calls
│   (Complete)    │      POST /api/sharing/...
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Permission      │ ◄─── Service Layer
│ Service         │      check_permission()
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Database      │ ◄─── Data Persistence
│   (SQLite)      │      Users, Roles, Permissions
└─────────────────┘
```

---

## Audit Trail

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AUDIT LOGGING                                   │
└─────────────────────────────────────────────────────────────────────┘

Every permission change is logged:

permission_audit_logs
┌────────────────────────────────────────────────────────────┐
│ Timestamp: 2025-10-28 10:30:00                             │
│ User: john@company.com (ID: 1)                             │
│ Action: grant_document_permission                          │
│ Resource: Document #123 (invoice.pdf)                      │
│ Target: sarah@company.com (ID: 2)                          │
│ Details: {"can_read": true, "can_write": false}            │
│ IP: 192.168.1.100                                          │
│ Success: true                                              │
└────────────────────────────────────────────────────────────┘

Query Examples:
• "What permissions changed last week?"
• "Who shared document 123?"
• "What has user 2 been given access to?"
• "Show all permission denials"
```

---

## Security Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                                 │
└─────────────────────────────────────────────────────────────────────┘

Layer 1: Authentication (TODO)
├── JWT tokens
├── Secure password storage (bcrypt)
└── Session management

Layer 2: Authorization (COMPLETE)
├── Permission checks on all operations
├── Resource-level access control
├── Owner privileges
└── Admin bypass with audit

Layer 3: Data Security
├── Row-level security in queries
├── Encrypted share link tokens
├── Password-protected shares
└── Audit trail for compliance

Layer 4: Network Security
├── HTTPS (production)
├── Rate limiting (TODO)
├── CORS configuration
└── API key rotation (TODO)
```

---

## Future Enhancements

```
┌─────────────────────────────────────────────────────────────────────┐
│                      ROADMAP                                         │
└─────────────────────────────────────────────────────────────────────┘

Phase 3: MCP Integration
├── Natural language permission commands
├── MCP tools for permission management
└── Resource endpoints for permission views

Phase 4: Natural Language
├── Parse: "Give John access to doc 123"
├── Extract entities (users, documents, actions)
└── Map to API calls

Phase 5: Frontend
├── Permissions Dashboard
├── Document Sharing Modal
├── Role Assignment UI
└── Audit Log Viewer

Phase 6: Advanced Features
├── Temporary access with auto-revocation
├── Conditional permissions (time-based)
├── Permission templates
├── Bulk permission changes
└── Permission inheritance rules

Phase 7: Enterprise Features
├── SSO integration (OAuth, SAML)
├── Active Directory sync
├── Advanced audit reports
├── Compliance dashboards
└── Permission analytics
```

---

**Last Updated**: 2025-10-28
**Status**: Core Backend Complete
**Next**: MCP Integration
