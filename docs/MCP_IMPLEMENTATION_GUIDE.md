# Paperbase MCP Implementation Guide

**Practical guide to implementing Model Context Protocol in Paperbase**

---

## 🎯 Quick Start

### What We're Building

Transform Paperbase so users can say:
```
"Claude, find all invoices from Acme Corp over $1000"
```

Instead of:
1. Open Paperbase UI
2. Navigate to search
3. Type vendor name
4. Set amount filter
5. Click search
6. Review results

---

## 📦 Phase 1: Core MCP Server (Week 1)

### Step 1.1: Install MCP SDK

```bash
# Backend requirements
cd backend
pip install mcp anthropic-mcp-server

# Add to requirements.txt
echo "mcp>=1.0.0" >> requirements.txt
echo "anthropic-mcp-server>=1.0.0" >> requirements.txt
```

### Step 1.2: Create MCP Server

**File:** `backend/app/mcp/server.py`

```python
"""
Paperbase MCP Server

Exposes document search, extraction, and management as MCP tools.
"""

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import logging

from app.services.elastic_service import ElasticsearchService
from app.services.claude_service import ClaudeService
from app.services.extraction_service import ExtractionService
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Initialize server
app = Server("paperbase")

# Service instances (reuse existing services)
elastic_service = ElasticsearchService()
claude_service = ClaudeService()
extraction_service = ExtractionService()


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List all available MCP tools.
    Called by Claude when it first connects.
    """
    return [
        Tool(
            name="search_documents",
            description="""
            Search documents using natural language or filters.

            Examples:
            - "invoices over $1000"
            - "contracts from Acme Corp"
            - "documents uploaded this week"

            Returns: List of matching documents with metadata.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query or keywords"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Optional filters (vendor, amount_min, amount_max, date_range)",
                        "properties": {
                            "vendor": {"type": "string"},
                            "amount_min": {"type": "number"},
                            "amount_max": {"type": "number"},
                            "date_from": {"type": "string", "format": "date"},
                            "date_to": {"type": "string", "format": "date"},
                            "template": {"type": "string"}
                        }
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        ),

        Tool(
            name="get_document",
            description="""
            Retrieve a specific document by ID or filename.

            Returns: Full document with all extracted fields, metadata, and confidence scores.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer"},
                    "filename": {"type": "string"}
                },
                "oneOf": [
                    {"required": ["document_id"]},
                    {"required": ["filename"]}
                ]
            }
        ),

        Tool(
            name="verify_extraction",
            description="""
            Verify or correct an extracted field value (Human-in-the-Loop).

            Use this when you notice an incorrect extraction or want to confirm a value.

            Returns: Updated verification record.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer"},
                    "field_name": {"type": "string"},
                    "verified_value": {"type": "string"},
                    "confidence": {
                        "type": "number",
                        "description": "Your confidence in this correction (0.0-1.0)",
                        "default": 1.0
                    },
                    "notes": {"type": "string"}
                },
                "required": ["document_id", "field_name", "verified_value"]
            }
        ),

        Tool(
            name="get_audit_queue",
            description="""
            Get documents/fields that need human review.

            Returns items with low confidence scores or flagged anomalies.

            Returns: List of items needing verification with context.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50},
                    "min_confidence": {"type": "number", "default": 0.6},
                    "template": {"type": "string"}
                }
            }
        ),

        Tool(
            name="export_data",
            description="""
            Export search results or document data to CSV/JSON.

            Returns: Download URL or data payload.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "format": {"type": "string", "enum": ["csv", "json", "excel"]},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific fields to export (default: all)"
                    }
                },
                "required": ["query", "format"]
            }
        ),

        Tool(
            name="analyze_documents",
            description="""
            Analyze patterns across multiple documents.

            Examples:
            - Find duplicate invoices
            - Detect anomalies (amount mismatches, missing fields)
            - Identify data quality issues
            - Generate summary statistics

            Returns: Analysis report with insights and recommendations.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "integer"}
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["duplicates", "anomalies", "quality", "summary"]
                    }
                },
                "required": ["analysis_type"]
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute an MCP tool.
    Called when Claude invokes a tool.
    """
    logger.info(f"MCP tool called: {name} with args: {arguments}")

    try:
        if name == "search_documents":
            return await search_documents(arguments)

        elif name == "get_document":
            return await get_document(arguments)

        elif name == "verify_extraction":
            return await verify_extraction(arguments)

        elif name == "get_audit_queue":
            return await get_audit_queue(arguments)

        elif name == "export_data":
            return await export_data(arguments)

        elif name == "analyze_documents":
            return await analyze_documents(arguments)

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


# Tool Implementations

async def search_documents(args: dict) -> list[TextContent]:
    """Search documents using Elasticsearch"""
    query = args.get("query", "")
    filters = args.get("filters", {})
    limit = args.get("limit", 20)

    # Use existing search service
    results = await elastic_service.search(
        query=query,
        filters=filters,
        page=1,
        size=limit
    )

    # Format results for Claude
    documents = results.get("documents", [])
    total = results.get("total", 0)

    if total == 0:
        return [TextContent(
            type="text",
            text=f"No documents found matching '{query}'"
        )]

    # Build response
    response = f"Found {total} documents (showing {len(documents)}):\n\n"

    for doc in documents:
        data = doc["data"]
        response += f"📄 {data.get('filename', 'Unknown')}\n"
        response += f"   ID: {data.get('document_id')}\n"

        # Show key fields
        if "invoice_total" in data:
            response += f"   Amount: ${data['invoice_total']}\n"
        if "vendor_name" in data:
            response += f"   Vendor: {data['vendor_name']}\n"
        if "invoice_date" in data:
            response += f"   Date: {data['invoice_date']}\n"

        response += "\n"

    return [TextContent(type="text", text=response)]


async def get_document(args: dict) -> list[TextContent]:
    """Get a specific document"""
    doc_id = args.get("document_id")

    # Use existing service
    doc = await elastic_service.get_document(doc_id)

    if not doc:
        return [TextContent(
            type="text",
            text=f"Document {doc_id} not found"
        )]

    # Format document data
    response = f"📄 Document: {doc.get('filename')}\n\n"
    response += "Extracted Fields:\n"

    for field, value in doc.items():
        # Skip metadata fields
        if field.startswith("_") or field in ["document_id", "filename"]:
            continue

        # Show confidence if available
        confidence = doc.get("confidence_scores", {}).get(field)
        conf_str = f" (confidence: {confidence:.2f})" if confidence else ""

        response += f"  • {field}: {value}{conf_str}\n"

    return [TextContent(type="text", text=response)]


async def verify_extraction(args: dict) -> list[TextContent]:
    """Submit a verification (HITL)"""
    doc_id = args["document_id"]
    field_name = args["field_name"]
    verified_value = args["verified_value"]
    confidence = args.get("confidence", 1.0)
    notes = args.get("notes", "")

    db = SessionLocal()

    try:
        # Use existing verification service
        from app.services.verification_service import VerificationService
        verification_service = VerificationService(db)

        result = await verification_service.verify_field(
            document_id=doc_id,
            field_name=field_name,
            verified_value=verified_value,
            confidence=confidence,
            notes=notes,
            verified_by="claude_mcp"
        )

        return [TextContent(
            type="text",
            text=f"✓ Verified {field_name} = '{verified_value}' for document {doc_id}"
        )]

    finally:
        db.close()


async def get_audit_queue(args: dict) -> list[TextContent]:
    """Get items needing review"""
    limit = args.get("limit", 50)
    min_confidence = args.get("min_confidence", 0.6)

    db = SessionLocal()

    try:
        from app.services.audit_service import AuditService
        audit_service = AuditService(db)

        queue = await audit_service.get_queue(
            max_confidence=min_confidence,
            limit=limit
        )

        if not queue:
            return [TextContent(
                type="text",
                text="✓ Audit queue is empty - all documents look good!"
            )]

        response = f"Found {len(queue)} items needing review:\n\n"

        for item in queue[:10]:  # Show first 10
            response += f"📋 Document {item['document_id']}: {item['filename']}\n"
            response += f"   Field: {item['field_name']}\n"
            response += f"   Value: {item['extracted_value']}\n"
            response += f"   Confidence: {item['confidence']:.2f}\n"
            response += f"   Issue: {item['reason']}\n\n"

        if len(queue) > 10:
            response += f"... and {len(queue) - 10} more items\n"

        return [TextContent(type="text", text=response)]

    finally:
        db.close()


async def export_data(args: dict) -> list[TextContent]:
    """Export search results"""
    # Implementation would generate CSV/JSON and return download link
    return [TextContent(
        type="text",
        text="Export feature coming soon!"
    )]


async def analyze_documents(args: dict) -> list[TextContent]:
    """Analyze documents for patterns/anomalies"""
    # Implementation would use Claude to analyze patterns
    return [TextContent(
        type="text",
        text="Analysis feature coming soon!"
    )]


# Resources

@app.list_resources()
async def handle_list_resources() -> list[EmbeddedResource]:
    """
    List available resources.
    Resources are read-only data sources.
    """
    return [
        EmbeddedResource(
            uri="paperbase://templates",
            name="Available Templates",
            description="List of all document templates/schemas",
            mimeType="application/json"
        ),
        EmbeddedResource(
            uri="paperbase://stats",
            name="System Statistics",
            description="Document counts, processing stats, etc.",
            mimeType="application/json"
        )
    ]


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a resource by URI"""
    if uri == "paperbase://templates":
        # Return template list
        db = SessionLocal()
        try:
            from app.models.template import SchemaTemplate
            templates = db.query(SchemaTemplate).all()

            template_list = [
                {
                    "id": t.id,
                    "name": t.name,
                    "category": t.category,
                    "field_count": len(t.fields)
                }
                for t in templates
            ]

            return json.dumps(template_list, indent=2)
        finally:
            db.close()

    elif uri == "paperbase://stats":
        # Return system stats
        stats = await elastic_service.get_index_stats()
        return json.dumps(stats, indent=2)

    else:
        raise ValueError(f"Unknown resource: {uri}")
```

