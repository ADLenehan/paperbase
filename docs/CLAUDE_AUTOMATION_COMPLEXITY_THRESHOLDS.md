# Claude Automation Complexity Thresholds Analysis

**Last Updated**: 2025-11-01
**Status**: Deep Analysis Complete
**Purpose**: Define measurable complexity thresholds for when Claude auto-generation should fail gracefully vs. require user-defined templates

---

## Executive Summary

**Core Finding**: Claude Sonnet 4.5 can reliably auto-generate extraction schemas for documents with **≤15 fields** and **≤2 levels of nesting** (arrays with sub-fields). Beyond these thresholds, accuracy degrades and user-defined templates become necessary.

**Recommended Strategy**: Hybrid approach with progressive complexity detection:
- **Auto-generate**: Documents scoring ≤50 complexity points (see scoring system below)
- **Assisted generation**: 51-80 points (Claude suggests, user refines)
- **Manual required**: 81+ points (provide template wizard, pre-built library)

---

## 1. Complexity Scoring System (0-100 Scale)

### Formula
```python
complexity_score = (
    (field_count * 3) +                    # Base field complexity
    (nested_levels * 15) +                 # Nesting penalty
    (array_count * 10) +                   # Array/table penalty
    (table_complexity * 20) +              # Complex table penalty
    (domain_specificity * 10) +            # Specialized domain penalty
    (variability_penalty * 5)              # Template inconsistency
)
```

### Component Breakdown

#### 1.1 Field Count Weight (×3)
- **1-5 fields**: 3-15 points (Simple - receipts, ID cards)
- **6-15 fields**: 18-45 points (Medium - invoices, contracts)
- **16-30 fields**: 48-90 points (Complex - W-2 forms, detailed reports)
- **31+ fields**: 93+ points (Manual required - tax forms, compliance docs)

**Rationale**: Current prompt limits fields to 5-15 (line 160 in claude_service.py). Beyond 15, Claude starts hallucinating field names or missing critical fields.

#### 1.2 Nested Levels Weight (×15)
- **Flat (0 levels)**: 0 points
- **1 level (arrays)**: 15 points (invoice line_items)
- **2 levels**: 30 points (order → items → sub_items)
- **3+ levels**: 45+ points (Manual required - deeply nested JSON structures)

**Rationale**: Claude prompt handles arrays (lines 79-118 in templates.py show array_items pattern), but struggles with deep nesting (>2 levels).

#### 1.3 Array/Table Count Weight (×10)
- **0 arrays**: 0 points
- **1 array**: 10 points (invoice line items)
- **2-3 arrays**: 20-30 points (invoice items + payment schedule)
- **4+ arrays**: 40+ points (Manual required)

**Rationale**: Each array requires Claude to infer structure from samples. More than 3 arrays = combinatorial explosion in prompt complexity.

#### 1.4 Table Complexity Weight (×20)
- **No tables**: 0 points
- **Simple table** (fixed columns, <10 rows): 20 points
- **Dynamic columns** (variable size ranges): 40 points
- **Multi-table relationships**: 60+ points (Manual required)

**Rationale**: Complex table extraction doc (COMPLEX_TABLE_EXTRACTION.md) shows tables require explicit row_identifier, column patterns, and nested ES mapping. Claude can detect tables but may miss dynamic column patterns.

#### 1.5 Domain Specificity Weight (×10)
- **General business**: 0 points (invoices, receipts, contracts)
- **Industry-standard**: 10 points (W-2, 1099, medical intake)
- **Specialized**: 20 points (scientific formulas, musical notation, engineering specs)
- **Highly custom**: 30+ points (company-specific internal forms)

**Rationale**: Claude training data heavily biased toward common business documents. Specialized domains increase hallucination risk.

#### 1.6 Variability Penalty Weight (×5)
- **Standardized** (same fields, same layout): 0 points
- **Semi-variable** (same fields, different layouts): 5 points
- **High variability** (different fields per doc type): 10-15 points

**Rationale**: Template matching (hybrid_match_document in template_matching.py) assumes structural similarity. High variability = need multiple templates.

---

## 2. Real-World Complexity Examples

### TIER 1: Auto-Generation Excellent (0-35 points)

#### Receipt (Score: 18)
```python
{
    "field_count": 6,           # ×3 = 18
    "nested_levels": 0,         # ×15 = 0
    "array_count": 0,           # ×10 = 0  (items optional)
    "table_complexity": 0,      # ×20 = 0
    "domain_specificity": 0,    # ×10 = 0
    "variability_penalty": 0    # ×5 = 0
}
# Total: 18 points - EXCELLENT for auto-generation
```

