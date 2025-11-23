# Railway Deployment Guide for Paperbase

## Overview

Paperbase requires **3 Railway services**:
1. **Backend** (Python/FastAPI)
2. **Frontend** (React/Vite)
3. **PostgreSQL** (database + full-text search)

## Step-by-Step Deployment

### 1. Create Backend Service

1. In Railway dashboard, click **"New Project"** → **"Deploy from GitHub repo"**
2. Select your `paperbase` repository
3. Railway will create a service - rename it to **"paperbase-backend"**
4. Configure the service:
   - **Root Directory**: `/backend`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. Add environment variables:
   ```
   ANTHROPIC_API_KEY=your-key-here
   REDUCTO_API_KEY=your-key-here
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   SECRET_KEY=your-secret-key-here
   CORS_ORIGINS=https://your-frontend-url.railway.app
   ```

### 2. Create PostgreSQL Database

1. In the same project, click **"New Service"** → **"Database"** → **"Add PostgreSQL"**
2. Railway will provision a PostgreSQL instance
3. The DATABASE_URL will be automatically available via `${{Postgres.DATABASE_URL}}`
4. Run migrations after first deploy (see Post-Deployment Setup below)

### 3. Create Frontend Service

1. In the same project, click **"New Service"** → **"GitHub Repo"**
2. Select your `paperbase` repository again
3. Rename the service to **"paperbase-frontend"**
4. Configure the service:
   - **Root Directory**: `/frontend`
   - **Build Command**: `npm run build`
   - **Start Command**: `npm run start`

5. Add environment variables:
   ```
   VITE_API_URL=https://your-backend-url.railway.app
   ```

6. After deployment, copy the frontend URL and update the backend's `CORS_ORIGINS`

### 4. Link Services Together

Railway automatically creates a private network between services in the same project:

- Frontend → Backend: Use the public backend URL (`https://paperbase-backend.railway.app`)
- Backend → PostgreSQL: Use `${{Postgres.DATABASE_URL}}` (automatically injected)

## Production Checklist

### Backend Configuration
- [ ] `DATABASE_URL` set to `${{Postgres.DATABASE_URL}}`
- [ ] `SECRET_KEY` is a strong random string (generate with `openssl rand -hex 32`)
- [ ] `ANTHROPIC_API_KEY` is set
- [ ] `REDUCTO_API_KEY` is set
- [ ] `CORS_ORIGINS` includes frontend URL

### Frontend Configuration
- [ ] `VITE_API_URL` points to backend URL
- [ ] Build completes successfully
- [ ] Static files are served correctly

### Database Setup
- [ ] Run PostgreSQL migrations: See Post-Deployment Setup below
- [ ] Initialize PostgreSQL extensions: pg_trgm, btree_gin (automatic via migrations)
- [ ] Initialize default roles: `POST /api/roles/initialize`
- [ ] Create admin user (see below)

## Post-Deployment Setup

### 1. Run Database Migrations

```bash
# In Railway backend shell (or via Railway CLI)
cd backend
python -m migrations.create_postgres_search_tables

# This will:
# - Install PostgreSQL extensions (pg_trgm, btree_gin)
# - Create search tables (document_search_index, template_signatures)
# - Set up full-text search indexes
```

### 2. Initialize Authentication System

```bash
# Call the initialization endpoint
curl -X POST https://your-backend-url.railway.app/api/roles/initialize
```

### 3. Create Admin User

Use the Railway backend shell or create a script:

```python
# backend/scripts/create_admin.py
from app.core.database import SessionLocal
from app.models.permissions import User, Role
from app.core.auth import get_password_hash

db = SessionLocal()

# Get admin role
admin_role = db.query(Role).filter(Role.name == "admin").first()

# Create admin user
admin = User(
    email="admin@paperbase.com",
    hashed_password=get_password_hash("change-this-password"),
    full_name="Admin User",
    is_active=True
)
admin.roles.append(admin_role)

db.add(admin)
db.commit()

print(f"Admin user created: {admin.email}")
```

