# Making Paperbase the Best MCP App: UI & Architecture Guide

**Goal:** Transform Paperbase into a world-class Model Context Protocol (MCP) application that lets Claude and other AI assistants seamlessly search, extract, and analyze documents.

---

## 🎯 Executive Summary

### What is an MCP App?

An MCP app exposes its functionality to AI assistants (like Claude) through standardized **tools** and **resources**, allowing natural language interaction with your data.

### The Vision: "Claude as Document Assistant"

**Instead of:**
```
User → UI → Click buttons → Search documents → Read results
```

**MCP-enabled:**
```
User → "Claude, find all invoices over $1000 from Acme Corp"
      → Claude uses Paperbase MCP tools
      → Returns answer with source documents
      → User can approve/edit extractions via UI
```

### Key Benefits

1. ✅ **Natural Language Interface** - Ask questions, don't build queries
2. ✅ **AI-Powered Insights** - Claude analyzes patterns across documents
3. ✅ **Workflow Automation** - Claude can bulk-process, tag, verify
4. ✅ **Context Awareness** - Claude remembers previous queries, learns preferences
5. ✅ **Hybrid UX** - Use UI or chat, whichever fits the task

---

## 📋 MCP Architecture for Paperbase

### MCP Server Components

Paperbase will implement an MCP server with these capabilities:

#### **1. Tools** (Actions Claude can perform)

| Tool Name | Purpose | Example Usage |
|-----------|---------|---------------|
| `search_documents` | Full-text + NL search | "Find contracts expiring in Q1" |
| `get_document` | Retrieve specific document | "Show me invoice #12345" |
| `extract_fields` | Run extraction on new doc | "Extract data from this PDF" |
| `verify_extraction` | Submit HITL verification | "Mark vendor_name as 'Acme Corp'" |
| `create_template` | Generate new schema | "Create template for tax forms" |
| `bulk_upload` | Upload multiple files | "Process these 50 invoices" |
| `get_audit_queue` | Get low-confidence items | "What needs review?" |
| `export_data` | Export search results | "Export to CSV" |
| `get_analytics` | Retrieve stats/metrics | "How many docs this month?" |

#### **2. Resources** (Data Claude can read)

| Resource URI | Data Provided | Example |
|--------------|---------------|---------|
| `paperbase://documents/{id}` | Full document + metadata | Single document view |
| `paperbase://templates/{id}` | Template schema definition | Template details |
| `paperbase://search?q={query}` | Search results | Query results |
| `paperbase://audit/queue` | HITL review queue | Items needing review |
| `paperbase://folders/{path}` | Folder contents | Template-organized docs |
| `paperbase://analytics/stats` | System statistics | Usage metrics |

#### **3. Prompts** (Pre-built workflows)

| Prompt Name | Workflow | Use Case |
|-------------|----------|----------|
| `analyze_document` | Extract → Verify → Summarize | Quick document analysis |
| `bulk_process` | Upload → Match → Confirm → Report | Batch processing |
| `audit_review` | Queue → Show → Verify loop | HITL workflow |
| `find_patterns` | Search → Analyze → Report | Data discovery |

---

## 🎨 UI Changes for Best MCP Experience

### Core Principle: **Hybrid UX**

The UI should be **equally powerful** whether used:
- Directly by humans (current state)
- Via Claude through MCP (new capability)
- In collaboration (Claude suggests, human approves via UI)

---

## 1️⃣ New Component: MCP Activity Feed

**Location:** Sidebar or Dashboard widget

**Purpose:** Show real-time MCP tool usage and results

```jsx
// components/MCPActivityFeed.jsx
<MCPActivityFeed>
  <Activity type="search" timestamp="2s ago">
    Claude searched: "invoices > $1000"
    → Found 23 documents
  </Activity>

  <Activity type="verification" timestamp="5s ago" status="pending">
    Claude suggested: vendor_name = "Acme Corp"
    → [Approve] [Reject] [Edit]
  </Activity>

  <Activity type="extraction" timestamp="10s ago" status="completed">
    Processed: invoice_2024.pdf
    → 12 fields extracted (confidence: 0.89)
  </Activity>
</MCPActivityFeed>
```