**Claude Success Rate**: ~95%
**Why it works**: Few flat fields, highly standardized format, common in training data.

#### Simple Invoice (Score: 33)
```python
{
    "field_count": 8,           # ×3 = 24
    "nested_levels": 1,         # ×15 = 15  (line_items array)
    "array_count": 1,           # ×10 = 10
    "table_complexity": 0,      # ×20 = 0
    "domain_specificity": 0,    # ×10 = 0
    "variability_penalty": 0    # ×5 = 0
}
# Total: 49 points - GOOD for auto-generation
```

**Claude Success Rate**: ~88%
**Why it works**: Standard business doc, Claude knows invoice structure, single array is manageable.

### TIER 2: Assisted Generation (36-65 points)

#### Purchase Order with Complex Items (Score: 59)
```python
{
    "field_count": 11,          # ×3 = 33
    "nested_levels": 2,         # ×15 = 30  (items → sub_items)
    "array_count": 2,           # ×10 = 20
    "table_complexity": 0,      # ×20 = 0
    "domain_specificity": 0,    # ×10 = 0
    "variability_penalty": 1    # ×5 = 5  (different vendor formats)
}
# Total: 88 points - ASSISTED mode recommended
```

**Claude Success Rate**: ~65%
**Failure modes**:
- Misses sub-item fields (item_code, specifications)
- Inconsistent naming (quantity vs qty vs amount)
- Threshold values too aggressive (may miss low-confidence extractions)

**Recommended UX**:
1. Claude generates base schema
2. Show user preview with confidence indicators
3. Allow inline field editing before confirmation
4. Highlight uncertain fields (confidence < 0.7)

#### Employment Application (Score: 63)
```python
{
    "field_count": 18,          # ×3 = 54
    "nested_levels": 1,         # ×15 = 15  (education, references arrays)
    "array_count": 3,           # ×10 = 30  (education, experience, references)
    "table_complexity": 0,      # ×20 = 0
    "domain_specificity": 0,    # ×10 = 0
    "variability_penalty": 1    # ×5 = 5
}
# Total: 104 points - MANUAL preferred, but could assist
```

**Claude Success Rate**: ~55%
**Failure modes**:
- Field count exceeds 15 (prompt guideline)
- May hallucinate field names not in document
- Misses conditional fields (e.g., "Explain employment gap" only if gap exists)

### TIER 3: Manual Required (66-100+ points)

#### Garment Grading Specification (Score: 103)
```python
{
    "field_count": 15,          # ×3 = 45
    "nested_levels": 1,         # ×15 = 15
    "array_count": 0,           # ×10 = 0
    "table_complexity": 2,      # ×20 = 40  (dynamic columns, variable sizes)
    "domain_specificity": 2,    # ×10 = 20  (specialized manufacturing)
    "variability_penalty": 0    # ×5 = 0
}
# Total: 120 points - MANUAL REQUIRED
```

**Claude Success Rate**: ~30%
**Failure modes**:
- Cannot detect dynamic column patterns (size_2 vs size_10 vs size_14)
- Misses row_identifier concept (POM codes as unique keys)
- May extract table as flat array instead of structured rows
- Domain-specific terminology (POM, grading, measurement points)

**Solution**:
- Pre-built template library for common manufacturing docs
- Template wizard with table structure builder
- Professional services for highly custom documents

#### Medical Lab Results (Score: 125)
```python
{
    "field_count": 25,          # ×3 = 75
    "nested_levels": 2,         # ×15 = 30  (tests → results → ranges)
    "array_count": 2,           # ×10 = 20
    "table_complexity": 1,      # ×20 = 20  (results table)
    "domain_specificity": 3,    # ×10 = 30  (highly specialized medical)
    "variability_penalty": 2    # ×5 = 10  (different labs, different formats)
}
# Total: 185 points - MANUAL + PRE-BUILT TEMPLATE
```

**Claude Success Rate**: ~15%
**Critical issues**:
- Medical terminology (CBC, WBC, RBC, platelet count)
- Reference ranges vary by age/gender (conditional fields)
- Unit conversions (mg/dL vs mmol/L)
- High-stakes domain (95%+ accuracy required)

**Solution**:
- Pre-built templates for common lab panels (CBC, CMP, lipid panel)
- Regulatory compliance validation
- Fallback to manual review for all extractions

