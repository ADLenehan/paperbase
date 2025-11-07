# Array Fields & Complex Data UI Strategy

**Last Updated**: 2025-11-01
**Status**: Design & Implementation Guide
**Related**: [COMPLEX_TABLE_EXTRACTION.md](./features/COMPLEX_TABLE_EXTRACTION.md), [CLAUDE.md](../CLAUDE.md)

## Executive Summary

This document provides a comprehensive specification for:
1. **Array field support** - How arrays differ from tables and how to handle them
2. **UI display strategy** - Multiple approaches for displaying complex data (tables, arrays, nested objects)

**Key Finding**: Arrays are already partially defined in templates but not implemented. Tables have a complete design but no implementation. This document consolidates both and provides a unified implementation strategy.

---

## Part 1: Array Field Specification

### 1.1 Array vs Table vs Simple Field

| Feature | Simple Field | Array | Table |
|---------|-------------|-------|-------|
| **Structure** | Single value | List of similar items | Multi-row, multi-column grid |
| **Example** | `"Navy"` | `["Navy", "Black", "White"]` | `{rows: [{pom: "B510", size_2: 10.5}]}` |
| **Row Identifier** | N/A | Index only | Explicit (e.g., POM code) |
| **Columns** | N/A | Implicit (all items same type) | Explicit (size_2, size_3, etc.) |
| **Use Case** | Single color | List of colors | Grading measurements |
| **DB Storage** | `field_value` (Text) | `field_value_json` (JSON) | `field_value_json` (JSON) |
| **ES Type** | `text`/`keyword` | `array` of primitives or `nested` | `nested` with defined properties |
| **Confidence** | Single score | Per-item OR overall | Per-row + per-cell + overall |

### 1.2 When to Use Each Type

**Simple Field** - Use when:
- Only one value per document (e.g., invoice number, effective date)
- No repeating pattern
- Examples: `contract_title`, `effective_date`, `total_amount`

**Array** - Use when:
- Multiple similar items without additional structure
- Items are primitives (strings, numbers) OR simple objects
- No complex relationships between items
- Examples:
  - Simple arrays: `["Navy", "Black", "White"]` (colors)
  - Array of objects: `[{name: "Cotton", percentage: 95}, {name: "Spandex", percentage: 5}]` (materials)

**Table** - Use when:
- Multi-dimensional data with row/column structure
- Row identifier exists (POM code, line number)
- Fixed or dynamic columns
- Complex queries needed (e.g., "find row B510, column size_10")
- Examples: grading specifications, invoice line items with multiple attributes, price matrices

### 1.3 Array Field Schema Definition

#### Simple Array (Primitives)

```json
{
  "name": "colors",
  "type": "array",
  "description": "Available colors for this garment",
  "required": false,
  "confidence_threshold": 0.7,
  "extraction_hints": ["Colors:", "Available in:", "Color Options:"],
  "array_config": {
    "item_type": "text",
    "min_items": 1,
    "max_items": 20,
    "allow_duplicates": false
  }
}
```

**Extraction Result**:
```json
{
  "field_name": "colors",
  "field_value": null,
  "field_value_json": {
    "items": ["Navy", "Charcoal", "Black", "White"],
    "item_count": 4,
    "confidence_per_item": [0.92, 0.88, 0.95, 0.90],
    "avg_confidence": 0.91
  },
  "confidence_score": 0.91
}
```

#### Array of Objects (Structured Items)

```json
{
  "name": "materials",
  "type": "array",
  "description": "Fabric composition breakdown",
  "required": false,
  "confidence_threshold": 0.75,
  "extraction_hints": ["Fabric:", "Material:", "Composition:"],
  "array_config": {
    "item_type": "object",
    "min_items": 1,
    "max_items": 10
  },
  "array_items": [
    {
      "name": "material",
      "type": "text",
      "description": "Material name (Cotton, Polyester, etc.)",
      "required": true,
      "extraction_hints": ["Material", "Fabric"]
    },
    {
      "name": "percentage",
      "type": "number",
      "description": "Percentage of total composition",
      "required": true,
      "extraction_hints": ["%", "Percent"]
    }
  ]
}
```

**Extraction Result**:
```json
{
  "field_name": "materials",
  "field_value": null,
  "field_value_json": {
    "items": [
      {
        "material": "Cotton",
        "percentage": 95,
        "confidence": 0.89
      },
      {
        "material": "Spandex",
        "percentage": 5,
        "confidence": 0.85
      }
    ],
    "item_count": 2,
    "avg_confidence": 0.87,
    "validation_errors": []
  },
  "confidence_score": 0.87
}
```

#### Array vs Table - Side by Side Example

