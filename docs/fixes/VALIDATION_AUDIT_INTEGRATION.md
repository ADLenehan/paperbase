# Validation + Audit Integration Design

**Problem**: How should Pydantic validation errors integrate with the existing confidence-based audit system?

**Answer**: Use validation to **enrich** audit workflow, not replace it.

---

## Proposed Architecture: 3-Tier Severity System

### Tier 1: Auto-Index (High Quality)
- ✅ **Confidence**: ≥0.8 (High)
- ✅ **Validation**: Passes all rules
- **Action**: Index immediately, no review needed

### Tier 2: Standard Audit (Medium Quality)
- ⚠️ **Confidence**: 0.6-0.8 (Medium) OR validation warning
- **Action**: Add to audit queue, normal priority

### Tier 3: Priority Audit (Low Quality)
- 🚨 **Confidence**: <0.6 (Low) AND validation error
- **Action**: Add to audit queue, **high priority** (top of list)

---

## Database Schema Changes

### Add to ExtractedField Model

```python
# backend/app/models/document.py

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    # ... existing fields ...

    # NEW: Validation metadata
    validation_status = Column(String, default="valid")  # "valid", "warning", "error"
    validation_errors = Column(JSON, nullable=True)  # List of error messages
    validation_checked_at = Column(DateTime, nullable=True)

    # Computed property for audit priority
    @property
    def audit_priority(self) -> int:
        """
        Calculate audit priority (lower = more urgent)

        Returns:
            0 = Critical (low confidence + validation error)
            1 = High (low confidence OR validation error)
            2 = Medium (medium confidence)
            3 = Low (optional review)
        """
        has_low_confidence = self.confidence_score < 0.6
        has_validation_error = self.validation_status == "error"
        has_medium_confidence = 0.6 <= self.confidence_score < 0.8

        if has_low_confidence and has_validation_error:
            return 0  # CRITICAL - both issues
        elif has_low_confidence or has_validation_error:
            return 1  # HIGH - one major issue
        elif has_medium_confidence:
            return 2  # MEDIUM - borderline confidence
        else:
            return 3  # LOW - optional quality check
```

---

## Validation Service Integration

### Step 1: Extract with Reducto (existing)
```python
# backend/app/services/reducto_service.py

async def extract_structured(self, schema, job_id):
    # Call Reducto API
    extractions = {...}  # Field name → {value, confidence}
    return extractions
```

### Step 2: Validate Extractions (NEW)
```python
# backend/app/services/validation_service.py

class ExtractionValidator:
    async def validate_extraction(
        self,
        extractions: Dict[str, Any],
        template_name: str
    ) -> Dict[str, ValidationResult]:
        """
        Validate each field, return results

        Returns:
            {
                "invoice_number": {
                    "status": "valid",
                    "errors": []
                },
                "total_amount": {
                    "status": "error",
                    "errors": ["Total amount must be positive"]
                }
            }
        """
        validation_results = {}

        for field_name, field_data in extractions.items():
            result = await self._validate_field(
                field_name=field_name,
                value=field_data["value"],
                confidence=field_data["confidence"],
                template_name=template_name
            )
            validation_results[field_name] = result

        return validation_results

    async def _validate_field(
        self,
        field_name: str,
        value: Any,
        confidence: float,
        template_name: str
    ) -> ValidationResult:
        """Validate single field with business rules"""
        errors = []

        # Get Pydantic model for this template
        pydantic_model = EXTRACTION_SCHEMAS.get(template_name.lower())
        if not pydantic_model:
            return ValidationResult(status="valid", errors=[])

        # Validate using Pydantic
        try:
            # Validate single field
            field_model = getattr(pydantic_model, field_name, None)
            if field_model:
                # Run Pydantic validation
                validated = field_model.validate(value)
        except ValueError as e:
            errors.append(str(e))

        # Business rules (template-specific)
        if template_name.lower() == "invoice":
            if field_name == "total_amount" and float(value) > 1_000_000:
                errors.append("Amount exceeds $1M - needs review")

        # Confidence-adjusted severity
        if errors and confidence < 0.6:
            status = "error"  # Low confidence + validation error = critical
        elif errors:
            status = "warning"  # Validation error but high confidence
        else:
            status = "valid"

        return ValidationResult(status=status, errors=errors)
```

