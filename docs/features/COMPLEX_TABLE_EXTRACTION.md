# Complex Table Extraction System Design

**Last Updated**: 2025-11-01
**Status**: Design Phase
**Related**: [MULTI_TEMPLATE_EXTRACTION.md](../MULTI_TEMPLATE_EXTRACTION.md), [ELASTICSEARCH_MAPPING_IMPROVEMENTS.md](./ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)

## Overview

This document outlines the architecture for extracting and managing **complex multi-cell tables** like garment grading specifications, invoice line items, and size charts. The system extends Paperbase's existing template system to handle structured tabular data while maintaining cost optimization and confidence tracking.

## Key Design Decisions

### 1. Hybrid Schema Approach

**Problem**: Current system supports only flat fields (text, date, number). Tables require nested structures.

**Solution**: Add new field types while preserving existing architecture:

```json
{
  "name": "Garment Grading Specification",
  "fields": [
    {
      "name": "request_number",
      "type": "text",
      "extraction_hints": ["Request No:", "Request #"],
      "confidence_threshold": 0.8
    },
    {
      "name": "grading_table",
      "type": "table",
      "table_schema": {
        "row_identifier": "pom_code",
        "columns": ["size_2", "size_3", "size_4", "size_5", "size_6", "size_7", "size_8", "size_10", "size_12", "size_14"],
        "dynamic_columns": true,
        "column_pattern": "size_.*",
        "value_type": "number"
      },
      "extraction_hints": ["POM Code", "Grading Table"],
      "confidence_threshold": 0.75
    }
  ]
}
```

### 2. Multi-Layer Storage Strategy

**Database (SQLite)**: Metadata + full JSON
```python
ExtractedField(
    field_name="grading_table",
    field_value=None,  # NULL for complex types
    field_value_json={
        "rows": [
            {
                "pom_code": "B510",
                "measurements": {"size_2": 10.5, "size_3": 11.0},
                "confidence": 0.82
            }
        ],
        "row_count": 15,
        "column_count": 12
    },
    confidence_score=0.82,  # Average
    source_page=2,
    source_bbox=[100, 200, 500, 600]
)
```

**Elasticsearch**: Searchable nested structure
```json
{
  "document_id": 123,
  "grading_table": {
    "type": "nested",
    "properties": {
      "pom_code": {"type": "keyword"},
      "size_2": {"type": "float"},
      "size_3": {"type": "float"}
    }
  }
}
```

### 3. Claude Prompt Strategy

**Schema Generation**: Enhanced to detect tables

```python
# In claude_service.py
def _build_schema_generation_prompt_with_tables(
    self,
    parsed_documents: List[Dict[str, Any]]
) -> str:
    return f"""Analyze these sample documents and generate an extraction schema.

**IMPORTANT: Detect tabular data structures**

For each field, determine if it's:
1. **Simple field** (text/date/number) - single value per document
2. **Table field** - multi-row, multi-column structure with repeating patterns
3. **Array field** - list of similar items

**Table Detection Guidelines:**
- Look for repeating row patterns (e.g., multiple rows with POM codes + measurements)
- Identify row identifiers (POM codes, line numbers, product IDs)
- Detect column headers (sizes, dates, categories)
- Note if columns are fixed or dynamic (e.g., variable size ranges)

Return JSON with field types: "text", "date", "number", "table", "array"

For table fields, include:
- row_identifier: field that uniquely identifies each row
- columns: array of column names
- dynamic_columns: true if column count may vary
- column_pattern: regex pattern for dynamic columns (e.g., "size_.*")
- value_type: "number" | "text" | "mixed"
"""
```

**Template Matching**: Include table structure similarity

```python
# Enhanced matching considers table structure
table_match_quality = {
    "column_overlap": 0.85,  # 85% of columns match
    "structure_similarity": 0.90,  # Same row/column pattern
    "notes": "Same grading table structure, different size range"
}
```

## Architecture Components

### 1. Database Changes

**New field type support** in [backend/app/models/document.py](../backend/app/models/document.py):

```python
class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    field_name = Column(String, nullable=False)

    # Existing for simple types
    field_value = Column(String)  # NULL for complex types

    # NEW: For complex types (tables, arrays)
    field_value_json = Column(JSON)

    confidence_score = Column(Float)
    source_page = Column(Integer)
    source_bbox = Column(JSON)  # [x, y, w, h] for table location
```

### 2. Elasticsearch Mapping

**Nested type for queryability** in [backend/app/services/elastic_service.py](../backend/app/services/elastic_service.py):