**Features:**
- Real-time updates via WebSocket
- Expandable details for each activity
- Quick actions (approve/reject/edit)
- Filter by type, status, date
- Export activity log

---

## 2️⃣ Enhanced Component: Chat Search (Primary MCP Interface)

**Current:** `ChatSearch.jsx` - Natural language search

**Enhanced:** Full Claude integration with MCP awareness

```jsx
// pages/ChatSearch.jsx (Enhanced)
<ChatInterface>
  <ConversationThread>
    <Message role="user">
      Find all invoices from Acme Corp over $1000
    </Message>

    <Message role="assistant" mcp_tools_used={["search_documents"]}>
      I found 23 invoices matching your criteria.

      <ResultsPreview>
        - Invoice #4521: $2,340.50 (2024-09-15)
        - Invoice #4623: $1,890.00 (2024-10-02)
        ...
      </ResultsPreview>

      <ActionButtons>
        [View All Results] [Export CSV] [Create Report]
      </ActionButtons>

      <MCPToolUsage>
        Used: search_documents(query="invoices", filters={vendor: "Acme", amount_min: 1000})
      </MCPToolUsage>
    </Message>

    <Message role="user">
      Are any of these missing purchase orders?
    </Message>

    <Message role="assistant" mcp_tools_used={["get_document"]}>
      Yes, 3 invoices are missing PO numbers:
      - Invoice #4623: No PO (needs review)
      - Invoice #4801: No PO (needs review)
      ...

      <QuickAction>
        [Add to Audit Queue] [Bulk Update POs]
      </QuickAction>
    </Message>
  </ConversationThread>

  <InputArea>
    <SuggestedPrompts>
      "What documents need review?"
      "Upload these receipts"
      "Create a monthly report"
    </SuggestedPrompts>
  </InputArea>
</ChatInterface>
```

**New Features:**
- **MCP Tool Visibility**: Show which tools Claude used
- **Inline Actions**: Approve/reject suggestions directly in chat
- **Rich Previews**: Embedded document viewers, charts, tables
- **Follow-up Suggestions**: Claude suggests next steps
- **Context Persistence**: Remember conversation history
- **Multi-modal**: Text, documents, images, exports

---

## 3️⃣ New Page: MCP Console (Developer/Admin)

**Location:** `/mcp-console`

**Purpose:** Monitor, test, and configure MCP integration

```jsx
// pages/MCPConsole.jsx
<MCPConsole>
  <Section title="Connection Status">
    <ConnectionInfo>
      ✓ MCP Server running on localhost:3001
      ✓ 2 clients connected (Claude Desktop, Claude Code)
      ✓ 47 requests today
    </ConnectionInfo>
  </Section>

  <Section title="Available Tools">
    <ToolList>
      <Tool name="search_documents">
        Status: ✓ Active
        Calls today: 23
        Avg response time: 145ms
        [Test Tool] [View Logs]
      </Tool>
      ...
    </ToolList>
  </Section>

  <Section title="Security & Authorization">
    <AuthSettings>
      <Toggle enabled={true}>Require consent for document access</Toggle>
      <Toggle enabled={false}>Auto-approve read-only operations</Toggle>
      <Scopes>
        ✓ documents:read
        ✓ documents:search
        ✓ templates:read
        ✗ documents:delete (disabled)
      </Scopes>
    </AuthSettings>
  </Section>

  <Section title="Activity Log">
    <LogViewer realtime={true} />
  </Section>
</MCPConsole>
```

---

## 4️⃣ Enhanced Component: Document Viewer

**Current:** Basic PDF viewer

**Enhanced:** MCP-aware with AI annotations