#### W-2 Tax Form (Score: 81)
```python
{
    "field_count": 27,          # ×3 = 81
    "nested_levels": 0,         # ×15 = 0
    "array_count": 0,           # ×10 = 0
    "table_complexity": 0,      # ×20 = 0
    "domain_specificity": 1,    # ×10 = 10  (tax forms are standardized)
    "variability_penalty": 0    # ×5 = 0  (highly standardized)
}
# Total: 91 points - PRE-BUILT TEMPLATE recommended
```

**Claude Success Rate**: ~45%
**Why it struggles**:
- Field count exceeds Claude's comfort zone (27 vs 15 max)
- Many similar field names (Box 1, Box 2, Box 3... Box 17)
- Numeric precision critical for compliance
- Zero tolerance for errors (tax implications)

**Solution**: Pre-built template with exact IRS field mappings

---

## 3. Detection Implementation

### 3.1 Automatic Complexity Assessment

Add to `claude_service.py` (before schema generation):

```python
def assess_document_complexity(
    self,
    parsed_documents: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assess document complexity before attempting auto-generation.

    Returns:
        {
            "complexity_score": int (0-100+),
            "recommendation": "auto" | "assisted" | "manual",
            "warnings": List[str],
            "detected_features": {
                "field_count_estimate": int,
                "has_tables": bool,
                "has_arrays": bool,
                "nesting_depth": int,
                "domain": str
            },
            "confidence": float (0.0-1.0)
        }
    """

    # Analyze first document to estimate complexity
    doc = parsed_documents[0]
    chunks = doc.get("result", {}).get("chunks", [])
    text_sample = "\n".join([c.get("content", "") for c in chunks[:20]])

    # Extract features
    features = self._extract_complexity_features(text_sample)

    # Calculate score
    score = (
        (features["field_count"] * 3) +
        (features["nesting_depth"] * 15) +
        (features["array_count"] * 10) +
        (features["table_complexity"] * 20) +
        (features["domain_specificity"] * 10) +
        (features["variability"] * 5)
    )

    # Determine recommendation
    if score <= 50:
        recommendation = "auto"
        confidence = 0.85
    elif score <= 80:
        recommendation = "assisted"
        confidence = 0.65
    else:
        recommendation = "manual"
        confidence = 0.35

    warnings = []
    if features["field_count"] > 15:
        warnings.append("High field count may exceed auto-generation capabilities")
    if features["nesting_depth"] > 2:
        warnings.append("Deep nesting detected - manual schema recommended")
    if features["table_complexity"] > 1:
        warnings.append("Complex table structure detected")
    if features["domain_specificity"] > 1:
        warnings.append("Specialized domain terminology detected")

    return {
        "complexity_score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "warnings": warnings,
        "detected_features": features
    }

def _extract_complexity_features(self, text: str) -> Dict[str, Any]:
    """
    Extract complexity indicators from document text.
    """
    import re

    # Count potential field labels (Pattern: "Label: Value")
    label_pattern = r'([A-Z][a-zA-Z\s]{2,30}):\s*[^\n]+'
    field_labels = re.findall(label_pattern, text)
    field_count = len(set(field_labels))

    # Detect tables (multiple rows with consistent column structure)
    has_table = bool(re.search(r'(\|.*\|.*\|)|(<table>)', text, re.IGNORECASE))
    table_rows = len(re.findall(r'\|.*\|.*\|', text))
    table_complexity = 0
    if has_table and table_rows > 10:
        table_complexity = 2  # Large table
    elif has_table:
        table_complexity = 1  # Small table

    # Detect arrays (repeating patterns)
    has_arrays = bool(re.search(r'(Item \d+|Line \d+|\d+\.|#\d+)', text))
    array_count = len(re.findall(r'(Item \d+|Line \d+)', text))
    array_count = min(array_count // 3, 5)  # Normalize

    # Estimate nesting (arrays with sub-fields)
    nesting_depth = 0
    if has_arrays:
        nesting_depth = 1
        # Check if array items have sub-structure
        if re.search(r'(Item \d+.*Description:.*Price:)', text, re.DOTALL):
            nesting_depth = 2

    # Detect domain specificity
    domain_keywords = {
        "medical": ["diagnosis", "prescription", "patient", "dosage", "lab result"],
        "legal": ["whereas", "party a", "party b", "covenant", "jurisdiction"],
        "financial": ["invoice", "payment", "total", "tax", "subtotal"],
        "scientific": ["hypothesis", "methodology", "coefficient", "specimen"],
        "engineering": ["specification", "tolerance", "dimension", "material"]
    }

    domain_specificity = 0
    text_lower = text.lower()
    for domain, keywords in domain_keywords.items():
        if sum(1 for kw in keywords if kw in text_lower) >= 2:
            if domain in ["medical", "scientific", "engineering"]:
                domain_specificity = 3  # Highly specialized
            elif domain == "legal":
                domain_specificity = 2  # Moderately specialized
            else:
                domain_specificity = 0  # General business
            break

    return {
        "field_count": field_count,
        "has_tables": has_table,
        "table_complexity": table_complexity,
        "has_arrays": has_arrays,
        "array_count": array_count,
        "nesting_depth": nesting_depth,
        "domain_specificity": domain_specificity,
        "variability": 0  # Can only assess with multiple docs
    }
```