### Step 1.3: Integrate with FastAPI

**File:** `backend/app/main.py`

```python
# Add MCP support to FastAPI

from app.mcp.server import app as mcp_server
import asyncio

# ... existing FastAPI setup ...

# Mount MCP server
@app.on_event("startup")
async def startup_mcp():
    """Start MCP server"""
    logger.info("Starting MCP server...")

    # Run MCP server in background
    asyncio.create_task(run_mcp_server())


async def run_mcp_server():
    """Run MCP server (stdio transport for Claude Desktop)"""
    async with mcp_server.run():
        await asyncio.Event().wait()


# Add HTTP endpoint for MCP status
@app.get("/mcp/status")
async def mcp_status():
    """Check MCP server status"""
    return {
        "status": "running",
        "tools_count": len(await mcp_server.list_tools()),
        "resources_count": len(await mcp_server.list_resources())
    }
```

---

## 🎨 Phase 2: UI Components (Week 2)

### Step 2.1: MCP Activity Feed Component

**File:** `frontend/src/components/MCPActivityFeed.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

export function MCPActivityFeed() {
  const [activities, setActivities] = useState([]);
  const { messages } = useWebSocket('ws://localhost:8000/mcp/stream');

  useEffect(() => {
    if (messages.length > 0) {
      const latestMessage = messages[messages.length - 1];
      setActivities(prev => [latestMessage, ...prev].slice(0, 50));
    }
  }, [messages]);

  return (
    <div className="mcp-activity-feed bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4 flex items-center">
        <span className="mr-2">🤖</span>
        Claude Activity
      </h3>

      {activities.length === 0 ? (
        <p className="text-gray-500 text-sm">No recent activity</p>
      ) : (
        <div className="space-y-3">
          {activities.map((activity, idx) => (
            <ActivityItem key={idx} activity={activity} />
          ))}
        </div>
      )}
    </div>
  );
}

function ActivityItem({ activity }) {
  const getIcon = (type) => {
    const icons = {
      search: '🔍',
      verification: '✓',
      extraction: '📄',
      analysis: '📊',
      error: '❌'
    };
    return icons[type] || '•';
  };

  const getStatusColor = (status) => {
    const colors = {
      completed: 'text-green-600',
      pending: 'text-yellow-600',
      error: 'text-red-600'
    };
    return colors[status] || 'text-gray-600';
  };

  return (
    <div className="border-l-4 border-blue-500 pl-3 py-2">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <span>{getIcon(activity.type)}</span>
            <span className="font-medium text-sm">{activity.title}</span>
          </div>
          <p className="text-xs text-gray-600 mt-1">{activity.description}</p>

          {activity.result && (
            <div className="mt-2 text-xs bg-gray-50 p-2 rounded">
              {activity.result}
            </div>
          )}

          {activity.requires_approval && (
            <div className="mt-2 flex space-x-2">
              <button className="btn-xs btn-primary">Approve</button>
              <button className="btn-xs btn-secondary">Reject</button>
              <button className="btn-xs btn-outline">Details</button>
            </div>
          )}
        </div>

        <div className="text-right">
          <span className="text-xs text-gray-400">{activity.timestamp}</span>
          <div className={`text-xs mt-1 ${getStatusColor(activity.status)}`}>
            {activity.status}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### Step 2.2: Enhanced Chat Search

**File:** `frontend/src/pages/ChatSearch.jsx` (Enhanced)

```jsx
import React, { useState, useRef, useEffect } from 'react';
import { MCPActivityFeed } from '../components/MCPActivityFeed';

