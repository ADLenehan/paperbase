# 🚨 Integration Fixes Required After Adding Authentication

**Date**: 2025-11-15
**Priority**: HIGH
**Impact**: Most API calls will fail authentication

---

## 🔍 Problem Identified

After implementing frontend authentication, **15 files** are using `fetch()` instead of the authenticated `apiClient`. This means:

- ❌ **No auth tokens are sent** with these requests
- ❌ **Backend will reject** if it requires authentication
- ❌ **Users cannot use core features** (upload, search, audit, etc.)

## 📊 Impact Analysis

### Critical (Breaks Core Functionality)
| File | API Endpoint | Impact |
|------|--------------|---------|
| `BulkUpload.jsx` | `/api/bulk/upload-and-analyze` | ✅ FIXED - File upload broken |
| `BulkUpload.jsx` | `/api/bulk/create-new-template` | ❌ Create template broken |
| `BulkUpload.jsx` | `/api/bulk/confirm-template` | ❌ Confirm template broken |
| `ChatSearch.jsx` | `/api/search` | ❌ Search broken |
| `ChatSearch.jsx` | `/api/audit/verify-and-regenerate` | ❌ Inline audit broken |
| `Audit.jsx` | `/api/audit/verify` | ❌ Audit verification broken |
| `Audit.jsx` | `/api/audit/bulk-verify` | ❌ Batch audit broken |

### High (Breaks Secondary Features)
| File | API Endpoint | Impact |
|------|--------------|---------|
| `DocumentDetail.jsx` | `/api/documents/{id}` | Document details broken |
| `Settings.jsx` | `/api/settings/*` | Settings broken |
| `Audit.jsx` | `/api/onboarding/schemas/{id}` | Schema loading broken |
| `ChatSearch.jsx` | `/api/templates` | Template list broken |

### Medium (Breaks UI Polish)
| File | API Endpoint | Impact |
|------|--------------|---------|
| `useConfidenceThresholds.js` | `/api/settings/category/confidence` | Confidence thresholds broken |
| `BulkUpload.jsx` | `/api/onboarding/schemas` | Template dropdown broken |
| `BulkUpload.jsx` | `/api/documents/{id}` (polling) | Status polling broken |

---

## ✅ Solution: Use `fetchWithAuth()` Wrapper

I've created a new utility: `frontend/src/utils/fetchWithAuth.js`

### Features:
- ✅ Automatically injects `Authorization: Bearer <token>` header
- ✅ Handles relative and absolute URLs
- ✅ Supports FormData (for file uploads)
- ✅ Helper functions for common use cases

### Usage:

```javascript
// Before (NO AUTH):
const response = await fetch(`${API_URL}/api/bulk/upload`, {
  method: 'POST',
  body: formData,
});

// After (WITH AUTH):
import { fetchWithAuth } from '../utils/fetchWithAuth';

const response = await fetchWithAuth('/api/bulk/upload', {
  method: 'POST',
  body: formData,
});
```

---

## 🛠️ Fix Strategy

### Option 1: Automated Script (Recommended)
I can create a script to automatically replace all `fetch()` calls with `fetchWithAuth()`.

**Pros**: Fast, consistent, less error-prone
**Cons**: Requires review to ensure correctness

### Option 2: Manual Fix
Update each file individually.

**Pros**: More control, can test incrementally
**Cons**: Time-consuming (15 files, 20+ fetch calls)

### Option 3: Hybrid
Auto-fix simple cases, manually review complex ones.

---

## 📝 Files Requiring Changes

### Priority 1: Core Features (Fix First)

**1. `pages/BulkUpload.jsx`** (5 fetch calls)
- ✅ Line 143: `/api/bulk/upload-and-analyze` - **FIXED**
- ❌ Line 50: `/api/documents/{id}` (status polling)
- ❌ Line 94: `/api/onboarding/schemas`
- ❌ Line 230: `/api/bulk/create-new-template`
- ❌ Line 249: `/api/bulk/confirm-template`

**2. `pages/ChatSearch.jsx`** (4 fetch calls)
- ❌ Line 37: `/api/templates`
- ❌ Line 71: `/api/search`
- ❌ Line 204: `/api/audit/verify-and-regenerate`
- ❌ Line 264: `/api/audit/bulk-verify-and-regenerate`

**3. `pages/Audit.jsx`** (4 fetch calls)
- ❌ Line 100: `/api/audit/verify`
- ❌ Line 164: `/api/onboarding/schemas/{id}`
- ❌ Line 170: `/api/documents?schema_id={id}`
- ❌ Line 184: `/api/audit/bulk-verify`

