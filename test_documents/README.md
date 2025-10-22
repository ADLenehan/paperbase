# Test Documents

This directory contains sample documents for testing Paperbase functionality.

## Purpose

- **Development**: Test document processing locally
- **Integration Tests**: Validate end-to-end workflows
- **Demo**: Showcase Paperbase capabilities
- **Onboarding**: Verify schema generation works correctly

## Document Types

### Invoices
Place sample invoices in `invoices/` subdirectory:
- 3-5 invoices from different vendors
- Should contain: invoice number, date, total, vendor details
- Format: PDF preferred
- Example names: `invoice_001.pdf`, `acme_invoice.pdf`

### Contracts
Place sample contracts in `contracts/` subdirectory:
- 3-5 service agreements or similar contracts
- Should contain: effective date, parties, terms, value
- Format: PDF preferred
- Example names: `contract_001.pdf`, `service_agreement.pdf`

### Receipts
Place sample receipts in `receipts/` subdirectory:
- 3-5 receipts from different merchants
- Should contain: date, total, merchant name, items
- Format: PDF preferred
- Example names: `receipt_001.pdf`, `store_receipt.pdf`

## Adding Test Documents

**IMPORTANT**: Do NOT commit actual confidential documents to git!

1. **Create subdirectories**:
   ```bash
   mkdir -p test_documents/invoices
   mkdir -p test_documents/contracts
   mkdir -p test_documents/receipts
   ```

2. **Add sample PDFs**:
   - Use fake/generated documents
   - Use publicly available samples
   - Redact any sensitive information

3. **Update .gitignore**:
   ```bash
   # Already configured to ignore PDF files in this directory
   test_documents/**/*.pdf
   ```

## Generating Fake Documents

If you need test documents, you can:

1. **Use online PDF generators**:
   - [Invoice Generator](https://invoice-generator.com)
   - [HelloSign Test Documents](https://www.hellosign.com/test-documents)

2. **Create from templates**:
   - Word/Google Docs → Export to PDF
   - Use realistic data (not real customer data)

3. **Download open-source examples**:
   - Many invoice/contract templates available online
   - Ensure they're marked for testing/demo use

## Testing Workflow

### 1. Schema Generation Test

```bash
# Upload 3-5 invoices to onboarding
# Verify schema is generated with fields:
# - invoice_number
# - invoice_date
# - total_amount
# - vendor_name
```

### 2. Extraction Test

```bash
# Upload additional invoices to Documents page
# Process them
# Verify extractions are accurate
# Check confidence scores are reasonable (>0.7)
```

### 3. Verification Test

```bash
# Introduce intentionally corrupted documents (e.g., poor scans)
# Verify they appear in verification queue
# Test verification workflow
```

## Document Requirements

**Format**:
- PDF (native or scanned)
- Max 50MB per file
- Text-based preferred (better than image-only)

**Quality**:
- Clear, legible text
- Standard document structure
- Consistent formatting within document type

**Content**:
- Representative of real use cases
- Contains all fields you want to extract
- Varies enough to test schema robustness

## Example Structure

```
test_documents/
├── README.md (this file)
├── invoices/
│   ├── invoice_acme_001.pdf
│   ├── invoice_globex_002.pdf
│   └── invoice_initech_003.pdf
├── contracts/
│   ├── service_agreement_001.pdf
│   ├── service_agreement_002.pdf
│   └── consulting_contract_003.pdf
└── receipts/
    ├── grocery_receipt_001.pdf
    ├── restaurant_receipt_002.pdf
    └── retail_receipt_003.pdf
```

## Security Notes

- **Never** commit real customer/business documents
- **Always** redact sensitive information
- **Use** fake data for testing (e.g., "Acme Corp" not real company names)
- **Sanitize** any documents before sharing

## Automated Tests

To use test documents in automated tests:

```python
# In tests/test_integration.py
import os

TEST_DOCS_DIR = "test_documents/invoices"

def test_invoice_processing():
    invoice_files = [
        os.path.join(TEST_DOCS_DIR, f)
        for f in os.listdir(TEST_DOCS_DIR)
        if f.endswith('.pdf')
    ]

    # Upload and process
    # Assert extractions are correct
```

---

**Last Updated**: January 2025
