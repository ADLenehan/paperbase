# Export Feature Documentation

## Overview

The export feature allows users to extract document data in multiple formats (CSV, Excel, JSON) for analysis, reporting, or integration with other systems.

**Status**: ✅ Complete and Ready to Use

## Features

### 1. Multiple Export Formats

- **Excel (.xlsx)** - Formatted spreadsheets with auto-sized columns and bold headers
- **CSV (.csv)** - Plain text format compatible with all tools
- **JSON (.json)** - Structured data for APIs and integrations

### 2. Flexible Filtering

- Filter by template/document type
- Date range filtering (from/to dates)
- Minimum confidence threshold
- Verified fields only
- Specific document selection

### 3. Data Formats

**Wide Format** (default):
- One row per document
- Each field as a column
- Best for spreadsheet analysis

**Long Format** (optional):
- One row per field
- Better for BI tools and pivoting

### 4. Metadata Options

- Include/exclude confidence scores
- Include/exclude verification status
- Document status and timestamps

## API Endpoints

### List Exportable Templates
```bash
GET /api/export/templates

Response:
{
  "templates": [
    {
      "id": 1,
      "name": "Invoice",
      "category": "finance",
      "document_count": 150,
      "field_count": 12
    }
  ]
}
```

### Export by Template (Simple)
```bash
# Excel format
GET /api/export/template/{template_id}/excel?date_from=2025-01-01&confidence_min=0.8

# CSV format
GET /api/export/template/{template_id}/csv

# JSON format
GET /api/export/template/{template_id}/json?format_type=pretty
```

**Query Parameters:**
- `date_from` (optional): Start date (YYYY-MM-DD)
- `date_to` (optional): End date (YYYY-MM-DD)
- `confidence_min` (optional): Minimum confidence (0.0-1.0)
- `verified_only` (optional): Only verified fields (true/false)
- `include_metadata` (optional): Include confidence/verification columns (true/false)
- `format_type` (JSON only): pretty, compact, or records

### Export Specific Documents
```bash
GET /api/export/documents?document_ids=1,2,3&format=excel
```

### Custom Export (Advanced)
```bash
POST /api/export/custom?format=excel

Body:
{
  "template_id": 1,
  "date_from": "2025-01-01",
  "date_to": "2025-12-31",
  "confidence_min": 0.7,
  "verified_only": false,
  "include_metadata": true,
  "format_type": "wide"  // or "long"
}
```

### Export Summary (Preview)
```bash
GET /api/export/summary?template_id=1&date_from=2025-01-01

Response:
{
  "total_documents": 150,
  "total_fields": 1800,
  "verified_fields": 1500,
  "verification_rate": 0.83,
  "average_confidence": 0.89,
  "template": {
    "id": 1,
    "name": "Invoice"
  }
}
```

## Frontend Usage

### 1. Export Page (Standalone)

Navigate to `/export` to browse all templates and export data:

```jsx
// Already integrated in App.jsx
<Route path="export" element={<Export />} />
```

Features:
- Template grid with document counts
- Category filtering
- One-click export with modal
- Export format selection
- Advanced filtering options

### 2. Export Button Component (Reusable)

Add export functionality anywhere in your app:

```jsx
import ExportButton from '../components/ExportButton';

// Export all documents for a template
<ExportButton templateId={5} />

// Export specific documents
<ExportButton documentIds={[1, 2, 3]} label="Export Selected" />

// Different button styles
<ExportButton templateId={5} variant="secondary" />
<ExportButton templateId={5} variant="ghost" />
```

### 3. Export Modal Component (Full Control)

```jsx
import { useState } from 'react';
import ExportModal from '../components/ExportModal';

function MyComponent() {
  const [showExport, setShowExport] = useState(false);

  return (
    <>
      <button onClick={() => setShowExport(true)}>
        Export
      </button>

      <ExportModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        templateId={5}
      />
    </>
  );
}
```

## Use Cases

### 1. Monthly Finance Reports
```bash
# Export all invoices from last month
GET /api/export/template/1/excel?date_from=2025-09-01&date_to=2025-09-30
```

### 2. High-Confidence Data Only
```bash
# Export only fields with 90%+ confidence
GET /api/export/template/1/csv?confidence_min=0.9
```

### 3. Verified Records for Audit
```bash
# Export only verified fields for compliance audit
GET /api/export/template/1/excel?verified_only=true&include_metadata=true
```

### 4. API Integration
```bash
# Get JSON for data pipeline
GET /api/export/template/1/json?format_type=records

# Returns JSON Lines format (one object per line)
{"document_id": 1, "invoice_number": "INV-001", ...}
{"document_id": 2, "invoice_number": "INV-002", ...}
```

### 5. Selected Documents Export
```bash
# From UI: User selects 5 documents → Export button
GET /api/export/documents?document_ids=101,102,103,104,105&format=excel
```

## Data Structure

### Wide Format (Default)
```csv
document_id,filename,status,invoice_number,amount,date,vendor_name
1,invoice_001.pdf,completed,INV-001,1500.00,2025-09-15,Acme Corp
2,invoice_002.pdf,completed,INV-002,3200.00,2025-09-16,Tech Solutions
```

