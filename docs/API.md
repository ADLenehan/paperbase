# Paperbase API Documentation

**Version**: 0.1.0
**Base URL**: `http://localhost:8000`

## Table of Contents

1. [Authentication](#authentication)
2. [Onboarding Endpoints](#onboarding-endpoints)
3. [Document Endpoints](#document-endpoints)
4. [Search Endpoints](#search-endpoints)
5. [Verification Endpoints](#verification-endpoints)
6. [Analytics Endpoints](#analytics-endpoints)
7. [Error Handling](#error-handling)
8. [Data Models](#data-models)

---

## Authentication

**MVP Note**: The current version does not require authentication. This will be added in a future release for multi-user support.

---

## Onboarding Endpoints

### POST /api/onboarding/analyze-samples

Analyze sample documents and generate an extraction schema using Claude AI.

**Request**:
```http
POST /api/onboarding/analyze-samples
Content-Type: multipart/form-data

files: [file1.pdf, file2.pdf, file3.pdf]
```

**Parameters**:
- `files` (form-data): 3-5 sample PDF documents

**Response** (200 OK):
```json
{
  "schema_id": "550e8400-e29b-41d4-a716-446655440000",
  "schema": {
    "name": "Service Agreements",
    "fields": [
      {
        "name": "effective_date",
        "type": "date",
        "required": true,
        "extraction_hints": ["Effective Date:", "Dated:", "As of"],
        "confidence_threshold": 0.75,
        "description": "Contract effective date"
      },
      {
        "name": "contract_value",
        "type": "number",
        "required": true,
        "extraction_hints": ["Total Value:", "Contract Amount:"],
        "confidence_threshold": 0.8,
        "description": "Total contract value"
      }
    ]
  },
  "sample_extractions": {
    "file1.pdf": {
      "effective_date": "2024-01-15",
      "contract_value": "125000"
    }
  }
}
```

**Errors**:
- `400`: Invalid files or insufficient samples
- `502`: Reducto or Claude API error

**Notes**:
- Upload 3-5 representative documents for best results
- Processing time: 1-3 minutes depending on document complexity
- Claude analyzes documents to identify common fields automatically

---

### GET /api/onboarding/schema

Retrieve the most recently generated schema.

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Service Agreements",
  "fields": [...],
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Errors**:
- `404`: No schema found

---

### PUT /api/onboarding/schema

Update an existing schema (edit fields, add/remove fields).

**Request**:
```json
{
  "schema_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Updated Service Agreements",
  "fields": [
    {
      "name": "effective_date",
      "type": "date",
      "required": true,
      "extraction_hints": ["Effective Date:", "Start Date:"],
      "confidence_threshold": 0.75,
      "description": "Contract effective date"
    }
  ]
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Schema updated successfully"
}
```

**Errors**:
- `400`: Invalid schema format
- `404`: Schema not found

---

## Document Endpoints

### POST /api/documents/upload

Upload documents for processing.

**Request**:
```http
POST /api/documents/upload
Content-Type: multipart/form-data

schema_id: 550e8400-e29b-41d4-a716-446655440000
files: [doc1.pdf, doc2.pdf, ...]
```

**Parameters**:
- `schema_id` (form-data): Schema to use for extraction
- `files` (form-data): One or more PDF documents

**Response** (200 OK):
```json
{
  "uploaded": [
    {
      "document_id": "650e8400-e29b-41d4-a716-446655440001",
      "filename": "doc1.pdf",
      "status": "pending"
    },
    {
      "document_id": "650e8400-e29b-41d4-a716-446655440002",
      "filename": "doc2.pdf",
      "status": "pending"
    }
  ],
  "count": 2
}
```

**Errors**:
- `400`: Invalid files or missing schema_id
- `404`: Schema not found

**Notes**:
- Files are uploaded but not processed immediately
- Call `/api/documents/process` to start extraction
- Maximum file size: 50MB per file

---

### POST /api/documents/process

Process uploaded documents using Reducto extraction.

**Request**:
```json
{
  "document_ids": [
    "650e8400-e29b-41d4-a716-446655440001",
    "650e8400-e29b-41d4-a716-446655440002"
  ]
}
```

**Response** (202 Accepted):
```json
{
  "processing": [
    "650e8400-e29b-41d4-a716-446655440001",
    "650e8400-e29b-41d4-a716-446655440002"
  ],
  "message": "Processing started"
}
```

**Errors**:
- `400`: Invalid document IDs
- `404`: Documents not found
- `502`: Reducto API error

**Notes**:
- Processing is asynchronous
- Check document status with `GET /api/documents/{id}`
- Processing time: 2-5 seconds per document

---

### GET /api/documents

List all documents with optional filters.

**Query Parameters**:
- `schema_id` (optional): Filter by schema
- `status` (optional): Filter by status (`pending`, `processing`, `completed`, `error`)
- `limit` (optional, default: 50): Number of results
- `offset` (optional, default: 0): Pagination offset

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "650e8400-e29b-41d4-a716-446655440001",
      "filename": "doc1.pdf",
      "schema_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "uploaded_at": "2024-01-15T10:00:00Z",
      "processed_at": "2024-01-15T10:00:03Z",
      "extraction_count": 5,
      "avg_confidence": 0.87
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### GET /api/documents/{document_id}

Get detailed document information including all extractions.

**Response** (200 OK):
```json
{
  "id": "650e8400-e29b-41d4-a716-446655440001",
  "filename": "doc1.pdf",
  "schema_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "uploaded_at": "2024-01-15T10:00:00Z",
  "processed_at": "2024-01-15T10:00:03Z",
  "extractions": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440001",
      "field_name": "effective_date",
      "value": "2024-01-15",
      "confidence_score": 0.92,
      "confidence_label": "High",
      "needs_verification": false,
      "verified": false,
      "source_page": 1,
      "extracted_at": "2024-01-15T10:00:03Z"
    }
  ]
}
```

**Errors**:
- `404`: Document not found

---

## Search Endpoints

### POST /api/search

Search documents by content and metadata.

**Request**:
```json
{
  "query": "contract value",
  "filters": {
    "schema_id": "550e8400-e29b-41d4-a716-446655440000",
    "confidence_min": 0.8,
    "fields": {
      "effective_date": {
        "gte": "2024-01-01",
        "lte": "2024-12-31"
      }
    }
  },
  "limit": 20,
  "offset": 0
}
```

**Parameters**:
- `query` (optional): Full-text search query
- `filters` (optional): Metadata filters
- `limit` (optional, default: 20): Number of results
- `offset` (optional, default: 0): Pagination offset

**Response** (200 OK):
```json
{
  "results": [
    {
      "document_id": "650e8400-e29b-41d4-a716-446655440001",
      "filename": "contract.pdf",
      "score": 0.95,
      "highlights": {
        "content": "...contract <em>value</em> of $125,000..."
      },
      "extractions": {
        "effective_date": "2024-03-15",
        "contract_value": "125000"
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "took_ms": 42
}
```

**Errors**:
- `400`: Invalid query
- `502`: Elasticsearch error

**Notes**:
- Search response time target: <200ms
- Results sorted by relevance score
- Highlights show matching text snippets

---

### GET /api/search/filters

Get available filter options and value distributions.

**Response** (200 OK):
```json
{
  "schemas": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Service Agreements",
      "document_count": 42
    }
  ],
  "confidence_ranges": {
    "high": 85,
    "medium": 12,
    "low": 3
  },
  "field_values": {
    "effective_date": {
      "min": "2024-01-01",
      "max": "2024-12-31"
    }
  }
}
```

---

## Verification Endpoints

### GET /api/verification/queue

Get items that need human verification (low confidence extractions).

**Query Parameters**:
- `schema_id` (optional): Filter by schema
- `field_name` (optional): Filter by specific field
- `limit` (optional, default: 20): Number of items

**Response** (200 OK):
```json
{
  "queue": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440001",
      "document_id": "650e8400-e29b-41d4-a716-446655440001",
      "filename": "contract.pdf",
      "field_name": "effective_date",
      "extracted_value": "2024-01-?5",
      "confidence_score": 0.55,
      "confidence_label": "Low",
      "source_page": 1,
      "context": "This agreement is effective on 2024-01-?5..."
    }
  ],
  "total": 1,
  "limit": 20
}
```

**Errors**:
- `400`: Invalid parameters

---

### POST /api/verification/verify

Submit a verification for a low-confidence extraction.

**Request**:
```json
{
  "extracted_field_id": "750e8400-e29b-41d4-a716-446655440001",
  "verification_type": "corrected",
  "corrected_value": "2024-01-15",
  "notes": "OCR misread the '1' as '?'"
}
```

**Parameters**:
- `extracted_field_id`: ID of the field being verified
- `verification_type`: One of `correct`, `corrected`, `not_found`
- `corrected_value` (required if type=`corrected`): The correct value
- `notes` (optional): Additional context

**Response** (200 OK):
```json
{
  "verified": true,
  "next_item": {
    "id": "750e8400-e29b-41d4-a716-446655440002",
    "field_name": "contract_value",
    "extracted_value": "125000"
  }
}
```

**Errors**:
- `400`: Invalid verification data
- `404`: Extracted field not found

**Notes**:
- Verifications create training examples for future improvements
- Response includes next item in queue for efficient workflow

---

### GET /api/verification/stats

Get verification queue statistics and accuracy metrics.

**Response** (200 OK):
```json
{
  "queue_size": 15,
  "verified_count": 142,
  "accuracy": 94.5,
  "by_field": {
    "effective_date": {
      "queue_size": 3,
      "verified": 25,
      "accuracy": 96.0
    },
    "contract_value": {
      "queue_size": 12,
      "verified": 117,
      "accuracy": 93.2
    }
  },
  "recent_verifications": [
    {
      "field_name": "effective_date",
      "verification_type": "correct",
      "verified_at": "2024-01-15T14:30:00Z"
    }
  ]
}
```

---

## Analytics Endpoints

### GET /api/analytics/dashboard

Get overall system metrics for dashboard.

**Response** (200 OK):
```json
{
  "documents": {
    "total": 523,
    "completed": 500,
    "processing": 20,
    "errors": 3
  },
  "confidence": {
    "by_field": [
      {
        "field": "effective_date",
        "average": 0.892
      },
      {
        "field": "contract_value",
        "average": 0.856
      }
    ]
  },
  "verification": {
    "queue_size": 15,
    "total_verified": 142,
    "accuracy": 94.5
  },
  "processing": {
    "avg_time_seconds": 3.2,
    "error_rate": 0.57
  }
}
```

---

### GET /api/analytics/schemas

Get per-schema statistics.

**Response** (200 OK):
```json
{
  "schemas": [
    {
      "schema_id": "550e8400-e29b-41d4-a716-446655440000",
      "schema_name": "Service Agreements",
      "document_count": 523,
      "completed_count": 500,
      "average_confidence": 0.874,
      "field_count": 8
    }
  ]
}
```

---

### GET /api/analytics/trends

Get processing trends over time.

**Query Parameters**:
- `days` (optional, default: 7): Number of days to analyze

**Response** (200 OK):
```json
{
  "documents_processed": [
    {
      "date": "2024-01-15",
      "count": 42
    },
    {
      "date": "2024-01-14",
      "count": 38
    }
  ],
  "confidence_trend": [
    {
      "date": "2024-01-15",
      "average": 0.87
    },
    {
      "date": "2024-01-14",
      "average": 0.85
    }
  ]
}
```

---

## Error Handling

All API errors follow a consistent format:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "path": "/api/endpoint",
  "details": {
    "field": "additional context"
  }
}
```

### Common Error Codes

| Code | Error Type | Description |
|------|-----------|-------------|
| 400 | ValidationError | Request validation failed |
| 404 | NotFoundError | Resource not found |
| 422 | UnprocessableEntity | Invalid request format |
| 500 | InternalServerError | Unexpected server error |
| 502 | ExternalServiceError | External API (Reducto/Claude/Elasticsearch) failed |

### Example Error Response

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "path": "/api/documents/upload",
  "details": [
    {
      "field": "schema_id",
      "message": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Data Models

### Schema

```typescript
{
  id: string (UUID)
  name: string
  fields: Field[]
  created_at: datetime
  updated_at: datetime
}
```

### Field

```typescript
{
  name: string
  type: "text" | "date" | "number" | "boolean"
  required: boolean
  extraction_hints: string[]
  confidence_threshold: number (0.0-1.0)
  description: string
}
```

### Document

```typescript
{
  id: string (UUID)
  filename: string
  file_path: string
  schema_id: string (UUID)
  status: "pending" | "processing" | "completed" | "error"
  uploaded_at: datetime
  processed_at: datetime | null
  error_message: string | null
}
```

### ExtractedField

```typescript
{
  id: string (UUID)
  document_id: string (UUID)
  field_name: string
  value: string
  confidence_score: number (0.0-1.0)
  confidence_label: "High" | "Medium" | "Low"
  needs_verification: boolean
  verified: boolean
  source_page: number
  source_bbox: number[] | null
  extracted_at: datetime
}
```

### Verification

```typescript
{
  id: string (UUID)
  extracted_field_id: string (UUID)
  verification_type: "correct" | "corrected" | "not_found"
  original_value: string
  corrected_value: string | null
  notes: string | null
  verified_at: datetime
}
```

---

## Rate Limits

**MVP**: No rate limits currently enforced.

**Future**: Will implement per-API-key rate limits for production.

---

## Changelog

### Version 0.1.0 (Current)
- Initial MVP release
- All core endpoints implemented
- No authentication required

---

## Support

- **Documentation**: See `README.md` and `CLAUDE.md`
- **Issues**: Create an issue in the project repository
- **Interactive Docs**: Visit `http://localhost:8000/docs` when server is running

---

**Last Updated**: January 2025