```jsx
// components/PDFViewer.jsx (Enhanced)
<DocumentViewer>
  <PDFCanvas document={doc} />

  <AIAnnotations>
    <Annotation field="invoice_total" bbox={[100, 200, 150, 220]} confidence={0.92}>
      $2,340.50
      <Actions>
        [Verify] [Edit] [Ask Claude]
      </Actions>
    </Annotation>

    <ClaudeInsight>
      💡 Claude noticed: This invoice total doesn't match the sum of line items ($2,315.50).
      <Actions>
        [Investigate] [Mark as Correct] [Add Note]
      </Actions>
    </ClaudeInsight>
  </AIAnnotations>

  <ChatPanel>
    <Message role="user">Why is there a discrepancy?</Message>
    <Message role="assistant">
      The difference ($25) appears to be a shipping charge listed separately...
    </Message>
  </ChatPanel>
</DocumentViewer>
```

**New Features:**
- **Bounding Box Highlights**: Show what Claude "sees"
- **Inline Chat**: Ask questions about the document
- **AI Insights**: Proactive anomaly detection
- **Comparison Mode**: Compare similar documents
- **History**: Show previous Claude interactions with this doc

---

## 5️⃣ New Component: Approval Queue (HITL + MCP)

**Location:** Dashboard or `/approvals`

**Purpose:** Review and approve Claude's suggestions

```jsx
// components/ApprovalQueue.jsx
<ApprovalQueue>
  <PendingApproval type="verification" source="mcp">
    <Context>
      Claude extracted from invoice_2024.pdf
    </Context>

    <Suggestion>
      vendor_name: "Acme Corporation" → "Acme Corp"
      Reason: Normalized to match existing vendor records
      Confidence: 0.95
    </Suggestion>

    <Actions>
      [Approve] [Reject] [Edit] [Ask Claude Why]
    </Actions>
  </PendingApproval>

  <PendingApproval type="bulk_action" source="mcp">
    <Context>
      Claude wants to mark 15 invoices as "verified"
    </Context>

    <Preview>
      Invoice #4521, #4623, #4801... (12 more)
      All have confidence > 0.90
    </Preview>

    <Actions>
      [Approve All] [Review Individually] [Reject]
    </Actions>
  </PendingApproval>
</ApprovalQueue>
```

---

## 6️⃣ Settings: MCP Configuration

**Location:** `/settings` → New "MCP" tab

```jsx
// pages/Settings.jsx - New Tab
<SettingsPage>
  <Tab name="MCP Integration">
    <Section title="Enable MCP">
      <Toggle enabled={true}>
        Allow AI assistants to access Paperbase via MCP
      </Toggle>
    </Section>

    <Section title="Authorized Clients">
      <ClientList>
        <Client name="Claude Desktop" authorized={true}>
          Scopes: documents:read, search, extract
          Last active: 2 minutes ago
          [Revoke] [Edit Scopes]
        </Client>

        <Client name="Claude Code" authorized={true}>
          Scopes: full_access
          Last active: 1 hour ago
          [Revoke] [Edit Scopes]
        </Client>
      </ClientList>

      <Button>+ Authorize New Client</Button>
    </Section>

    <Section title="Consent Settings">
      <Checkbox checked={true}>
        Ask before allowing document uploads
      </Checkbox>
      <Checkbox checked={false}>
        Auto-approve read-only operations
      </Checkbox>
      <Checkbox checked={true}>
        Require approval for bulk verifications
      </Checkbox>
    </Section>

    <Section title="Data Sharing">
      <Warning>
        MCP allows Claude to access your documents. Review what's shared:
      </Warning>

      <SharingSettings>
        ✓ Document text and extracted fields
        ✓ Templates and schemas
        ✓ Search results and analytics
        ✗ Raw PDFs (stored locally only)
        ✗ User credentials
      </SharingSettings>
    </Section>
  </Tab>
</SettingsPage>
```

---

## 7️⃣ Dashboard: MCP Stats Widget

**Location:** Main Dashboard