export function ChatSearch() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Send to MCP-enabled backend
      const response = await fetch('/api/mcp/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input })
      });

      const data = await response.json();

      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        tools_used: data.tools_used,
        results: data.results,
        actions: data.suggested_actions
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b px-6 py-4">
          <h1 className="text-2xl font-bold">Chat with Claude</h1>
          <p className="text-sm text-gray-600">
            Ask questions about your documents in natural language
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 ? (
            <WelcomeScreen />
          ) : (
            messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))
          )}

          {loading && (
            <div className="flex items-center space-x-2 text-gray-500">
              <div className="animate-spin">⏳</div>
              <span>Claude is thinking...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t px-6 py-4">
          <div className="flex space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Ask about your documents..."
              className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="btn-primary px-6"
            >
              Send
            </button>
          </div>

          <SuggestedPrompts onSelect={setInput} />
        </div>
      </div>

      {/* Activity Sidebar */}
      <div className="w-80 bg-gray-50 border-l p-4 overflow-y-auto">
        <MCPActivityFeed />
      </div>
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="text-center py-12">
      <div className="text-6xl mb-4">🤖</div>
      <h2 className="text-2xl font-bold mb-2">Hi! I'm Claude</h2>
      <p className="text-gray-600 mb-6">
        I can help you search, analyze, and verify your documents.
      </p>

      <div className="grid grid-cols-2 gap-4 max-w-2xl mx-auto">
        <ExampleQuery>
          Find all invoices over $1000
        </ExampleQuery>
        <ExampleQuery>
          What documents need review?
        </ExampleQuery>
        <ExampleQuery>
          Show me contracts expiring this quarter
        </ExampleQuery>
        <ExampleQuery>
          Export all Acme Corp documents
        </ExampleQuery>
      </div>
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl ${isUser ? 'bg-blue-500 text-white' : 'bg-gray-100'} rounded-lg px-4 py-3`}>
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* Show tools used */}
        {message.tools_used && (
          <div className="mt-2 text-xs opacity-75">
            <details>
              <summary className="cursor-pointer">Tools used</summary>
              <ul className="mt-1 space-y-1">
                {message.tools_used.map((tool, idx) => (
                  <li key={idx}>• {tool}</li>
                ))}
              </ul>
            </details>
          </div>
        )}

        {/* Show results */}
        {message.results && (
          <ResultsPreview results={message.results} />
        )}

        {/* Suggested actions */}
        {message.actions && (
          <div className="mt-3 flex flex-wrap gap-2">
            {message.actions.map((action, idx) => (
              <button key={idx} className="btn-xs btn-outline">
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultsPreview({ results }) {
  return (
    <div className="mt-3 bg-white text-gray-800 rounded p-3 text-sm">
      <h4 className="font-semibold mb-2">Found {results.total} documents</h4>
      <ul className="space-y-1">
        {results.documents.slice(0, 5).map((doc, idx) => (
          <li key={idx} className="flex justify-between">
            <span>{doc.filename}</span>
            <span className="text-gray-500">${doc.amount}</span>
          </li>
        ))}
      </ul>
      {results.total > 5 && (
        <p className="text-xs text-gray-500 mt-2">
          ... and {results.total - 5} more
        </p>
      )}
    </div>
  );
}

function SuggestedPrompts({ onSelect }) {
  const prompts = [
    "What documents need review?",
    "Find invoices from last month",
    "Show audit queue",
    "Export recent documents"
  ];

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {prompts.map((prompt, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(prompt)}
          className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-full"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}

function ExampleQuery({ children }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer">
      <p className="text-sm">{children}</p>
    </div>
  );
}
```

### Step 2.3: MCP Settings Tab

**File:** `frontend/src/pages/Settings.jsx` (Add new tab)

```jsx
// Add to existing Settings.jsx

function MCPSettingsTab() {
  const [mcpEnabled, setMCPEnabled] = useState(true);
  const [clients, setClients] = useState([]);
  const [consentSettings, setConsentSettings] = useState({
    requireApprovalForUploads: true,
    autoApproveReadOnly: false,
    requireApprovalForBulk: true
  });

  useEffect(() => {
    loadMCPSettings();
  }, []);

  const loadMCPSettings = async () => {
    const response = await fetch('/api/mcp/settings');
    const data = await response.json();
    setClients(data.clients || []);
    setConsentSettings(data.consent || {});
  };

  return (
    <div className="space-y-6">
      {/* Enable/Disable MCP */}
      <Section title="MCP Integration">
        <Toggle
          enabled={mcpEnabled}
          onChange={setMCPEnabled}
          label="Allow AI assistants to access Paperbase via MCP"
        />
        {mcpEnabled && (
          <p className="text-sm text-gray-600 mt-2">
            Claude and other AI assistants can search, extract, and verify documents.
          </p>
        )}
      </Section>

      {/* Authorized Clients */}
      <Section title="Authorized Clients">
        {clients.length === 0 ? (
          <p className="text-gray-500">No clients authorized yet</p>
        ) : (
          <div className="space-y-3">
            {clients.map(client => (
              <ClientCard key={client.id} client={client} />
            ))}
          </div>
        )}
        <button className="btn-secondary mt-3">
          + Authorize New Client
        </button>
      </Section>

      {/* Consent Settings */}
      <Section title="Consent & Permissions">
        <div className="space-y-3">
          <Checkbox
            checked={consentSettings.requireApprovalForUploads}
            onChange={(val) => setConsentSettings({...consentSettings, requireApprovalForUploads: val})}
            label="Ask before allowing document uploads"
          />
          <Checkbox
            checked={consentSettings.autoApproveReadOnly}
            onChange={(val) => setConsentSettings({...consentSettings, autoApproveReadOnly: val})}
            label="Auto-approve read-only operations (search, view)"
          />
          <Checkbox
            checked={consentSettings.requireApprovalForBulk}
            onChange={(val) => setConsentSettings({...consentSettings, requireApprovalForBulk: val})}
            label="Require approval for bulk actions"
          />
        </div>
      </Section>

      {/* Data Sharing */}
      <Section title="Data Sharing">
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
          <p className="text-sm text-yellow-800 font-medium mb-2">
            What Claude can access:
          </p>
          <ul className="text-sm text-yellow-700 space-y-1">
            <li>✓ Document text and extracted fields</li>
            <li>✓ Templates and schemas</li>
            <li>✓ Search results and analytics</li>
            <li>✗ Raw PDF files (stored locally only)</li>
            <li>✗ User credentials</li>
          </ul>
        </div>
      </Section>

      <button className="btn-primary">Save Settings</button>
    </div>
  );
}

function ClientCard({ client }) {
  return (
    <div className="border rounded-lg p-4">
      <div className="flex justify-between items-start">
        <div>
          <h4 className="font-medium">{client.name}</h4>
          <p className="text-sm text-gray-600">
            Scopes: {client.scopes.join(', ')}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Last active: {client.last_active}
          </p>
        </div>
        <div className="flex space-x-2">
          <button className="btn-xs btn-outline">Edit Scopes</button>
          <button className="btn-xs btn-danger">Revoke</button>
        </div>
      </div>
    </div>
  );
}
```

---

## 🚀 Phase 3: Testing & Deployment (Week 3)

### Step 3.1: Test MCP Server with Claude Desktop

**File:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "paperbase": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/paperbase/backend",
      "env": {
        "PYTHONPATH": "/path/to/paperbase/backend"
      }
    }
  }
}
```

### Step 3.2: Manual Testing

```bash
# In Claude Desktop, try:
> Use the paperbase tool to search for invoices over $1000

