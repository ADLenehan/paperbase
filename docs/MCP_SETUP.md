# Paperbase MCP Server Setup Guide

## Overview

The Paperbase MCP (Model Context Protocol) server enables Claude Desktop and other MCP clients to interact directly with your Paperbase document extraction system. This provides intelligent search, template management, analytics, and audit capabilities through natural language.

## Features

### Tools (User Actions)
- **Document Operations**: Search, retrieve, and filter documents
- **Template Management**: List, compare, and analyze templates
- **Analytics**: Extraction stats, confidence distribution, processing metrics
- **Audit**: HITL queue management and verification tracking

### Resources (Read-Only Data)
- `paperbase://templates` - All templates
- `paperbase://templates/{id}` - Specific template
- `paperbase://stats/daily` - Daily statistics
- `paperbase://stats/audit` - Audit summary
- `paperbase://system/health` - System health status
- `paperbase://documents/{id}/fields` - Document fields

### Prompts (Workflow Templates)
- `analyze-low-confidence` - Analyze audit queue patterns
- `compare-templates` - Compare template structures
- `document-summary` - Generate document extraction summary

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs FastMCP and other required dependencies.

### 2. Configure Environment

Ensure your `.env` file has the required variables:

```bash
DATABASE_URL=sqlite:///./paperbase.db
ELASTICSEARCH_URL=http://localhost:9200
```

### 3. Test the MCP Server

Run the server directly to verify it works:

```bash
cd backend
python -m mcp_server
```

You should see log output indicating the server started successfully.

## Claude Desktop Integration

### Configuration File Location

The Claude Desktop configuration file is located at:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Configuration

