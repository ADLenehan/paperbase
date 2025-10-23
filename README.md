# Paperbase 🚀

**AI-powered document extraction with bulk processing and natural language search**

Upload documents → AI matches templates → Bulk confirmation → Search with plain English

---

## ⚡ Quick Start (3 minutes)

### 1. Install Prerequisites
- Docker Desktop (or Colima)
- API Keys: [Reducto](https://reducto.ai) + [Anthropic](https://console.anthropic.com)

### 2. Setup
```bash
# Clone and configure
git clone <your-repo-url>
cd paperbase
cp .env.example .env

# Add your API keys to .env
REDUCTO_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Start services (Option 1: Docker)
docker-compose up -d

# OR (Option 2: Local dev)
# Terminal 1: Start Elasticsearch
docker run -d --name paperbase-es \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Terminal 2: Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Terminal 3: Start frontend
cd frontend
npm install
npm run dev
```

### 3. Open Application
- **Frontend**: http://localhost:3001 (or 3000/5173 depending on ports)
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 4. Fresh Start (Optimized Setup)
```bash
# Reset everything with optimized Elasticsearch mappings
./scripts/fresh_start.sh

# This gives you:
# ✓ Production-ready mappings (dynamic: strict)
# ✓ 30-40% storage reduction
# ✓ 20-30% faster bulk indexing
# ✓ Real-time health monitoring
```

**See**: [Quick Start Guide](docs/QUICK_START_OPTIMIZED_MAPPINGS.md) for details.

---

## 🎯 How It Works

### New Bulk-First Workflow

1. **Upload** → Drop 5-10 documents (no setup needed!)
2. **AI Match** → Claude automatically groups similar docs and suggests templates
3. **Confirm** → Review all extractions in a table view
4. **Search** → Ask questions in natural language

### Key Features

- ✨ **Zero Setup**: Upload and go - no manual schema creation
- 🤖 **Smart Matching**: AI recognizes invoices, contracts, receipts automatically
- 📊 **Bulk Review**: Edit all extractions in a spreadsheet-like table
- 💬 **NL Search**: "Show invoices over $1000" - just ask!
- 🎯 **Confidence Scores**: Color-coded fields (🟢 high, 🟡 medium, 🔴 low)
- 📈 **Learning**: System improves from your corrections

### Latest Optimizations (2025-10-23)

- 🚀 **Production-Ready Elasticsearch**: Strict schema control prevents mapping explosion
- 💾 **30-40% Storage Reduction**: Optimized field mappings
- ⚡ **20-30% Faster Indexing**: Bulk operation tuning
- 📊 **Real-Time Monitoring**: Health checks via `/api/search/index-stats`
- 🛡️ **Field Protection**: Prevents indexing failures on edge cases

---

## 📁 Project Structure

```
paperbase/
├── backend/                 # FastAPI + Python 3.11+
│   ├── app/
│   │   ├── api/            # REST endpoints
│   │   │   ├── bulk_upload.py      # NEW: Bulk upload & template matching
│   │   │   ├── search.py           # NEW: Natural language search
│   │   │   └── ...
│   │   ├── services/       # Business logic
│   │   │   ├── claude_service.py   # Template matching + NL queries
│   │   │   ├── reducto_service.py  # Document parsing
│   │   │   └── elastic_service.py  # Search & storage
│   │   ├── models/         # SQLAlchemy models
│   │   └── core/           # Config & DB
│   ├── requirements.txt
│   └── paperbase.db        # SQLite (metadata)
│
├── frontend/               # React 18 + TailwindCSS
│   ├── src/
│   │   ├── pages/
│   │   │   ├── BulkUpload.jsx         # NEW: Main entry point
│   │   │   ├── BulkConfirmation.jsx   # NEW: Table review
│   │   │   ├── ChatSearch.jsx         # NEW: NL search interface
│   │   │   └── ...
│   │   └── components/
│   └── package.json
│
├── test_documents/         # Sample PDFs for testing
├── docker-compose.yml
├── .env.example
│
└── 📚 Documentation/
    ├── CLAUDE.md                    # Project architecture & context
    ├── QUICK_START.md               # Detailed usage guide
    ├── NEW_ARCHITECTURE.md          # Implementation details
    ├── VERIFICATION_CHECKLIST.md    # Testing guide
    └── PROJECT_PLAN.md              # Development roadmap
```

---

## 🔧 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI, Python 3.11+ | REST API & orchestration |
| **Frontend** | React 18, TailwindCSS, Vite | User interface |
| **Document Parsing** | Reducto API | PDF/image → structured data |
| **Search** | Elasticsearch 8.x | Storage & full-text search |
| **AI** | Claude Sonnet 4.5 | Template matching & NL queries |
| **Database** | SQLite | Metadata (docs, schemas, verifications) |
| **Deployment** | Docker Compose | Containerized services |

---

## 📖 Documentation Guide

| File | Purpose | When to Read |
|------|---------|--------------|
| **[QUICK_START.md](QUICK_START.md)** | User guide with workflows & API examples | First time using the app |
| **[docs/QUICK_START_OPTIMIZED_MAPPINGS.md](docs/QUICK_START_OPTIMIZED_MAPPINGS.md)** | **NEW** Fresh start with optimized ES | Setting up or resetting |
| **[CLAUDE.md](CLAUDE.md)** | Architecture, design decisions, dev setup | Before coding |
| **[NEW_ARCHITECTURE.md](NEW_ARCHITECTURE.md)** | Implementation details, file-by-file guide | When modifying features |
| **[docs/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md](docs/ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)** | **NEW** ES best practices & optimizations | Performance tuning |
| **[docs/ELASTICSEARCH_MIGRATION_GUIDE.md](docs/ELASTICSEARCH_MIGRATION_GUIDE.md)** | **NEW** Production migration guide | Upgrading production |
| **[VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md)** | Testing checklist & scenarios | Before deploying |
| **[PROJECT_PLAN.md](PROJECT_PLAN.md)** | Roadmap, TODOs, future features | Planning next work |

---

## 🎮 Usage Examples

### Example 1: Process Invoices
```bash
1. Go to http://localhost:3001
2. Upload 10 invoice PDFs
3. AI says: "These look like invoices (95% confidence)"
4. Click "Use This Template"
5. Review table - fix 2 low-confidence amounts
6. Click "Confirm All"
7. Search: "Show invoices over $500"
```

### Example 2: New Document Type
```bash
1. Upload 5 employment contracts
2. AI says: "No template match - create new?"
3. Enter name: "Employment Contracts"
4. AI generates schema with 12 fields
5. Review & confirm extractions
6. Search: "Contracts expiring this year"
```

---

## 🔌 Key API Endpoints

### Bulk Upload (Primary Flow)
```bash
# Upload and analyze documents
POST /api/bulk/upload-and-analyze

# Confirm template match
POST /api/bulk/confirm-template

# Create new template
POST /api/bulk/create-new-template

# Bulk verification
POST /api/bulk/verify
```

### Search
```bash
# Natural language search
POST /api/search/nl
{
  "query": "Show me all invoices over $1000 from last month"
}
```

### Templates
```bash
# List all templates
GET /api/templates/

# Get template details
GET /api/templates/{id}
```

See full API at: http://localhost:8000/docs

---

## 💰 Cost Optimization

**Strategy**: Minimize LLM calls, maximize Reducto + Elasticsearch

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Template matching | ~$0.01-0.05 | Once per upload batch |
| Schema generation | ~$0.10-0.50 | Once per new template |
| NL search query | ~$0.01 | Per search (cached) |
| Document extraction | $0.02-0.03 | Per document (Reducto) |
| Structured search | FREE | Unlimited (Elasticsearch) |

**Target**: <$3 per batch, ~$20-30 per 1000 docs/month

---

## 🧪 Development

### Run Tests
```bash
# Backend
cd backend
pytest -v --cov=app

# Frontend (when added)
cd frontend
npm test
```

### Code Quality
```bash
# Python linting
cd backend
ruff check app/

# Type checking
mypy app/

# Frontend linting
cd frontend
npm run lint
```

### Database
```bash
# Reset database
rm backend/paperbase.db

# Check tables
sqlite3 backend/paperbase.db ".tables"
```

---

## 🐛 Troubleshooting

### Services won't start
```bash
# Check Docker memory (needs 8GB+)
docker system info | grep Memory

# Restart everything
docker-compose down -v
docker-compose up --build
```

### Elasticsearch fails (exit 137)
- Increase Docker memory allocation
- Or run ES separately with memory limits:
  ```bash
  docker run -d --name paperbase-es \
    -p 9200:9200 \
    -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
    docker.elastic.co/elasticsearch/elasticsearch:8.11.0
  ```

### Frontend can't reach backend
- Check `.env` has `VITE_API_URL=http://localhost:8000`
- Verify backend is running: `curl http://localhost:8000/health`
- Check CORS settings in `backend/app/main.py`

### Template matching not working
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check backend logs: `docker-compose logs -f backend`
- Test API directly: http://localhost:8000/docs

---

## 🚀 Next Steps

1. ✅ Upload your first batch (5-10 documents)
2. ✅ Try template matching
3. ✅ Review in table view
4. ✅ Search with natural language
5. 📊 Check analytics dashboard
6. 🔁 Process more documents

**Ready to go! Open http://localhost:3001 and upload documents** 🎉

---

## 📞 Support

- **Issues**: Check [VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md)
- **Architecture**: See [CLAUDE.md](CLAUDE.md)
- **API Docs**: http://localhost:8000/docs (when running)
- **Logs**: `docker-compose logs -f backend`

## 📄 License

[Your License Here]

---

**Built with Claude Code** • [Documentation](CLAUDE.md) • [Roadmap](PROJECT_PLAN.md)
