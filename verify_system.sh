#!/bin/bash
# Paperbase System Verification Script
# Checks all services and components are working correctly

echo "🔍 Paperbase System Verification"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

echo "1. Checking Backend Service..."
if curl -s http://localhost:8001/health | grep -q "healthy"; then
    check_pass "Backend is healthy (port 8001)"
else
    check_fail "Backend not responding on port 8001"
fi

echo ""
echo "2. Checking Frontend Service..."
if curl -s -I http://localhost:3000 | grep -q "200"; then
    check_pass "Frontend is accessible (port 3000)"
else
    check_fail "Frontend not accessible on port 3000"
fi

echo ""
echo "3. Checking Elasticsearch..."
if curl -s http://localhost:9200 | grep -q "cluster_name"; then
    check_pass "Elasticsearch is running (port 9200)"
else
    check_fail "Elasticsearch not running on port 9200"
fi

echo ""
echo "4. Checking Database..."
if [ -f "backend/paperbase.db" ]; then
    SIZE=$(ls -lh backend/paperbase.db | awk '{print $5}')
    check_pass "Database exists (size: $SIZE)"

    # Check tables
    TABLES=$(sqlite3 backend/paperbase.db ".tables" 2>/dev/null | wc -w)
    if [ "$TABLES" -gt 5 ]; then
        check_pass "Database has $TABLES tables"
    else
        check_warn "Database may not be fully initialized (only $TABLES tables)"
    fi
else
    check_fail "Database not found at backend/paperbase.db"
fi

echo ""
echo "5. Checking Templates..."
TEMPLATE_COUNT=$(curl -s http://localhost:8001/api/templates/ 2>/dev/null | grep -o '"id"' | wc -l)
if [ "$TEMPLATE_COUNT" -ge 5 ]; then
    check_pass "Found $TEMPLATE_COUNT templates"
else
    check_warn "Only $TEMPLATE_COUNT templates found (expected 5+)"
fi

echo ""
echo "6. Checking Documents..."
DOC_COUNT=$(sqlite3 backend/paperbase.db "SELECT COUNT(*) FROM documents;" 2>/dev/null)
if [ -n "$DOC_COUNT" ] && [ "$DOC_COUNT" -gt 0 ]; then
    check_pass "Database has $DOC_COUNT documents"

    # Check completed documents
    COMPLETED=$(sqlite3 backend/paperbase.db "SELECT COUNT(*) FROM documents WHERE status='completed';" 2>/dev/null)
    if [ "$COMPLETED" -gt 0 ]; then
        check_pass "$COMPLETED documents processed successfully"
    fi
else
    check_warn "No documents in database yet"
fi

echo ""
echo "7. Checking Pipeline Optimization..."
CACHED=$(sqlite3 backend/paperbase.db "SELECT COUNT(*) FROM documents WHERE reducto_job_id IS NOT NULL;" 2>/dev/null)
if [ "$CACHED" -gt 0 ]; then
    check_pass "$CACHED documents have cached pipeline data"
else
    check_warn "No documents with pipeline cache yet"
fi

echo ""
echo "8. Checking File Organization..."
if [ -d "backend/uploads" ]; then
    FOLDERS=$(find backend/uploads -type d | wc -l)
    check_pass "Upload directory exists with $FOLDERS folders"

    # Check for template folders
    if [ -d "backend/uploads/contract" ] || [ -d "backend/uploads/invoice" ]; then
        check_pass "Template-based folders found"
    else
        check_warn "No template folders created yet"
    fi
else
    check_warn "Upload directory not found"
fi

echo ""
echo "9. Checking Environment Configuration..."
if [ -f "backend/.env" ]; then
    check_pass "Backend .env file exists"

    if grep -q "REDUCTO_API_KEY" backend/.env; then
        check_pass "Reducto API key configured"
    else
        check_fail "Reducto API key not found in .env"
    fi

    if grep -q "ANTHROPIC_API_KEY" backend/.env; then
        check_pass "Anthropic API key configured"
    else
        check_fail "Anthropic API key not found in .env"
    fi
else
    check_fail "Backend .env file not found"
fi

if [ -f "frontend/.env" ]; then
    check_pass "Frontend .env file exists"
else
    check_warn "Frontend .env file not found"
fi

echo ""
echo "10. Checking Documentation..."
DOCS=$(ls -1 *.md 2>/dev/null | wc -l)
if [ "$DOCS" -ge 10 ]; then
    check_pass "Found $DOCS documentation files"
else
    check_warn "Only $DOCS documentation files found"
fi

echo ""
echo "=================================="
echo "📊 Verification Summary"
echo "=================================="
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo -e "${RED}Failed:${NC} $FAIL"
echo ""

if [ $FAIL -eq 0 ] && [ $PASS -gt 15 ]; then
    echo -e "${GREEN}✅ System is fully operational!${NC}"
    exit 0
elif [ $FAIL -eq 0 ]; then
    echo -e "${YELLOW}⚠️  System is mostly operational but needs attention${NC}"
    exit 0
else
    echo -e "${RED}❌ System has critical issues that need fixing${NC}"
    exit 1
fi
