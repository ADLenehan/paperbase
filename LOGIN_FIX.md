# 🔧 LOGIN FIX - Quick Resolution

## ❌ Problem

Cannot login - email validation rejecting `default@paperbase.local` (`.local` TLD is reserved).

## ✅ Quick Fix (30 seconds)

### Step 1: Update Database
```bash
cd /Users/adlenehan/Projects/paperbase

# Set valid email and password
sqlite3 backend/paperbase.db "UPDATE users SET email = 'admin@paperbase.dev', hashed_password = '\$2b\$12\$Wkg6Of8iG8h654sLNoG1K.rHKxnbnTB0Ljqnv2Zvy4P1sA0LjhO4G' WHERE id = 1;"

# Verify
sqlite3 backend/paperbase.db "SELECT id, email FROM users WHERE id = 1;"
# Should show: 1|admin@paperbase.dev
```

### Step 2: Update Frontend Config
```bash
# Edit frontend/src/utils/auth.js
# Change line 155:
#   FROM: email: 'default@paperbase.local',
#   TO:   email: 'admin@paperbase.dev',
```

### Step 3: Login
```
Email:    admin@paperbase.dev
Password: admin
```

---

## 🚀 Alternative: Use Dev Bypass

**Easiest option**: Just click **"Skip Login (Admin Access)"** on the login page!

This bypasses authentication entirely - perfect for testing.

---

## 📋 Full Manual Fix

If the quick fix doesn't work, run this script:

```bash
cd /Users/adlenehan/Projects/paperbase/backend

python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('paperbase.db')
cursor = conn.cursor()

# Update user
cursor.execute("""
UPDATE users
SET email = 'admin@paperbase.dev',
    hashed_password = '$2b$12$Wkg6Of8iG8h654sLNoG1K.rHKxnbnTB0Ljqnv2Zvy4P1sA0LjhO4G'
WHERE id = 1
""")

conn.commit()

# Verify
cursor.execute("SELECT id, email FROM users WHERE id = 1")
print("Updated user:", cursor.fetchone())

conn.close()
EOF
```

---

## ✅ Test Login

```bash
# Test with curl:
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@paperbase.dev","password":"admin"}'

# Should return:
# {"access_token":"eyJ0eXAiOiJKV1QiLC...","token_type":"bearer","user":{...}}
```

---

## 🎯 What Changed

| Before | After |
|--------|-------|
| `default@paperbase.local` | `admin@paperbase.dev` |
| Invalid TLD (`.local`) | Valid TLD (`.dev`) |
| Email validation fails | Email validation passes |

---

## 💡 Why `.local` Failed

Pydantic email validation (used by FastAPI) rejects special-use/reserved TLDs like:
- `.local` - mDNS/Bonjour
- `.localhost` - Loopback
- `.invalid` - Reserved for invalid domains
- `.test` - Testing

**Valid alternatives**: `.dev`, `.com`, `.example`, `.test` (if validation allows)

---

You should now be able to login with `admin@paperbase.dev` / `admin`!
