# Low-Confidence Data Audit Links - Implementation Design

## Overview

Whenever low-confidence extracted data is used in an AI answer (Ask AI feature or MCP responses), we automatically inject **clickable audit links** that allow users to verify the source extraction and correct it if needed.

This creates a seamless "human-in-the-loop" feedback cycle where:
1. AI answers cite specific extracted fields
2. Low-confidence fields get audit links embedded in the answer
3. User clicks link → Opens audit UI with PDF + highlighted bbox
4. User verifies/corrects → Improves data quality + future AI answers

---

## Architecture

### 1. Data Flow

```
User Query → Claude generates answer using ES data
              ↓
          Answer contains field references (e.g., "invoice_total: $1,250.00")
              ↓
          System identifies which ExtractedFields were used
              ↓
          For each field with confidence < threshold:
            - Generate audit link
            - Inject citation with link into answer
              ↓
          Return enhanced answer with embedded audit metadata
```

### 2. Components

#### A. Citation Tracker (`app/services/citation_tracker.py`)
Tracks which extracted fields are used in AI answers and generates audit links.

**Responsibilities:**
- Parse AI answer to identify field references
- Match references to `ExtractedField` records
- Generate audit URLs for low-confidence fields
- Track citation usage statistics

#### B. Enhanced Answer Format
Answers include structured citations with audit metadata:

```json
{
  "answer": "Found 3 invoices totaling $5,420.00. The largest is from Acme Corp for $2,100.00.",
  "citations": [
    {
      "field_id": 123,
      "field_name": "invoice_total",
      "field_value": "$2,100.00",
      "confidence": 0.62,
      "document_id": 45,
      "filename": "acme_invoice_2024.pdf",
      "needs_audit": true,
      "audit_link": "/audit?field_id=123&document_id=45&highlight=true",
      "citation_text": "Acme Corp invoice total"
    }
  ],
  "low_confidence_count": 1,
  "audit_recommended": true
}
```

#### C. Audit Link Format

**Frontend URL:**
```
/audit?field_id=123&document_id=45&highlight=true&source=ai_answer&query_id=abc123
```

**Query Parameters:**
- `field_id`: ExtractedField ID to audit
- `document_id`: Document ID for context
- `highlight`: Boolean to highlight bbox in PDF viewer
- `source`: Tracking source (`ai_answer`, `mcp_query`, `search_result`)
- `query_id`: Optional query ID for analytics

**API Endpoint:**
```
GET /api/audit/field/{field_id}
Returns: {
  field: ExtractedField,
  document: Document,
  pdf_url: "/api/documents/{id}/pdf",
  page: int,
  bbox: [x, y, width, height],
  template: Schema,
  verification_history: [...]
}
```

---

## Implementation Details

### 1. Database Schema Extensions

#### Add to `ExtractedField` model:
```python
class ExtractedField(Base):
    # ... existing fields ...

    # NEW: Citation tracking
    citation_count = Column(Integer, default=0)  # How many times cited in answers
    last_cited_at = Column(DateTime, nullable=True)
    cited_in_queries = Column(JSON, default=list)  # List of query IDs that used this field
```

#### Add new `FieldCitation` model:
```python
class FieldCitation(Base):
    """Track when fields are used in AI answers"""
    __tablename__ = "field_citations"

    id = Column(Integer, primary_key=True)
    field_id = Column(Integer, ForeignKey("extracted_fields.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    # Query context
    query_text = Column(Text)
    query_id = Column(String, index=True)  # For deduplication and analytics
    query_source = Column(String)  # "ask_ai", "mcp_search", "mcp_rag"

    # Citation metadata
    confidence_at_citation = Column(Float)
    was_verified = Column(Boolean, default=False)
    citation_context = Column(Text)  # Surrounding text in answer

    # Audit tracking
    audit_link_clicked = Column(Boolean, default=False)
    audit_completed_at = Column(DateTime, nullable=True)
    correction_made = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    field = relationship("ExtractedField", backref="citations")
    document = relationship("Document")
```

---

### 2. Citation Tracker Service