**Invoice Line Items as Array**:
```json
{
  "name": "line_items",
  "type": "array",
  "array_items": [
    {"name": "description", "type": "text"},
    {"name": "quantity", "type": "number"},
    {"name": "unit_price", "type": "number"},
    {"name": "amount", "type": "number"}
  ]
}
```
✅ **Use for**: Simple lists where order matters, no complex queries needed
❌ **Don't use for**: Need to query "all items where quantity > 10"

**Invoice Line Items as Table**:
```json
{
  "name": "line_items",
  "type": "table",
  "table_schema": {
    "row_identifier": "line_number",
    "columns": ["description", "quantity", "unit_price", "amount"],
    "dynamic_columns": false
  }
}
```
✅ **Use for**: Complex queries, large datasets, need row identifiers
❌ **Don't use for**: Simple lists, order-based access

**Recommendation**: For invoice line items, use **table** if you need queries like "show invoices with any line item > $1000". Use **array** if you just need to display/verify the list.

### 1.4 Database Schema Changes

Add to `ExtractedField` model:

```python
class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    # Existing fields
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    field_name = Column(String, nullable=False)

    # Simple fields use this
    field_value = Column(Text, nullable=True)

    # NEW: Complex fields (arrays, tables) use this
    field_value_json = Column(JSON, nullable=True)

    # NEW: Field type to distinguish
    field_type = Column(String, default="text")  # text, number, date, array, table

    confidence_score = Column(Float, nullable=True)
    source_page = Column(Integer, nullable=True)
    source_bbox = Column(JSON, nullable=True)

    # ... existing fields
```

**Migration Strategy**:
```sql
-- Add new columns
ALTER TABLE extracted_fields ADD COLUMN field_value_json JSON;
ALTER TABLE extracted_fields ADD COLUMN field_type VARCHAR(20) DEFAULT 'text';

-- Migrate existing data
UPDATE extracted_fields SET field_type = 'text' WHERE field_value IS NOT NULL;
```

### 1.5 Elasticsearch Mapping

**Simple Array** (primitives):
```python
# colors: ["Navy", "Black", "White"]
{
  "colors": {
    "type": "keyword"  # ES auto-handles arrays of primitives
  }
}
```

**Array of Objects** (structured):
```python
# materials: [{material: "Cotton", percentage: 95}, ...]
{
  "materials": {
    "type": "nested",
    "properties": {
      "material": {"type": "keyword"},
      "percentage": {"type": "float"}
    }
  }
}
```

**Query Examples**:

```python
# Simple array: Find documents with "Navy" color
{
  "query": {
    "term": {"colors": "Navy"}
  }
}

# Nested array: Find documents with >90% cotton
{
  "query": {
    "nested": {
      "path": "materials",
      "query": {
        "bool": {
          "must": [
            {"term": {"materials.material": "Cotton"}},
            {"range": {"materials.percentage": {"gte": 90}}}
          ]
        }
      }
    }
  }
}
```

### 1.6 Confidence Tracking for Arrays

**Approach 1: Overall Confidence Only** (SIMPLE)
```json
{
  "field_name": "colors",
  "confidence_score": 0.85,  // Single overall score
  "field_value_json": {
    "items": ["Navy", "Black", "White"]
  }
}
```
✅ Simple, works with existing system
❌ Can't identify which specific item has low confidence

**Approach 2: Per-Item Confidence** (RECOMMENDED)
```json
{
  "field_name": "colors",
  "confidence_score": 0.82,  // Average of per-item scores
  "field_value_json": {
    "items": ["Navy", "Black", "White"],
    "confidence_per_item": [0.92, 0.85, 0.70],  // Per-item scores
    "low_confidence_items": [2]  // Indices with confidence < threshold
  }
}
```
✅ Granular tracking, can highlight specific items
✅ Enables HITL review of only low-confidence items
❌ More complex

**Recommendation**: Use **Approach 2** for initial implementation. Store per-item confidence, calculate average for overall score. This enables:
- Highlighting low-confidence items in UI
- Filtering audit queue by "any item below threshold"
- Better training data for Claude improvements

### 1.7 Claude Prompt Enhancement

Add to schema generation prompt:

```python
def _build_schema_generation_prompt_with_arrays(
    self,
    parsed_documents: List[Dict[str, Any]]
) -> str:
    return f"""Analyze these sample documents and generate an extraction schema.

**Field Type Selection Guidelines:**

1. **Simple Field** (text/number/date):
   - Single value per document
   - Examples: invoice_number, total_amount, effective_date

2. **Array Field**:
   - List of similar items (colors, sizes, materials)
   - Items are primitives OR simple objects with 2-5 properties
   - NO row identifier needed
   - Examples: ["Navy", "Black"], [{color: "Navy", code: "NV1"}]

3. **Table Field**:
   - Multi-row, multi-column grid
   - Row identifier exists (POM code, line number)
   - Complex queries needed
   - Examples: grading specs, line items with many attributes

**For Array Fields, specify**:
- `item_type`: "text" | "number" | "object"
- `array_items`: Array of field definitions (if item_type is "object")
- `min_items`, `max_items`: Expected range

**Return JSON with field type clearly specified.**
"""
```

