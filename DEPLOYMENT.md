# Deployment Guide

This guide covers deploying Paperbase to various cloud hosting platforms for regular testing and production use.

## Platform Recommendations

### 🚀 Railway (Recommended - Easiest)
**Best for:** Quick deployment, automatic HTTPS, managed databases
- ✅ Free tier: $5/month credit
- ✅ Automatic deployments from GitHub
- ✅ Built-in environment variable management
- ✅ Supports monorepo with multiple services
- ⚠️ Elasticsearch requires alternative (use Elastic Cloud free tier)

### 🎨 Render
**Best for:** Full control, Docker support, free tier
- ✅ Free tier available (with limitations)
- ✅ Infrastructure as code (render.yaml)
- ✅ Native Docker support for Elasticsearch
- ✅ Managed PostgreSQL option
- ⚠️ Slower cold starts on free tier

### ⚡ Vercel (Frontend Only)
**Best for:** Blazing fast frontend, free tier
- ✅ Unlimited free hosting for frontend
- ✅ Automatic preview deployments
- ❌ Requires separate backend hosting (pair with Railway/Render)

---

## Option 1: Railway Deployment (Fastest)

### Prerequisites
- GitHub account
- Railway account (free): https://railway.app
- Elastic Cloud account (free): https://cloud.elastic.co

### Step 1: Setup Elasticsearch on Elastic Cloud
1. Create free account at https://cloud.elastic.co
2. Create deployment (choose AWS region closest to Railway)
3. Copy the Cloud ID and credentials
4. Get the Elasticsearch endpoint URL

### Step 2: Push to GitHub
```bash
cd /home/user/paperbase
git add .
git commit -m "Add deployment configs"
git push origin main  # or your branch
```

### Step 3: Deploy on Railway
1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select your `paperbase` repository
4. Railway will detect the services automatically

### Step 4: Configure Environment Variables
In Railway dashboard, set these for **backend service**:
```
REDUCTO_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
ELASTICSEARCH_URL=https://your-elastic-cloud-url:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=your_password
DATABASE_URL=postgresql://user:pass@host:5432/paperbase  # Railway provides this
```

For **frontend service**:
```
VITE_API_URL=https://your-backend.railway.app
```

### Step 5: Deploy
- Railway deploys automatically
- Check logs for any errors
- Your app will be live at: `https://your-app.railway.app`

**Total Time:** ~10 minutes

---

## Option 2: Render Deployment

### Prerequisites
- GitHub account
- Render account (free): https://render.com

### Step 1: Push to GitHub
```bash
cd /home/user/paperbase
git add .
git commit -m "Add Render config"
git push origin main
```

### Step 2: Deploy via Blueprint
1. Go to https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Render reads `render.yaml` and creates all services

### Step 3: Set Secret Environment Variables
In Render dashboard, set for backend:
```
REDUCTO_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

### Step 4: Wait for Build
- Backend: ~5-8 minutes
- Frontend: ~3-5 minutes
- Elasticsearch: ~2 minutes

**Free Tier Notes:**
- Services spin down after 15 min inactivity
- First request after sleep: ~30-60 second cold start
- 750 hours/month free (covers 1 service 24/7)

**Total Time:** ~15 minutes

---

## Option 3: Vercel (Frontend) + Railway (Backend)

### Best for: Maximum frontend performance with free backend

### Step 1: Deploy Backend to Railway
Follow Railway steps above, but only deploy backend + Elasticsearch

### Step 2: Deploy Frontend to Vercel
```bash
cd frontend
npx vercel
```

When prompted:
- Set up and deploy: `Y`
- Scope: (your account)
- Link to existing project: `N`
- Project name: `paperbase`
- Directory: `./`
- Override settings: `N`

### Step 3: Set Environment Variable
```bash
npx vercel env add VITE_API_URL production
# Enter: https://your-backend.railway.app
```

### Step 4: Deploy
```bash
npx vercel --prod
```

**Total Time:** ~5 minutes

---

## Post-Deployment Checklist

### 1. Health Check
```bash
curl https://your-backend-url.com/health
```
Should return: `{"status": "healthy"}`

### 2. Test Document Upload
- Go to your frontend URL
- Upload a sample PDF
- Check processing status

### 3. Verify Elasticsearch Connection
```bash
curl https://your-backend-url.com/api/search
```

### 4. Check Logs
- Railway: Click service → "Logs" tab
- Render: Click service → "Logs"
- Vercel: Dashboard → Project → "Logs"

### 5. Setup Custom Domain (Optional)
- Railway: Settings → Domains → Add custom domain
- Render: Settings → Custom Domain
- Vercel: Settings → Domains

---

## Environment Variables Reference

### Backend (Required)
| Variable | Example | Where to Get |
|----------|---------|--------------|
| `REDUCTO_API_KEY` | `rdc_...` | https://reducto.ai/dashboard |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com |
| `ELASTICSEARCH_URL` | `https://...es.io:9200` | Elastic Cloud dashboard |
| `DATABASE_URL` | Auto-set by Railway/Render | - |

