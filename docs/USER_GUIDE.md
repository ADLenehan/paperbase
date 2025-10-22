# Paperbase User Guide

Welcome to Paperbase! This guide will walk you through using the platform to extract structured data from your documents.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Onboarding: Creating Your Schema](#onboarding-creating-your-schema)
3. [Processing Documents](#processing-documents)
4. [Searching & Finding Documents](#searching--finding-documents)
5. [Verifying Extractions](#verifying-extractions)
6. [Analytics Dashboard](#analytics-dashboard)
7. [Tips & Best Practices](#tips--best-practices)
8. [FAQ](#faq)

---

## Getting Started

### What is Paperbase?

Paperbase is a no-code document extraction platform that:
- **Learns from your documents** - Upload 3-5 samples, AI generates extraction schema
- **Processes documents automatically** - Bulk upload and extract structured data
- **Maintains high accuracy** - Human-in-the-loop verification for low-confidence items
- **Scales efficiently** - Costs ~$25-35 per 1000 documents

### First Time Setup

1. **Access the application**: Navigate to `http://localhost:3000` (or your deployment URL)

2. **No login required** (MVP): The current version is single-user

3. **Ensure services are running**:
   - Backend: `http://localhost:8000/health` should return `{"status": "healthy"}`
   - Frontend should load without errors

---

## Onboarding: Creating Your Schema

### Step 1: Prepare Sample Documents

Choose 3-5 representative documents of the same type. For example:
- ✅ **Good**: 5 invoices from different vendors
- ✅ **Good**: 4 employment contracts with varying formats
- ❌ **Bad**: Mix of invoices, contracts, and receipts

**Tips**:
- Documents should contain all fields you want to extract
- Include variety in formatting (different vendors, dates, etc.)
- PDFs work best (max 50MB each)

### Step 2: Upload Samples

1. Click **"Onboarding"** in the navigation
2. Drag and drop 3-5 PDF files into the upload area
   - Or click to browse files
3. Click **"Analyze Documents"**

**What happens next**:
- Reducto parses each document (20-30 seconds per document)
- Claude analyzes patterns and generates schema (1-2 minutes)
- You'll see the generated schema with suggested fields

### Step 3: Review Generated Schema

The AI-generated schema includes:

```
Schema Name: Service Agreements

Fields:
- effective_date (Date) - Contract effective date
  Hints: "Effective Date:", "Dated:", "As of"

- contract_value (Number) - Total contract value
  Hints: "Total Value:", "Contract Amount:"

- party_a (Text) - First contracting party
  Hints: "Client:", "Customer:"
```

**Field Properties**:
- **Name**: Machine-readable field name (snake_case)
- **Type**: Data type (text, date, number, boolean)
- **Required**: Whether field must be present
- **Hints**: Keywords that appear near the field value
- **Confidence Threshold**: Minimum confidence for auto-acceptance

### Step 4: Edit Schema (Optional)

**Add a Field**:
1. Click **"Add Field"**
2. Enter natural language: "Add a field for customer email"
3. Review AI suggestion
4. Click **"Add"**

**Edit a Field**:
1. Click the edit icon next to any field
2. Modify:
   - Field name
   - Data type
   - Extraction hints (add/remove keywords)
   - Confidence threshold (slider)
   - Required flag
3. Click **"Save"**

**Remove a Field**:
1. Click the delete icon
2. Confirm deletion

**Test on Samples**:
1. Click **"Test Extraction"**
2. See how current schema performs on your samples
3. Adjust hints if extraction is incorrect

### Step 5: Finalize Schema

1. Review all fields
2. Click **"Save Schema"**
3. You're ready to process documents!

---

## Processing Documents

### Bulk Upload

1. Click **"Documents"** in navigation
2. Select your schema from dropdown
3. Drag and drop documents (or click to browse)
   - Upload 1-100+ documents at once
   - Max 50MB per file
4. Click **"Upload"**

**Upload Progress**:
- Green checkmark: Uploaded successfully
- Yellow spinner: Uploading...
- Red X: Upload failed (hover for details)

### Start Processing

1. Select uploaded documents (checkbox)
   - Or click **"Process All"**
2. Click **"Start Processing"**

**Processing Status**:
- **Pending**: Uploaded, waiting for processing
- **Processing**: Currently being extracted
- **Completed**: Extraction complete
- **Error**: Processing failed

**Monitoring**:
- Processing time: 2-5 seconds per document
- Progress bar shows completion percentage
- Errors are logged and can be retried

### View Extraction Results

1. Click on any completed document
2. See all extracted fields:

```
Document: invoice_12345.pdf
Status: Completed
Processed: 2024-01-15 10:05:32

Extractions:
✓ invoice_number: "INV-12345" (92% confidence)
✓ invoice_date: "2024-01-15" (88% confidence)
⚠ total_amount: "1250.00" (65% confidence) - Needs verification
```

**Confidence Indicators**:
- 🟢 **High (≥80%)**: Highly confident, auto-accepted
- 🟡 **Medium (60-80%)**: Good confidence, review if important
- 🔴 **Low (<60%)**: Needs human verification

---

## Searching & Finding Documents

### Basic Search

1. Click **"Search"** in navigation
2. Enter search query: e.g., "contract value 125000"
3. Press Enter

**Results show**:
- Document filename
- Relevance score
- Highlighted matching text
- Key extracted fields

### Advanced Filtering

Click **"Filters"** to refine results:

**Filter by Confidence**:
- High confidence only
- Medium or higher
- All results including low

**Filter by Field Values**:
- Date ranges: "Invoice Date: 2024-01-01 to 2024-12-31"
- Number ranges: "Total Amount: $1000 to $5000"
- Text matches: "Vendor: Acme Corp"

**Filter by Schema**:
- Select specific document type
- Useful if you have multiple schemas

### Search Examples

```
# Find invoices over $10,000
Query: invoice
Filters: total_amount >= 10000

# Find contracts from Q1 2024
Query: contract
Filters: effective_date >= 2024-01-01, effective_date <= 2024-03-31

# Find documents needing review
Filters: confidence < 0.8

# Find specific vendor
Query: "Acme Corporation"
```

### Export Results

1. Select documents from search results
2. Click **"Export"**
3. Choose format:
   - CSV: Spreadsheet-compatible
   - JSON: For API integration
   - PDF: Printable report

---

## Verifying Extractions

### Why Verify?

Low-confidence extractions (<60% by default) need human verification to:
- Ensure accuracy
- Create training examples for future improvements
- Maintain data quality

### Verification Queue

1. Click **"Verify"** in navigation
2. See queue summary:
   - Total items needing review
   - Grouped by document or field
   - Priority sorting

### Reviewing Items

**Verification Interface**:

```
┌──────────────────────┬──────────────────────┐
│ PDF Preview          │ Verification Form     │
│                      │                      │
│ [Document page       │ Field: invoice_number│
│  with highlighted    │                      │
│  extraction region]  │ Extracted: "INV-12?45"│
│                      │ Confidence: 55%      │
│                      │                      │
│                      │ ○ Correct            │
│                      │ ● Incorrect - Enter: │
│                      │   [INV-12345]        │
│                      │ ○ Not found          │
│                      │                      │
│                      │ [Skip] [Submit]      │
└──────────────────────┴──────────────────────┘
```

**Verification Options**:

1. **Correct**: Extracted value is accurate
   - Click "Correct" or press 1
   - Moves to next item

2. **Incorrect**: Extracted value is wrong
   - Select "Incorrect"
   - Enter correct value
   - Click "Submit" or press Enter

3. **Not Found**: Field doesn't exist in this document
   - Select "Not Found" or press N
   - Useful for optional fields

**Keyboard Shortcuts**:
- `1` - Mark as correct
- `2` - Mark as incorrect (then type value)
- `N` - Mark as not found
- `S` - Skip to next
- `Enter` - Submit correction
- `←/→` - Navigate PDF pages

### Verification Tips

**Speed up review**:
- Use keyboard shortcuts
- Review similar documents in batch
- Set time limit (e.g., 50 verifications in 10 minutes)

**When to correct vs. skip**:
- **Correct**: Wrong value, OCR error, wrong field
- **Skip**: Unclear document, need more context

**Training the system**:
- Your verifications create training examples
- After ~50 verifications, accuracy typically improves 5-10%
- Weekly AI improvements use this feedback

---

## Analytics Dashboard

### Overview Metrics

Click **"Analytics"** to see:

**Document Metrics**:
- Total documents processed
- Completion rate
- Processing errors
- Average processing time

**Confidence Metrics**:
- Average confidence by field
- Confidence distribution
- Trends over time

**Verification Metrics**:
- Queue size
- Verification accuracy
- Items verified this week

**System Health**:
- Error rate
- Processing speed
- Storage usage

### Understanding Charts

**Documents Processed (Line Chart)**:
- Shows daily/weekly document volume
- Identify processing peaks
- Monitor system load

**Confidence by Field (Bar Chart)**:
- Compare field extraction quality
- Identify fields needing improvement
- Guide verification priorities

**Confidence Trend (Line Chart)**:
- Track accuracy improvements over time
- Measure impact of verifications
- Detect quality regressions

**Document Status (Pie Chart)**:
- See distribution of pending/completed/error
- Monitor processing pipeline health

### Using Analytics for Optimization

**If confidence is low for a field**:
1. Check extraction hints - are they too generic?
2. Review verified examples - any patterns?
3. Update schema with better hints
4. Re-test on sample documents

**If processing errors are high**:
1. Check document quality (scans vs. native PDFs)
2. Review error messages in document details
3. Verify Reducto API status
4. Check system resources

**If verification queue is growing**:
1. Adjust confidence thresholds (lower = fewer verifications)
2. Schedule dedicated verification time
3. Improve schema to increase accuracy
4. Consider field importance (not all need 100% accuracy)

---

## Tips & Best Practices

### Schema Design

**DO**:
- ✅ Start with 5-10 most important fields
- ✅ Use specific extraction hints ("Invoice #:" not "Number:")
- ✅ Test schema on varied samples before bulk processing
- ✅ Set appropriate confidence thresholds per field importance

**DON'T**:
- ❌ Create 50+ fields for first schema (start simple)
- ❌ Use vague hints ("Date", "Amount")
- ❌ Set all thresholds to 0.9 (you'll verify everything)
- ❌ Extract data that's calculated (derive from other fields)

### Document Quality

**Best Results**:
- Native PDF documents (not scanned images)
- Clear, legible text
- Standard formatting
- Recent documents (better OCR for scans)

**Handling Scans**:
- Use high-resolution scans (300+ DPI)
- Ensure proper contrast
- Straighten/deskew images before uploading
- Consider pre-processing with OCR tools

### Processing Workflow

**Recommended Workflow**:

1. **Batch upload** similar documents together
2. **Process in groups** of 50-100 documents
3. **Spot-check** first 5-10 results
4. **Verify low-confidence** items in dedicated sessions
5. **Review analytics** weekly
6. **Refine schema** based on feedback
7. **Re-process** if major improvements made

### Cost Optimization

**Keep costs low**:
- Upload 3-5 samples (not 50) for onboarding
- Use schema editor to refine (free) before re-testing
- Batch process documents to minimize API overhead
- Set smart confidence thresholds (balance accuracy vs. verification time)
- Run weekly improvements, not daily

**Expected Costs**:
- Onboarding: <$5 for 5 samples
- Processing: $25-35 per 1000 documents
- Improvements: ~$2-5 per weekly run

---

## FAQ

### General

**Q: What document types are supported?**
A: Currently PDFs. Support for Word docs, images, and other formats coming soon.

**Q: Is my data secure?**
A: MVP is single-user, local deployment. Documents stored on your server, not shared. Production will add encryption and access controls.

**Q: Can I process documents in batches?**
A: Yes! Upload hundreds of documents at once. Processing is parallelized.

**Q: What languages are supported?**
A: English is best supported. Other Latin-alphabet languages work well. Non-Latin scripts (Arabic, Chinese) may have lower accuracy.

### Schema & Extraction

**Q: How do I handle multi-page extractions?**
A: Fields can span pages. Use hints that appear on the relevant page. System tracks source page for each extraction.

**Q: Can I extract tables?**
A: Yes, but as individual fields. Table extraction as structured data is on the roadmap.

**Q: What if my documents have different formats?**
A: Create separate schemas for different document types, or use broad hints that work across formats.

**Q: How do I extract optional fields?**
A: Mark field as `required: false` in schema. System will extract if found, skip if not.

### Verification

**Q: How many documents do I need to verify?**
A: Depends on confidence. Typically 5-15% need verification. After 50-100 verifications, accuracy improves significantly.

**Q: Can I skip verification?**
A: Yes, but accuracy may suffer. Verification creates training data for improvements.

**Q: Can multiple people verify?**
A: Not in MVP (single-user). Multi-user verification workflow is planned for v1.1.

### Performance

**Q: How fast is processing?**
A: 2-5 seconds per document typically. Large documents (50+ pages) may take 10-15 seconds.

**Q: Can I process 10,000 documents?**
A: Yes! MVP handles <10k docs well with SQLite. For larger volumes, migrate to PostgreSQL (see Deployment Guide).

**Q: What if processing fails?**
A: Errors are logged. You can retry failed documents. Common causes: corrupt PDF, API timeouts, oversized files.

### Analytics

**Q: How is confidence calculated?**
A: Reducto provides `logprobs_confidence` (0.0-1.0) for each extraction, based on OCR/parsing certainty.

**Q: What's a good confidence threshold?**
A: Depends on use case:
  - Critical data (financial, legal): 0.85+
  - Important data (names, dates): 0.75+
  - Nice-to-have (descriptions): 0.6+

**Q: Can I export analytics?**
A: Yes, via API. Dashboard export feature coming soon.

---

## Getting Help

- **Documentation**: See `README.md`, `CLAUDE.md`, `API.md`
- **API Docs**: Visit `http://localhost:8000/docs`
- **Issues**: Report bugs on GitHub
- **Deployment**: See `DEPLOYMENT.md` for production setup

---

**Last Updated**: January 2025
**Version**: 0.1.0 (MVP)