# Expected: Claude calls search_documents tool, returns results

> Get document 123

# Expected: Claude calls get_document tool, shows extracted fields

> What needs review?

# Expected: Claude calls get_audit_queue, shows low-confidence items
```

### Step 3.3: Automated Tests

**File:** `backend/tests/test_mcp_server.py`

```python
import pytest
from app.mcp.server import app as mcp_server

@pytest.mark.asyncio
async def test_list_tools():
    """Test that all tools are registered"""
    tools = await mcp_server.list_tools()

    assert len(tools) >= 6  # Expected number of tools
    tool_names = [t.name for t in tools]

    assert "search_documents" in tool_names
    assert "get_document" in tool_names
    assert "verify_extraction" in tool_names


@pytest.mark.asyncio
async def test_search_documents_tool():
    """Test search_documents tool"""
    result = await mcp_server.call_tool(
        "search_documents",
        {"query": "test invoice", "limit": 5}
    )

    assert result is not None
    assert "documents" in str(result)


@pytest.mark.asyncio
async def test_invalid_tool():
    """Test calling non-existent tool"""
    with pytest.raises(Exception):
        await mcp_server.call_tool("invalid_tool", {})
```

---

## 📊 Success Metrics

Track these to measure MCP adoption:

1. **Usage Metrics**
   - MCP queries per day
   - Most-used tools
   - Success rate (successful vs errored calls)

2. **User Experience**
   - Time saved vs manual UI
   - User satisfaction (survey)
   - Adoption rate (% of users using MCP)

3. **Quality**
   - Auto-verification accuracy
   - Approval rate for Claude suggestions
   - Error rate

---

## 🎯 Next Steps

1. **Week 1:** Implement MCP server (Phase 1)
2. **Week 2:** Build UI components (Phase 2)
3. **Week 3:** Test & deploy (Phase 3)
4. **Week 4:** Gather feedback, iterate

---

**Questions? See:**
- [MCP_UI_ARCHITECTURE.md](./MCP_UI_ARCHITECTURE.md) - Full design
- [Official MCP Docs](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/anthropics/anthropic-mcp-server-python)

---

**Last Updated:** 2025-10-23
**Status:** Ready for Implementation
