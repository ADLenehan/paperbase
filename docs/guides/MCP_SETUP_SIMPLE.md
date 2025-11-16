# Paperbase MCP Setup - Simplified Guide

## One-Command Setup

Run this from the project root:

```bash
./setup-mcp.sh
```

That's it! The script will:
- ✓ Check dependencies
- ✓ Auto-detect paths
- ✓ Configure Claude Desktop
- ✓ Backup existing config
- ✓ Verify setup

Then just **restart Claude Desktop** and start chatting!

---

## Step-by-Step (If Needed)

### 1. Install Dependencies

```bash
./setup-mcp.sh install
```

Or manually:
```bash
cd backend
pip install fastmcp>=2.0.0 cachetools mcp>=1.0.0
```

### 2. Run Setup

```bash
./setup-mcp.sh
```

### 3. Verify

```bash
./setup-mcp.sh health
```

### 4. Restart Claude Desktop

Completely quit (Cmd+Q) and relaunch Claude Desktop.

---

## Quick Commands

```bash
./setup-mcp.sh          # Run setup
./setup-mcp.sh health   # Health check
./setup-mcp.sh test     # Test server
./setup-mcp.sh install  # Install dependencies
./setup-mcp.sh help     # Show help
```

---

## Test It Works

In Claude Desktop, try:

```
List all document templates in Paperbase
```

```
Show me the audit queue
```

```
Search for invoices over $1000
```

---

## Troubleshooting

### "Dependencies missing"
```bash
./setup-mcp.sh install
```

### "Database not found"
Make sure Paperbase is set up:
```bash
docker-compose up -d
```

### "Elasticsearch not connected"
```bash
curl http://localhost:9200/_cluster/health
```

### Health check
```bash
./setup-mcp.sh health
```

### Check logs
```bash
cat ~/Library/Logs/Claude/mcp-server-paperbase.log
```

---

## Manual Setup (Advanced)

If the automated setup doesn't work, you can manually edit:

```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add:

```json
{
  "mcpServers": {
    "paperbase": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/FULL/PATH/TO/paperbase/backend",
      "env": {
        "DATABASE_URL": "sqlite:////FULL/PATH/TO/paperbase/backend/paperbase.db",
        "ELASTICSEARCH_URL": "http://localhost:9200"
      }
    }
  }
}
```

**Important**: Use absolute paths!

---

## What You Get

Once set up, Claude can:

- Search your documents with natural language
- List and compare templates
- Show audit queues
- Get extraction statistics
- Find documents by criteria
- Analyze patterns in your data

### Available Tools

| Tool | Description |
|------|-------------|
| `search_documents` | Natural language search |
| `get_document_details` | Full document info |
| `list_templates` | All templates |
| `get_audit_queue` | HITL review queue |
| `get_extraction_stats` | Processing metrics |
| And 6 more... |

---

## Example Queries

```
Find all invoices from last month with amounts over $5000
```

```
What fields in the Invoice template have low confidence?
```

```
Compare the Invoice and Receipt templates
```

```
Show me extraction statistics for the last 7 days
```

```
What documents are in the audit queue?
```

---

## Configuration Options

The setup script auto-detects paths, but you can customize by setting environment variables:

```bash
export ELASTICSEARCH_URL="http://localhost:9200"
export FRONTEND_URL="http://localhost:3000"
export MCP_LOG_LEVEL="DEBUG"  # For troubleshooting

./setup-mcp.sh
```

---

## Uninstall

To remove the MCP server from Claude Desktop:

1. Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Remove the `"paperbase"` entry from `mcpServers`
3. Restart Claude Desktop

Or use `jq`:

```bash
jq 'del(.mcpServers.paperbase)' ~/Library/Application\ Support/Claude/claude_desktop_config.json > temp.json && mv temp.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

---

## Getting Help

Run the health check to diagnose issues:

```bash
./setup-mcp.sh health
```

Check the detailed guides:
- [MCP_QUICK_START.md](docs/MCP_QUICK_START.md) - Quick start guide
- [MCP_SERVER_GUIDE.md](docs/MCP_SERVER_GUIDE.md) - Full API reference
- [CLAUDE.md](CLAUDE.md) - Project documentation

---

**Status**: Ready to use!
**Setup Time**: < 2 minutes
**Requirements**: Python 3.11+, Claude Desktop
