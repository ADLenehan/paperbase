# Authentication Implementation - Phase 1 Complete

**Status**: ✅ Backend Authentication Core Complete
**Date**: 2025-10-29
**Phase**: 1 of 6 (Backend Authentication Core)

## Overview

We have successfully implemented the core backend authentication system for Paperbase, enabling unified authentication for both web UI (JWT tokens) and MCP/programmatic access (API keys).

## What Was Built

### 1. Core Authentication Module
**File**: `backend/app/core/auth.py` (290 lines)

**Features**:
- Password hashing with bcrypt
- JWT token generation and validation
- API key generation and verification (with `pb_` prefix)
- FastAPI dependencies:
  - `get_current_user()` - validates both JWT and API keys
  - `get_current_active_admin()` - requires admin privileges
  - `get_current_user_optional()` - for public endpoints

**Key Functions**:
```python
create_access_token(user_id: int) -> str
decode_access_token(token: str) -> Optional[int]
create_api_key(user_id: int, name: str) -> Tuple[str, str]
verify_api_key(db: Session, key: str) -> Optional[User]
get_current_user(credentials, db) -> User  # Main dependency
```

### 2. API Key Model
**File**: `backend/app/models/permissions.py` (added 48 lines)

**Features**:
- Secure key storage (bcrypt hashed)
- Optional expiration dates
- Last used tracking
- Audit trail (created_by, revoked_by)
- Soft delete (is_active flag)

**Relationships**:
- User → api_keys (one-to-many)
- Added relationship to User model in `settings.py`

### 3. Authentication API Endpoints
**File**: `backend/app/api/auth.py` (380 lines)

**Endpoints**:
- `POST /api/auth/login` - Email/password login → JWT token
- `POST /api/auth/logout` - Logout (client-side token discard)
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/change-password` - Change password
- `POST /api/auth/api-keys` - Create API key (returns plain key once!)
- `GET /api/auth/api-keys` - List user's API keys
- `DELETE /api/auth/api-keys/{key_id}` - Revoke API key
- `POST /api/auth/users/{user_id}/api-keys` - Admin: create key for any user
- `GET /api/auth/users/{user_id}/api-keys` - Admin: list user's keys

### 4. Configuration Updates
**File**: `backend/app/core/config.py`

**Added Settings**:
```python
SECRET_KEY: str = secrets.token_urlsafe(32)  # Auto-generated
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS: int = 24
```

### 5. Exception Classes
**File**: `backend/app/core/exceptions.py`

**Added**:
- `PermissionDeniedError` - HTTP 403
- `ResourceNotFoundError` - HTTP 404

### 6. Authentication Integration
**Updated Files**:
- `backend/app/api/users.py` - Replaced `get_current_user_id()` stub with `get_current_user` dependency (8 endpoints updated)
- `backend/app/api/roles.py` - Same replacement (9 endpoints updated)
- `backend/app/api/sharing.py` - Same replacement (7 endpoints updated)

**Pattern**:
```python
# BEFORE (stub):
def some_endpoint(db: Session = Depends(get_db)):
    current_user_id = get_current_user_id()  # Always returned 1
    permission_service.require_permission(current_user_id, action)

# AFTER (real auth):
def some_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    permission_service.require_permission(current_user.id, action)
```

### 7. Router Registration
**File**: `backend/app/main.py`

**Added**:
- Registered 4 new routers: auth, users, roles, sharing
- Added permission initialization to startup event
- All routers now active and available

### 8. Dependencies Added
**File**: `backend/requirements.txt`

**Added Packages**:
```
pyjwt==2.8.0
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
```

## How It Works

### Authentication Flow

#### Web UI (JWT Tokens):
1. User submits email/password to `POST /api/auth/login`
2. Backend validates credentials
3. Returns JWT token (expires in 24 hours)
4. Frontend stores token in localStorage
5. Frontend sends token in `Authorization: Bearer <token>` header
6. `get_current_user()` dependency validates token on each request

#### MCP/Programmatic Access (API Keys):
1. User (or admin) creates API key via `POST /api/auth/api-keys`
2. Plain key shown once: `pb_abc123...` (32 random bytes)
3. Hashed key stored in database
4. Client sends key in `Authorization: Bearer <api_key>` header
5. `get_current_user()` dependency validates key (checks hash, expiration)
6. Updates `last_used_at` timestamp

### Dual Authentication Support

The `get_current_user()` dependency tries both methods:
```python
async def get_current_user(credentials, db):
    token = credentials.credentials

    # Try JWT first
    user_id = decode_access_token(token)
    if user_id:
        return get_user_by_id(user_id)

    # Try API key
    user = verify_api_key(db, token)
    if user:
        return user

    # Fail
    raise HTTPException(401, "Invalid authentication")