Run in Railway shell:
```bash
cd backend && python scripts/create_admin.py
```

## PostgreSQL Configuration

Paperbase uses PostgreSQL for both metadata storage and full-text search (replacing Elasticsearch).

### PostgreSQL Extensions Required

The migration script automatically installs:
- **pg_trgm**: Trigram similarity for fuzzy matching and template similarity
- **btree_gin**: GIN indexes on scalar types for better performance

### Full-Text Search

PostgreSQL provides:
- `tsvector` columns for full-text indexing
- `ts_rank` for BM25-style relevance ranking
- GIN indexes for fast text search
- JSONB support for dynamic fields

## File Storage Considerations

**Important**: Railway's filesystem is **ephemeral** - uploaded files will be lost on redeploy!

### Solution Options:

#### Option 1: Railway Volumes (Persistent Storage)
1. In backend service settings, go to **"Volumes"**
2. Add a volume mounted at `/app/backend/uploaded_documents`
3. Ensures files persist across deployments

#### Option 2: Cloud Storage (Recommended for Scale)
Migrate to S3/GCS/Azure Blob Storage:
- Update `file_service.py` to use cloud storage SDK
- Store file URLs instead of local paths
- Better for scaling across multiple instances

## Monitoring & Debugging

### View Logs
```bash
# In Railway dashboard, click on service → "Deployments" → Select deployment → "View Logs"
```

### Common Issues

**Backend won't start:**
- Check environment variables are set correctly
- Verify Python version (3.11+ required)
- Check `requirements.txt` dependencies

**Frontend shows blank page:**
- Check `VITE_API_URL` is correct
- Verify CORS settings in backend
- Check browser console for errors

**PostgreSQL connection failed:**
- Verify PostgreSQL service is running in Railway
- Check `DATABASE_URL` is correctly injected: `${{Postgres.DATABASE_URL}}`
- Ensure services are in the same project (private network)

**Database errors:**
- Ensure migrations ran: `python -m migrations.create_postgres_search_tables`
- Check PostgreSQL extensions are installed (pg_trgm, btree_gin)
- Check `DATABASE_URL` format is correct

**Search not working:**
- Verify `document_search_index` table exists
- Check GIN indexes are created on tsvector columns
- Ensure documents are being indexed (check table for rows)

## Cost Optimization

Railway charges based on:
- CPU/RAM usage
- Data transfer
- Database storage

Tips:
1. Use the **Hobby Plan** ($5/month per service) for small deployments
2. PostgreSQL is included in Railway's database plans (~$5-10/month)
3. Monitor database storage and implement archival strategies
4. Use Railway's sleep feature for non-production environments
5. Consider connection pooling (PgBouncer) for high-traffic scenarios

## Environment Variables Reference

### Backend (.env)
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
REDUCTO_API_KEY=...
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-injected by Railway
SECRET_KEY=your-secret-key-here

# Optional
CORS_ORIGINS=https://your-frontend-url.railway.app
LOG_LEVEL=INFO
DEBUG=False
```

### Frontend (.env.production)
```bash
VITE_API_URL=https://your-backend-url.railway.app
```

## Deployment Commands

### Manual Deploy from CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Deploy backend
railway up --service paperbase-backend

# Deploy frontend
railway up --service paperbase-frontend
```

## Health Checks

After deployment, verify all services:

```bash
# Backend health
curl https://your-backend-url.railway.app/health

# Frontend (should return HTML)
curl https://your-frontend-url.railway.app

# PostgreSQL connection (from backend shell)
psql $DATABASE_URL -c "SELECT version();"

# Check search tables exist
psql $DATABASE_URL -c "SELECT COUNT(*) FROM document_search_index;"
```

## Next Steps

1. Set up custom domain (Railway supports this)
2. Configure SSL certificates (automatic with Railway)
3. Set up monitoring/alerts
4. Configure backups (especially for PostgreSQL)
5. Implement proper error tracking (e.g., Sentry)

## Support

- Railway Docs: https://docs.railway.app
- Paperbase Issues: https://github.com/yourusername/paperbase/issues
