# Railway Deployment Guide for Paperbase

## Overview

Paperbase requires **3 Railway services**:
1. **Backend** (Python/FastAPI)
2. **Frontend** (React/Vite)
3. **Elasticsearch** (search engine)

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
   DATABASE_URL=sqlite:///./paperbase.db
   ELASTICSEARCH_URL=http://elasticsearch:9200
   SECRET_KEY=your-secret-key-here
   CORS_ORIGINS=https://your-frontend-url.railway.app
   ```

### 2. Create Elasticsearch Service

1. In the same project, click **"New Service"** → **"Database"** → **"Add Elasticsearch"**
2. Railway will provision an Elasticsearch instance
3. Note the internal URL (usually `http://elasticsearch:9200`)
4. Update the backend's `ELASTICSEARCH_URL` to point to this URL

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

Railway automatically creates a private network between services in the same project. Use these internal URLs:

- Frontend → Backend: Use the public backend URL (`https://paperbase-backend.railway.app`)
- Backend → Elasticsearch: Use internal URL (`http://elasticsearch:9200`)

## Production Checklist

### Backend Configuration
- [ ] `DATABASE_URL` set (consider PostgreSQL for production instead of SQLite)
- [ ] `ELASTICSEARCH_URL` points to Railway Elasticsearch service
- [ ] `SECRET_KEY` is a strong random string (generate with `openssl rand -hex 32`)
- [ ] `ANTHROPIC_API_KEY` is set
- [ ] `REDUCTO_API_KEY` is set
- [ ] `CORS_ORIGINS` includes frontend URL

### Frontend Configuration
- [ ] `VITE_API_URL` points to backend URL
- [ ] Build completes successfully
- [ ] Static files are served correctly

### Database Setup
- [ ] Run migrations if using PostgreSQL: `alembic upgrade head`
- [ ] Initialize default roles: `POST /api/roles/initialize`
- [ ] Create admin user (see below)

## Post-Deployment Setup

### 1. Initialize Authentication System

```bash
# Call the initialization endpoint
curl -X POST https://your-backend-url.railway.app/api/roles/initialize
```

### 2. Create Admin User

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

## Switching to PostgreSQL (Recommended for Production)

SQLite is not recommended for Railway because the filesystem is ephemeral. Use PostgreSQL:

1. Add PostgreSQL database in Railway:
   - Click **"New Service"** → **"Database"** → **"Add PostgreSQL"**

2. Update backend environment variable:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```
   (Railway will auto-inject the PostgreSQL connection string)

3. Run migrations:
   ```bash
   # In Railway backend shell
   alembic upgrade head
   ```

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

**Elasticsearch connection failed:**
- Verify Elasticsearch service is running
- Check `ELASTICSEARCH_URL` is correct
- Ensure services are in the same project (private network)

**Database errors:**
- If using PostgreSQL, ensure migrations ran: `alembic upgrade head`
- Check `DATABASE_URL` format is correct

## Cost Optimization

Railway charges based on:
- CPU/RAM usage
- Data transfer
- Storage (volumes)

Tips:
1. Use the **Hobby Plan** ($5/month per service) for small deployments
2. Consider combining frontend/backend into one service (not recommended but possible)
3. Monitor Elasticsearch resource usage (it can be memory-intensive)
4. Use Railway's sleep feature for non-production environments

## Environment Variables Reference

### Backend (.env)
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
REDUCTO_API_KEY=...
DATABASE_URL=postgresql://user:pass@host:5432/paperbase
ELASTICSEARCH_URL=http://elasticsearch:9200
SECRET_KEY=your-secret-key-here

# Optional
CORS_ORIGINS=https://your-frontend-url.railway.app
LOG_LEVEL=INFO
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

# Elasticsearch (from backend shell)
curl http://elasticsearch:9200
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