---

## Part 2: UI Display Strategy

### 2.1 Analysis of Current UI Patterns

**Existing Components**:
1. **AuditTableView** (Spreadsheet Grid)
   - Documents (rows) × Fields (columns)
   - Inline text editing
   - Confidence color coding
   - Works well for: Simple fields, <20 documents, <15 fields
   - Breaks down for: Complex fields, wide tables, mobile

2. **Audit.jsx Single Field Mode** (PDF + Sidebar)
   - Left: PDF viewer with bbox highlighting
   - Right: Field details + verification buttons
   - Works well for: Deep focus, one field at a time
   - Breaks down for: Bulk editing, seeing context

3. **DocumentViewer** (PDF Viewer)
   - Pagination, zoom, bbox overlays
   - Works well for: Visual verification
   - Missing: Inline annotation

**Key Insights**:
- Current system only handles simple text fields
- No support for nested data (arrays, tables, objects)
- Two modes (table vs single) provide complementary workflows
- Modal approach already designed in COMPLEX_TABLE_EXTRACTION.md

### 2.2 UI Strategy Decision Matrix

| Data Type | Primary View | Secondary View | Edit Mode | Mobile Support |
|-----------|--------------|----------------|-----------|----------------|
| **Simple Field** | Inline (AuditTableView) | Sidebar (Audit) | Direct edit | ✅ Full |
| **Simple Array** | Chip list | Expandable list | Modal or drawer | ⚠️ Limited |
| **Array of Objects** | Badge (N items) | Modal table | Modal editor | ❌ View only |
| **Table** | Badge (N×M) | Modal table | Modal editor | ❌ View only |
| **Nested Object** | Badge (N fields) | Drawer | Inline in drawer | ⚠️ Limited |

### 2.3 Recommended UI Patterns

#### Pattern 1: Inline Chip List (Simple Arrays)

**Use for**: Simple arrays with <10 items (colors, sizes, materials)

**Implementation**:
```jsx
// frontend/src/components/cells/ArrayChipCell.jsx
export default function ArrayChipCell({ field, value, onEdit, confidence }) {
  const [isEditing, setIsEditing] = useState(false);
  const items = value?.items || [];

  if (isEditing) {
    return <ArrayChipEditor items={items} onSave={onEdit} onCancel={() => setIsEditing(false)} />;
  }

  return (
    <div className="flex flex-wrap gap-1" onClick={() => setIsEditing(true)}>
      {items.map((item, idx) => {
        const itemConfidence = value?.confidence_per_item?.[idx] || confidence;
        return (
          <span
            key={idx}
            className={`px-2 py-1 text-xs rounded ${
              itemConfidence >= 0.8 ? 'bg-green-100 text-green-800' :
              itemConfidence >= 0.6 ? 'bg-yellow-100 text-yellow-800' :
              'bg-red-100 text-red-800'
            }`}
          >
            {item}
          </span>
        );
      })}
      <button className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700">
        +
      </button>
    </div>
  );
}
```

**Visual**:
```
┌─────────────────────────────────────────────┐
│ Colors                                      │
├─────────────────────────────────────────────┤
│ [Navy] [Charcoal] [Black] [White] [+]      │
│  92%    88%       95%     70%               │
└─────────────────────────────────────────────┘
```

**Pros**:
- Visual, scannable
- Shows confidence per-item
- Quick edits (click chip to edit, + to add)
- No modal needed for <10 items

**Cons**:
- Takes vertical space with many items
- Hard to see on mobile

#### Pattern 2: Badge + Modal (Arrays of Objects, Tables)

**Use for**: Complex arrays, tables, any data with >10 items or >3 properties

**Implementation**:
```jsx
// frontend/src/components/cells/ComplexDataCell.jsx
export default function ComplexDataCell({ field, value, schema, onSave, confidence }) {
  const [showModal, setShowModal] = useState(false);

  const summary = getSummary(field.type, value);
  // summary: "4 items" for array, "15 rows × 12 cols" for table

  return (
    <>
      <div
        onClick={() => setShowModal(true)}
        className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded"
      >
        <TableIcon className="w-4 h-4 text-gray-400" />
        <span className="text-sm">{summary}</span>
        <ConfidenceBadge confidence={confidence} />
      </div>

      {showModal && (
        <ComplexDataModal
          field={field}
          value={value}
          schema={schema}
          onSave={onSave}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
```