Add the Paperbase MCP server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "paperbase": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server"
      ],
      "cwd": "/Users/YOUR_USERNAME/Projects/paperbase/backend",
      "env": {
        "DATABASE_URL": "sqlite:////Users/YOUR_USERNAME/Projects/paperbase/backend/paperbase.db",
        "ELASTICSEARCH_URL": "http://localhost:9200",
        "MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Important**: Replace `/Users/YOUR_USERNAME/Projects/paperbase` with your actual project path.

### Alternative: Using uvx (Recommended for Production)

If you package the MCP server as a PyPI package:

```json
{
  "mcpServers": {
    "paperbase": {
      "command": "uvx",
      "args": ["paperbase-mcp-server"],
      "env": {
        "DATABASE_URL": "sqlite:////path/to/paperbase.db",
        "ELASTICSEARCH_URL": "http://localhost:9200"
      }
    }
  }
}
```

## Verification

### 1. Restart Claude Desktop

After updating the configuration, completely quit and restart Claude Desktop.

### 2. Check for the MCP Server

In a new conversation, you should see a 🔌 icon or indicator that MCP servers are connected.

### 3. Test Basic Functionality

Try these commands in Claude Desktop:

```
Can you list all document templates in Paperbase?
```

```
Show me the audit queue for low-confidence extractions
```

```
Search for invoices uploaded in the last week
```

```
What are the system health stats?
```

## Troubleshooting

### Server Won't Start

**Check logs**: Look at Claude Desktop logs or run the server manually to see errors:

```bash
cd backend
python -m mcp_server
```

**Common issues**:
- Python not found: Use full path to Python interpreter
- Module import errors: Ensure all dependencies are installed
- Database not found: Use absolute path in DATABASE_URL

### No Tools Appear in Claude

**Verify configuration**:
1. Check that `claude_desktop_config.json` is valid JSON
2. Ensure paths are absolute, not relative
3. Restart Claude Desktop completely (quit, not just close window)

**Check server status**:
```bash
# Run server and look for "MCP server ready" message
python -m mcp_server
```

### Permission Errors

**Database access**:
```bash
chmod 644 /path/to/paperbase.db
```

**Elasticsearch connection**:
```bash
curl http://localhost:9200/_cluster/health
```

## Usage Examples

### Searching Documents

```
Search for all contracts signed in the last month with amounts over $50,000
```

The MCP server will:
1. Parse the natural language query
2. Identify filters (date range, amount threshold, document type)
3. Execute optimized Elasticsearch query
4. Return formatted results

### Template Analysis

```
Compare the Invoice and Receipt templates and tell me what fields they have in common
```

The MCP server will:
1. Fetch both templates
2. Analyze field structures
3. Identify common and unique fields
4. Present comparison

### Audit Queue Review

```
Show me the top 10 fields in the audit queue and identify patterns
```

The MCP server will:
1. Fetch audit queue sorted by confidence
2. Group by field type and document type
3. Identify trends
4. Suggest improvements

## Advanced Configuration

### Custom Cache Settings

Add to your environment:

```bash
MCP_CACHE_ENABLED=true
MCP_CACHE_MAX_SIZE=2000
MCP_CACHE_DEFAULT_TTL=600  # 10 minutes
```

### Query Optimization

```bash
MCP_ENABLE_QUERY_OPTIMIZATION=true
MCP_MAX_SEARCH_RESULTS=100
```

### Rate Limiting (Future HTTP Mode)

```bash
MCP_RATE_LIMIT_ENABLED=true
MCP_RATE_LIMIT_PER_MIN=100
```

## Development

### Testing Tools Locally

You can test individual tools without Claude Desktop:

```python
import asyncio
from mcp_server.tools.documents import search_documents

async def test():
    result = await search_documents("invoices", limit=5)
    print(result)

asyncio.run(test())
```

### Adding New Tools

1. Create tool function in `mcp_server/tools/`
2. Add to `mcp_server/tools/__init__.py`
3. Register in `mcp_server/server.py` with `@mcp.tool()` decorator
4. Restart MCP server

### Adding New Resources

1. Create resource function in `mcp_server/resources/`
2. Register in `mcp_server/server.py` with `@mcp.resource()` decorator
3. Use URI format: `paperbase://category/resource`

## Performance

### Caching Strategy

The MCP server uses multi-tier caching:

- **Templates**: 5 min TTL (infrequent changes)
- **Stats**: 1 min TTL (frequent updates)
- **Documents**: 30 sec TTL (actively changing)
- **Search results**: Not cached (always fresh)

### Query Optimization

The query optimizer analyzes natural language queries to:
- Identify intent (search, filter, aggregate)
- Extract filters (date ranges, numeric comparisons)
- Resolve field aliases (amount → total_amount)
- Choose optimal query type (exact, fuzzy, semantic)

## Security

### Local Mode (stdio)

When running via stdio (Claude Desktop), the server:
- Only accepts connections from local process
- No network exposure
- No authentication needed
- Inherits user permissions

### Future HTTP Mode

When deployed as HTTP server:
- OAuth 2.0 authentication required
- Rate limiting enforced
- HTTPS only
- API key rotation

## Support

### Logs

MCP server logs go to stderr (visible in Claude Desktop logs):

**macOS**: `~/Library/Logs/Claude/mcp-server-paperbase.log`

### Common Issues

| Issue | Solution |
|-------|----------|
| Tools not appearing | Restart Claude Desktop completely |
| Database locked | Close other connections to SQLite |
| ES connection failed | Verify Elasticsearch is running |
| Slow queries | Check cache settings and ES performance |

### Getting Help

1. Check server logs: Run `python -m mcp_server` and observe output
2. Verify configuration: Ensure paths and env vars are correct
3. Test components: Test DB and ES connections separately
4. Review documentation: See [MCP official docs](https://modelcontextprotocol.io)

## Next Steps

- Add custom tools for your specific workflows
- Create domain-specific prompts
- Deploy as HTTP server for multi-user access
- Integrate with other MCP clients (VS Code, etc.)

## References

- [FastMCP Documentation](https://gofastmcp.com)
- [Model Context Protocol Spec](https://modelcontextprotocol.io)
- [Claude Desktop MCP Guide](https://docs.anthropic.com/claude/docs/mcp)
- [Paperbase Documentation](../README.md)