### Frontend (Required)
| Variable | Example |
|----------|---------|
| `VITE_API_URL` | `https://api.yourapp.com` |

### Optional (Backend)
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | `50` | Max file size |
| `CONFIDENCE_THRESHOLD_LOW` | `0.6` | HITL trigger threshold |
| `ENABLE_CLAUDE_FALLBACK` | `true` | Use Claude for matching |

---

## Cost Estimates (Monthly)

### Free Tier (Testing)
- **Railway Free:** $5 credit/month
  - Backend: ~$5/month (512MB RAM, always on)
  - Need Elastic Cloud free tier (14 days, then ~$17/month)
- **Render Free:** $0/month
  - All services free (with sleep)
  - Elasticsearch 1GB storage free
- **Vercel Free:** Unlimited frontend hosting

**Best Free Option:** Render (all-in-one, true free tier)

### Light Usage (~1000 docs/month)
- Railway: ~$10/month (backend + DB)
- Elastic Cloud: ~$17/month (basic tier)
- Vercel: Free (frontend)
- **Total:** ~$27/month

### Production (~10k docs/month)
- Railway: ~$20/month (backend + DB)
- Elastic Cloud: ~$95/month (4GB RAM)
- Vercel: Free (frontend)
- **Total:** ~$115/month

---

## Troubleshooting

### "Module not found" errors
**Fix:** Check build command includes `pip install -r requirements.txt`

### Frontend can't connect to backend
**Fix:** Verify `VITE_API_URL` points to backend URL (without trailing slash)

### Elasticsearch connection failed
**Fix:**
1. Check `ELASTICSEARCH_URL` format: `https://host:9200`
2. For Elastic Cloud, include username/password in env vars
3. Check Elasticsearch service logs

### 502 Bad Gateway
**Fix:** Backend still starting up (wait 30-60 seconds on first deploy)

### Upload fails
**Fix:**
1. Check `REDUCTO_API_KEY` is set correctly
2. Verify Railway/Render has enough RAM (min 512MB)
3. Check backend logs for errors

---

## Monitoring & Logs

### Railway
- Real-time logs: Dashboard → Service → Logs
- Metrics: Dashboard → Service → Metrics
- Alerts: Settings → Notifications

### Render
- Logs: Dashboard → Service → Logs (last 7 days on free tier)
- Metrics: Dashboard → Service → Metrics
- Alerts: Settings → Notifications (paid plans)

### Vercel
- Logs: Dashboard → Deployments → Function Logs
- Analytics: Dashboard → Analytics (free tier limited)

---

## Updating Your Deployment

### Railway (Auto-deploy from Git)
```bash
git add .
git commit -m "Update feature"
git push origin main  # Auto-deploys
```

### Render (Auto-deploy from Git)
```bash
git push origin main  # Auto-deploys
```

### Manual Deploy
- Railway: Dashboard → Service → "Deploy"
- Render: Dashboard → Service → "Manual Deploy" → "Deploy latest commit"

---

## Rollback

### Railway
1. Dashboard → Deployment → "Deployments"
2. Find previous working deployment
3. Click "..." → "Rollback"

### Render
1. Dashboard → Service → "Events"
2. Find previous deploy
3. Click "Rollback to this version"

---

## Migration to Production

When ready for production (>10k docs/month), consider:

1. **Upgrade Database:** SQLite → PostgreSQL (both platforms offer managed PG)
2. **Add Redis:** For caching (Railway/Render add-on)
3. **Scale Elasticsearch:** Increase RAM/storage on Elastic Cloud
4. **Add Monitoring:** Sentry, LogRocket, or Datadog
5. **Setup CDN:** Cloudflare (free) for static assets
6. **Add Auth:** Implement user authentication
7. **Backup Strategy:** Regular DB snapshots

---

## Getting Help

- Railway: https://discord.gg/railway
- Render: https://render.com/docs
- Vercel: https://vercel.com/support

**Recommended for Testing:** Start with **Railway** (easiest) or **Render** (true free tier)

**Last Updated:** 2025-10-23