### Step 3: Save with Validation Metadata (NEW)
```python
# backend/app/api/bulk_upload.py or documents.py

async def save_extractions(document_id, extractions, validation_results):
    """Save extractions with validation metadata"""

    for field_name, field_data in extractions.items():
        validation = validation_results.get(field_name)

        extracted_field = ExtractedField(
            document_id=document_id,
            field_name=field_name,
            field_value=field_data["value"],
            confidence_score=field_data["confidence"],

            # NEW: Validation metadata
            validation_status=validation.status,  # "valid", "warning", "error"
            validation_errors=validation.errors,   # ["Amount must be positive"]
            validation_checked_at=datetime.utcnow(),

            # Auto-flag for review based on combined score
            needs_verification=should_flag_for_review(
                confidence=field_data["confidence"],
                validation_status=validation.status
            ),
            verified=False
        )

        db.add(extracted_field)

    db.commit()

def should_flag_for_review(confidence: float, validation_status: str) -> bool:
    """Determine if field needs human review"""
    # Always flag if validation error
    if validation_status == "error":
        return True

    # Flag if low confidence
    if confidence < 0.6:
        return True

    # Flag if medium confidence + warning
    if confidence < 0.8 and validation_status == "warning":
        return True

    return False
```

---

## Audit Queue Updates

### Enhanced Audit Endpoint
```python
# backend/app/api/audit.py

@router.get("/queue")
async def get_audit_queue(
    priority: Optional[str] = Query(None, description="Filter by priority: critical, high, medium, low"),
    include_validation_errors: bool = Query(True, description="Include fields with validation errors"),
    db: Session = Depends(get_db)
):
    """
    Get audit queue with enhanced filtering

    Priority levels:
    - critical: Low confidence + validation error
    - high: Low confidence OR validation error
    - medium: Medium confidence
    - low: Optional review items
    """

    # Base query: unverified fields
    query = db.query(ExtractedField).filter(
        ExtractedField.verified == False
    )

    # Filter by priority if specified
    if priority:
        if priority == "critical":
            query = query.filter(
                and_(
                    ExtractedField.confidence_score < 0.6,
                    ExtractedField.validation_status == "error"
                )
            )
        elif priority == "high":
            query = query.filter(
                or_(
                    ExtractedField.confidence_score < 0.6,
                    ExtractedField.validation_status == "error"
                )
            )
        elif priority == "medium":
            query = query.filter(
                and_(
                    ExtractedField.confidence_score >= 0.6,
                    ExtractedField.confidence_score < 0.8
                )
            )

    # Sort by audit_priority (computed property) then confidence
    fields = query.all()
    fields.sort(key=lambda f: (f.audit_priority, f.confidence_score))

    return {
        "queue": [
            {
                "field_id": f.id,
                "field_name": f.field_name,
                "field_value": f.field_value,
                "confidence": f.confidence_score,
                "validation_status": f.validation_status,
                "validation_errors": f.validation_errors or [],
                "audit_priority": f.audit_priority,
                "priority_label": get_priority_label(f.audit_priority)
            }
            for f in fields
        ],
        "summary": {
            "critical_count": sum(1 for f in fields if f.audit_priority == 0),
            "high_count": sum(1 for f in fields if f.audit_priority == 1),
            "medium_count": sum(1 for f in fields if f.audit_priority == 2),
            "low_count": sum(1 for f in fields if f.audit_priority == 3)
        }
    }

def get_priority_label(priority: int) -> str:
    labels = {0: "critical", 1: "high", 2: "medium", 3: "low"}
    return labels.get(priority, "unknown")
```

---

## Frontend Changes