### Priority 2: Supporting Features

**4. `pages/Settings.jsx`** (3 fetch calls)
- ❌ Line 23: `/api/settings/`
- ❌ Line 53: `/api/settings/{key}` (PUT)
- ❌ Line 81: `/api/settings/{key}` (DELETE)

**5. `pages/DocumentDetail.jsx`** (1 fetch call)
- ❌ Line 70: `/api/documents/{id}`

**6. `hooks/useConfidenceThresholds.js`** (1 fetch call)
- ❌ Line 44: `/api/settings/category/confidence`

### Priority 3: Other Files (Need Investigation)
- `pages/DocumentsDashboard.jsx`
- `components/AddFieldModal.jsx`
- `components/FieldEditor.jsx`
- `components/Layout.jsx`
- `components/DocumentDetailModal.jsx`
- `components/modals/ProcessingModal.jsx`
- `hooks/useMCP.js`
- `pages/FolderView.jsx`
- `pages/SchemaEditor.jsx`

---

## 🔧 Additional Integration Fixes Needed

### 1. Token Expiry Handler

**Issue**: JWT tokens expire after 24 hours. Current implementation doesn't handle this gracefully.

**Solution**: Add 401 response interceptor to redirect to login:

```javascript
// In client.js
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### 2. PDF File Serving

**Issue**: Direct `<a href>` links to PDF files won't have auth headers.

**Current**: `<a href="/api/files/serve/123">`
**Breaks**: Browser GET request has no Authorization header

**Solution**: Use blob download with auth:

```javascript
async function downloadFile(fileId) {
  const response = await apiClient.get(`/api/files/serve/${fileId}`, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(response.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'document.pdf';
  a.click();
}
```

### 3. Background Polling

**Issue**: Status polling in BulkUpload happens in the background.
If token expires mid-poll, polling fails silently.

**Solution**: Add error handling to polling:

```javascript
const pollStatus = async (docId) => {
  try {
    const response = await fetchWithAuth(`/api/documents/${docId}`);
    if (!response.ok && response.status === 401) {
      // Token expired
      window.location.href = '/login';
      return;
    }
    // ... process status
  } catch (error) {
    console.error('Polling failed:', error);
    // Handle error gracefully
  }
};
```

---

## 🧪 Testing Checklist

After fixes, test these flows:

### Core Workflows
- [ ] Upload documents (BulkUpload)
- [ ] Create new template
- [ ] Confirm template match
- [ ] Natural language search (ChatSearch)
- [ ] Inline audit verification
- [ ] Batch audit
- [ ] Document detail view
- [ ] Settings update

### Auth Edge Cases
- [ ] Login → upload → logout → try upload again (should redirect to login)
- [ ] Login → wait 24 hours → try upload (should handle 401)
- [ ] Dev bypass → upload (should work even with mock token)

### File Operations
- [ ] Download PDF with auth
- [ ] Serve PDF in viewer with auth
- [ ] Upload multiple files with auth

---

## ⚡ Quick Fix Script

I can create a script to automatically apply these fixes. Should I:

1. **Auto-fix all fetch() calls now** (fast, needs review)
2. **Show me the changes first** (safer, slower)
3. **Fix incrementally** (fix P1 files, test, then P2, etc.)

---

## 📊 Estimated Effort

| Task | Files | Time |
|------|-------|------|
| Fix all fetch() calls | 15 files | 30-45 min |
| Add 401 handler | 1 file | 5 min |
| Fix PDF serving | 2-3 files | 15 min |
| Test all workflows | - | 30 min |
| **Total** | | **~1.5 hours** |

---

## 🎯 Recommendation

**Best approach**: Let me create an automated fix script that:
1. Replaces all `fetch()` with `fetchWithAuth()`
2. Adds the import statements
3. Updates the URL format (removes `${API_URL}` prefix)
4. Adds 401 error handler to `client.js`
5. Creates a summary report of all changes

Then you can review and test incrementally.

**Alternative**: I can fix the 3 critical files manually right now (BulkUpload, ChatSearch, Audit) so core features work, then we can decide on the rest.

---

## ❓ Questions for You

1. Should I auto-fix all fetch() calls, or would you prefer to review first?
2. Do you want me to add the 401 handler now?
3. Should I create test scripts to verify each fix?

Let me know how you'd like to proceed!