```python
# app/services/citation_tracker.py

class CitationTracker:
    """
    Tracks which extracted fields are used in AI answers and generates audit links.
    """

    def __init__(self, db: Session, settings_service: SettingsService):
        self.db = db
        self.settings_service = settings_service
        self.audit_threshold = self._get_audit_threshold()

    def _get_audit_threshold(self) -> float:
        """Get dynamic audit confidence threshold from settings"""
        org = self.settings_service.get_or_create_default_org()
        user = self.settings_service.get_or_create_default_user(org.id)
        return self.settings_service.get_setting(
            key="review_threshold",
            user_id=user.id,
            org_id=org.id,
            default=0.6
        )

    async def track_answer_citations(
        self,
        query: str,
        query_id: str,
        answer: str,
        source_documents: List[Dict[str, Any]],
        query_source: str = "ask_ai"
    ) -> Dict[str, Any]:
        """
        Analyze an AI-generated answer and track which fields were cited.

        Args:
            query: Original user query
            query_id: Unique query identifier
            answer: AI-generated answer text
            source_documents: Documents used to generate answer
            query_source: Source of query (ask_ai, mcp_search, mcp_rag)

        Returns:
            Enhanced answer with citation metadata and audit links
        """

        citations = []
        low_confidence_fields = []

        # For each source document, identify which fields appear in the answer
        for doc in source_documents:
            doc_id = doc.get("id") or doc.get("document_id")

            # Get all extracted fields for this document
            fields = self.db.query(ExtractedField).filter(
                ExtractedField.document_id == doc_id
            ).all()

            for field in fields:
                if not field.field_value:
                    continue

                # Check if field value appears in answer
                if self._field_referenced_in_text(field.field_value, answer):
                    citation = self._create_citation(
                        field=field,
                        query=query,
                        query_id=query_id,
                        query_source=query_source,
                        answer_context=self._extract_context(answer, field.field_value)
                    )

                    citations.append(citation)

                    # Track low-confidence fields
                    if field.confidence_score < self.audit_threshold:
                        low_confidence_fields.append(citation)

        return {
            "answer": answer,
            "citations": citations,
            "low_confidence_citations": low_confidence_fields,
            "low_confidence_count": len(low_confidence_fields),
            "audit_recommended": len(low_confidence_fields) > 0,
            "audit_threshold": self.audit_threshold
        }

    def _field_referenced_in_text(self, field_value: str, text: str) -> bool:
        """Check if field value appears in text (with fuzzy matching for numbers)"""
        if not field_value or not text:
            return False

        # Exact match
        if str(field_value).lower() in text.lower():
            return True

        # Fuzzy match for numbers (handle formatting differences)
        if self._is_number(field_value):
            # Strip currency symbols, commas, etc.
            normalized_value = self._normalize_number(field_value)
            if normalized_value in self._normalize_number(text):
                return True

        return False

    def _create_citation(
        self,
        field: ExtractedField,
        query: str,
        query_id: str,
        query_source: str,
        answer_context: str
    ) -> Dict[str, Any]:
        """Create citation record and return metadata"""

        # Create database record
        citation = FieldCitation(
            field_id=field.id,
            document_id=field.document_id,
            query_text=query,
            query_id=query_id,
            query_source=query_source,
            confidence_at_citation=field.confidence_score,
            was_verified=field.verified,
            citation_context=answer_context
        )
        self.db.add(citation)

        # Update field citation count
        field.citation_count += 1
        field.last_cited_at = datetime.utcnow()

        self.db.commit()

        # Generate audit link if low confidence
        needs_audit = field.confidence_score < self.audit_threshold and not field.verified

        audit_link = None
        if needs_audit:
            audit_link = (
                f"/audit?"
                f"field_id={field.id}&"
                f"document_id={field.document_id}&"
                f"highlight=true&"
                f"source={query_source}&"
                f"query_id={query_id}"
            )

        return {
            "citation_id": citation.id,
            "field_id": field.id,
            "field_name": field.field_name,
            "field_value": field.field_value,
            "confidence": round(field.confidence_score, 3),
            "document_id": field.document_id,
            "filename": field.document.filename,
            "verified": field.verified,
            "needs_audit": needs_audit,
            "audit_link": audit_link,
            "citation_text": f"{field.field_name}: {field.field_value}",
            "context": answer_context
        }

    def _extract_context(self, text: str, value: str, context_chars: int = 100) -> str:
        """Extract surrounding context for a value in text"""
        value_lower = str(value).lower()
        text_lower = text.lower()

        idx = text_lower.find(value_lower)
        if idx == -1:
            return ""

        start = max(0, idx - context_chars)
        end = min(len(text), idx + len(value) + context_chars)

        context = text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context

    def _is_number(self, value: str) -> bool:
        """Check if value is numeric (with potential formatting)"""
        import re
        # Remove common number formatting characters
        cleaned = re.sub(r'[$,€£¥\s]', '', str(value))
        try:
            float(cleaned)
            return True
        except ValueError:
            return False

    def _normalize_number(self, text: str) -> str:
        """Normalize numbers by removing formatting"""
        import re
        return re.sub(r'[$,€£¥\s]', '', str(text))

    async def mark_audit_link_clicked(self, citation_id: int):
        """Track when user clicks an audit link"""
        citation = self.db.query(FieldCitation).filter(
            FieldCitation.id == citation_id
        ).first()

        if citation:
            citation.audit_link_clicked = True
            self.db.commit()

    async def mark_audit_completed(self, citation_id: int, correction_made: bool):
        """Track when user completes audit from citation link"""
        citation = self.db.query(FieldCitation).filter(
            FieldCitation.id == citation_id
        ).first()

        if citation:
            citation.audit_completed_at = datetime.utcnow()
            citation.correction_made = correction_made
            self.db.commit()
```