```jsx
// components/MCPStatsWidget.jsx
<Widget title="Claude Activity">
  <Stats>
    <Stat label="Queries Today" value="47" trend="+12%" />
    <Stat label="Auto-verified" value="23" trend="+5%" />
    <Stat label="Pending Approval" value="3" alert={true} />
  </Stats>

  <RecentActivity>
    <Activity>2m ago: Searched invoices</Activity>
    <Activity>5m ago: Extracted 5 documents</Activity>
    <Activity>12m ago: Created report</Activity>
  </RecentActivity>

  <QuickActions>
    [Open Chat] [Review Approvals] [View Logs]
  </QuickActions>
</Widget>
```

---

## 8️⃣ Notifications: MCP Events

**Location:** Global notification system

```jsx
// components/NotificationCenter.jsx
<Notifications>
  <Notification type="mcp_approval_needed" priority="high">
    Claude needs approval to verify 15 invoices
    [Review Now] [Dismiss]
  </Notification>

  <Notification type="mcp_insight" priority="medium">
    Claude found anomalies in 3 documents
    [View Details] [Dismiss]
  </Notification>

  <Notification type="mcp_success" priority="low">
    Bulk upload completed: 50 documents processed
    [View Results] [Dismiss]
  </Notification>
</Notifications>
```

---

## 🏗️ Technical Architecture Changes

### Backend: MCP Server Implementation

**New File:** `backend/app/mcp/server.py`

```python
# MCP Server using official SDK
from mcp import Server, Tool, Resource

server = Server("paperbase")

# Register tools
@server.tool()
async def search_documents(
    query: str,
    filters: dict = None,
    limit: int = 20
) -> dict:
    """
    Search documents using natural language.

    Args:
        query: Natural language search query
        filters: Optional filters (vendor, date_range, amount_range)
        limit: Max results to return

    Returns:
        List of matching documents with metadata
    """
    # Call existing search API
    results = await elastic_service.search(query=query, filters=filters)
    return results

@server.tool()
async def verify_extraction(
    document_id: int,
    field_name: str,
    verified_value: str,
    confidence: float = 1.0
) -> dict:
    """
    Verify an extracted field value (HITL).

    Args:
        document_id: Document ID
        field_name: Field to verify
        verified_value: Corrected value
        confidence: Confidence score (0-1)

    Returns:
        Verification record
    """
    # Call existing verification API
    result = await verification_service.verify_field(
        document_id, field_name, verified_value, confidence
    )
    return result

# Register resources
@server.resource("paperbase://documents/{id}")
async def get_document_resource(id: int):
    """Get full document with all metadata and extractions"""
    doc = await document_service.get_document(id)
    return doc

@server.resource("paperbase://audit/queue")
async def get_audit_queue():
    """Get current HITL audit queue"""
    queue = await audit_service.get_queue()
    return queue
```

**New File:** `backend/app/api/mcp.py`

```python
# FastAPI endpoints for MCP
from fastapi import APIRouter

router = APIRouter(prefix="/mcp", tags=["mcp"])

@router.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, params: dict):
    """Execute an MCP tool"""
    # Validate authorization
    # Execute tool
    # Log activity
    # Return result

@router.get("/resources")
async def list_resources():
    """List available MCP resources"""
    # Return resource catalog

@router.get("/activity")
async def get_activity(limit: int = 50):
    """Get recent MCP activity log"""
    # Return activity feed

@router.post("/authorize")
async def authorize_client(client_info: dict):
    """Authorize a new MCP client"""
    # OAuth-style flow
    # Generate access token
    # Return credentials
```

### Frontend: MCP Integration

**New File:** `frontend/src/services/mcp.js`

```javascript
// MCP Activity Service
class MCPService {
  constructor() {
    this.ws = null;
    this.activities = [];
  }

  connect() {
    // WebSocket for real-time activity feed
    this.ws = new WebSocket('ws://localhost:8000/mcp/stream');

    this.ws.onmessage = (event) => {
      const activity = JSON.parse(event.data);
      this.handleActivity(activity);
    };
  }

  handleActivity(activity) {
    // Add to feed
    this.activities.unshift(activity);

    // Show notification if needed
    if (activity.requires_approval) {
      showNotification({
        type: 'approval_needed',
        message: activity.message,
        action: () => navigateTo(`/approvals/${activity.id}`)
      });
    }

    // Update UI
    eventBus.emit('mcp:activity', activity);
  }

  async executeQuery(query) {
    // Send to backend, which forwards to Claude via MCP
    const response = await fetch('/api/mcp/query', {
      method: 'POST',
      body: JSON.stringify({ query })
    });

    return response.json();
  }
}

export default new MCPService();
```

