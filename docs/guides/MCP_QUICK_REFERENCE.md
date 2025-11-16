# Paperbase MCP - Quick Reference Card

## 🚀 Setup (First Time)

```bash
./setup-mcp.sh
```

Then restart Claude Desktop. **Done!**

---

## 📋 Common Commands

```bash
./setup-mcp.sh          # Run setup wizard
./setup-mcp.sh health   # Check if everything works
./setup-mcp.sh test     # Test server startup
./setup-mcp.sh install  # Install dependencies
./setup-mcp.sh help     # Show help
```

Or use Python directly:

```bash
cd backend
python3 -m mcp_server setup    # Setup wizard
python3 -m mcp_server health   # Health check
python3 -m mcp_server          # Start server
python3 -m mcp_server --help   # Help
```

---

## 💬 Try These Queries in Claude Desktop

**Templates & Documents:**
```
List all document templates in Paperbase
Show me the Invoice template details
Compare Invoice and Receipt templates
Find all documents uploaded today
```

**Search:**
```
Search for invoices over $1000
Find contracts expiring this month
Show me all documents with low confidence extractions
```

**Analytics:**
```
What are the extraction statistics?
Show me the audit queue
How many documents need review?
What fields have the lowest confidence scores?
```

**Specific Documents:**
```
Get details for document ID 123
Show me all fields for invoice.pdf
What's the status of my recent uploads?
```

---

## 🩺 Troubleshooting

### Quick Health Check
```bash
./setup-mcp.sh health
```

### Common Issues

| Problem | Solution |
|---------|----------|
| Dependencies missing | `./setup-mcp.sh install` |
| Tools don't appear | Restart Claude Desktop (Cmd+Q) |
| Database error | `docker-compose up -d` |
| Elasticsearch down | `curl http://localhost:9200` |
| Config issue | `./setup-mcp.sh` (re-run) |

### Check Logs
```bash
cat ~/Library/Logs/Claude/mcp-server-paperbase.log
```

---

## ⚙️ Configuration

Config file location (auto-configured):
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Backup location (created automatically):
```
~/Library/Application Support/Claude/claude_desktop_config.json.backup
```

---

## 🛠️ Available MCP Tools

| Tool | What It Does |
|------|--------------|
| `search_documents` | Natural language search |
| `get_document_details` | Full document info |
| `get_document_by_filename` | Find by filename |
| `list_templates` | Show all templates |
| `get_template_details` | Template details + stats |
| `compare_templates` | Compare two templates |
| `get_extraction_stats` | Processing metrics |
| `get_audit_queue` | HITL review queue |
| `get_low_confidence_fields` | Fields needing review |
| `get_audit_stats` | Audit summary |
| `get_system_health` | System health check |

---

## 📁 Project Structure

```
paperbase/
├── setup-mcp.sh                    # Main setup script ⭐
├── MCP_SETUP_SIMPLE.md            # Simple guide ⭐
├── MCP_QUICK_REFERENCE.md         # This file ⭐
├── backend/
│   ├── mcp_server/
│   │   ├── __main__.py            # CLI entry point
│   │   ├── setup.py               # Setup wizard ⭐
│   │   ├── health_check.py        # Diagnostics ⭐
│   │   ├── server.py              # MCP server
│   │   ├── config.py              # Configuration
│   │   ├── tools/                 # 11 MCP tools
│   │   ├── resources/             # 6 MCP resources
│   │   └── prompts/               # 3 MCP prompts
│   └── paperbase.db               # Database
└── docs/
    ├── MCP_QUICK_START.md         # Original quick start
    └── MCP_SERVER_GUIDE.md        # Full API reference
```

⭐ = New/improved files

---

## 🎯 Quick Start Checklist

- [ ] Run `./setup-mcp.sh`
- [ ] Wait for "Setup Complete!" message
- [ ] Restart Claude Desktop (Cmd+Q, then relaunch)
- [ ] Start a new conversation
- [ ] Try: "List all document templates in Paperbase"
- [ ] See tools working? ✅ You're done!

---

## 🔗 Links

- **Simple Setup**: [MCP_SETUP_SIMPLE.md](MCP_SETUP_SIMPLE.md)
- **Before/After**: [MCP_IMPROVEMENTS_SUMMARY.md](MCP_IMPROVEMENTS_SUMMARY.md)
- **Quick Start**: [docs/MCP_QUICK_START.md](docs/MCP_QUICK_START.md)
- **Full API Guide**: [docs/MCP_SERVER_GUIDE.md](docs/MCP_SERVER_GUIDE.md)
- **Project Docs**: [CLAUDE.md](CLAUDE.md)

---

## ⏱️ Quick Stats

| Metric | Time |
|--------|------|
| Setup | < 1 min |
| Health check | < 5 sec |
| First query | Instant |

---

## 💡 Pro Tips

1. **Use health check first**: `./setup-mcp.sh health`
2. **Check logs if stuck**: `~/Library/Logs/Claude/mcp-server-paperbase.log`
3. **Restart cleanly**: Completely quit Claude Desktop (Cmd+Q)
4. **Test locally**: `./setup-mcp.sh test` to verify server loads
5. **Re-run setup**: Safe to run multiple times (creates backups)

---

**Last Updated**: 2025-01-19
**Version**: 1.0.0 (Simplified Setup)
**Tested On**: macOS (Sequoia 15.5)