**Visual (Main View)**:
```
┌─────────────────────────────────────────────┐
│ Line Items                                  │
├─────────────────────────────────────────────┤
│ [📋] 8 items • 78% confidence [Edit]       │
└─────────────────────────────────────────────┘
```

**Visual (Modal)**:
```
┌───────────────────────────────────────────────────────────────┐
│ Edit Line Items for invoice_001.pdf               [X]         │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  Description       Quantity  Unit Price  Amount  Confidence   │
│  ────────────────  ────────  ──────────  ──────  ──────────   │
│  Widget A          10        $25.00      $250    92%          │
│  Service B         1         $150.00     $150    88%          │
│  Supplies C        5         $12.50      $62.50  75% ⚠        │
│  [+ Add Row]                                                   │
│                                                                │
│  Showing 1-3 of 8                          [< Prev] [Next >]  │
│                                                                │
├───────────────────────────────────────────────────────────────┤
│                               [Cancel]  [Save Changes]        │
└───────────────────────────────────────────────────────────────┘
```

**Pros**:
- Doesn't clutter main view
- Full screen space for editing
- Pagination for large datasets
- Clear context (filename in title)

**Cons**:
- Context switch (leaves table view)
- Can't compare across documents easily

#### Pattern 3: Drawer (Contextual Detail View)

**Use for**: Viewing full document details while maintaining table context

**Implementation**:
```jsx
// frontend/src/components/DocumentDrawer.jsx
export default function DocumentDrawer({ document, schema, onClose, onSave }) {
  const [activeTab, setActiveTab] = useState('simple');

  return (
    <div className="fixed inset-y-0 right-0 w-2/3 bg-white shadow-xl z-40 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="text-lg font-semibold">{document.filename}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        <TabButton active={activeTab === 'simple'} onClick={() => setActiveTab('simple')}>
          Simple Fields
        </TabButton>
        <TabButton active={activeTab === 'arrays'} onClick={() => setActiveTab('arrays')}>
          Arrays & Tables
        </TabButton>
        <TabButton active={activeTab === 'preview'} onClick={() => setActiveTab('preview')}>
          PDF Preview
        </TabButton>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'simple' && <SimpleFieldsEditor document={document} />}
        {activeTab === 'arrays' && <ComplexFieldsEditor document={document} />}
        {activeTab === 'preview' && <DocumentViewer fileUrl={document.file_url} />}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2 p-4 border-t">
        <button onClick={onClose} className="px-4 py-2 border rounded">Cancel</button>
        <button onClick={onSave} className="px-4 py-2 bg-blue-600 text-white rounded">
          Save Changes
        </button>
      </div>
    </div>
  );
}
```

**Visual**:
```
┌────────────────────┬──────────────────────────────────────────┐
│ AuditTableView     │ Document Drawer (2/3 width)              │
│                    │ ──────────────────────────────────────── │
│ [Doc List]         │ invoice_001.pdf                      [X] │
│                    │ ──────────────────────────────────────── │
│ • invoice_001.pdf  │ [Simple] [Arrays & Tables] [Preview]     │
│ • invoice_002.pdf  │                                          │
│ • invoice_003.pdf  │ Line Items (8 items)                     │
│                    │ ┌──────────────────────────────────────┐ │
│                    │ │ Description: Widget A                │ │
│                    │ │ Quantity: 10                         │ │
│                    │ │ Price: $25.00                        │ │
│                    │ └──────────────────────────────────────┘ │
└────────────────────┴──────────────────────────────────────────┘
```

**Pros**:
- Keeps table visible for context
- Can navigate between documents easily
- Tabbed interface separates concerns

**Cons**:
- Limited width for wide tables
- More complex state management

### 2.4 Recommended Hybrid Approach

**Strategy**: Use different patterns based on context and field complexity

#### In AuditTableView (Bulk Confirmation)

| Field Type | Display | Edit Mode |
|------------|---------|-----------|
| Simple (text, number, date) | Inline input | Direct edit |
| Simple array (<5 items) | Chip list | Inline chip editor |
| Simple array (>5 items) | Badge "N items" | Modal editor |
| Array of objects | Badge "N items" | Modal editor |
| Table | Badge "N×M" | Modal editor |

#### In Audit Single Field Mode

| Field Type | Display | Edit Mode |
|------------|---------|-----------|
| All types | PDF + Sidebar detail | Inline in sidebar |
| Complex (array, table) | Scrollable list/table in sidebar | Inline edit |

### 2.5 Detailed Component Architecture