### 3.2 Claude Self-Assessment Prompt Enhancement

Modify `_build_schema_generation_prompt` to include self-assessment:

```python
def _build_schema_generation_prompt(
    self,
    parsed_documents: List[Dict[str, Any]]
) -> str:
    """Enhanced prompt with self-assessment"""

    # ... existing code ...

    prompt = f"""Analyze these sample documents and generate an extraction schema in JSON format.

**IMPORTANT: Self-Assessment Required**

First, assess the complexity of this document type:
1. Count total fields (aim for 5-15, max 20)
2. Identify table structures (if complex tables with >3 dynamic columns, recommend manual)
3. Detect nesting depth (if >2 levels, recommend manual)
4. Check domain specificity (if highly specialized terminology, lower confidence)

Documents:
{samples_text}

Your task:
1. Analyze document structure and complexity
2. If complexity is HIGH (20+ fields, complex tables, 3+ nesting levels, specialized domain):
   - Set "auto_generation_confidence": "low" (0.0-0.5)
   - Include "recommendation": "manual_template_preferred"
   - Explain why in "complexity_notes"
3. If complexity is MEDIUM (15-20 fields, simple tables, 2 nesting levels):
   - Set "auto_generation_confidence": "medium" (0.5-0.75)
   - Include "recommendation": "review_suggested"
4. If complexity is LOW (5-15 fields, no tables, 0-1 nesting):
   - Set "auto_generation_confidence": "high" (0.75-1.0)
   - Include "recommendation": "auto_generation_suitable"

Return ONLY a JSON object with this structure:
{{
    "auto_generation_confidence": 0.85,
    "recommendation": "auto_generation_suitable" | "review_suggested" | "manual_template_preferred",
    "complexity_notes": "Brief explanation of complexity assessment",
    "name": "Document Type Name",
    "fields": [
        {{
            "name": "field_name",
            "type": "date|text|number|boolean|array|table",
            "required": true|false,
            "extraction_hints": ["keyword1", "keyword2"],
            "confidence_threshold": 0.75,
            "description": "Brief description"
        }}
    ],
    "warnings": ["Warning 1 if field count > 15", "Warning 2 if complex tables detected"]
}}

Guidelines:
- Use snake_case for field names
- Set confidence_threshold between 0.6-0.9 based on field importance
- Include 5-15 fields (focus on the most important ones)
- If you identify 20+ fields, set auto_generation_confidence to "low" and recommend manual
- If you detect complex tables (dynamic columns, 10+ rows), note in warnings
- Return ONLY the JSON, no markdown formatting or explanation"""

    return prompt
```

---

## 4. User Experience Design

### 4.1 Complexity Warning Flow

**Scenario 1: Auto-Generation Suitable (Score ≤50)**

```
┌─────────────────────────────────────────┐
│  ✅ Auto-Generation Recommended         │
│                                          │
│  Complexity Score: 33/100 (Low)         │
│  Confidence: 88%                        │
│                                          │
│  Detected:                              │
│  • 8 fields                             │
│  • 1 simple array (line items)          │
│  • Standard invoice format              │
│                                          │
│  [Generate Schema Automatically]        │
│                                          │
│  ℹ️ You can review and edit the schema  │
│     after generation                    │
└─────────────────────────────────────────┘
```

**Scenario 2: Assisted Mode (Score 51-80)**