### Long Format
```csv
document_id,filename,field_name,extracted_value,verified_value,final_value,confidence_score,verified
1,invoice_001.pdf,invoice_number,INV-001,INV-001,INV-001,0.95,true
1,invoice_001.pdf,amount,1500.00,1500.00,1500.00,0.89,true
1,invoice_001.pdf,date,2025-09-15,2025-09-15,2025-09-15,0.92,true
```

### With Metadata
```csv
document_id,filename,invoice_number,invoice_number_confidence,invoice_number_verified,amount,amount_confidence,amount_verified
1,invoice_001.pdf,INV-001,0.95,true,1500.00,0.89,true
```

## Performance

- **Small exports** (<100 docs): Instant download
- **Medium exports** (100-1000 docs): 1-3 seconds
- **Large exports** (1000+ docs): 5-10 seconds

**Tips for large exports:**
- Use CSV instead of Excel for better performance
- Apply filters to reduce dataset size
- Export in batches using date ranges

## File Naming

Exported files automatically include:
- Template name (sanitized)
- Export date
- Appropriate extension

Examples:
- `Invoice_20251014.xlsx`
- `Contract_20251014.csv`
- `Receipt_20251014.json`

## Error Handling

### No Documents Found
```json
{
  "detail": "No documents found matching criteria"
}
```

**Solution**: Adjust filters or check if template has processed documents

### Template Not Found
```json
{
  "detail": "Template not found"
}
```

**Solution**: Verify template ID exists

### Invalid Parameters
```json
{
  "detail": "Invalid document IDs format"
}
```

**Solution**: Check query parameter format

## Integration Examples

### Python
```python
import requests

# Export to Excel
response = requests.get(
    'http://localhost:8000/api/export/template/1/excel',
    params={
        'date_from': '2025-01-01',
        'confidence_min': 0.8
    }
)

with open('export.xlsx', 'wb') as f:
    f.write(response.content)
```

### JavaScript/Node.js
```javascript
const response = await fetch(
  'http://localhost:8000/api/export/template/1/json'
);
const data = await response.json();
console.log(data);
```

### cURL
```bash
# Download Excel file
curl -O -J 'http://localhost:8000/api/export/template/1/excel?confidence_min=0.8'

# Save to specific filename
curl 'http://localhost:8000/api/export/template/1/csv' > invoices.csv
```

## Future Enhancements

### Planned Features
- [ ] Scheduled exports (daily/weekly/monthly)
- [ ] Email delivery of exports
- [ ] Google Sheets direct integration
- [ ] Excel templates with formulas
- [ ] Multi-template exports (combine multiple templates)
- [ ] Custom column selection
- [ ] Export to cloud storage (S3, GCS, Azure)

### Premium Features (Monetization)
- [ ] QuickBooks integration (sync directly)
- [ ] Xero integration
- [ ] Data warehouse connectors (Snowflake, BigQuery)
- [ ] Advanced reporting with charts
- [ ] Automated reconciliation reports

## Testing

### Manual Testing
1. Navigate to http://localhost:3001/export
2. Select a template with documents
3. Click "Export Data"
4. Choose format (Excel/CSV/JSON)
5. Apply filters (optional)
6. Click "Export"
7. Verify downloaded file

### API Testing
```bash
# Test summary endpoint
curl http://localhost:8000/api/export/summary?template_id=1

# Test CSV export
curl http://localhost:8000/api/export/template/1/csv > test.csv

# Test Excel export
curl -O -J http://localhost:8000/api/export/template/1/excel

# Test JSON export
curl http://localhost:8000/api/export/template/1/json?format_type=pretty
```

### Check Exported Data
```bash
# View CSV
head test.csv

# Count rows
wc -l test.csv

# Check Excel structure (requires Python)
python -c "import pandas as pd; df = pd.read_excel('test.xlsx'); print(df.head()); print(df.shape)"
```

## Troubleshooting

### Export button not showing
- Verify template has documents (`document_count > 0`)
- Check browser console for errors
- Ensure backend is running

### Download fails
- Check browser's download folder settings
- Verify popup blocker isn't blocking download
- Check backend logs for errors

### Empty export file
- Verify filters aren't too restrictive
- Check that documents have extracted fields
- Try exporting without filters first

### Formatting issues in Excel
- Try CSV format instead
- Check for special characters in field values
- Ensure proper encoding (UTF-8)

## Architecture

### Backend Stack
```
FastAPI → ExportService → pandas → Excel/CSV/JSON
            ↓
       SQLAlchemy (query documents)
            ↓
       Database (SQLite/PostgreSQL)
```

### Service Layer
- `ExportService` - Core export logic
- `build_export_query()` - Dynamic query building with filters
- `documents_to_records()` - Data transformation (wide format)
- `documents_to_long_format()` - Data transformation (long format)
- `export_to_csv()` - CSV generation
- `export_to_excel()` - Excel generation with formatting
- `export_to_json()` - JSON generation

### Frontend Components
- `Export.jsx` - Full export page
- `ExportModal.jsx` - Reusable modal component
- `ExportButton.jsx` - Simple button wrapper

## Dependencies

### Backend
```txt
pandas==2.1.3         # Data manipulation
openpyxl==3.1.2       # Excel file generation
```

### Frontend
```txt
None (uses standard React/Axios)
```

## Configuration

No configuration required! Works out of the box.

Optional environment variables:
```env
# None currently - all export settings are user-configurable via UI
```

---

**Last Updated**: 2025-10-14
**Version**: 1.0.0
**Status**: Production Ready ✅
