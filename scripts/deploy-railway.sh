#!/bin/bash
set -e

echo "🚂 Railway Deployment Helper for Paperbase"
echo "==========================================="
echo ""

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found!"
    echo ""
    echo "Install it with:"
    echo "  npm i -g @railway/cli"
    echo ""
    echo "Or use Railway web dashboard: https://railway.app/new"
    exit 1
fi

echo "✅ Railway CLI found"
echo ""

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "🔐 Please login to Railway:"
    railway login
fi

echo "✅ Logged in to Railway"
echo ""

# Check if project exists
if ! railway status &> /dev/null; then
    echo "📦 Creating new Railway project..."
    railway init
else
    echo "✅ Railway project already exists"
fi

echo ""
echo "📝 Setting environment variables..."
echo ""

# Prompt for required API keys
read -p "Enter REDUCTO_API_KEY: " REDUCTO_KEY
railway variables set REDUCTO_API_KEY="$REDUCTO_KEY"

read -p "Enter ANTHROPIC_API_KEY: " ANTHROPIC_KEY
railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"

read -p "Enter Elasticsearch URL (e.g., https://xxx.es.io:9200): " ES_URL
railway variables set ELASTICSEARCH_URL="$ES_URL"

read -p "Enter Elasticsearch username (default: elastic): " ES_USER
ES_USER=${ES_USER:-elastic}
railway variables set ELASTICSEARCH_USERNAME="$ES_USER"

read -sp "Enter Elasticsearch password: " ES_PASS
echo ""
railway variables set ELASTICSEARCH_PASSWORD="$ES_PASS"

echo ""
echo "✅ Environment variables set"
echo ""

# Ask about database
read -p "Use PostgreSQL? (recommended for production) [y/N]: " USE_PG

if [[ $USE_PG =~ ^[Yy]$ ]]; then
    echo "📊 Adding PostgreSQL..."
    railway add --plugin postgresql
    echo "✅ PostgreSQL added (DATABASE_URL will be set automatically)"
else
    echo "ℹ️  Using SQLite (set DATABASE_URL manually if needed)"
fi

echo ""
echo "🚀 Deploying to Railway..."
railway up

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "Next steps:"
echo "1. Check deployment status: railway status"
echo "2. View logs: railway logs"
echo "3. Get your app URL: railway domain"
echo ""
echo "📖 Full guide: /home/user/paperbase/DEPLOYMENT.md"
