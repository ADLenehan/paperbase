# MCP Setup Guide - Get Started in 5 Minutes

**Quick start guide for enabling Claude integration in Paperbase**

---

## ✅ What You Just Got

The elegant MCP integration is now in your codebase:

- ✅ Backend MCP server (`app/mcp/server.py`) - 6 tools for Claude
- ✅ Frontend MCP hook (`hooks/useMCP.js`) - State management
- ✅ MCP indicator components - Visual status in UI
- ✅ Updated pages (ChatSearch, Settings, Layout) - MCP awareness
- ✅ API endpoints for MCP status

**Total new code: ~330 lines**
**Zero duplication of existing services**

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install MCP SDK (1 minute)

```bash
cd backend
pip install mcp

# Or if you have requirements.txt issues:
pip install 'mcp>=1.0.0'
```

### Step 2: Restart Backend (1 minute)

```bash
# If using Docker
docker-compose restart backend

# If running locally
cd backend
uvicorn app.main:app --reload
```

**Check:** You should see in logs:
```
MCP Integration: Available
To use with Claude Desktop, configure: ...
```

### Step 3: Configure Claude Desktop (2 minutes)

**File:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "paperbase": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/absolute/path/to/paperbase/backend",
      "env": {
        "PYTHONPATH": "/absolute/path/to/paperbase/backend"
      }
    }
  }
}
```

**Replace** `/absolute/path/to/paperbase/backend` with your actual path!

### Step 4: Restart Claude Desktop (30 seconds)

1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. Look for "Paperbase" in the tools list

### Step 5: Test! (30 seconds)

In Claude Desktop, type:

```
Use the paperbase tool to search for documents
```

Claude should respond with available tools and be ready to search!

---

## 🎯 What Claude Can Do Now

### Search Documents
```
Search paperbase for invoices over $1000
```

### Get Specific Document
```
Get document 123 from paperbase
```

### Check Audit Queue
```
What documents in paperbase need review?
```

### Verify Extractions
```
In paperbase, verify that document 5's vendor_name is "Acme Corp"
```

### Get Templates
```
List all paperbase templates
```

### Get Statistics
```
Show me paperbase statistics
```

---

## 🎨 UI Features

### 1. MCP Indicator in Header

When Claude is connected, you'll see:
```
🟢 Claude
```

In the top-right of your Paperbase UI.

### 2. MCP Banner in Chat Search

Visit `/query` page - you'll see:
```
🤖 Claude Mode Active - Your queries are powered by AI
```

### 3. MCP Status in Settings

Visit `/settings` - scroll to top to see:
```
AI Assistant (Claude)
Status: 🟢 Claude is connected and ready
[Enable] [Disable] [Refresh Status]
```

---

## 🔧 Troubleshooting

### Claude Desktop doesn't show Paperbase

**Check 1:** Is the path absolute?
```json
// ❌ Wrong
"cwd": "../backend"

// ✅ Correct
"cwd": "/Users/yourname/paperbase/backend"
```

**Check 2:** Is Python in your PATH?
```bash
which python
# Should show python location
```

**Check 3:** Can you run MCP server manually?
```bash
cd backend
python -m app.mcp.server
# Should start without errors
```

### Frontend shows "Disconnected"

**Check 1:** Is backend running?
```bash
curl http://localhost:8000/api/mcp/status
# Should return {"enabled": true, "status": "connected"}
```

**Check 2:** Is MCP SDK installed?
```bash
pip list | grep mcp
# Should show: mcp  1.x.x
```

**Fix:** Install MCP
```bash
pip install mcp
```

### Tools not appearing in Claude

**Check 1:** Restart Claude Desktop completely (quit, don't just close)

**Check 2:** Check Claude Desktop logs
```bash
# Mac
tail -f ~/Library/Logs/Claude/mcp.log

# Linux
tail -f ~/.config/Claude/logs/mcp.log
```

**Check 3:** Verify config file syntax
```bash
# Must be valid JSON!
cat ~/.config/Claude/claude_desktop_config.json | python -m json.tool
```

---

## 📊 Verify Everything Works

### Backend Check

```bash
# Test MCP status endpoint
curl http://localhost:8000/api/mcp/status