**New File:** `frontend/src/hooks/useMCPActivity.js`

```javascript
// React hook for MCP activity
import { useState, useEffect } from 'react';
import mcpService from '../services/mcp';

export function useMCPActivity() {
  const [activities, setActivities] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);

  useEffect(() => {
    mcpService.connect();

    const handleActivity = (activity) => {
      setActivities(prev => [activity, ...prev]);

      if (activity.requires_approval) {
        setPendingApprovals(prev => [...prev, activity]);
      }
    };

    eventBus.on('mcp:activity', handleActivity);

    return () => {
      eventBus.off('mcp:activity', handleActivity);
    };
  }, []);

  return { activities, pendingApprovals };
}
```

---

## 🎯 Priority UI Changes (Ranked)

### Phase 1: Core MCP Integration (Week 1-2)
1. ✅ **Enhanced ChatSearch.jsx** - Primary MCP interface
2. ✅ **MCPActivityFeed component** - Real-time visibility
3. ✅ **MCP Settings tab** - Authorization & consent
4. ✅ **Backend MCP server** - Tool/resource implementation

### Phase 2: Developer Experience (Week 3)
5. ✅ **MCP Console page** - Testing & monitoring
6. ✅ **Activity logging** - Audit trail
7. ✅ **WebSocket integration** - Real-time updates

### Phase 3: Advanced Features (Week 4)
8. ✅ **Approval Queue component** - HITL workflow
9. ✅ **Enhanced PDFViewer** - AI annotations
10. ✅ **MCP Stats Dashboard widget** - Analytics

### Phase 4: Polish (Week 5)
11. ✅ **Notification system** - MCP events
12. ✅ **Documentation** - User & developer guides
13. ✅ **Testing** - End-to-end MCP workflows

---

## 📊 Key Metrics to Track

### User Experience
- **MCP Query Success Rate**: % of queries Claude handles correctly
- **Approval Rate**: % of Claude suggestions approved
- **Time Saved**: UI clicks avoided vs direct Claude interaction
- **User Satisfaction**: Survey ratings for MCP vs traditional UI

### Technical Performance
- **Tool Response Time**: <200ms target
- **Resource Access Time**: <100ms for cached, <500ms for fresh
- **WebSocket Latency**: <50ms for activity feed
- **Error Rate**: <1% for MCP tool calls

### Business Value
- **Adoption Rate**: % of users using MCP features
- **Automation Rate**: % of extractions auto-verified by Claude
- **Cost Reduction**: Savings from reduced manual review
- **Accuracy Improvement**: Verification accuracy with Claude assistance

---

## 🛡️ Security Considerations

### 1. Authorization & Consent
```jsx
// Always show consent dialog for first-time access
<ConsentDialog>
  Claude Desktop wants to access your documents.

  Permissions requested:
  ✓ Read document text and extractions
  ✓ Search and filter documents
  ✓ Suggest verifications (requires approval)

  [Allow] [Deny] [Customize Permissions]
</ConsentDialog>
```

### 2. Audit Trail
- Log every MCP tool call with:
  - Client ID
  - Tool name & parameters
  - Result status
  - User who approved (if applicable)
  - Timestamp

### 3. Scope-Based Access Control
```python
# Define scopes
SCOPES = {
    "documents:read": "View documents and extractions",
    "documents:search": "Search and filter documents",
    "documents:write": "Upload and modify documents",
    "documents:delete": "Delete documents",
    "templates:read": "View templates",
    "templates:write": "Create/modify templates",
    "verify:suggest": "Suggest verifications",
    "verify:execute": "Execute verifications (dangerous)"
}
```