---

### 3. Enhanced ClaudeService Integration

```python
# app/services/claude_service.py

async def answer_question_about_results(
    self,
    query: str,
    search_results: List[Dict[str, Any]],
    total_count: int,
    query_id: Optional[str] = None,
    include_citations: bool = True
) -> Dict[str, Any]:  # Changed return type from str to Dict
    """
    Generate natural language answer about search results WITH citation tracking.

    Now returns structured response with audit links for low-confidence data.
    """

    # ... existing answer generation logic ...

    answer = message.content[0].text.strip()

    # NEW: Track citations if enabled
    if include_citations:
        from app.services.citation_tracker import CitationTracker
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            tracker = CitationTracker(db, SettingsService(db))

            # Generate unique query ID if not provided
            if not query_id:
                import hashlib
                query_id = hashlib.sha256(f"{query}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]

            enhanced_answer = await tracker.track_answer_citations(
                query=query,
                query_id=query_id,
                answer=answer,
                source_documents=search_results,
                query_source="ask_ai"
            )

            return enhanced_answer
        finally:
            db.close()

    # Legacy: Return plain string if citations disabled
    return {"answer": answer, "citations": [], "low_confidence_count": 0}
```

---

### 4. API Endpoint Enhancements

#### A. Search Endpoint (`app/api/search.py`)

```python
@router.post("")
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    # ... existing search logic ...

    # Generate answer with citation tracking
    answer_result = await claude_service.answer_question_about_results(
        query=request.query,
        search_results=search_results.get("documents", []),
        total_count=search_results.get("total", 0),
        include_citations=True  # NEW
    )

    return {
        "query": request.query,
        "answer": answer_result["answer"],  # Plain text for backward compatibility
        "answer_enhanced": answer_result,   # NEW: Full structured response
        "citations": answer_result.get("citations", []),
        "low_confidence_warnings": answer_result.get("low_confidence_citations", []),
        "results": search_results.get("documents", []),
        "total": search_results.get("total", 0),
        # ... rest of response
    }
```

#### B. MCP RAG Endpoint (`app/api/mcp_search.py`)

