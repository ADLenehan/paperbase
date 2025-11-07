# Paperbase MCP Server Guide

## Overview

Paperbase now provides a comprehensive MCP (Model Context Protocol) server interface for document search and aggregation. This allows AI assistants and other tools to search and analyze documents programmatically.

## Features

### Search Capabilities
- **Natural Language Search**: Search using natural language queries
- **Keyword Search**: Traditional keyword-based search
- **Filtered Search**: Apply filters on specific fields
- **Folder-Scoped Search**: Restrict searches to specific folders
- **Aggregated Results**: Include summary statistics with search results

### Aggregation Capabilities
- **Terms Aggregation**: Group by field values
- **Stats Aggregation**: Calculate min, max, avg, sum for numeric fields
- **Date Histogram**: Analyze temporal trends
- **Cardinality**: Count unique values
- **Range Aggregation**: Group by value ranges
- **Multi-Aggregation**: Run multiple aggregations in one query
- **Nested Aggregation**: Hierarchical grouping

### Discovery Tools
- **List Fields**: Discover all searchable fields
- **List Templates**: View available document templates
- **Query Explanation**: Understand how queries are executed
- **Search Statistics**: Get index health and usage metrics

## MCP Server Configuration

The MCP server configuration is defined in `mcp-server-config.json`:

```json
{
  "name": "paperbase-search",
  "server": {
    "type": "http",
    "url": "http://localhost:8000"
  }
}
```

## Available Tools

### 1. search_documents

Search for documents using natural language or keywords.

**Input:**
```json
{
  "query": "invoices over $1000 from last month",
  "max_results": 10,
  "include_aggregations": true,
  "filters": {
    "status": "completed"
  }
}
```

**Output:**
```json
{
  "success": true,
  "query": "invoices over $1000 from last month",
  "total_results": 42,
  "returned_results": 10,
  "documents": [...],
  "aggregations": {...},
  "metadata": {
    "query_confidence": 0.95,
    "used_claude": false
  }
}
```

### 2. get_document

Retrieve a single document with full details.

**Input:**
```json
{
  "document_id": 123
}
```

**Output:**
```json
{
  "success": true,
  "document_id": 123,
  "document": {
    "filename": "invoice-2024.pdf",
    "status": "completed",
    "invoice_number": "INV-001",
    "total_amount": 1500.00,
    ...
  }
}
```

### 3. aggregate_field

Execute aggregation on a specific field.

**Input:**
```json
{
  "field": "status",
  "aggregation_type": "terms"
}
```

**Output:**
```json
{
  "success": true,
  "field": "status",
  "aggregation_type": "terms",
  "results": {
    "status_terms": {
      "buckets": [
        {"key": "completed", "doc_count": 150},
        {"key": "processing", "doc_count": 25}
      ]
    }
  }
}
```

### 4. multi_aggregate

Run multiple aggregations in one query.

**Input:**
```json
{
  "aggregations": [
    {"name": "status_breakdown", "field": "status", "type": "terms"},
    {"name": "amount_stats", "field": "total_amount", "type": "stats"},
    {"name": "monthly_trends", "field": "uploaded_at", "type": "date_histogram",
     "config": {"interval": "month"}}
  ]
}
```

**Output:**
```json
{
  "success": true,
  "aggregation_count": 3,
  "results": {
    "status_breakdown": {...},
    "amount_stats": {...},
    "monthly_trends": {...}
  }
}
```

### 5. list_fields

Discover all searchable fields.

**Output:**
```json
{
  "success": true,
  "total_fields": 45,
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "description": "Invoice identifier",
      "aliases": ["inv_no", "invoice_id"],
      "templates": ["Invoices", "Receipts"]
    },
    ...
  ]
}
```

### 6. list_templates

Get all document templates.

**Output:**
```json
{
  "success": true,
  "total_templates": 5,
  "templates": [
    {
      "id": 1,
      "name": "Invoices",
      "category": "Financial",
      "field_count": 12,
      "fields": ["invoice_number", "total_amount", ...]
    },
    ...
  ]
}
```

### 7. get_search_stats

Get index statistics.

**Output:**
```json
{
  "success": true,
  "statistics": {
    "total_docs": {"value": 1500},
    "status_breakdown": {...},
    "template_usage": {...}
  }
}
```

### 8. explain_query

Understand query execution.

**Input:**
```json
{
  "query": "show me all invoices over $1000"
}
```

**Output:**
```json
{
  "success": true,
  "query": "show me all invoices over $1000",
  "analysis": {
    "intent": "filter",
    "confidence": 0.95,
    "query_type": "hybrid",
    "target_fields": ["invoice_total", "amount"],
    "filters": [
      {"field": "amount", "operator": ">", "value": 1000}
    ],
    "would_use_claude": false
  },
  "elasticsearch_query": {...}
}
```

### 9. get_dashboard_analytics

Get pre-configured analytics.

**Output:**
```json
{
  "success": true,
  "dashboard": "overview",
  "results": {
    "status_breakdown": {...},
    "template_usage": {...},
    "monthly_uploads": {...},
    "total_documents": {...}
  }
}
```

## API Endpoints Reference

### MCP Search API (`/api/mcp/search`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/documents` | POST | Search documents |
| `/document/{id}` | GET | Get single document |
| `/aggregate` | POST | Single aggregation |
| `/fields` | GET | List all fields |
| `/templates` | GET | List templates |
| `/stats` | GET | Get statistics |
| `/query/explain` | POST | Explain query |