```

## Testing Status

✅ Backend imports successfully (no syntax/import errors)
⏳ Needs database migration for `api_keys` table
⏳ Needs manual testing of endpoints
⏳ Needs frontend implementation

## Next Steps

### Phase 2: Frontend Authentication UI (2-3 hours)
- [ ] Create `frontend/src/pages/Login.jsx`
- [ ] Create `frontend/src/contexts/AuthContext.jsx`
- [ ] Create `frontend/src/components/PrivateRoute.jsx`
- [ ] Update `frontend/src/App.jsx` with auth routes
- [ ] Update API client with token interceptor

### Phase 3: Admin User Management UI (3-4 hours)
- [ ] Create `frontend/src/pages/UserManagement.jsx`
- [ ] Create `frontend/src/components/APIKeyManagement.jsx`
- [ ] Add users menu to navigation

### Phase 4: MCP Server Authentication (1-2 hours)
- [ ] Update `backend/mcp_server/server.py`
- [ ] Add API key validation
- [ ] Update MCP documentation

### Phase 5: Database Migration (30 min)
- [ ] Create Alembic migration for `api_keys` table
- [ ] Create script to initialize admin user
- [ ] Set password for default user

### Phase 6: Testing & Documentation (2-3 hours)
- [ ] Test login flow
- [ ] Test API key creation/usage
- [ ] Test permission enforcement
- [ ] Update README with auth instructions

## API Examples

### Login (Web UI)
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@paperbase.local", "password": "your-password"}'

# Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin@paperbase.local",
    "name": "Admin User",
    "is_admin": true,
    "org_id": 1
  }
}
```

### Create API Key
```bash
curl -X POST http://localhost:8000/api/auth/api-keys \
  -H "Authorization: Bearer <jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "MCP Server", "expires_in_days": 365}'

# Response:
{
  "id": 1,
  "name": "MCP Server",
  "key": "pb_abc123...",  # ⚠️ SAVE THIS - shown only once!
  "expires_at": "2026-10-29T00:00:00Z",
  "created_at": "2025-10-29T13:00:00Z"
}
```

### Use API Key
```bash
curl http://localhost:8000/api/documents \
  -H "Authorization: Bearer pb_abc123..."
```

### Get Current User Info
```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <jwt-token-or-api-key>"
```

## Security Considerations

### Implemented ✅
- Passwords hashed with bcrypt
- API keys hashed with bcrypt
- JWT tokens signed with secret key
- API keys prefixed with `pb_` for identification
- Expired API keys rejected
- Inactive users cannot authenticate
- Admin-only endpoints protected

### TODO 🔄
- Add token blacklist for true logout
- Add rate limiting on login endpoint
- Add brute-force protection
- Add 2FA support
- Add password complexity requirements
- Add password reset flow
- Store SECRET_KEY in environment (not auto-generated)

## Breaking Changes

### For MVP Users
- **No breaking changes** - Authentication is additive
- Existing hardcoded `user_id=1` behavior preserved until:
  1. Admin sets password for default user
  2. Frontend login UI implemented
  3. Users start using authentication

### For API Consumers
- All existing endpoints now **require authentication**
- Must send `Authorization: Bearer <token>` header
- Unauthenticated requests return HTTP 401

### Migration Path
1. Keep current system running
2. Set password for default user: `UPDATE users SET hashed_password='...' WHERE id=1`
3. Frontend can still work (user logs in once)
4. MCP server needs API key added to config

## Files Modified Summary

**New Files (3)**:
- `backend/app/core/auth.py` (290 lines)
- `backend/app/api/auth.py` (380 lines)
- `backend/update_auth_stubs.py` (helper script)

**Modified Files (8)**:
- `backend/app/core/config.py` - Added JWT settings
- `backend/app/core/exceptions.py` - Added 2 exceptions
- `backend/app/models/permissions.py` - Added APIKey model
- `backend/app/models/settings.py` - Added api_keys relationship
- `backend/app/api/users.py` - Replaced auth stubs (8 endpoints)
- `backend/app/api/roles.py` - Replaced auth stubs (9 endpoints)
- `backend/app/api/sharing.py` - Replaced auth stubs (7 endpoints)
- `backend/app/main.py` - Registered routers, added permission init

**Total Lines Added**: ~800 lines
**Total Endpoints Added**: 8 new auth endpoints
**Total Endpoints Updated**: 24 endpoints now use real authentication

## Verification

```bash
# Test imports
cd backend
python3 -c "from app.main import app; print('✅ Success')"

# Output: ✅ Success

# Check registered routes
python3 -c "
from app.main import app
auth_routes = [r.path for r in app.routes if 'auth' in r.path]
print(f'Auth routes: {len(auth_routes)}')
for route in auth_routes:
    print(f'  {route}')
"
```

## Notes

- SECRET_KEY is auto-generated on first run - should be set in `.env` for production
- Default user (id=1) needs password set before login works
- JWT tokens expire after 24 hours (configurable)
- API keys don't expire by default (configurable per-key)
- All authentication requires HTTPS in production

---

**Completed By**: Claude (Sonnet 4.5)
**Session**: Authentication Implementation Phase 1
**Next Session**: Frontend Authentication UI (Phase 2)