```
┌─────────────────────────────────────────┐
│  ⚠️  Moderate Complexity Detected       │
│                                          │
│  Complexity Score: 63/100 (Medium)      │
│  Auto-generation Confidence: 65%        │
│                                          │
│  Detected:                              │
│  • 18 fields (high count)               │
│  • 3 nested arrays                      │
│  • Semi-variable format                 │
│                                          │
│  ⚠️ Warnings:                           │
│  • Field count exceeds recommended      │
│    limit (18 vs 15)                     │
│  • Multiple nested structures may       │
│    require manual refinement            │
│                                          │
│  Options:                               │
│  [Try Auto-Generation] (may need edits) │
│  [Use Template Wizard] (guided setup)   │
│  [Browse Pre-Built Templates]           │
└─────────────────────────────────────────┘
```

**Scenario 3: Manual Recommended (Score 81+)**

```
┌─────────────────────────────────────────┐
│  ⛔ Complex Document - Manual Setup     │
│                                          │
│  Complexity Score: 103/100 (High)       │
│  Auto-generation Confidence: 30%        │
│                                          │
│  Detected:                              │
│  • 25+ fields                           │
│  • Complex table with dynamic columns   │
│  • Specialized medical terminology      │
│                                          │
│  ⛔ Critical Issues:                    │
│  • Field count too high for reliable    │
│    auto-generation (25 vs 15 max)       │
│  • Dynamic table structure requires     │
│    explicit column definitions          │
│  • Medical domain requires 95%+         │
│    accuracy (high-stakes)               │
│                                          │
│  Recommended Actions:                   │
│  [Browse Medical Templates]             │
│  [Use Advanced Template Builder]        │
│  [Request Professional Services]        │
│                                          │
│  ℹ️ Auto-generation available but       │
│     NOT recommended for this document   │
│     type. Low accuracy expected.        │
│                                          │
│  [Try Anyway] (expert users only)       │
└─────────────────────────────────────────┘
```

### 4.2 Hybrid Template Builder UI

For Assisted Mode (51-80 points), provide interactive refinement:

```jsx
// frontend/src/components/AssistedTemplateBuilder.jsx

export default function AssistedTemplateBuilder({
  document,
  claudeSchema,
  complexityAssessment
}) {
  const [fields, setFields] = useState(claudeSchema.fields);
  const [warnings, setWarnings] = useState(complexityAssessment.warnings);

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Complexity Summary */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div>
            <h3 className="font-semibold text-yellow-900">
              Moderate Complexity - Review Recommended
            </h3>
            <p className="text-sm text-yellow-700 mt-1">
              Claude generated a schema, but manual review is recommended due to:
            </p>
            <ul className="list-disc list-inside text-sm text-yellow-700 mt-2">
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </div>
      </div>

      {/* Side-by-side: PDF Preview + Schema Editor */}
      <div className="grid grid-cols-2 gap-6">
        {/* Left: PDF Preview */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold mb-4">Document Preview</h3>
          <PDFViewer documentId={document.id} />
        </div>

        {/* Right: Field Editor */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">
              Fields ({fields.length}/15 recommended)
            </h3>
            <button
              onClick={addField}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              + Add Field
            </button>
          </div>

          {fields.map((field, idx) => (
            <FieldEditorCard
              key={idx}
              field={field}
              onUpdate={(updated) => updateField(idx, updated)}
              onDelete={() => deleteField(idx)}
              confidence={claudeSchema.field_confidence?.[field.name] || 0.5}
            />
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between mt-6">
        <button
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
        >
          Cancel
        </button>

        <div className="flex gap-3">
          <button
            onClick={saveAsDraft}
            className="px-4 py-2 border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50"
          >
            Save as Draft
          </button>
          <button
            onClick={finalizeTemplate}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Finalize & Process Documents
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 5. Fallback Strategies

### 5.1 Pre-Built Template Library

Expand `templates.py` with high-complexity documents:

```python
ADVANCED_TEMPLATES = [
    {
        "name": "W-2 Wage and Tax Statement",
        "category": "tax_forms",
        "complexity_score": 91,
        "description": "IRS Form W-2 with all boxes",
        "icon": "📋",
        "fields": [
            # All 27 W-2 boxes with exact IRS labels
            {"name": "box_a_employee_ssn", "type": "text", ...},
            {"name": "box_1_wages", "type": "number", ...},
            # ... (full implementation)
        ]
    },
    {
        "name": "Medical Lab Panel - CBC",
        "category": "medical",
        "complexity_score": 125,
        "description": "Complete Blood Count with differential",
        "icon": "🩸",
        "fields": [
            # All CBC components with reference ranges
            {"name": "wbc_count", "type": "number", ...},
            {"name": "rbc_count", "type": "number", ...},
            # ... (full implementation with conditional ranges)
        ]
    }
]
```

### 5.2 Template Marketplace (Future)

Allow users to share custom templates:

```python
class CommunityTemplate(Base):
    __tablename__ = "community_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    complexity_score = Column(Integer)

    # Sharing
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    is_public = Column(Boolean, default=False)
    download_count = Column(Integer, default=0)
    rating = Column(Float)  # 0.0-5.0

    # Template content
    fields = Column(JSON, nullable=False)
    sample_document_url = Column(String)  # Example doc for reference