```
frontend/src/components/
├── cells/                          # Cell renderers for AuditTableView
│   ├── SimpleFieldCell.jsx         # Text input (existing)
│   ├── ArrayChipCell.jsx           # NEW: Chip list for simple arrays
│   ├── ComplexDataCell.jsx         # NEW: Badge + modal trigger
│   └── FieldCellFactory.jsx        # NEW: Router based on field type
│
├── modals/
│   ├── ArrayEditorModal.jsx        # NEW: Edit array of primitives
│   ├── ArrayOfObjectsModal.jsx     # NEW: Edit array of objects (table view)
│   ├── TableEditorModal.jsx        # From COMPLEX_TABLE_EXTRACTION.md
│   └── ComplexDataModal.jsx        # NEW: Router to specific modal
│
├── editors/
│   ├── ChipListEditor.jsx          # NEW: Inline chip editing
│   ├── ArrayItemEditor.jsx         # NEW: Edit single array item
│   └── TableCellEditor.jsx         # NEW: Edit table cell with validation
│
├── AuditTableView.jsx              # EXISTING: Update to use FieldCellFactory
├── DocumentDrawer.jsx              # NEW: Optional drawer view
└── DocumentViewer.jsx              # EXISTING: No changes needed
```

### 2.6 Key Screens & User Flows

#### Flow 1: Bulk Confirmation with Simple Array

**Scenario**: User confirms 10 invoices, each with a "colors" array field

1. **Initial State**: AuditTableView shows 10 docs × 8 fields
   ```
   Document       | Invoice # | Date      | Colors                  | Total
   ───────────────┼───────────┼───────────┼─────────────────────────┼───────
   invoice_001    | INV-001   | 2025-01-15| [Navy][Black][White] +  | $250
   invoice_002    | INV-002   | 2025-01-16| [Red][Blue] +           | $180
   ```

2. **User clicks a chip**: Inline editor opens
   ```
   Colors: [Navy ✓] [Black ✓] [White ✓] [+ Add]
           Type new color... [Enter to add]
   ```

3. **User edits**: Adds "Gray", removes "White"
   ```
   Colors: [Navy ✓] [Black ✓] [Gray ✓] [+ Add]
   ```

4. **Click outside or Enter**: Saves inline
   ```
   Document       | Colors                  |
   ───────────────┼─────────────────────────┤
   invoice_001    | [Navy][Black][Gray] +   |
   ```

5. **Bulk confirm**: All edits saved to DB + ES

**Key UX Points**:
- No modal needed for simple arrays
- Visual feedback (chips change color)
- Keyboard friendly (Enter to add, Backspace to remove)

#### Flow 2: Bulk Confirmation with Array of Objects

**Scenario**: User confirms 10 invoices with "line_items" array

1. **Initial State**: Badge shows summary
   ```
   Document       | Line Items              | Total
   ───────────────┼─────────────────────────┼───────
   invoice_001    | [📋] 8 items • 78% ⚠   | $250
   invoice_002    | [📋] 3 items • 92% ✓   | $180
   ```

2. **User clicks badge**: Modal opens full screen
   ```
   ┌────────────────────────────────────────────────────┐
   │ Edit Line Items for invoice_001.pdf          [X]  │
   ├────────────────────────────────────────────────────┤
   │ Description       Qty  Price    Amount  Conf       │
   │ ────────────────  ───  ───────  ──────  ────       │
   │ Widget A          10   $25.00   $250    92% ✓      │
   │ Service B         1    $150.00  $150    88% ✓      │
   │ Supplies C ⚠      5    $12.50   $62.50  75% ⚠      │
   │ [+ Add Row]                                        │
   │                                                    │
   │ Low confidence items: 1                            │
   │ [Cancel]                       [Save Changes]      │
   └────────────────────────────────────────────────────┘
   ```

3. **User edits low-confidence row**: Clicks "Supplies C", inline edit
   ```
   │ Supplies & Materials  5    $12.50   $62.50  ✓     │
   ```

4. **User saves**: Returns to table view
   ```
   Document       | Line Items              | Total
   ───────────────┼─────────────────────────┼───────
   invoice_001    | [📋] 8 items • 92% ✓   | $250  ← confidence improved
   ```

5. **User repeats** for other low-confidence docs

6. **Bulk confirm**: Saves all changes

**Key UX Points**:
- Modal doesn't block workflow (can cancel and move to next doc)
- Confidence shown per-row and overall
- Auto-highlights low-confidence items
- Pagination for large datasets

#### Flow 3: Single Field Mode with Table

**Scenario**: User audits low-confidence fields one by one, encounters table

1. **Queue shows**: "grading_table" field with 75% confidence

2. **PDF viewer**: Shows page with table, bbox highlights entire table

