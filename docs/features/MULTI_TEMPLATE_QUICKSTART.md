# Multi-Template Extraction - Quick Start Guide

## 🚀 Getting Started

### Prerequisites

1. Backend running on `http://localhost:8000`
2. Database migrated to new schema
3. At least 2 templates configured

### Quick Setup

```bash
# 1. Backup your database
cp backend/paperbase.db backend/paperbase.db.backup

# 2. Run migration
cd backend
python -m app.migrations.migrate_to_extractions --create-tables
python -m app.migrations.migrate_to_extractions

# 3. Verify migration
python -m app.migrations.migrate_to_extractions --dry-run
```

## 📖 Common Use Cases

### Use Case 1: Upload File and Try Multiple Templates

**Scenario**: You have a document that could be either an Invoice or a Contract. Try both!

```bash
# Upload and extract with 2 templates
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@document.pdf" \
  -F "template_ids=1" \
  -F "template_ids=2"
```

**Result**:
- 1 physical file stored
- 2 extractions created (Invoice and Contract)
- Compare results to see which template fits better

### Use Case 2: Batch Process 100 Invoices

**Scenario**: You have 100 invoice PDFs to process with the Invoice template.

```bash
# Step 1: Upload all files (they get deduplicated automatically)
for file in invoices/*.pdf; do
  curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
    -F "files=@$file"
done

# Step 2: Get all physical file IDs
curl http://localhost:8000/api/folders/browse?path= | jq -r '.files[].physical_file_id'

# Step 3: Batch extract with Invoice template
curl -X POST http://localhost:8000/api/extractions/batch-extract \
  -H "Content-Type: application/json" \
  -d '{
    "physical_file_ids": [1,2,3,4,5,...],
    "template_id": 1,
    "batch_name": "Q3 2025 Invoices"
  }'
```

**Result**:
- All files organized in `Invoice/2025-10-11/` folder
- Progress tracking via batch API
- Parse results cached (no redundant API calls)

### Use Case 3: Reorganize Files into Archive

**Scenario**: Move all completed extractions from Q3 to archive folder.

```bash
# Step 1: Browse Invoice folder
curl http://localhost:8000/api/folders/browse?path=Invoice/2025-09 | jq

# Step 2: Get completed extraction IDs
EXTRACTION_IDS=$(curl http://localhost:8000/api/folders/browse?path=Invoice/2025-09 \
  | jq -r '.files[] | select(.status=="completed") | .extraction_id')

# Step 3: Move to archive
curl -X POST http://localhost:8000/api/folders/reorganize \
  -H "Content-Type: application/json" \
  -d "{
    \"extraction_ids\": [$EXTRACTION_IDS],
    \"target_path\": \"Archive/2025-Q3\"
  }"
```

**Result**:
- Files instantly moved to Archive folder (metadata only, no copying!)
- Original physical files unchanged
- Can move back anytime

### Use Case 4: Compare Template Results

**Scenario**: Same document extracted with different templates - which one is better?

```bash
# Step 1: Get all extractions for a file
curl http://localhost:8000/api/extractions/extractions/1 | jq

# Response shows both extractions:
{
  "physical_file_id": 1,
  "filename": "contract.pdf",
  "extractions": [
    {
      "id": 1,
      "template_name": "Invoice",
      "confidence": 0.65,
      "status": "completed",
      "field_count": 8
    },
    {
      "id": 2,
      "template_name": "Contract",
      "confidence": 0.92,
      "status": "completed",
      "field_count": 15
    }
  ]
}

# Step 2: Compare field details
curl http://localhost:8000/api/extractions/extractions/detail/1 | jq
curl http://localhost:8000/api/extractions/extractions/detail/2 | jq

# Step 3: Choose better one, delete the other
curl -X DELETE http://localhost:8000/api/extractions/extractions/1
```