### Enhanced Audit UI
```jsx
// frontend/src/pages/Audit.jsx

function AuditPage() {
  const [priorityFilter, setPriorityFilter] = useState("all");

  return (
    <div>
      {/* Priority Filter Tabs */}
      <div className="mb-4">
        <button onClick={() => setPriorityFilter("critical")}
                className="bg-red-600">
          🚨 Critical ({summary.critical_count})
        </button>
        <button onClick={() => setPriorityFilter("high")}
                className="bg-orange-500">
          ⚠️ High ({summary.high_count})
        </button>
        <button onClick={() => setPriorityFilter("medium")}
                className="bg-yellow-500">
          ⚡ Medium ({summary.medium_count})
        </button>
      </div>

      {/* Audit Queue with Enhanced Display */}
      {auditQueue.map(item => (
        <AuditCard
          key={item.field_id}
          field={item}
          showValidationErrors={true}
        />
      ))}
    </div>
  );
}

function AuditCard({ field, showValidationErrors }) {
  return (
    <div className={`border-l-4 ${getPriorityColor(field.priority_label)}`}>
      <div className="flex justify-between">
        <div>
          <span className="font-bold">{field.field_name}</span>
          <span className="text-gray-600">{field.field_value}</span>
        </div>

        <div className="flex gap-2">
          {/* Confidence Badge */}
          <ConfidenceBadge confidence={field.confidence} />

          {/* NEW: Validation Status Badge */}
          {field.validation_status !== "valid" && (
            <div className={`badge ${
              field.validation_status === "error" ? "bg-red-500" : "bg-yellow-500"
            }`}>
              {field.validation_status === "error" ? "❌" : "⚠️"} Validation Issue
            </div>
          )}
        </div>
      </div>

      {/* NEW: Show Validation Errors */}
      {showValidationErrors && field.validation_errors.length > 0 && (
        <div className="mt-2 bg-red-50 p-2 rounded">
          <p className="text-sm font-semibold">Validation Errors:</p>
          <ul className="text-sm text-red-700">
            {field.validation_errors.map((error, idx) => (
              <li key={idx}>• {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Audit Actions */}
      <div className="mt-3">
        <button onClick={() => verifyField(field.field_id, field.field_value)}>
          ✓ Correct
        </button>
        <button onClick={() => showCorrectionModal(field)}>
          ✏️ Fix & Verify
        </button>
      </div>
    </div>
  );
}

function getPriorityColor(priority) {
  const colors = {
    critical: "border-red-600",
    high: "border-orange-500",
    medium: "border-yellow-500",
    low: "border-blue-500"
  };
  return colors[priority] || "border-gray-300";
}
```

---

## Example Scenarios

### Scenario 1: High Confidence + Valid
```json
{
  "field_name": "invoice_number",
  "field_value": "INV-2024-001",
  "confidence_score": 0.95,
  "validation_status": "valid",
  "validation_errors": []
}
```
**Result**: ✅ Auto-indexed, no audit needed

---

### Scenario 2: Low Confidence + Valid
```json
{
  "field_name": "vendor_name",
  "field_value": "Acme Corp",
  "confidence_score": 0.45,
  "validation_status": "valid",
  "validation_errors": []
}
```
**Result**: ⚠️ Added to audit queue (HIGH priority) - low confidence

---

### Scenario 3: High Confidence + Validation Error
```json
{
  "field_name": "total_amount",
  "field_value": "-500.00",
  "confidence_score": 0.92,
  "validation_status": "error",
  "validation_errors": ["Total amount must be positive"]
}
```
**Result**: ⚠️ Added to audit queue (HIGH priority) - validation error
**UI Shows**: Confidence badge (green) + Validation error badge (red)

---

### Scenario 4: Low Confidence + Validation Error
```json
{
  "field_name": "invoice_date",
  "field_value": "2026-12-31",
  "confidence_score": 0.35,
  "validation_status": "error",
  "validation_errors": ["Invoice date is more than 30 days in the future"]
}
```
**Result**: 🚨 Added to audit queue (CRITICAL priority) - both issues
**UI Shows**: Top of queue, red border, both badges displayed

