#!/bin/bash
# Fresh Start - Complete reset of Paperbase
# Clears all data and initializes with latest optimized settings

set -e

echo "🚀 Paperbase Fresh Start"
echo "======================="
echo ""
echo "This will reset:"
echo "  • SQLite database (documents, schemas, templates)"
echo "  • Elasticsearch indices (documents, template_signatures)"
echo "  • Uploaded files (optional)"
echo ""
read -p "Continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Aborted."
    exit 0
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$(dirname "$0")/.."

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Delete SQLite database
if [ -f "backend/paperbase.db" ]; then
    echo "🗑️  Deleting SQLite database..."
    rm backend/paperbase.db
    echo -e "${GREEN}✓ Database deleted${NC}"
fi

# Ask about uploaded files
read -p "Delete uploaded files? (yes/no): " -r
echo ""
if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    if [ -d "backend/uploads" ]; then
        echo "🗑️  Deleting uploaded files..."
        rm -rf backend/uploads/*
        echo -e "${GREEN}✓ Uploaded files deleted${NC}"
    fi
fi

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for Elasticsearch
echo "⏳ Waiting for Elasticsearch to be ready..."
until curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; do
    sleep 2
    echo -n "."
done
echo ""
echo -e "${GREEN}✓ Elasticsearch is ready${NC}"

# Wait for backend
echo "⏳ Waiting for backend to be ready..."
sleep 5
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
    echo -n "."
done
echo ""
echo -e "${GREEN}✓ Backend is ready${NC}"

echo ""
echo -e "${GREEN}✅ Fresh start complete!${NC}"
echo ""
echo "Your Paperbase instance is now running with:"
echo "  ✓ Optimized Elasticsearch mappings (2025 best practices)"
echo "  ✓ Clean database"
echo "  ✓ Latest schema configurations"
echo ""
echo "Access your application:"
echo "  • Frontend: http://localhost:3000"
echo "  • Backend API: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo ""
echo "Check index health:"
echo "  curl http://localhost:8000/api/search/index-stats"
echo ""