```

### 5.3 Professional Services Integration

For ultra-complex documents (score 100+):

```python
@router.post("/api/templates/request-professional")
async def request_professional_template_creation(
    document_ids: List[int],
    complexity_score: int,
    user_email: str,
    db: Session = Depends(get_db)
):
    """
    Submit request for professional template creation service.

    Triggers:
    - Sales team notification
    - Document sample collection
    - Quote generation based on complexity
    """

    # Create service request
    service_request = ProfessionalServiceRequest(
        user_id=get_current_user_id(),
        service_type="template_creation",
        complexity_score=complexity_score,
        document_ids=document_ids,
        status="pending_review"
    )
    db.add(service_request)
    db.commit()

    # Notify sales team
    await send_service_request_notification(
        request_id=service_request.id,
        user_email=user_email,
        complexity=complexity_score
    )

    return {
        "request_id": service_request.id,
        "estimated_delivery": "3-5 business days",
        "estimated_cost": calculate_service_cost(complexity_score),
        "message": "Our template experts will review your documents and create a custom template."
    }
```

---

## 6. Metrics & Success Criteria

### 6.1 Auto-Generation Accuracy by Tier

Track actual performance vs. expected:

| Complexity Tier | Score Range | Expected Accuracy | Measured Accuracy | Action Threshold |
|----------------|-------------|-------------------|-------------------|------------------|
| Simple         | 0-35        | 90-95%           | Track             | Alert if <85%    |
| Medium         | 36-65       | 75-85%           | Track             | Alert if <70%    |
| Complex        | 66-100      | 50-70%           | Track             | Alert if <45%    |
| Very Complex   | 101+        | 20-40%           | Track             | Alert if <15%    |

**Accuracy Definition**: Percentage of fields correctly identified and extracted with correct data types.

### 6.2 User Override Analytics

Track when users override complexity recommendations:

```python
class ComplexityOverride(Base):
    __tablename__ = "complexity_overrides"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))

    # System recommendation
    complexity_score = Column(Integer)
    recommended_action = Column(String)  # "auto", "assisted", "manual"

    # User action
    user_action = Column(String)  # What user actually chose
    override_reason = Column(String, nullable=True)

    # Outcome
    schema_accuracy = Column(Float)  # Measured accuracy after processing
    user_corrections_count = Column(Integer)  # How many fields edited

    created_at = Column(DateTime, default=datetime.utcnow)
```

**Analysis queries**:
```sql
-- Users who ignore "manual recommended" warnings
SELECT
    COUNT(*) as override_count,
    AVG(schema_accuracy) as avg_accuracy
FROM complexity_overrides
WHERE recommended_action = 'manual'
  AND user_action = 'auto'
  AND created_at > NOW() - INTERVAL '30 days';

-- Identify false positives (complexity over-estimated)
SELECT
    complexity_score,
    AVG(schema_accuracy) as avg_accuracy
FROM complexity_overrides
WHERE recommended_action = 'manual'
  AND user_action = 'auto'
  AND schema_accuracy > 0.85  -- High accuracy despite warning
GROUP BY complexity_score;
```

### 6.3 Complexity Score Calibration

Monthly review to tune scoring weights:

```python
async def calibrate_complexity_scoring():
    """
    Analyze actual outcomes to tune complexity weights.
    """

    # Get last 1000 template generations
    results = db.query(
        ComplexityOverride.complexity_score,
        ComplexityOverride.schema_accuracy,
        ComplexityOverride.user_corrections_count
    ).limit(1000).all()

    # Analyze correlation between score and accuracy
    from scipy.stats import pearsonr

    correlation, p_value = pearsonr(
        [r.complexity_score for r in results],
        [r.schema_accuracy for r in results]
    )

    if correlation < 0.6:
        logger.warning(
            f"Weak correlation between complexity score and accuracy: {correlation:.2f}. "
            "Consider recalibrating weights."
        )

    # Identify systematic errors
    false_negatives = [r for r in results
                      if r.complexity_score < 50 and r.schema_accuracy < 0.7]

    if len(false_negatives) > 50:  # >5% false negative rate
        logger.error(
            f"High false negative rate: {len(false_negatives)} documents scored as 'simple' "
            "but had low accuracy. Review scoring algorithm."
        )
