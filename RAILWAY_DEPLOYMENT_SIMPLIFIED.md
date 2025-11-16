# Railway Deployment Guide - Paperbase (PostgreSQL)

## Quick Deploy (3 Services)

Your app needs:
1. **Backend** (Python/FastAPI)
2. **Frontend** (React/Vite)
3. **PostgreSQL Database**

---

## Step 1: Create New Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select your `paperbase` repository

---

## Step 2: Set Up PostgreSQL Database

1. In your new project, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway provisions the database automatically
3. Note: Railway will create a `DATABASE_URL` variable you can reference

---

## Step 3: Configure Backend Service

Railway created a service when you connected GitHub. Configure it:

### Service Settings:
- **Name**: `paperbase-backend`
- **Root Directory**: `backend`
- **Start Command**: (auto-detected, but verify): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Environment Variables:
Click **"Variables"** tab and add:

```bash
# Required API Keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
REDUCTO_API_KEY=your-reducto-key

# Database (reference the PostgreSQL service)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Security
SECRET_KEY=<generate with: openssl rand -hex 32>

# CORS (add frontend URL after it's deployed)
CORS_ORIGINS=https://your-frontend-url.railway.app

# Optional
LOG_LEVEL=INFO
DEBUG=false
```

### Generate SECRET_KEY:
```bash
openssl rand -hex 32
```

---

## Step 4: Configure Frontend Service