```python
@router.post("/rag/query")
async def rag_query_mcp(
    question: str = Query(...),
    max_results: int = Query(default=5),
    filters: Optional[Dict[str, Any]] = None
):
    # ... existing RAG logic ...

    # Get answer with citations (MCP-aware)
    answer_result = await claude_service.answer_question_about_results(
        query=question,
        search_results=search_results.get("documents", []),
        total_count=search_results.get("total", 0),
        include_citations=True
    )

    # Format citations for MCP consumption
    mcp_citations = []
    for citation in answer_result.get("citations", []):
        mcp_citation = {
            "field": citation["field_name"],
            "value": citation["field_value"],
            "confidence": citation["confidence"],
            "document": citation["filename"],
            "verified": citation["verified"]
        }

        # Add audit link for low confidence
        if citation["needs_audit"]:
            mcp_citation["audit_required"] = True
            mcp_citation["audit_url"] = f"{settings.FRONTEND_URL}{citation['audit_link']}"
            mcp_citation["warning"] = f"Low confidence ({citation['confidence']:.0%}) - verification recommended"

        mcp_citations.append(mcp_citation)

    return {
        "success": True,
        "summary": f"Answered based on {len(context_chunks)} documents",
        "question": question,
        "answer": answer_result["answer"],
        "sources": [...],  # existing sources
        "citations": mcp_citations,  # NEW
        "data_quality": {
            "total_fields_cited": len(answer_result.get("citations", [])),
            "low_confidence_count": answer_result.get("low_confidence_count", 0),
            "audit_recommended": answer_result.get("audit_recommended", False),
            "audit_threshold": answer_result.get("audit_threshold", 0.6)
        },
        # ... rest of response
    }
```

#### C. New Audit Link Endpoint

```python
# app/api/audit.py

@router.get("/field/{field_id}")
async def get_audit_field_details(
    field_id: int,
    citation_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get complete audit context for a specific field.

    Used when user clicks an audit link from an AI answer.
    Returns everything needed to render the audit UI.
    """

    field = db.query(ExtractedField).filter(ExtractedField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    document = field.document

    # Track that audit link was clicked
    if citation_id:
        from app.services.citation_tracker import CitationTracker
        tracker = CitationTracker(db, SettingsService(db))
        await tracker.mark_audit_link_clicked(citation_id)

    # Get verification history
    verifications = db.query(Verification).filter(
        Verification.extracted_field_id == field_id
    ).order_by(Verification.verified_at.desc()).all()

    return {
        "field": {
            "id": field.id,
            "name": field.field_name,
            "value": field.field_value,
            "confidence": field.confidence_score,
            "verified": field.verified,
            "verified_value": field.verified_value,
            "source_page": field.source_page,
            "source_bbox": field.source_bbox
        },
        "document": {
            "id": document.id,
            "filename": document.filename,
            "file_path": document.file_path,
            "pdf_url": f"/api/documents/{document.id}/pdf"
        },
        "template": {
            "id": document.schema.id,
            "name": document.schema.name
        } if document.schema else None,
        "verification_history": [
            {
                "type": v.verification_type,
                "original": v.original_value,
                "corrected": v.verified_value,
                "confidence": v.original_confidence,
                "notes": v.reviewer_notes,
                "verified_at": v.verified_at
            }
            for v in verifications
        ],
        "citation_context": {
            "citation_count": field.citation_count,
            "last_cited": field.last_cited_at,
            "recent_queries": db.query(FieldCitation).filter(
                FieldCitation.field_id == field_id
            ).order_by(FieldCitation.created_at.desc()).limit(5).all()
        }
    }
```

---

### 5. Frontend Components

#### A. Citation Display Component

```tsx
// src/components/audit/CitationLink.tsx

interface CitationLinkProps {
  citation: {
    field_name: string;
    field_value: string;
    confidence: number;
    needs_audit: boolean;
    audit_link?: string;
    filename: string;
  };
  inline?: boolean;
}

export function CitationLink({ citation, inline = false }: CitationLinkProps) {
  const confidenceColor =
    citation.confidence >= 0.8 ? 'green' :
    citation.confidence >= 0.6 ? 'yellow' : 'red';

  if (!citation.needs_audit) {
    // High confidence - show as simple badge
    return (
      <span className={`inline-flex items-center px-2 py-1 text-xs rounded bg-${confidenceColor}-100 text-${confidenceColor}-800`}>
        <CheckCircleIcon className="w-3 h-3 mr-1" />
        {citation.field_value}
      </span>
    );
  }

  // Low confidence - show as clickable audit link
  return (
    <Link
      to={citation.audit_link}
      className={`inline-flex items-center px-2 py-1 text-xs rounded bg-${confidenceColor}-100 text-${confidenceColor}-800 hover:bg-${confidenceColor}-200 border border-${confidenceColor}-300`}
    >
      <ExclamationTriangleIcon className="w-3 h-3 mr-1" />
      {citation.field_value}
      <span className="ml-1 text-xs opacity-75">
        ({Math.round(citation.confidence * 100)}%)
      </span>
      <span className="ml-1 text-xs underline">verify</span>
    </Link>
  );
}
```

