# Paperbase Quick Start Guide

## What's New? 🎉

Paperbase now has a **simpler, faster workflow**:
1. **Upload documents** (no setup needed)
2. **AI matches templates** automatically
3. **Bulk confirm** extractions in a table
4. **Search with natural language** - just ask questions!

## Getting Started in 3 Minutes

### 1. Start the Application

```bash
# Start all services
docker-compose up

# Or run separately:
# Backend
cd backend && uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev
```

### 2. Upload Documents

1. Open [http://localhost:5173](http://localhost:5173)
2. Drop 5-10 documents (PDFs) on the upload zone
3. Wait ~30 seconds for analysis
4. System groups similar documents and suggests templates

### 3. Confirm Templates

**If High Confidence Match (≥70%):**
- Click "Use This Template"
- Processing starts automatically

**If No Match or Low Confidence:**
- Click "Create New Template"
- Enter template name (e.g., "Purchase Orders")
- System generates schema with AI

### 4. Review Extractions

1. Navigate to `/confirm` (or click the link)
2. See table: Documents (rows) × Fields (columns)
3. Edit any incorrect values inline
4. Check color coding:
   - 🟢 Green = High confidence (≥80%)
   - 🟡 Yellow = Medium (60-80%)
   - 🔴 Red = Low (<60%)
5. Click "Confirm All & Continue"

### 5. Search Your Documents

1. Go to `/search`
2. Ask natural language questions:
   - "Show me all invoices over $1000"
   - "What contracts were signed last month?"
   - "Find purchase orders from Acme Corp"
3. Get AI-generated answers with matching documents

## Example Workflows

### Example 1: Invoices
```
1. Upload 10 invoice PDFs
2. System: "These look like invoices (95% confidence)"
3. Click "Use This Template"
4. Review table - all 10 docs × invoice fields
5. Fix 2 low-confidence amounts
6. Click "Confirm All"
7. Search: "Show invoices over $500"
```

### Example 2: New Document Type
```
1. Upload 5 employment contracts (new type)
2. System: "No template match - create new?"
3. Enter "Employment Contracts"
4. AI generates schema with 12 fields
5. Tweak field names if needed
6. Confirm schema
7. Review extractions
8. Search: "Show contracts expiring this year"
```

## Key Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Bulk Upload** | `/` | Main entry point - upload & template matching |
| **Bulk Confirm** | `/confirm` | Review all extractions in table |
| **Documents** | `/documents` | Status dashboard - see all uploads |
| **Search** | `/search` | Natural language search interface |
| **Analytics** | `/analytics` | Stats and insights |

## API Quick Reference

### Primary Endpoints
```bash
# Upload and analyze
POST /api/bulk/upload-and-analyze
curl -F "files=@invoice1.pdf" -F "files=@invoice2.pdf" http://localhost:8000/api/bulk/upload-and-analyze

# Confirm template
POST /api/bulk/confirm-template
curl -X POST http://localhost:8000/api/bulk/confirm-template \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [1,2,3], "template_id": 1}'

# Create new template
POST /api/bulk/create-new-template
curl -X POST http://localhost:8000/api/bulk/create-new-template \
  -H "Content-Type: application/json" \
  -d '{"document_ids": [4,5], "template_name": "Service Contracts"}'

# Bulk verify
POST /api/bulk/verify
curl -X POST http://localhost:8000/api/bulk/verify \
  -H "Content-Type: application/json" \
  -d '{"verifications": [...]}'

# Natural language search
POST /api/search/nl
curl -X POST http://localhost:8000/api/search/nl \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me all invoices over $1000"}'
```

## Environment Setup

### Required Environment Variables
```bash
# .env file
REDUCTO_API_KEY=your_reducto_key_here
ANTHROPIC_API_KEY=your_claude_key_here
ELASTICSEARCH_URL=http://localhost:9200
UPLOAD_DIR=./uploads
```

### Get API Keys
- **Reducto**: https://reducto.ai → Sign up → API Keys
- **Claude**: https://console.anthropic.com → Get API Key

## Troubleshooting

### Documents stuck in "analyzing"
- Check Reducto API key is valid
- Check backend logs: `docker-compose logs -f backend`
- Verify Reducto service is up: https://status.reducto.ai

### Template matching not working
- Ensure Claude API key is set
- Check you have built-in templates: `GET /api/templates`
- Backend logs will show Claude errors

### Search returns no results
- Verify documents are "completed" status
- Check Elasticsearch is running: `curl http://localhost:9200`
- Documents must be processed before searchable

### Table view not loading
- Check schema_id in URL
- Verify documents have extractions
- Check browser console for errors

## Tips for Best Results

### 1. Upload in Batches
- Upload 5-10 similar documents at once
- Better template matching with more samples
- Easier to review in table view

### 2. Trust High Confidence
- Green cells (≥80%) are usually correct
- Focus review on yellow/red cells
- Bulk confirm saves time

### 3. Use Natural Language Search
- Be specific: "invoices over $1000 from last month"
- Ask follow-ups: "show me the highest one"
- System remembers conversation context

### 4. Create Good Templates
- Descriptive names: "Purchase Orders" not "POs"
- Let AI generate initial fields
- Refine based on first batch

## What's Different from v1?

| Old Flow | New Flow |
|----------|----------|
| Templates → Samples → Schema | Upload → Auto-match |
| One-by-one verification | Bulk table review |
| Keyword search with filters | Natural language chat |
| Manual template selection | AI suggestions |

## Next Steps

1. ✅ Upload your first batch of documents
2. ✅ Review and confirm template match
3. ✅ Verify extractions in table
4. ✅ Try natural language search
5. 📊 Check analytics for insights
6. 🔁 Upload more documents (same or new types)

## Support

- **Documentation**: See `CLAUDE.md` for architecture details
- **API Docs**: http://localhost:8000/docs (when running)
- **Architecture**: See `NEW_ARCHITECTURE.md` for implementation
- **Issues**: Check backend logs and Elasticsearch status

---

**Ready to process thousands of documents? Just upload and let AI do the work! 🚀**