```python
def _build_table_mapping(self, table_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Build ES mapping for table fields"""

    properties = {
        table_schema["row_identifier"]: {"type": "keyword"}
    }

    if table_schema.get("dynamic_columns"):
        # Use dynamic templates for variable columns
        return {
            "type": "nested",
            "dynamic": "true",
            "dynamic_templates": [
                {
                    "size_columns": {
                        "match_pattern": "regex",
                        "match": table_schema.get("column_pattern", "size_.*"),
                        "mapping": {
                            "type": "float" if table_schema["value_type"] == "number" else "text"
                        }
                    }
                }
            ],
            "properties": properties
        }
    else:
        # Fixed columns
        value_type = "float" if table_schema["value_type"] == "number" else "text"
        for col in table_schema["columns"]:
            properties[col] = {"type": value_type}

        return {
            "type": "nested",
            "properties": properties
        }
```

**Enables powerful nested queries**:

```json
{
  "query": {
    "nested": {
      "path": "grading_table",
      "query": {
        "bool": {
          "must": [
            {"term": {"grading_table.pom_code": "B510"}},
            {"range": {"grading_table.size_10": {"gte": 12.0}}}
          ]
        }
      }
    }
  }
}
```

### 3. Reducto Integration

**Enhanced extraction** in [backend/app/services/reducto_service.py](../backend/app/services/reducto_service.py):

```python
async def extract_structured(
    self,
    schema: Dict[str, Any],
    file_path: str = None,
    job_id: str = None
) -> Dict[str, Any]:
    """Enhanced to handle table schemas"""

    reducto_schema = {"fields": []}

    for field in schema.get("fields", []):
        if field.get("type") == "table":
            reducto_schema["fields"].append({
                "name": field["name"],
                "type": "table",
                "description": f"Extract table with {field['table_schema']['row_identifier']} rows",
                "table_config": {
                    "extract_headers": True,
                    "preserve_structure": True,
                    "output_format": "array_of_objects"
                }
            })
        else:
            # Standard field
            reducto_schema["fields"].append({
                "name": field["name"],
                "type": field["type"],
                "description": " ".join(field.get("extraction_hints", []))
            })

    response = await self.client.extract.run(
        document_url=self._get_document_url(file_path, job_id),
        schema=reducto_schema
    )

    return self._normalize_table_extractions(response, schema)
```

**Post-processing normalization**:

```python
def _normalize_table_extraction(
    self,
    raw_table: List[Dict[str, Any]],
    table_schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Normalize table extraction:
    - Convert strings to numbers where expected
    - Calculate per-row confidence
    - Validate structure
    """

    rows = []
    row_confidences = []

    for row_data in raw_table:
        normalized_row = {}
        cell_confidences = []

        for col_name, col_value in row_data.items():
            expected_type = table_schema.get("value_type", "text")

            if expected_type == "number":
                try:
                    normalized_row[col_name] = float(col_value)
                    cell_confidences.append(0.90)
                except (ValueError, TypeError):
                    normalized_row[col_name] = None
                    cell_confidences.append(0.30)  # Low confidence
            else:
                normalized_row[col_name] = str(col_value) if col_value else None
                cell_confidences.append(0.85)

        rows.append(normalized_row)
        row_confidences.append(
            sum(cell_confidences) / len(cell_confidences) if cell_confidences else 0.0
        )

    return {
        "rows": rows,
        "row_confidences": row_confidences,
        "avg_confidence": sum(row_confidences) / len(row_confidences) if row_confidences else 0.0,
        "row_count": len(rows),
        "column_count": len(table_schema.get("columns", []))
    }
```

### 4. UI Components

**Modal-based table editor** (RECOMMENDED approach):