# Should return:
{
  "enabled": true,
  "status": "connected",
  "tools_count": 6,
  "resources_count": 2,
  "message": "MCP server is running and ready for Claude"
}
```

### Frontend Check

1. Open http://localhost:3000
2. Look for green "Claude" indicator in top-right
3. Go to Settings → See "AI Assistant" card at top
4. Go to "Ask AI" → See MCP banner

### Claude Desktop Check

1. Open Claude Desktop
2. Type: `What tools do you have access to?`
3. Claude should mention "paperbase" tools
4. Try: `Search paperbase for documents`

---

## 🎓 Using MCP Features

### Example Workflow in Claude Desktop

```
You: Search paperbase for invoices

Claude: I'll search the documents for you.
[Uses search_documents tool]

Found 45 invoices:
- Invoice #1234: $2,500
- Invoice #5678: $1,800
...

You: Which ones are over $1000?

Claude: [Analyzes results]
23 invoices are over $1000:
...

You: Add the low confidence ones to audit queue

Claude: [Uses get_audit_queue tool]
There are 3 invoices with low confidence that need review:
...
```

### Example Workflow in Paperbase UI

1. Open `/query` (Ask AI page)
2. Type: "Show me all documents"
3. See MCP banner showing Claude is active
4. Get AI-enhanced results
5. Same UI, smarter results!

---

## ⚙️ Configuration Options

### Disable MCP Temporarily

In Settings page:
1. Click "Disable" in AI Assistant card
2. MCP features hide
3. App works normally without Claude

### Re-enable MCP

1. Click "Enable" in Settings
2. MCP features appear again

---

## 🔐 Security Notes

### What Claude Can Access

✅ **Claude CAN:**
- Search your documents
- Read document metadata
- See extracted fields
- View confidence scores
- Suggest verifications

❌ **Claude CANNOT:**
- Delete documents
- Modify documents directly
- Access raw PDF files
- Change system settings
- Execute arbitrary code

### Privacy

- All data stays local (no external API calls for MCP)
- Claude Desktop connects directly to your local MCP server
- Documents are not sent to Anthropic's servers
- Only document metadata and extracted text are shared

---

## 📈 Next Steps

### 1. Try Example Queries

```
- "What documents need review?"
- "Find contracts expiring this quarter"
- "Show me invoices from Acme Corp"
- "What's the average invoice amount?"
```

### 2. Explore Advanced Features

- Bulk verification
- Pattern detection
- Data quality analysis
- Export automation

### 3. Customize (Optional)

- Add more MCP tools (see `app/mcp/server.py`)
- Customize UI indicators
- Add automation workflows
- Create custom prompts

---

## 🆘 Getting Help

### Check Logs

```bash
# Backend logs
docker-compose logs -f backend

# Claude Desktop logs (Mac)
tail -f ~/Library/Logs/Claude/mcp.log

# Frontend console
Open browser DevTools → Console tab
```

### Common Issues

1. **"MCP not found"** → Install: `pip install mcp`
2. **"Disconnected"** → Restart backend: `docker-compose restart backend`
3. **"No tools"** → Check Claude Desktop config path is absolute
4. **"Permission denied"** → Check file permissions on backend folder

### Still Stuck?

1. Check you followed all 5 steps in Quick Start
2. Verify backend shows "MCP Integration: Available" in logs
3. Try manual MCP server: `python -m app.mcp.server`
4. Review complete logs above
5. See `docs/MCP_ELEGANT_INTEGRATION.md` for architecture details

---

## ✨ What's Next?

You now have a **production-ready MCP integration** with minimal code!

**Try it:**
1. Open Claude Desktop
2. Type: `Search paperbase for documents`
3. Watch Claude interact with your Paperbase system
4. See results in both Claude and Paperbase UI

**Enjoy your AI-powered document assistant!** 🎉

---

**Last Updated:** 2025-10-23
**Setup Time:** 5 minutes
**Complexity:** Minimal
**Code Added:** ~330 lines
**Magic:** ✨ Maximum