#### B. Enhanced Answer Display

```tsx
// src/components/search/AnswerDisplay.tsx

interface AnswerDisplayProps {
  answerData: {
    answer: string;
    citations: Citation[];
    low_confidence_count: number;
    audit_recommended: boolean;
  };
}

export function AnswerDisplay({ answerData }: AnswerDisplayProps) {
  return (
    <div className="space-y-4">
      {/* Main answer */}
      <div className="prose max-w-none">
        <AnswerText text={answerData.answer} citations={answerData.citations} />
      </div>

      {/* Audit warning */}
      {answerData.audit_recommended && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Data Quality Notice
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>
                  This answer includes {answerData.low_confidence_count} field(s) with low confidence scores.
                  Click the highlighted values to review and verify the source data.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Citations list */}
      {answerData.citations.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-medium text-gray-700">
            Sources ({answerData.citations.length} field citations)
          </summary>
          <div className="mt-2 space-y-2">
            {answerData.citations.map((citation, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-mono text-xs text-gray-600">{citation.field_name}</span>
                  <span className="mx-2">→</span>
                  <CitationLink citation={citation} inline />
                </div>
                <div className="text-xs text-gray-500">
                  {citation.filename}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
```

---

## Analytics & Tracking

### Dashboard Metrics

Track audit link effectiveness:

```sql
-- Audit link click-through rate
SELECT
  query_source,
  COUNT(*) as total_citations,
  SUM(CASE WHEN audit_link_clicked THEN 1 ELSE 0 END) as clicks,
  SUM(CASE WHEN audit_completed_at IS NOT NULL THEN 1 ELSE 0 END) as completed,
  SUM(CASE WHEN correction_made THEN 1 ELSE 0 END) as corrections,
  ROUND(100.0 * SUM(CASE WHEN audit_link_clicked THEN 1 ELSE 0 END) / COUNT(*), 2) as ctr_pct
FROM field_citations
WHERE confidence_at_citation < 0.6
GROUP BY query_source;
```

### Quality Improvement Metrics

Track how citations improve data quality over time:

```sql
-- Fields that were corrected after being cited
SELECT
  ef.field_name,
  COUNT(DISTINCT fc.id) as times_cited,
  AVG(fc.confidence_at_citation) as avg_confidence,
  SUM(CASE WHEN fc.correction_made THEN 1 ELSE 0 END) as corrections_made,
  ROUND(100.0 * SUM(CASE WHEN fc.correction_made THEN 1 ELSE 0 END) / COUNT(*), 2) as correction_rate
FROM extracted_fields ef
JOIN field_citations fc ON fc.field_id = ef.id
WHERE fc.confidence_at_citation < 0.6
GROUP BY ef.field_name
ORDER BY corrections_made DESC
LIMIT 20;
```

---

## Migration Plan

### Phase 1: Backend Foundation (Week 1)
1. Add database schema (FieldCitation table, ExtractedField columns)
2. Implement CitationTracker service
3. Create audit link endpoint
4. Add unit tests

### Phase 2: Integration (Week 2)
5. Integrate with ClaudeService
6. Update Ask AI endpoint
7. Update MCP RAG endpoint
8. Add citation tracking to analytics

### Phase 3: Frontend (Week 3)
9. Build CitationLink component
10. Enhance AnswerDisplay component
11. Update Audit page to accept citation_id parameter
12. Add audit link tracking events