```jsx
// frontend/src/components/TableEditorModal.jsx
import { useState } from 'react';
import { Dialog } from '@headlessui/react';

export default function TableEditorModal({
  title,
  data,
  schema,
  onSave,
  onClose
}) {
  const [editedRows, setEditedRows] = useState(data.rows);
  const [page, setPage] = useState(1);
  const ROWS_PER_PAGE = 20;

  const handleCellEdit = (rowIdx, colName, newValue) => {
    const updated = [...editedRows];
    updated[rowIdx][colName] = newValue;
    setEditedRows(updated);
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'bg-green-50 border-green-300';
    if (confidence >= 0.6) return 'bg-yellow-50 border-yellow-300';
    return 'bg-red-50 border-red-300';
  };

  const paginatedRows = editedRows.slice(
    (page - 1) * ROWS_PER_PAGE,
    page * ROWS_PER_PAGE
  );

  return (
    <Dialog open={true} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />

      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="mx-auto max-w-7xl bg-white rounded-lg shadow-xl">
          <Dialog.Title className="text-lg font-semibold p-6 border-b">
            {title}
          </Dialog.Title>

          <div className="p-6 max-h-[600px] overflow-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    {schema.row_identifier.replace(/_/g, ' ')}
                  </th>
                  {schema.columns.map(col => (
                    <th key={col} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      {col.replace(/^size_/, 'Size ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {paginatedRows.map((row, rowIdx) => {
                  const actualRowIdx = (page - 1) * ROWS_PER_PAGE + rowIdx;
                  const rowConfidence = data.row_confidences?.[actualRowIdx] || 0.5;

                  return (
                    <tr key={actualRowIdx}>
                      <td className="px-4 py-2 font-medium">
                        {row[schema.row_identifier]}
                      </td>
                      {schema.columns.map(col => (
                        <td key={col} className="px-4 py-2">
                          <input
                            type={schema.value_type === 'number' ? 'number' : 'text'}
                            value={row[col] || ''}
                            onChange={(e) => handleCellEdit(actualRowIdx, col, e.target.value)}
                            className={`w-full px-2 py-1 border rounded ${getConfidenceColor(rowConfidence)}`}
                            step={schema.value_type === 'number' ? '0.01' : undefined}
                          />
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {editedRows.length > ROWS_PER_PAGE && (
            <div className="px-6 py-3 border-t flex items-center justify-between">
              <span className="text-sm text-gray-700">
                Showing {(page - 1) * ROWS_PER_PAGE + 1} to {Math.min(page * ROWS_PER_PAGE, editedRows.length)} of {editedRows.length} rows
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 border rounded disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => Math.min(Math.ceil(editedRows.length / ROWS_PER_PAGE), p + 1))}
                  disabled={page >= Math.ceil(editedRows.length / ROWS_PER_PAGE)}
                  className="px-3 py-1 border rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="px-6 py-4 border-t flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={() => onSave({ ...data, rows: editedRows })}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Save Changes
            </button>
          </div>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}
```

**Integration in AuditTableView**:

```jsx
// frontend/src/components/AuditTableView.jsx (enhanced)
import TableEditorModal from './TableEditorModal';

const TableFieldCell = ({ document, field }) => {
  const [showEditor, setShowEditor] = useState(false);
  const tableData = JSON.parse(document.fields[field.name] || '{"rows": []}');

  const handleSave = async (updatedData) => {
    await onVerifyField(document.id, field.name, updatedData);
    setShowEditor(false);
  };

  return (
    <>
      <td
        onClick={() => setShowEditor(true)}
        className="px-6 py-4 cursor-pointer hover:bg-gray-50"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span className="text-sm">
            {tableData.rows.length} rows × {tableData.column_count || 0} cols
          </span>
          <span className={`ml-2 px-2 py-0.5 text-xs rounded ${
            tableData.avg_confidence >= 0.8 ? 'bg-green-100 text-green-800' :
            tableData.avg_confidence >= 0.6 ? 'bg-yellow-100 text-yellow-800' :
            'bg-red-100 text-red-800'
          }`}>
            {Math.round((tableData.avg_confidence || 0) * 100)}%
          </span>
        </div>
      </td>

      {showEditor && (
        <TableEditorModal
          title={`Edit ${field.name} for ${document.filename}`}
          data={tableData}
          schema={field.table_schema}
          onSave={handleSave}
          onClose={() => setShowEditor(false)}
        />
      )}
    </>
  );
};
```

## Edge Cases & Solutions

### 1. Variable Column Count Across Documents

**Problem**: Document A has sizes 2-10, Document B has sizes 2-14

**Solution**: Union of all columns in schema, NULL for missing values

```python
def _merge_table_schemas(schemas: List[Dict]) -> Dict:
    """Merge schemas from multiple documents to find union of columns"""
    all_columns = set()
    for schema in schemas:
        all_columns.update(schema.get("columns", []))

    # Detect pattern (e.g., "size_2", "size_3" → "size_.*")
    pattern = _detect_column_pattern(list(all_columns))

    return {
        "columns": sorted(list(all_columns)),
        "dynamic_columns": True,
        "column_pattern": pattern
    }
```

### 2. Merged Cells in PDF

**Problem**: Reducto might split merged cells incorrectly

**Solution**: Post-processing validation with warnings

```python
def _validate_table_structure(
    rows: List[Dict],
    row_identifier: str
) -> List[str]:
    """Detect structural issues in extracted table"""
    issues = []

    # Check for duplicate row identifiers
    row_ids = [r.get(row_identifier) for r in rows]
    if len(row_ids) != len(set(row_ids)):
        duplicates = [x for x in row_ids if row_ids.count(x) > 1]
        issues.append(f"Duplicate row identifiers: {set(duplicates)}")

    # Check for missing required columns
    if rows:
        first_row_cols = set(rows[0].keys())
        for i, row in enumerate(rows[1:], 1):
            if set(row.keys()) != first_row_cols:
                issues.append(f"Row {i} has different columns than row 0")

    return issues
```

