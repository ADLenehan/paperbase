# 🚀 Quick Deploy Guide

Get Paperbase running in the cloud in **under 10 minutes**.

## Fastest Option: Railway (Recommended)

### Prerequisites
- [ ] GitHub account with paperbase repo
- [ ] [Reducto API key](https://reducto.ai/dashboard)
- [ ] [Anthropic API key](https://console.anthropic.com)
- [ ] [Elastic Cloud account](https://cloud.elastic.co) (free tier)

### Step 1: Setup Elasticsearch (2 minutes)
1. Go to https://cloud.elastic.co/registration
2. Create free deployment (AWS us-east-1 recommended)
3. Save these:
   - **Endpoint URL**: `https://xxx-xxx.es.io:9200`
   - **Username**: `elastic`
   - **Password**: (save this!)

### Step 2: Deploy to Railway (5 minutes)

#### Option A: Web UI (No CLI needed)
1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select `paperbase` repository
4. Railway auto-detects backend + frontend
5. Click "Add variables" → Set these:

**Backend Service:**
```
REDUCTO_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
ELASTICSEARCH_URL=https://xxx-xxx.es.io:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=your_password
```

**Frontend Service:**
```
VITE_API_URL=https://your-backend-XXXX.railway.app
```
(Get this URL from backend service settings after first deploy)

6. Click "Deploy"
7. Wait 3-5 minutes
8. Click backend service → "Settings" → "Generate Domain"
9. Copy that URL
10. Go to frontend service → "Variables" → Update `VITE_API_URL`
11. Frontend will redeploy automatically

#### Option B: CLI (Automated)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Run helper script
cd /home/user/paperbase
./scripts/deploy-railway.sh
```

### Step 3: Verify Deployment (1 minute)
```bash
# Check backend health
curl https://your-backend-XXXX.railway.app/health

# Expected response:
# {"status":"healthy","version":"0.1.0","service":"paperbase-api"}
```

### Step 4: Access Your App
- **Frontend**: `https://your-frontend-XXXX.railway.app`
- **Backend API**: `https://your-backend-XXXX.railway.app/docs`

---

## Alternative: Render (Free Tier)

### One-Click Deploy
1. Go to https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub `paperbase` repo
4. Render reads `render.yaml` automatically
5. Set these secret env vars:
   - `REDUCTO_API_KEY`
   - `ANTHROPIC_API_KEY`
6. Click "Apply"
7. Wait 8-10 minutes for all services to start

**Note:** Free tier spins down after 15 min inactivity (30-60s cold start)

---

## Alternative: Vercel (Frontend) + Railway (Backend)

### For Maximum Frontend Speed

1. **Deploy Backend to Railway** (see above)
2. **Deploy Frontend to Vercel:**
   ```bash
   cd frontend
   npx vercel --prod
   ```
3. **Set environment variable:**
   ```bash
   npx vercel env add VITE_API_URL production
   # Enter: https://your-backend.railway.app
   ```
4. **Redeploy:**
   ```bash
   npx vercel --prod
   ```

---

## Troubleshooting

### "Connection refused" errors
**Fix:** Backend still starting. Wait 30-60 seconds and retry.

### Frontend shows "Failed to fetch"
**Fix:** Check `VITE_API_URL` is correct and doesn't have trailing `/`

### Elasticsearch connection failed
**Fix:**
1. Verify Elastic Cloud deployment is running
2. Check username/password are correct
3. Ensure URL includes `https://` and port `:9200`

### 413 Request Entity Too Large
**Fix:** Railway/Render proxy limits file uploads. Set `MAX_UPLOAD_SIZE_MB=10` in backend env vars.

---

## Cost Breakdown

### Railway (Recommended)
- **Backend**: ~$5/month (512MB RAM, always-on)
- **Frontend**: ~$3/month (256MB RAM)
- **Database**: $0 (SQLite) or ~$5/month (PostgreSQL)
- **Elasticsearch**: Use Elastic Cloud (~$17/month for 4GB)
- **Total**: ~$25-30/month

### Render (Free Option)
- **Backend**: $0 (spins down after 15 min)
- **Frontend**: $0 (spins down after 15 min)
- **Elasticsearch**: $0 (1GB storage)
- **Total**: $0/month (with limitations)

### Vercel + Railway (Best Performance)
- **Frontend (Vercel)**: $0 (unlimited)
- **Backend (Railway)**: ~$5/month
- **Elasticsearch**: ~$17/month
- **Total**: ~$22/month

---

## Next Steps

1. ✅ Upload test document
2. ✅ Create first template
3. ✅ Test extraction workflow
4. ✅ Try natural language search
5. 📖 Read full guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

---

## Need Help?

- **Railway Issues**: https://discord.gg/railway
- **Render Issues**: https://render.com/docs
- **Vercel Issues**: https://vercel.com/support
- **Paperbase Issues**: Check [DEPLOYMENT.md](./DEPLOYMENT.md)

**Last Updated:** 2025-10-23