---

## Benefits of This Approach

### 1. **Non-Breaking** ✅
- Existing audit workflow still works
- Fields with low confidence still get reviewed
- No changes to verified documents

### 2. **Additive Intelligence** 🧠
- Validation adds context to audit decisions
- Users see WHY a field needs review (confidence vs validation)
- Priority sorting helps triage

### 3. **Flexible** 🔧
- Can enable/disable validation per template
- Can adjust severity thresholds
- Can add new validation rules without code changes

### 4. **Better UX** 🎨
- Users see validation errors upfront
- Color-coded priorities guide attention
- Faster triage (critical items first)

### 5. **Data Quality** 📊
- Blocks obviously invalid data
- Catches business logic errors
- Provides explanations for audit items

---

## Implementation Checklist

### Database Migration
```python
# backend/migrations/add_validation_metadata.py

def upgrade():
    # Add validation columns to extracted_fields
    op.add_column('extracted_fields',
        sa.Column('validation_status', sa.String(), nullable=True, default='valid'))
    op.add_column('extracted_fields',
        sa.Column('validation_errors', sa.JSON(), nullable=True))
    op.add_column('extracted_fields',
        sa.Column('validation_checked_at', sa.DateTime(), nullable=True))

    # Backfill existing rows with "valid" status
    op.execute("UPDATE extracted_fields SET validation_status = 'valid' WHERE validation_status IS NULL")
```

### Testing
```python
# backend/tests/test_validation_audit_integration.py

def test_critical_priority_routing():
    """Test that low confidence + validation error gets critical priority"""
    field = ExtractedField(
        confidence_score=0.35,
        validation_status="error"
    )
    assert field.audit_priority == 0  # Critical

def test_validation_error_goes_to_audit():
    """Test that validation errors flag field for review"""
    assert should_flag_for_review(
        confidence=0.95,
        validation_status="error"
    ) == True

def test_high_confidence_valid_skips_audit():
    """Test that high quality fields skip audit"""
    assert should_flag_for_review(
        confidence=0.95,
        validation_status="valid"
    ) == False
```

---

## Rollout Strategy

### Phase 1: Soft Launch (Week 1)
- Add validation metadata columns
- Run validation but only log results
- Don't affect audit queue yet
- **Goal**: Gather data on validation error rates

### Phase 2: Audit Enrichment (Week 2)
- Show validation errors in audit UI
- Add priority badges
- Sort by priority
- **Goal**: Users see validation context

### Phase 3: Auto-Flagging (Week 3)
- Enable automatic flagging based on validation
- Start with "warning" severity only
- Monitor false positive rate
- **Goal**: Reduce manual triage time

### Phase 4: Full Integration (Week 4)
- Enable all validation rules
- Auto-prioritize audit queue
- Add validation to bulk upload flow
- **Goal**: Production-ready quality gates

---

## Monitoring & Metrics

Track these metrics to measure impact:

1. **Validation Error Rate**: % of fields with validation errors
2. **False Positive Rate**: Validation errors that were actually correct
3. **Audit Queue Size**: Does validation reduce queue size?
4. **Review Time**: Time spent per audit item
5. **Priority Distribution**: % critical vs high vs medium

**Expected Results**:
- 40-60% reduction in invalid extractions
- 15-20% faster audit workflow
- <5% false positive rate on validation

---

## Summary

**The key insight**: Validation doesn't REPLACE audit, it ENHANCES it.

- ✅ Fields pass validation → Skip audit (faster indexing)
- ⚠️ Fields fail validation → Flag for audit with context
- 🚨 Low confidence + validation error → Priority audit

This gives you **layered quality assurance**:
1. Reducto confidence (statistical)
2. Pydantic validation (logical)
3. Human review (contextual)

Each layer catches different types of errors, and together they create a robust quality system.