3. **Sidebar**: Shows table summary + edit button
   ```
   ┌────────────────────────────────┐
   │ Field: Grading Table           │
   ├────────────────────────────────┤
   │ Extracted Value:               │
   │                                │
   │ 15 rows × 12 columns           │
   │ Avg Confidence: 75% ⚠          │
   │                                │
   │ Low confidence rows: 3         │
   │ - Row 5 (POM B510): 68%        │
   │ - Row 8 (POM C220): 72%        │
   │ - Row 12 (POM D150): 70%       │
   │                                │
   │ [Edit Table]                   │
   │ [✓ Correct] [✗ Fix] [⊘ Not Found]│
   └────────────────────────────────┘
   ```

4. **User clicks "Edit Table"**: Modal opens
   ```
   ┌──────────────────────────────────────────────┐
   │ Edit Grading Table for spec_001.pdf    [X]  │
   ├──────────────────────────────────────────────┤
   │ POM Code  Size 2  Size 3  ...  Size 10      │
   │ ────────  ──────  ──────  ───  ───────      │
   │ B510      10.5    11.0    ...  12.5    92%  │
   │ B520      10.0    10.5    ...  12.0    88%  │
   │ ...                                          │
   │ B510 ⚠    11.2 ⚠  11.8 ⚠  ...  13.1 ⚠  68%  │ ← low conf row
   │ ...                                          │
   │                                              │
   │ [Filter: Low Confidence Only ▼]             │
   │ Showing rows 1-10 of 15  [< Prev] [Next >]  │
   │                                              │
   │ [Save & Mark Correct]        [Save & Next]  │
   └──────────────────────────────────────────────┘
   ```

5. **User filters** to low-confidence rows only, edits

6. **User saves**: Returns to sidebar, confidence updated

7. **User marks "Correct"**: Moves to next field in queue

**Key UX Points**:
- PDF stays visible (context)
- Table editor integrated into audit flow
- Can filter to problem areas
- Save + continue workflow

### 2.7 Mobile Strategy

**Decision**: Complex data (arrays of objects, tables) is **view-only** on mobile

| Device | Simple Fields | Simple Arrays | Complex Data |
|--------|---------------|---------------|--------------|
| Desktop | ✅ Full edit | ✅ Full edit | ✅ Full edit (modal) |
| Tablet | ✅ Full edit | ✅ Full edit | ✅ Limited edit (drawer) |
| Mobile | ✅ Full edit | ⚠️ View + basic add/remove | ❌ View only |

**Mobile UI** (Simple Array Example):
```
┌─────────────────────────────┐
│ Colors                      │
├─────────────────────────────┤
│ • Navy (92%)                │
│ • Charcoal (88%)            │
│ • Black (95%)               │
│ • White (70%) ⚠             │
│                             │
│ [+ Add Color]               │
│ [Edit on Desktop →]         │
└─────────────────────────────┘
```

**Reasoning**:
- Table editing requires horizontal space (impossible on phone)
- Bulk confirmation is primarily a desktop workflow
- Mobile audit can focus on simple fields only
- Complex data can be reviewed on mobile, edited on desktop

### 2.8 Edge Cases & Solutions

#### Edge Case 1: Very Large Arrays (100+ items)

**Problem**: 100+ colors in a color palette document

**Solution**: Pagination + search
```jsx
<ArrayEditorModal>
  <SearchInput placeholder="Search colors..." />
  <ChipGrid items={filteredItems} maxVisible={20} />
  <Pagination currentPage={page} totalItems={items.length} />
</ArrayEditorModal>
```

**UX**: Show first 20, search to find specific item, paginate to browse

#### Edge Case 2: Nested Arrays (Array within Array)

**Problem**:
```json
{
  "care_instructions": [
    {
      "category": "Washing",
      "steps": ["Machine wash cold", "Use mild detergent"]
    },
    {
      "category": "Drying",
      "steps": ["Tumble dry low", "Remove promptly"]
    }
  ]
}
```

**Solution**: Two-level expansion
```
Care Instructions (2 categories)
├─ [▼] Washing (2 steps)
│  ├─ Machine wash cold
│  └─ Use mild detergent
└─ [▼] Drying (2 steps)
   ├─ Tumble dry low
   └─ Remove promptly
```

**UX**: Expandable tree view, edit leaf nodes inline

#### Edge Case 3: Mixed Confidence in Array

**Problem**: Array has items with wildly different confidence (20% to 95%)

**Solution**: Visual sorting + filtering
```jsx
// Sort by confidence (low to high)
const sortedItems = items.sort((a, b) =>
  (confidence[a] || 0) - (confidence[b] || 0)
);

// Highlight low-confidence items
<Chip
  className={conf < 0.6 ? 'ring-2 ring-red-500' : ''}
  showWarningIcon={conf < 0.6}
/>
```

**UX**:
- Default sort: Low confidence first (review these first)
- Toggle: "Show only low confidence"
- Visual indicator: Red ring around low-confidence chips

#### Edge Case 4: Array Item Validation Errors

**Problem**: User adds "XL" to sizes array, but schema expects "X-Large"