### 3. Partial Table Extraction

**Problem**: Reducto extracts 10 out of 15 expected rows

**Solution**: Quality assessment with automatic flagging

```python
def _assess_table_extraction_quality(
    extracted: Dict,
    expected_row_count: Optional[int] = None
) -> Dict[str, Any]:
    """Assess completeness of table extraction"""

    row_count = len(extracted.get("rows", []))
    issues = []

    # Check row count
    if expected_row_count and row_count < expected_row_count * 0.8:
        issues.append(f"Only {row_count}/{expected_row_count} rows extracted (expected 80%+)")

    # Check for empty cells
    total_cells = row_count * len(extracted.get("columns", []))
    empty_cells = sum(
        1 for row in extracted["rows"]
        for val in row.values()
        if val is None or val == ""
    )

    if total_cells > 0 and empty_cells > total_cells * 0.2:
        issues.append(f"{empty_cells}/{total_cells} cells empty (>20% threshold)")

    quality_score = 1.0 - (len(issues) * 0.25)  # Each issue reduces by 25%

    return {
        "quality_score": max(0.0, quality_score),
        "issues": issues,
        "needs_verification": len(issues) > 0 or quality_score < 0.7
    }
```

## Implementation Roadmap

### Phase 1: Schema & Data Model (1-2 days)

- [ ] Add `field_value_json` column to `ExtractedField` model
- [ ] Add migration script for existing data
- [ ] Update `Schema` model to support `table` field type
- [ ] Add `table_schema` JSON field validation

### Phase 2: Claude Integration (2 days)

- [ ] Enhance schema generation prompt to detect tables
- [ ] Add table structure comparison in template matching
- [ ] Test with sample documents (invoices, grading specs)

### Phase 3: Reducto Integration (2-3 days)

- [ ] Update `extract_structured()` to handle table schemas
- [ ] Add table normalization logic
- [ ] Add validation and quality assessment
- [ ] Test with real PDF tables

### Phase 4: Elasticsearch (2 days)

- [ ] Add nested mapping support in `create_index()`
- [ ] Add dynamic template support for variable columns
- [ ] Test nested queries
- [ ] Add table-specific aggregations

### Phase 5: Frontend (3-4 days)

- [ ] Create `TableEditorModal` component
- [ ] Update `AuditTableView` to detect table fields
- [ ] Add table preview in document dashboard
- [ ] Handle table field updates via API

### Phase 6: Testing & Polish (2-3 days)

- [ ] Test with various document types (invoices, specs, charts)
- [ ] Handle edge cases (large tables, merged cells, partial extraction)
- [ ] Performance testing (100+ row tables)
- [ ] Documentation updates

**Total Estimated Time**: 12-16 days

## Success Metrics

### Extraction Quality
- **Table detection accuracy**: >85% (Claude identifies tables correctly)
- **Row extraction completeness**: >90% (rows extracted vs. expected)
- **Cell accuracy**: >85% (correct values extracted)

### Performance
- **Extraction time**: <10s for tables with <50 rows
- **ES indexing time**: <1s for nested documents
- **UI responsiveness**: Table editor loads in <500ms

### User Experience
- **Verification time**: <2 min per table (with modal editor)
- **Confidence visibility**: Clear indicators at row/table level
- **Error recovery**: Validation warnings guide corrections

## Key Innovations

This system enables **impossible-before queries** like:

> "Show me all grading specs where size 10 measurement for POM B510 exceeds 12.0 inches"

```json
{
  "query": {
    "bool": {
      "must": [
        {"term": {"template_name": "Grading Specification"}},
        {
          "nested": {
            "path": "grading_table",
            "query": {
              "bool": {
                "must": [
                  {"term": {"grading_table.pom_code": "B510"}},
                  {"range": {"grading_table.size_10": {"gt": 12.0}}}
                ]
              }
            }
          }
        }
      ]
    }
  }
}
```

**Why This Matters**:
- Traditional flat schemas would require separate documents per row (explosion)
- OR flatten to `grading_b510_size_10` (unmaintainable with dynamic columns)
- Nested structure maintains relationships while enabling powerful queries

## Related Documentation

- [Multi-Template Extraction](../MULTI_TEMPLATE_EXTRACTION.md) - File deduplication & virtual folders
- [Elasticsearch Mapping Improvements](./ELASTICSEARCH_MAPPING_IMPROVEMENTS.md) - Production mapping strategies
- [Pipeline Optimization](./PIPELINE_OPTIMIZATION.md) - Reducto cost optimization
- [CLAUDE.md](../CLAUDE.md) - Main project overview

---

**Next Steps**: Review this design, then proceed with Phase 1 implementation (Schema & Data Model).