### Aggregations API (`/api/aggregations`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/single` | POST | Single aggregation |
| `/multi` | POST | Multiple aggregations |
| `/nested` | POST | Nested aggregations |
| `/dashboard` | GET | Dashboard analytics |
| `/insights/{field}` | GET | Field insights |
| `/custom` | POST | Custom aggregation |
| `/presets/{name}` | GET | Preset aggregations |

## Usage Examples

### Example 1: Search with Aggregations

```bash
curl -X POST http://localhost:8000/api/mcp/search/documents \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contracts expiring this year",
    "max_results": 20,
    "include_aggregations": true
  }'
```

### Example 2: Multi-Dimensional Analytics

```bash
curl -X POST http://localhost:8000/api/aggregations/multi \
  -H "Content-Type: application/json" \
  -d '{
    "aggregations": [
      {"name": "by_vendor", "field": "vendor_name", "type": "terms"},
      {"name": "amount_stats", "field": "total_amount", "type": "stats"},
      {"name": "monthly_trend", "field": "created_date", "type": "date_histogram",
       "config": {"interval": "month"}}
    ],
    "filters": {"status": "active"}
  }'
```

### Example 3: Nested Aggregation

```bash
curl -X POST http://localhost:8000/api/aggregations/nested \
  -H "Content-Type: application/json" \
  -d '{
    "parent_agg": {
      "name": "by_status",
      "field": "status",
      "type": "terms"
    },
    "sub_aggs": [
      {"name": "avg_amount", "field": "total_amount", "type": "stats"},
      {"name": "unique_vendors", "field": "vendor_name", "type": "cardinality"}
    ]
  }'
```

### Example 4: Field Insights

```bash
curl http://localhost:8000/api/aggregations/insights/total_amount
```

## Integration with MCP Clients

### Claude Desktop Integration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "paperbase": {
      "type": "http",
      "url": "http://localhost:8000",
      "config": "mcp-server-config.json"
    }
  }
}
```

### Custom MCP Client

```python
from mcp_client import MCPClient

client = MCPClient("http://localhost:8000")

# Search documents
results = client.call_tool("search_documents", {
    "query": "invoices over $1000",
    "max_results": 10
})

# Get aggregations
stats = client.call_tool("multi_aggregate", {
    "aggregations": [
        {"name": "status", "field": "status", "type": "terms"},
        {"name": "amounts", "field": "total_amount", "type": "stats"}
    ]
})
```

## Query Optimization

The search API automatically optimizes queries:

1. **Intent Detection**: Understands search vs filter vs aggregation intent
2. **Field Resolution**: Maps aliases to actual field names
3. **Confidence Scoring**: Uses Claude only when needed (>70% confidence threshold)
4. **Query Caching**: Caches frequently used queries
5. **Filter Optimization**: Efficiently combines filters

## Aggregation Types

### Terms Aggregation
Groups documents by field values. Best for categorical data.

```json
{
  "field": "status",
  "aggregation_type": "terms",
  "config": {"size": 10}
}
```

### Stats Aggregation
Calculates statistics for numeric fields.

```json
{
  "field": "total_amount",
  "aggregation_type": "stats"
}
```

### Date Histogram
Analyzes temporal trends.

```json
{
  "field": "uploaded_at",
  "aggregation_type": "date_histogram",
  "config": {
    "interval": "month",
    "format": "yyyy-MM"
  }
}
```

### Range Aggregation
Groups by value ranges.

```json
{
  "field": "total_amount",
  "aggregation_type": "range",
  "config": {
    "ranges": [
      {"to": 100},
      {"from": 100, "to": 1000},
      {"from": 1000}
    ]
  }
}
```

### Cardinality
Counts unique values.

```json
{
  "field": "vendor_name",
  "aggregation_type": "cardinality"
}
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message",
  "status_code": 500
}
```

Common status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found
- `500`: Server error

## Performance Considerations

1. **Pagination**: Use `max_results` to limit response size
2. **Aggregations**: Aggregations run on all matched documents, not just returned results
3. **Field Queries**: Searching specific fields is faster than full-text search
4. **Caching**: Repeated queries are cached for faster responses
5. **Batch Processing**: Use multi-aggregation for multiple analytics in one call

## Security Notes

⚠️ **Current State**: No authentication (MVP)

**For Production**:
- Add API key authentication
- Implement rate limiting
- Use HTTPS
- Add request validation
- Enable CORS restrictions

## Testing

Start the server:
```bash
cd backend
uvicorn app.main:app --reload
```

Test with curl:
```bash
# Health check
curl http://localhost:8000/health

# List fields
curl http://localhost:8000/api/mcp/search/fields

# Search
curl -X POST http://localhost:8000/api/mcp/search/documents \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 5}'
```

## Troubleshooting

### Connection Issues
- Ensure backend is running: `http://localhost:8000/health`
- Check Elasticsearch is running: `curl http://localhost:9200`

### Search Returns No Results
- Check index exists: Use `/api/mcp/search/stats`
- Verify field names: Use `/api/mcp/search/fields`
- Explain query: Use `/api/mcp/search/query/explain`

### Aggregation Errors
- Verify field type matches aggregation type
- Check field name is correct (use `.keyword` suffix for text fields)
- Ensure field exists in indexed documents

## Next Steps

1. **Add Authentication**: Implement API key or OAuth
2. **Rate Limiting**: Add request throttling
3. **Monitoring**: Add logging and metrics
4. **Caching Layer**: Add Redis for query caching
5. **Advanced Aggregations**: Add percentile ranks, moving averages, etc.

## Support

See main documentation:
- [CLAUDE.md](./CLAUDE.md) - Project overview
- [PROJECT_PLAN.md](./PROJECT_PLAN.md) - Feature roadmap
- API Docs: http://localhost:8000/docs