**Solution**: Real-time validation with suggestions
```jsx
<ChipInput
  value={input}
  onChange={setInput}
  onKeyDown={(e) => {
    if (e.key === 'Enter') {
      const validation = validateItem(input, schema);
      if (!validation.valid) {
        setError(validation.message);
        setSuggestions(validation.suggestions);
      } else {
        addItem(input);
      }
    }
  }}
/>

{error && (
  <div className="text-red-600 text-sm">
    {error}
    {suggestions.length > 0 && (
      <div className="mt-1">
        Did you mean: {suggestions.map(s => (
          <button key={s} onClick={() => addItem(s)} className="underline">
            {s}
          </button>
        ))}?
      </div>
    )}
  </div>
)}
```

**UX**: Inline validation, smart suggestions, prevent invalid data

#### Edge Case 5: Batch Editing Same Field Across Docs

**Problem**: User wants to add "Navy" to colors field for 10 documents at once

**Solution**: Batch edit mode
```jsx
// In AuditTableView, add checkbox selection
<button onClick={() => setBatchEditMode(true)}>
  Batch Edit Selected
</button>

// Show batch editor modal
<BatchEditModal
  field="colors"
  selectedDocuments={selectedDocs}
  onApplyToAll={(operation) => {
    // operation: {action: "add", value: "Navy"}
    selectedDocs.forEach(doc => applyOperation(doc, operation));
  }}
/>
```

**UX**:
1. User selects 10 documents (checkboxes)
2. Click "Batch Edit > Colors"
3. Modal: "Add Navy to all selected" + preview
4. Confirm → Applied to all 10

**Caveat**: Only for simple operations (add item, remove item). Complex edits still per-document.

### 2.9 Performance Considerations

#### Large Dataset Rendering

**Problem**: Rendering 100 documents × 20 fields = 2000 cells

**Solution**: Virtual scrolling
```jsx
import { useVirtualizer } from '@tanstack/react-virtual';

function AuditTableView({ documents, schema }) {
  const parentRef = useRef();

  const rowVirtualizer = useVirtualizer({
    count: documents.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60,
    overscan: 10
  });

  return (
    <div ref={parentRef} className="h-screen overflow-auto">
      <div style={{ height: `${rowVirtualizer.getTotalSize()}px` }}>
        {rowVirtualizer.getVirtualItems().map(virtualRow => {
          const doc = documents[virtualRow.index];
          return <TableRow key={doc.id} document={doc} />;
        })}
      </div>
    </div>
  );
}
```

**Result**: Only renders visible rows (~20), smooth scrolling with 1000+ docs

#### Complex Data Caching

**Problem**: Opening modal for same document multiple times re-fetches data

**Solution**: React Query caching
```jsx
import { useQuery } from '@tanstack/react-query';

function ComplexDataModal({ document, field }) {
  const { data, isLoading } = useQuery({
    queryKey: ['field', document.id, field.name],
    queryFn: () => fetchFieldData(document.id, field.name),
    staleTime: 5 * 60 * 1000, // 5 min cache
  });

  return <ModalContent data={data} />;
}
```

**Result**: Instant modal open on second+ view, reduced API calls

### 2.10 Implementation Priority

**Phase 1: Foundation** (Week 1)
- [ ] Add `field_value_json` and `field_type` columns to DB
- [ ] Update ES mapping to support nested fields
- [ ] Create FieldCellFactory component (routes to correct cell type)
- [ ] Update AuditTableView to use FieldCellFactory

**Phase 2: Simple Arrays** (Week 2)
- [ ] Create ArrayChipCell component (inline chip editor)
- [ ] Create ArrayEditorModal (for arrays >5 items)
- [ ] Update Reducto service to extract arrays
- [ ] Test with "colors", "sizes" fields

**Phase 3: Arrays of Objects** (Week 3)
- [ ] Create ArrayOfObjectsModal (table editor for array items)
- [ ] Add confidence tracking per array item
- [ ] Update Claude prompts to detect array fields
- [ ] Test with "line_items", "materials" fields

**Phase 4: Tables** (Week 4)
- [ ] Implement TableEditorModal (from COMPLEX_TABLE_EXTRACTION.md)
- [ ] Add table schema support in Claude prompts
- [ ] Add nested ES queries for tables
- [ ] Test with grading specs, price matrices

**Phase 5: Polish** (Week 5)
- [ ] Add batch editing for arrays
- [ ] Implement virtual scrolling for large datasets
- [ ] Add mobile responsive views
- [ ] Handle all edge cases (nested arrays, validation, etc.)

---

## Part 3: Complete Examples

### Example 1: Invoice Template with Mixed Field Types

