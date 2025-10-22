# Paperbase API Documentation

Complete API reference for the Paperbase document extraction platform.

**Base URL:** `http://localhost:8001`
**Version:** 0.1.0

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Health Check](#health-check)
3. [Templates](#templates)
4. [Bulk Upload](#bulk-upload)
5. [Documents](#documents)
6. [Search](#search)
7. [Schemas](#schemas)
8. [Verification](#verification)
9. [Error Handling](#error-handling)

---

## 🔐 Authentication

**Current:** No authentication (MVP single-user mode)
**Future:** Bearer token authentication

---

## 🏥 Health Check

### GET /health

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "service": "paperbase-api"
}
```

**Status Codes:**
- `200` - Service healthy
- `503` - Service unavailable

---

## 📑 Templates

### GET /api/templates/

List all available document templates.

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "Invoice",
      "category": "invoice",
      "description": "Standard invoice with line items, totals, and payment terms",
      "icon": "🧾",
      "field_count": 9,
      "usage_count": 0,
      "is_builtin": true
    }
  ]
}
```

---

### GET /api/templates/{template_id}

Get detailed template information including fields.

**Parameters:**
- `template_id` (path) - Template ID

**Response:**
```json
{
  "id": 1,
  "name": "Invoice",
  "category": "invoice",
  "description": "Standard invoice with line items",
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "description": "Unique invoice identifier",
      "required": true,
      "confidence_threshold": 0.85,
      "extraction_hints": ["Invoice #", "Invoice No"]
    }
  ],
  "is_builtin": true,
  "created_at": "2025-10-10T00:00:00"
}
```

**Status Codes:**
- `200` - Success
- `404` - Template not found

---

### GET /api/templates/category/{category}

Get templates by category.

**Parameters:**
- `category` (path) - Category name (invoice, receipt, contract, etc.)

**Response:**
```json
{
  "category": "invoice",
  "templates": [...]
}
```

---

### POST /api/templates/{template_id}/use

Mark template as used (increments usage counter).

**Parameters:**
- `template_id` (path) - Template ID

**Response:**
```json
{
  "success": true,
  "template_id": 1,
  "usage_count": 1
}
```

---

## 📤 Bulk Upload

### POST /api/bulk/upload-and-analyze

Upload multiple documents, parse with Reducto, group similar docs, and match to templates.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `files` - Array of files to upload

**Example:**
```bash
curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@receipt.pdf"
```

**Response:**
```json
{
  "success": true,
  "total_documents": 3,
  "groups": [
    {
      "document_ids": [1, 2],
      "filenames": ["invoice1.pdf", "invoice2.pdf"],
      "suggested_name": "Invoice Documents",
      "template_match": {
        "template_id": 1,
        "template_name": "Invoice",
        "confidence": 0.85,
        "reasoning": "Documents contain invoice numbers, dates, and line items"
      },
      "common_fields": ["invoice_number", "date", "total"]
    },
    {
      "document_ids": [3],
      "filenames": ["receipt.pdf"],
      "suggested_name": "Receipt",
      "template_match": {
        "template_id": 2,
        "template_name": "Receipt",
        "confidence": 0.90
      },
      "common_fields": ["date", "merchant", "total"]
    }
  ],
  "message": "Uploaded and analyzed 3 documents into 2 groups"
}
```

**Process:**
1. Upload files to `/uploads/unmatched/`
2. Create document records with status `uploaded`
3. Parse each document with Reducto (stores `reducto_job_id`)
4. Group similar documents with Claude
5. Match each group to best template
6. Update document status to `template_matched`

**Status Codes:**
- `200` - Success
- `400` - Invalid files
- `413` - File too large
- `500` - Processing error

---

### POST /api/bulk/confirm-template

Confirm template match and start extraction for a group of documents.

**Request Body:**
```json
{
  "document_ids": [1, 2, 3],
  "template_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "schema_id": 1,
  "updated_documents": 3,
  "message": "Confirmed template and started processing 3 documents"
}
```

**Process:**
1. Get or create schema from template
2. Organize files into template folder (`/uploads/invoice/`)
3. Update document `schema_id` and status to `processing`
4. Trigger background extraction (uses `jobid://` for pipelining)
5. Extract fields using Reducto
6. Index in Elasticsearch
7. Update status to `completed`

**Status Codes:**
- `200` - Success
- `404` - Template or documents not found
- `500` - Processing error

---

### POST /api/bulk/create-new-template

Create a new template for documents that don't match existing ones.

**Request Body:**
```json
{
  "document_ids": [4, 5],
  "template_name": "W-2 Tax Form"
}
```

**Response:**
```json
{
  "success": true,
  "template_id": 6,
  "schema_id": 2,
  "fields": [
    {
      "name": "employee_name",
      "type": "text",
      "description": "Employee full name",
      "required": true
    }
  ],
  "message": "Created new template and started processing 2 documents"
}
```

**Process:**
1. Analyze sample documents with Claude
2. Generate schema with field definitions
3. Create new template
4. Create schema
5. Process documents with new schema

---

### POST /api/bulk/verify

Submit bulk verification for extracted fields.

**Request Body:**
```json
{
  "verifications": [
    {
      "document_id": 1,
      "field_id": 10,
      "field_name": "invoice_number",
      "original_value": "INV-001",
      "verified_value": "INV-001",
      "action": "confirmed"
    },
    {
      "document_id": 1,
      "field_id": 11,
      "field_name": "total",
      "original_value": "100.00",
      "verified_value": "150.00",
      "action": "corrected"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "verified_count": 2,
  "corrections_count": 1,
  "message": "Verified 2 fields"
}
```

**Actions:**
- `confirmed` - Value is correct
- `corrected` - Value was wrong, corrected
- `rejected` - Value is wrong, no correction provided

---

## 📄 Documents

### GET /api/documents

List documents with optional filters.

**Query Parameters:**
- `schema_id` (optional) - Filter by schema
- `status` (optional) - Filter by status
- `page` (optional, default: 1) - Page number
- `size` (optional, default: 20) - Results per page

**Example:**
```bash
curl "http://localhost:8001/api/documents?schema_id=1&status=completed&page=1&size=10"
```

**Response:**
```json
{
  "total": 25,
  "page": 1,
  "size": 10,
  "documents": [
    {
      "id": 1,
      "filename": "invoice_001.pdf",
      "status": "completed",
      "uploaded_at": "2025-10-10T12:00:00",
      "processed_at": "2025-10-10T12:00:15",
      "schema_id": 1,
      "extracted_fields": [
        {
          "id": 10,
          "field_name": "invoice_number",
          "field_value": "INV-2025-001",
          "confidence_score": 0.92,
          "needs_verification": false,
          "verified": false
        }
      ]
    }
  ]
}
```

**Document Status Values:**
- `uploaded` - File uploaded, not yet processed
- `analyzing` - Being parsed by Reducto
- `template_matched` - Matched to template
- `template_needed` - No match, needs new template
- `processing` - Extracting fields
- `completed` - Extraction complete
- `verified` - User verified
- `error` - Processing failed

---

### GET /api/documents/{document_id}

Get single document with full details.

**Parameters:**
- `document_id` (path) - Document ID

**Response:**
```json
{
  "id": 1,
  "filename": "invoice_001.pdf",
  "file_path": "/uploads/invoice/invoice_001.pdf",
  "status": "completed",
  "schema_id": 1,
  "uploaded_at": "2025-10-10T12:00:00",
  "processed_at": "2025-10-10T12:00:15",
  "elasticsearch_id": "1",
  "reducto_job_id": "uuid-here",
  "schema": {
    "id": 1,
    "name": "Invoice"
  },
  "extracted_fields": [
    {
      "id": 10,
      "field_name": "invoice_number",
      "field_value": "INV-2025-001",
      "confidence_score": 0.92,
      "needs_verification": false,
      "verified": false,
      "source_page": 1,
      "source_bbox": [100, 200, 300, 220]
    }
  ]
}
```

---

### POST /api/documents/upload

Upload documents to existing schema (legacy endpoint).

**Request:**
- Content-Type: `multipart/form-data`
- Body: `files` - Files to upload
- Body: `schema_id` - Schema ID

**Response:**
```json
{
  "success": true,
  "documents": [
    {
      "id": 10,
      "filename": "doc.pdf",
      "status": "uploaded"
    }
  ],
  "message": "Uploaded 1 documents"
}
```

---

### POST /api/documents/process

Trigger processing for uploaded documents.

**Request Body:**
```json
[1, 2, 3]
```
Array of document IDs.

**Response:**
```json
{
  "success": true,
  "message": "Processing 3 documents in background"
}
```

**Note:** Processing happens asynchronously. Check document status to see when complete.

---

## 🔍 Search

### POST /api/search

Search documents with filters.

**Request Body:**
```json
{
  "query": "invoice",
  "filters": {
    "status": "completed",
    "schema_id": 1
  },
  "min_confidence": 0.8,
  "page": 1,
  "size": 10
}
```

**Response:**
```json
{
  "total": 5,
  "page": 1,
  "size": 10,
  "results": [
    {
      "document_id": 1,
      "filename": "invoice_001.pdf",
      "score": 0.95,
      "status": "completed",
      "extracted_fields": {
        "invoice_number": "INV-001",
        "total": "1500.00"
      },
      "highlight": {
        "full_text": ["...found <em>invoice</em> number..."]
      }
    }
  ],
  "aggregations": {
    "by_status": {
      "completed": 5
    }
  }
}
```

---

### POST /api/search/nl

Natural language search - ask questions in plain English.

**Request Body:**
```json
{
  "query": "Show me all invoices over $1000 from January 2025",
  "schema_id": 1,
  "conversation_history": [
    {
      "role": "user",
      "content": "Previous question"
    },
    {
      "role": "assistant",
      "content": "Previous answer"
    }
  ]
}
```

**Response:**
```json
{
  "query": "Show me all invoices over $1000 from January 2025",
  "answer": "I found 3 invoices over $1000 from January 2025. The invoices are from Acme Corp ($1,500), Tech Services ($2,000), and Consulting LLC ($1,200).",
  "explanation": "I searched for documents in the Invoice schema where the total field is greater than 1000 and the invoice_date is in January 2025.",
  "results": [
    {
      "document_id": 1,
      "filename": "invoice_001.pdf",
      "extracted_fields": {
        "invoice_number": "INV-001",
        "invoice_date": "2025-01-15",
        "total": "1500.00"
      }
    }
  ],
  "total": 3,
  "elasticsearch_query": {
    "bool": {
      "must": [
        {
          "range": {
            "extracted_fields.total": {
              "gte": 1000
            }
          }
        },
        {
          "range": {
            "extracted_fields.invoice_date": {
              "gte": "2025-01-01",
              "lt": "2025-02-01"
            }
          }
        }
      ]
    }
  }
}
```

**Features:**
- Natural language to Elasticsearch query conversion
- Conversational context support
- Natural language answer generation
- Query explanation

---

### GET /api/search/filters

Get available filter options.

**Response:**
```json
{
  "available_filters": [
    {
      "field": "status",
      "type": "keyword",
      "values": {
        "completed": 25,
        "processing": 3,
        "error": 2
      }
    },
    {
      "field": "confidence",
      "type": "range",
      "min": 0.0,
      "max": 1.0
    }
  ]
}
```

---

## 📊 Schemas

### GET /api/onboarding/schemas/{schema_id}

Get schema details.

**Parameters:**
- `schema_id` (path) - Schema ID

**Response:**
```json
{
  "id": 1,
  "name": "Invoice",
  "description": "Invoice documents",
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "description": "Unique invoice identifier",
      "required": true,
      "confidence_threshold": 0.85,
      "extraction_hints": ["Invoice #", "Invoice No"]
    }
  ],
  "created_at": "2025-10-10T00:00:00",
  "document_count": 25
}
```

---

### GET /api/onboarding/schema

Get active schema (legacy - returns first schema).

**Response:**
```json
{
  "id": 1,
  "name": "Invoice",
  "fields": [...]
}
```

---

### PUT /api/onboarding/schema

Update schema fields (legacy).

**Request Body:**
```json
{
  "schema_id": 1,
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "required": true
    }
  ]
}
```

---

## ✅ Verification

### GET /api/verification/queue

Get fields needing human verification (low confidence).

**Query Parameters:**
- `limit` (optional, default: 50)
- `min_confidence` (optional, default: 0.6)

**Response:**
```json
{
  "queue": [
    {
      "field_id": 100,
      "document_id": 10,
      "document_filename": "invoice_042.pdf",
      "field_name": "tax_amount",
      "field_value": "15.50",
      "confidence_score": 0.55,
      "needs_verification": true
    }
  ],
  "total": 12
}
```

---

### POST /api/verification/verify

Submit verification for a field.

**Request Body:**
```json
{
  "field_id": 100,
  "verified_value": "15.75",
  "feedback": "OCR misread decimal point"
}
```

**Response:**
```json
{
  "success": true,
  "field_id": 100,
  "original_value": "15.50",
  "verified_value": "15.75",
  "improvement_logged": true
}
```

---

### GET /api/verification/stats

Get verification statistics.

**Response:**
```json
{
  "total_fields": 1000,
  "verified_fields": 850,
  "pending_verification": 150,
  "accuracy_rate": 0.92,
  "corrections_by_field": {
    "invoice_number": 5,
    "total": 12,
    "tax_amount": 8
  }
}
```

---

## ❌ Error Handling

### Error Response Format

All errors follow this structure:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "details": "Additional details or validation errors",
  "path": "/api/endpoint",
  "timestamp": "2025-10-10T12:00:00"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (future)
- `403` - Forbidden (future)
- `404` - Not Found
- `413` - Payload Too Large
- `422` - Unprocessable Entity
- `429` - Too Many Requests (future)
- `500` - Internal Server Error
- `503` - Service Unavailable

### Common Errors

**Validation Error (400):**
```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "details": [
    {
      "field": "template_id",
      "message": "Field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Not Found (404):**
```json
{
  "error": "NotFoundError",
  "message": "Document not found",
  "document_id": 999
}
```

**Processing Error (500):**
```json
{
  "error": "ProcessingError",
  "message": "Failed to extract fields from document",
  "details": "Reducto API timeout"
}
```

---

## 🔄 Webhooks (Future)

### POST /api/webhooks/register

Register webhook for document processing events.

**Coming Soon**

---

## 📈 Rate Limits (Future)

Currently no rate limits (MVP).

Future limits:
- 100 requests/minute per IP
- 1000 documents/day per user
- 10 concurrent uploads

---

## 🔧 Utility Endpoints

### GET /api/stats

Get system statistics.

**Response:**
```json
{
  "total_documents": 1000,
  "documents_by_status": {
    "completed": 850,
    "processing": 50,
    "error": 100
  },
  "total_schemas": 5,
  "total_templates": 5,
  "storage_used_mb": 1024.5,
  "api_calls_today": {
    "reducto": 150,
    "claude": 25,
    "elasticsearch": 500
  }
}
```

---

## 📚 Examples

### Complete Workflow Example

```bash
# 1. Upload documents
RESPONSE=$(curl -X POST http://localhost:8001/api/bulk/upload-and-analyze \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf")

# 2. Extract document IDs
DOC_IDS=$(echo $RESPONSE | jq -r '.groups[0].document_ids | @json')

# 3. Confirm template
curl -X POST http://localhost:8001/api/bulk/confirm-template \
  -H "Content-Type: application/json" \
  -d "{
    \"document_ids\": $DOC_IDS,
    \"template_id\": 1
  }"

# 4. Wait for processing (check status)
sleep 15

# 5. Get extractions
curl "http://localhost:8001/api/documents?schema_id=1&status=completed"

# 6. Search
curl -X POST http://localhost:8001/api/search/nl \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me invoices from last month"
  }'
```

---

## 🔗 SDKs & Client Libraries

### Python Client (Coming Soon)

```python
from paperbase import PaperbaseClient

client = PaperbaseClient(api_url="http://localhost:8001")

# Upload documents
result = client.bulk.upload_and_analyze(["invoice1.pdf", "invoice2.pdf"])

# Confirm template
client.bulk.confirm_template(
    document_ids=result.groups[0].document_ids,
    template_id=1
)

# Search
results = client.search.nl("Show me invoices over $1000")
```

### JavaScript/TypeScript Client (Coming Soon)

```typescript
import { PaperbaseClient } from '@paperbase/client';

const client = new PaperbaseClient({
  apiUrl: 'http://localhost:8001'
});

// Upload and analyze
const result = await client.bulk.uploadAndAnalyze([
  file1, file2
]);

// Search
const results = await client.search.nl(
  'Show me recent contracts'
);
```

---

## 📖 API Changelog

### v0.1.0 (2025-10-10)
- Initial API release
- Bulk upload and analysis
- Template matching
- Pipelined extraction
- Natural language search
- Bulk verification

---

**API Version:** 0.1.0
**Last Updated:** 2025-10-10
**Base URL:** http://localhost:8001