**Result**:
- Side-by-side comparison
- Keep the better extraction
- Physical file remains (still referenced by extraction #2)

### Use Case 5: Reprocess with Different Template

**Scenario**: Extraction failed or used wrong template. Try again!

```bash
# Option 1: Reprocess with same template
curl -X POST http://localhost:8000/api/extractions/extractions/123/reprocess

# Option 2: Reprocess with different template
curl -X POST http://localhost:8000/api/extractions/extractions/123/reprocess \
  -H "Content-Type: application/json" \
  -d '{"template_id": 5}'
```

**Result**:
- Creates new extraction with new template
- Original extraction kept for comparison
- Reuses cached parse result (fast & cheap!)

## 📊 Monitoring & Statistics

### Check System Stats

```bash
# Overall extraction statistics
curl http://localhost:8000/api/extractions/stats | jq

# Sample response:
{
  "extractions": {
    "total_extractions": 1500,
    "by_status": {
      "completed": 1400,
      "processing": 50,
      "error": 50
    },
    "by_template": {
      "Invoice": 800,
      "Contract": 500,
      "Receipt": 200
    }
  },
  "storage": {
    "total_files": 1000,
    "total_size_mb": 512.5,
    "total_extractions": 1500,
    "duplicates_avoided": 500,  # 500 files were deduplicated!
    "avg_file_size_mb": 0.51
  }
}
```

### Browse Folder Structure

```bash
# Get folder tree
curl http://localhost:8000/api/folders/tree?max_depth=2 | jq

# Sample response:
{
  "tree": [
    {
      "name": "Invoice",
      "path": "Invoice",
      "children": [
        {"name": "2025-10-01", "path": "Invoice/2025-10-01", "children": []},
        {"name": "2025-10-11", "path": "Invoice/2025-10-11", "children": []}
      ]
    },
    {
      "name": "Contract",
      "path": "Contract",
      "children": [...]
    }
  ]
}
```

### Search in Folder

```bash
# Search for "agreement" in Contract folder
curl "http://localhost:8000/api/folders/search?path=Contract&q=agreement" | jq

# Sample response:
{
  "results": [
    {
      "id": 45,
      "extraction_id": 45,
      "filename": "service_agreement.pdf",
      "template": "Contract",
      "path": "Contract/2025-10-11/service_agreement.pdf",
      "status": "completed",
      "confidence": 0.95
    }
  ],
  "count": 1,
  "query": "agreement",
  "path": "Contract"
}
```

## 🔧 Troubleshooting

### Problem: File uploaded twice, wasted storage

**Solution**: Files are automatically deduplicated! Check response:

```bash
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@document.pdf" | jq '.duplicates_found'

# If duplicates_found > 0, the file was already uploaded
```

### Problem: Extraction stuck in "processing"

**Solution**: Check error message and reprocess:

```bash
# Get extraction details
curl http://localhost:8000/api/extractions/extractions/detail/123 | jq '.error_message'

# Reprocess
curl -X POST http://localhost:8000/api/extractions/extractions/123/reprocess
```

### Problem: Can't find extraction in folder

**Solution**: Check organized path:

```bash
# Get extraction details
curl http://localhost:8000/api/extractions/extractions/detail/123 | jq '.organized_path'

# Browse that path
curl "http://localhost:8000/api/folders/browse?path=Invoice/2025-10-11" | jq
```

### Problem: Want to delete file but it says "still referenced"

**Solution**: Delete all extractions first:

```bash
# List all extractions for file
curl http://localhost:8000/api/extractions/extractions/1 | jq '.extractions[].id'

# Delete each extraction
curl -X DELETE http://localhost:8000/api/extractions/extractions/2
curl -X DELETE http://localhost:8000/api/extractions/extractions/3

# Now delete physical file (automatic when last extraction deleted)
```

## 💡 Pro Tips

### Tip 1: Always use template_ids parameter

```bash
# ❌ Bad: Upload without templates (requires manual extraction later)
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@doc.pdf"

# ✅ Good: Upload with templates (processes immediately)
curl -X POST http://localhost:8000/api/extractions/upload-and-extract \
  -F "files=@doc.pdf" \
  -F "template_ids=1"
```

### Tip 2: Use batch extraction for large volumes

```bash
# ❌ Bad: Process files one by one (slow)
for file in *.pdf; do
  curl -X POST ... # Individual requests
done

# ✅ Good: Batch process (fast, tracked)
curl -X POST http://localhost:8000/api/extractions/batch-extract ...
```

### Tip 3: Virtual folders are instant

```bash
# Reorganizing 1000 files takes <1 second (metadata only!)
curl -X POST http://localhost:8000/api/folders/reorganize \
  -d '{"extraction_ids": [1,2,3,...,1000], "target_path": "Archive"}'
```

### Tip 4: Parse once, extract many times

```bash
# First extraction: parses document
curl -X POST ... -F "template_ids=1"  # Calls Reducto parse + extract

# Second extraction: reuses parse
curl -X POST ... -F "template_ids=2"  # Only calls Reducto extract (jobid://)
# Cost: ~60% savings!
```

## 📈 Cost Optimization

### Scenario: 1000 documents, 3 templates each

**Old Way** (no deduplication, no caching):
- Uploads: 3000 (same doc uploaded 3×)
- Parses: 3000
- Extractions: 3000
- **Cost**: ~$300

**New Way** (with deduplication + caching):
- Uploads: 1000 (deduplicated)
- Parses: 1000 (cached)
- Extractions: 3000 (using jobid://)
- **Cost**: ~$120

**Savings**: 60% ($180 saved!)

## 🎯 Next Steps

1. **Frontend Integration**: Build UI components (see `FRONTEND_COMPONENTS.md`)
2. **Advanced Search**: Full-text search within folders
3. **Template Comparison UI**: Visual side-by-side comparison
4. **Batch Progress**: Real-time progress tracking
5. **Folder Analytics**: Per-folder statistics dashboard

## 📚 API Reference

- [Complete API Documentation](./MULTI_TEMPLATE_EXTRACTION.md)
- [Migration Guide](./MULTI_TEMPLATE_EXTRACTION.md#migration-guide)
- [Troubleshooting](./MULTI_TEMPLATE_EXTRACTION.md#troubleshooting)

---

**Questions?** Check the full documentation or open an issue.