```json
{
  "name": "Invoice Template",
  "category": "invoice",
  "fields": [
    {
      "name": "invoice_number",
      "type": "text",
      "required": true,
      "confidence_threshold": 0.85
    },
    {
      "name": "invoice_date",
      "type": "date",
      "required": true,
      "confidence_threshold": 0.8
    },
    {
      "name": "payment_terms",
      "type": "array",
      "description": "Payment terms and conditions",
      "array_config": {
        "item_type": "text",
        "min_items": 1,
        "max_items": 10
      },
      "extraction_hints": ["Payment Terms:", "Terms:"]
    },
    {
      "name": "line_items",
      "type": "table",
      "description": "Invoice line items",
      "table_schema": {
        "row_identifier": "line_number",
        "columns": ["description", "quantity", "unit_price", "amount"],
        "dynamic_columns": false
      },
      "confidence_threshold": 0.75
    },
    {
      "name": "total_amount",
      "type": "number",
      "required": true,
      "confidence_threshold": 0.9
    }
  ]
}
```

**Rendered in AuditTableView**:
```
Document      | Invoice # | Date       | Payment Terms            | Line Items        | Total
──────────────┼───────────┼────────────┼──────────────────────────┼───────────────────┼────────
invoice_001   | INV-001   | 2025-01-15 | [Net 30][2% disc...] +   | [📋] 8×4 • 78% ⚠ | $250.00
invoice_002   | INV-002   | 2025-01-16 | [Net 15] +               | [📋] 3×4 • 92% ✓ | $180.50
```

### Example 2: Garment Spec with Complex Arrays

```json
{
  "name": "Garment Specification",
  "category": "apparel",
  "fields": [
    {
      "name": "style_number",
      "type": "text",
      "required": true
    },
    {
      "name": "colors",
      "type": "array",
      "array_config": {
        "item_type": "text",
        "min_items": 1,
        "max_items": 20
      }
    },
    {
      "name": "sizes",
      "type": "array",
      "array_config": {
        "item_type": "text",
        "min_items": 1,
        "max_items": 15
      }
    },
    {
      "name": "materials",
      "type": "array",
      "array_config": {
        "item_type": "object"
      },
      "array_items": [
        {
          "name": "material",
          "type": "text",
          "required": true
        },
        {
          "name": "percentage",
          "type": "number",
          "required": true
        },
        {
          "name": "supplier",
          "type": "text",
          "required": false
        }
      ]
    },
    {
      "name": "grading_table",
      "type": "table",
      "table_schema": {
        "row_identifier": "pom_code",
        "columns": ["size_2", "size_4", "size_6", "size_8", "size_10", "size_12"],
        "dynamic_columns": true,
        "column_pattern": "size_.*",
        "value_type": "number"
      }
    }
  ]
}
```

**Rendered in AuditTableView**:
```
Document    | Style | Colors                    | Sizes                     | Materials      | Grading
────────────┼───────┼───────────────────────────┼───────────────────────────┼────────────────┼──────────
spec_001    | S1234 | [Navy][Black][White] +    | [XS][S][M][L][XL] +      | [📋] 3 • 87%  | [📋] 15×12 • 82%
spec_002    | S1235 | [Red][Blue] +             | [2][4][6][8][10] +       | [📋] 2 • 92%  | [📋] 12×8 • 88%
```

---

## Summary & Recommendations

### Key Decisions

1. **Array Fields**: Implement with per-item confidence tracking
   - Simple arrays: Store as JSON array with confidence array
   - Arrays of objects: Nested structure with confidence per item
   - Tables: Use table schema (from existing design doc)

2. **UI Strategy**: Hybrid approach based on field complexity
   - Simple fields: Inline editing (current)
   - Simple arrays: Chip list with inline editor
   - Complex arrays & tables: Badge + modal editor
   - Optional: Drawer for contextual detail view

3. **Mobile**: View-only for complex data, full edit for simple fields

4. **Performance**: Virtual scrolling + React Query caching for large datasets

### Next Steps

1. **Review this document** with team for feedback
2. **Choose Phase 1 or Phase 2** as starting point:
   - Phase 1: If you want full foundation (DB, ES, routing)
   - Phase 2: If you want to see arrays working quickly (can backfill foundation)
3. **Create tickets** for chosen phase
4. **Implement** using provided component examples
5. **Test** with real documents from your use case

### Success Criteria

- ✅ Users can edit arrays inline (chip list) in <30s
- ✅ Users can edit complex arrays in modal in <2 min
- ✅ Confidence shown per-item for arrays
- ✅ Audit queue works with complex fields
- ✅ Bulk confirmation supports all field types
- ✅ Mobile users can view (not necessarily edit) all data

---

**Questions or Feedback?** Review this doc and let me know which approach you prefer for each component. I can then generate detailed implementation code for the chosen path.