### Phase 4: Polish & Monitoring (Week 4)
13. Add analytics dashboard for audit links
14. Performance testing with high-citation answers
15. Documentation and examples
16. User testing and iteration

---

## Configuration

Add to settings:

```python
# app/models/settings.py

DEFAULT_SETTINGS = {
    # ... existing settings ...

    # Citation & Audit Links
    "citation_tracking_enabled": {
        "value": True,
        "type": "boolean",
        "description": "Track field usage in AI answers",
        "category": "audit"
    },
    "citation_audit_threshold": {
        "value": 0.6,
        "type": "float",
        "description": "Confidence threshold for audit link injection",
        "category": "audit",
        "min": 0.0,
        "max": 1.0
    },
    "citation_context_chars": {
        "value": 100,
        "type": "integer",
        "description": "Characters of context to save for citations",
        "category": "audit"
    }
}
```

---

## Example Usage

### Ask AI Query

**User asks:** "What are the total amounts from Acme Corp invoices last month?"

**Response:**
```json
{
  "answer": "Found 3 invoices from Acme Corp last month totaling $5,420.00. The invoices were for $2,100.00, $1,850.00, and $1,470.00.",
  "citations": [
    {
      "field_name": "invoice_total",
      "field_value": "$2,100.00",
      "confidence": 0.58,
      "needs_audit": true,
      "audit_link": "/audit?field_id=123&document_id=45&highlight=true&source=ask_ai",
      "filename": "acme_invoice_jan.pdf"
    },
    {
      "field_name": "invoice_total",
      "field_value": "$1,850.00",
      "confidence": 0.92,
      "needs_audit": false,
      "filename": "acme_invoice_feb.pdf"
    },
    {
      "field_name": "invoice_total",
      "field_value": "$1,470.00",
      "confidence": 0.64,
      "needs_audit": true,
      "audit_link": "/audit?field_id=125&document_id=47&highlight=true&source=ask_ai",
      "filename": "acme_invoice_mar.pdf"
    }
  ],
  "low_confidence_count": 2,
  "audit_recommended": true
}
```

**Frontend renders:**

> Found 3 invoices from Acme Corp last month totaling **$5,420.00**. The invoices were for **[$2,100.00* (58%)](verify)**, **$1,850.00**, and **[$1,470.00* (64%)](verify)**.
>
> ⚠️ **Data Quality Notice:** This answer includes 2 field(s) with low confidence scores. Click the highlighted values to review and verify.

---

## Benefits

1. **Proactive Quality Control** - Users see data quality issues immediately
2. **Seamless Verification** - One click to audit source
3. **Improved Trust** - Transparent confidence scores
4. **Analytics Goldmine** - Track which data needs most attention
5. **Feedback Loop** - Corrections improve future extractions
6. **MCP-Ready** - Works for both UI and programmatic access

---

## Security Considerations

- **Authorization**: Audit links respect document permissions (check `created_by_user_id`)
- **Rate Limiting**: Prevent abuse of citation tracking endpoints
- **Privacy**: Don't expose field values in URLs (use field_id)
- **Audit Trail**: Log all audit link clicks for compliance

---

## Testing Strategy

### Unit Tests
- CitationTracker field matching logic
- Confidence threshold logic
- Audit link generation

### Integration Tests
- End-to-end: Query → Answer → Citations → Audit
- MCP endpoint citation format
- Permission checks on audit links

### E2E Tests
- User clicks audit link → Audit page loads correctly
- Verify correction updates citation record
- Analytics dashboard shows citation metrics

---

## Future Enhancements

1. **Smart Citation Formatting** - Inject inline citations in markdown format
2. **Bulk Audit** - "Verify all low-confidence fields in this answer"
3. **Citation Heatmap** - Visualize which fields are most/least reliable
4. **Predictive Audit** - Suggest audit before user asks query
5. **Citation Explanations** - "Why is this low confidence?"
6. **Auto-correction** - Learn from verifications to improve extractions

---

**Status**: Design Complete
**Next Step**: Phase 1 Implementation (Database Schema + Citation Tracker)
**Owner**: Backend Team
**Timeline**: 4 weeks (aggressive), 6 weeks (comfortable)