1. In the same project, click **"New"** → **"GitHub Repo"**
2. Select your `paperbase` repo again
3. Configure:
   - **Name**: `paperbase-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Start Command**: `npm run start`

### Environment Variables:
```bash
VITE_API_URL=https://your-backend-url.railway.app
```

**After backend deploys**, copy its URL and paste it here.

---

## Step 5: Enable Auto-Deploy from GitHub

**This is what you wanted!** Railway can auto-deploy on every git push.

### For Each Service (Backend & Frontend):

1. Go to service **Settings** tab
2. Scroll to **"Deployments"** section
3. Find **"Watch Paths"** - this controls what triggers rebuilds
   - Backend: Set to `backend/**`
   - Frontend: Set to `frontend/**`
4. Ensure **"Auto Deploy"** is enabled (it should be by default)

Now when you push to GitHub:
- Changes in `/backend` → Backend redeploys
- Changes in `/frontend` → Frontend redeploys
- Changes in both → Both redeploy

### Set Deploy Branch:
- Go to **Settings** → **"Source"**
- Set **Branch** to `main` (or your production branch)

---

## Step 6: Update CORS After Frontend Deploys

1. After frontend deploys, copy its Railway URL (e.g., `https://paperbase-frontend.up.railway.app`)
2. Go to backend service → **Variables**
3. Update `CORS_ORIGINS` to match the frontend URL
4. Backend will auto-redeploy

---

## Step 7: Initialize Database & Auth

### Run Migrations (if needed):
```bash
# In Railway backend shell (click "..." → "Open Shell")
alembic upgrade head
```

### Initialize Auth System:
```bash
# Call the initialization endpoint (replace URL)
curl -X POST https://your-backend-url.railway.app/api/roles/initialize
```

### Create Admin User:
Create `backend/scripts/create_admin.py`:

```python
from app.core.database import SessionLocal
from app.models.permissions import User, Role
from app.core.auth import get_password_hash

db = SessionLocal()

# Get admin role
admin_role = db.query(Role).filter(Role.name == "admin").first()

# Create admin user
admin = User(
    email="admin@yourcompany.com",
    hashed_password=get_password_hash("ChangeThisPassword123!"),
    full_name="Admin User",
    is_active=True
)
admin.roles.append(admin_role)

db.add(admin)
db.commit()
db.close()

print(f"✓ Admin user created: {admin.email}")
```

Run in Railway shell:
```bash
cd backend && python scripts/create_admin.py
```

---

## Step 8: Configure File Storage (IMPORTANT!)

⚠️ **Railway's filesystem is ephemeral** - uploaded files disappear on redeploy!

### Option 1: Railway Volumes (Persistent Storage)

1. Go to backend service → **Settings** → **"Volumes"**
2. Click **"New Volume"**
3. Set:
   - **Mount Path**: `/app/uploads`
   - **Size**: 10GB (adjust as needed)
4. Redeploy backend

### Option 2: Cloud Storage (Recommended)
Migrate to AWS S3, Google Cloud Storage, or similar for production.

---

## Environment Variables Summary

### Backend `.env` equivalent:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
REDUCTO_API_KEY=xxxxx
DATABASE_URL=${{Postgres.DATABASE_URL}}
SECRET_KEY=<32-byte-hex-string>
CORS_ORIGINS=https://your-frontend.railway.app
LOG_LEVEL=INFO
DEBUG=false
```

### Frontend `.env` equivalent:
```bash
VITE_API_URL=https://your-backend.railway.app
```

---

## Testing Your Deployment

### 1. Check Backend Health:
```bash
curl https://your-backend-url.railway.app/health
```

Should return: `{"status": "healthy"}`

### 2. Check Frontend:
Visit `https://your-frontend-url.railway.app` in browser

### 3. Check Database Connection:
Look at backend logs in Railway dashboard - should see:
```
INFO: Connected to database
```

### 4. Test Login:
Visit frontend → Try logging in with admin credentials

---

## Auto-Deploy Workflow

Now your workflow is:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# Railway automatically:
# 1. Detects push to GitHub
# 2. Determines what changed (backend/ or frontend/)
# 3. Rebuilds affected services
# 4. Deploys new version
# 5. Runs health checks
```

You can watch deployments in Railway dashboard under **"Deployments"** tab.

---

## Troubleshooting

### Backend won't start:
- Check logs: Service → "Deployments" → Latest → "View Logs"
- Verify all environment variables are set
- Check `DATABASE_URL` is referencing Postgres correctly

### Frontend shows blank page:
- Check `VITE_API_URL` is correct
- Verify CORS settings in backend
- Check browser console for errors
- Ensure backend is running first

### Database connection errors:
- Ensure backend service is linked to Postgres service
- Check `DATABASE_URL` format: `postgresql://user:pass@host:port/db`
- Run migrations: `alembic upgrade head`

### File uploads fail:
- Add Railway volume (see Step 8)
- Check `UPLOAD_DIR` environment variable
- Verify disk space

### Auto-deploy not working:
- Check **"Watch Paths"** are configured correctly
- Verify branch is set to `main` (or your deploy branch)
- Check GitHub webhook is active (Settings → Source)
- Look for errors in deployment logs

---

## Cost Optimization

Railway pricing:
- **Starter Plan**: $5/month per resource (backend, frontend, database)
- **Total**: ~$15/month for all 3 services

Tips:
- Use sleep schedules for non-production environments
- Monitor resource usage in dashboard
- Consider combining frontend/backend if needed (not recommended)

---

## Production Checklist

- [ ] PostgreSQL database provisioned
- [ ] Backend service deployed with all env vars
- [ ] Frontend service deployed with `VITE_API_URL`
- [ ] CORS configured correctly
- [ ] Railway volumes added for file storage
- [ ] Migrations run: `alembic upgrade head`
- [ ] Auth system initialized: `POST /api/roles/initialize`
- [ ] Admin user created
- [ ] Auto-deploy enabled for both services
- [ ] Watch paths configured (`backend/**` and `frontend/**`)
- [ ] Health checks passing
- [ ] Custom domain configured (optional)
- [ ] SSL certificates active (automatic with Railway)

---

## Next Steps

1. **Set up monitoring**: Railway provides basic metrics
2. **Add error tracking**: Consider Sentry integration
3. **Configure backups**: Railway auto-backs up PostgreSQL
4. **Custom domain**: Add your domain in Railway settings
5. **CI/CD**: Railway handles this automatically via GitHub!

---

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Paperbase Issues: [Your GitHub repo]/issues