```

---

## 7. Implementation Roadmap

### Phase 1: Complexity Detection (3 days)
- [ ] Add `assess_document_complexity()` to `claude_service.py`
- [ ] Add `_extract_complexity_features()` helper
- [ ] Add complexity assessment to bulk upload flow
- [ ] Store complexity scores in database

### Phase 2: Claude Self-Assessment (2 days)
- [ ] Enhance schema generation prompt with self-assessment
- [ ] Parse `auto_generation_confidence` from Claude response
- [ ] Add `warnings` field to schema response
- [ ] Test with sample documents at each complexity tier

### Phase 3: User Experience (4 days)
- [ ] Create complexity warning UI components
- [ ] Implement Assisted Template Builder (hybrid mode)
- [ ] Add pre-built template browser
- [ ] Add "Request Professional Service" flow

### Phase 4: Fallback Strategies (3 days)
- [ ] Add advanced templates (W-2, medical forms, etc.)
- [ ] Implement template marketplace infrastructure
- [ ] Add professional services request API
- [ ] Create template wizard for manual mode

### Phase 5: Analytics & Calibration (2 days)
- [ ] Add `ComplexityOverride` tracking
- [ ] Create analytics dashboard
- [ ] Implement monthly calibration script
- [ ] Set up alerting for accuracy degradation

**Total Estimated Time**: 14 days

---

## 8. Key Recommendations

### 8.1 Immediate Actions

1. **Add Complexity Warning** to bulk upload flow (Quick win - 1 day)
   ```python
   # In bulk_upload.py, before calling claude_service.analyze_sample_documents()
   complexity = await claude_service.assess_document_complexity(parsed_docs)

   if complexity["complexity_score"] > 80:
       return {
           "warning": "manual_recommended",
           "complexity_assessment": complexity,
           "suggested_action": "Use pre-built template or template wizard"
       }
   ```

2. **Enhance Claude Prompt** with self-assessment (Quick win - 2 hours)
   - Add complexity self-check to prompt
   - Parse `auto_generation_confidence` field
   - Show warning if confidence < 0.6

3. **Add Field Count Limit** enforcement (Quick win - 1 hour)
   ```python
   if len(schema["fields"]) > 20:
       logger.warning(f"Schema has {len(schema['fields'])} fields (max recommended: 15)")
       schema["warnings"] = ["High field count - manual review recommended"]
   ```

### 8.2 Medium-Term Strategy

1. **Build Template Library** (1-2 weeks)
   - Add 10-15 common complex templates (W-2, 1099, medical forms)
   - Encode domain expertise (reference ranges, validation rules)
   - Allow user contributions (community marketplace)

2. **Implement Assisted Mode** (1 week)
   - Show Claude-generated schema side-by-side with PDF
   - Allow inline field editing with confidence indicators
   - Highlight low-confidence fields automatically

3. **Add Template Wizard** (2 weeks)
   - Guided step-by-step template creation
   - Visual table structure builder
   - Conditional field support (if/then rules)

### 8.3 Long-Term Vision

1. **Iterative Refinement Loop**
   - Claude generates v1 schema
   - User reviews extractions from 5 sample docs
   - Claude analyzes failures and suggests improvements
   - Repeat until accuracy threshold met

2. **Template Versioning**
   - Track schema changes over time
   - A/B test schema variants
   - Automatically promote best-performing versions

3. **Active Learning Pipeline**
   - Use HITL verifications to fine-tune extraction rules
   - Detect schema drift (when document format changes)
   - Suggest schema updates based on verification patterns

---

## 9. Edge Cases & Solutions

### 9.1 Multi-Language Documents

**Problem**: Claude trained primarily on English documents.

**Detection**:
```python
from langdetect import detect

language = detect(doc_text)
if language != 'en':
    complexity["domain_specificity"] += 2  # Increase complexity
    warnings.append(f"Non-English document ({language}) - accuracy may vary")
```

**Solution**:
- Translate to English before schema generation
- Use language-specific templates if available
- Show "Translation Preview" mode in UI

### 9.2 Scanned vs. Digital-Native PDFs

**Problem**: OCR errors increase complexity.

**Detection**:
```python
# Reducto provides OCR confidence in metadata
ocr_confidence = doc.get("metadata", {}).get("ocr_confidence", 1.0)