### 4. Rate Limiting
- Per-client rate limits
- Expensive operations (bulk actions) have lower limits
- Show rate limit status in MCP Console

---

## 📱 Mobile Considerations

### MCP on Mobile
Since MCP is primarily for desktop AI assistants, mobile UI should:

1. **Show MCP Activity**: Display what Claude is doing
2. **Handle Approvals**: Push notifications for approval requests
3. **View Results**: See Claude-generated reports/insights
4. **Simplified Chat**: Mobile-optimized chat interface

```jsx
// Mobile-specific component
<MobileMCPView>
  <ActivityFeedCompact />
  <ApprovalsBadge count={pendingApprovals.length} />
  <QuickChatButton />
</MobileMCPView>
```

---

## 🎓 User Onboarding

### First-Time MCP Setup
```jsx
<OnboardingWizard>
  <Step title="Meet Your AI Assistant">
    Claude can now help you search, extract, and verify documents
    using natural language.

    <Demo>
      Try: "Show me all invoices over $1000"
    </Demo>
  </Step>

  <Step title="Grant Permissions">
    Claude needs access to your documents.

    <PermissionsList>
      ✓ Read documents (required)
      ✓ Search (required)
      ✓ Suggest edits (recommended)
      ✗ Auto-approve (not recommended)
    </PermissionsList>
  </Step>

  <Step title="Set Preferences">
    <Preferences>
      <Toggle>Always ask before uploading documents</Toggle>
      <Toggle>Notify me of Claude's insights</Toggle>
      <Toggle>Auto-approve high-confidence (>0.95) extractions</Toggle>
    </Preferences>
  </Step>

  <Step title="Try It Out">
    <ExampleQueries>
      "What documents need review?"
      "Find contracts expiring this quarter"
      "Upload these 10 invoices and extract data"
    </ExampleQueries>
  </Step>
</OnboardingWizard>
```

---

## 🔮 Future Enhancements

### 1. Proactive Claude
Claude monitors in background and surfaces insights:
- "I noticed 3 duplicate invoices this week"
- "Vendor 'Acme Corp' appears under 4 different spellings - shall I normalize?"
- "Your average processing time increased 30% - want to review templates?"

### 2. Multi-Agent Workflows
Multiple AI agents collaborate:
- **Extractor Agent**: Processes documents
- **Auditor Agent**: Checks for anomalies
- **Reporter Agent**: Generates summaries
- **Orchestrator**: Coordinates workflow

### 3. Learning from Feedback
Claude improves over time:
- Learn from verifications
- Adapt to user preferences
- Discover new patterns
- Suggest template improvements

---

## 📚 Documentation Needs

### For Users
- "Getting Started with Claude + Paperbase"
- "What can Claude do?"
- "Privacy & Security FAQ"
- "Troubleshooting MCP"

### For Developers
- "MCP Server API Reference"
- "Adding New MCP Tools"
- "Security Best Practices"
- "Testing MCP Integrations"

---

## ✅ Success Criteria

Paperbase is a "best-in-class MCP app" when:

1. ✅ **80%+ of searches** happen via natural language (Claude) vs manual UI
2. ✅ **50%+ of verifications** auto-approved by Claude with high confidence
3. ✅ **Users say:** "I can't imagine using Paperbase without Claude"
4. ✅ **Developers say:** "MCP integration was straightforward and well-documented"
5. ✅ **Security audits:** Pass with zero critical vulnerabilities
6. ✅ **Performance:** <200ms tool response time, 99.9% uptime
7. ✅ **Adoption:** Featured in Anthropic's MCP showcase

---

**Next Steps:**
1. Review this architecture with team
2. Prioritize Phase 1 components
3. Set up MCP SDK and testing environment
4. Implement ChatSearch enhancements
5. Build MCP activity feed
6. Deploy and gather feedback

**Timeline:** 4-5 weeks to full MCP integration

---

**Last Updated:** 2025-10-23
**Status:** Architecture Design Ready for Implementation