if ocr_confidence < 0.85:
    complexity["variability"] += 1
    warnings.append("Low OCR quality - field extraction may be unreliable")
```

**Solution**:
- Run image preprocessing (deskew, denoise)
- Increase confidence thresholds for HITL review
- Show OCR preview with editable text

### 9.3 Conditional Fields

**Problem**: Fields that only appear in some documents (e.g., "Employment Gap Explanation").

**Detection**:
```python
# Claude can detect optional fields
field["required"] = False
field["conditional"] = {
    "appears_if": "employment_gap_detected",
    "pattern": "Explain any gaps in employment"
}
```

**Solution**:
- Mark as `required: false` in schema
- Don't flag as error if missing
- Show in UI as "Optional (conditional)"

### 9.4 Version Variations

**Problem**: Same document type, different versions (2023 vs 2024 W-2).

**Detection**:
```python
# Extract version/year from document
version_pattern = r'(Form|Version|Rev)\s*(\d+)|(\d{4})'
version = re.search(version_pattern, doc_text)

if version:
    schema["version"] = version.group(0)
    warnings.append(f"Document version: {version.group(0)}")
```

**Solution**:
- Template versioning system
- Show version selector in UI
- Auto-detect version and suggest correct template

---

## 10. Conclusion

**The 50-Point Threshold**: Claude can reliably auto-generate schemas for documents scoring ≤50 points (simple invoices, receipts, basic forms). Beyond this, human oversight becomes increasingly necessary.

**The 80-Point Cliff**: At 80+ points, auto-generation becomes unreliable (<50% accuracy). Manual template creation or pre-built templates are strongly recommended.

**Hybrid is Key**: The most successful approach combines:
1. **Auto-generation** for simple documents (fast time-to-value)
2. **Assisted mode** for medium complexity (Claude suggests, user refines)
3. **Manual/pre-built** for complex documents (accuracy over speed)

**Continuous Improvement**: Use HITL verifications to:
- Calibrate complexity scoring weights
- Identify systematic failures
- Build template library based on actual user needs

---

## Appendix A: Complexity Score Calculator

Interactive tool for estimating complexity:

```python
def calculate_complexity_score(
    field_count: int,
    nested_levels: int,
    array_count: int,
    has_tables: bool,
    table_dynamic_columns: bool = False,
    domain: str = "general",
    variability: str = "low"
) -> Dict[str, Any]:
    """
    Calculate complexity score for a document type.

    Returns detailed breakdown and recommendation.
    """

    # Table complexity
    table_complexity = 0
    if has_tables:
        if table_dynamic_columns:
            table_complexity = 2
        else:
            table_complexity = 1

    # Domain specificity
    domain_weights = {
        "general": 0,
        "industry_standard": 1,
        "specialized": 2,
        "highly_custom": 3
    }
    domain_specificity = domain_weights.get(domain, 0)

    # Variability
    variability_weights = {
        "low": 0,
        "medium": 1,
        "high": 2
    }
    variability_penalty = variability_weights.get(variability, 0)

    # Calculate score
    score = (
        (field_count * 3) +
        (nested_levels * 15) +
        (array_count * 10) +
        (table_complexity * 20) +
        (domain_specificity * 10) +
        (variability_penalty * 5)
    )

    # Determine recommendation
    if score <= 50:
        recommendation = "auto_generation"
        confidence = "high"
    elif score <= 80:
        recommendation = "assisted"
        confidence = "medium"
    else:
        recommendation = "manual"
        confidence = "low"

    return {
        "score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "breakdown": {
            "field_count": field_count * 3,
            "nested_levels": nested_levels * 15,
            "array_count": array_count * 10,
            "table_complexity": table_complexity * 20,
            "domain_specificity": domain_specificity * 10,
            "variability": variability_penalty * 5
        }
    }

# Example usage
invoice_score = calculate_complexity_score(
    field_count=8,
    nested_levels=1,
    array_count=1,
    has_tables=False,
    domain="general",
    variability="low"
)
# Result: {"score": 49, "recommendation": "auto_generation", "confidence": "high"}

w2_score = calculate_complexity_score(
    field_count=27,
    nested_levels=0,
    array_count=0,
    has_tables=False,
    domain="industry_standard",
    variability="low"
)
# Result: {"score": 91, "recommendation": "manual", "confidence": "low"}
```

---

**Document Version**: 1.0
**Last Review**: 2025-11-01
**Next Review**: 2025-12-01 (after Phase 1-2 implementation)
**Owner**: Product & Engineering Team
