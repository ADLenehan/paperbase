#!/bin/bash

# Demo script for Reducto Validation Integration
# Shows validation working with both valid and invalid schemas

echo "🔍 Reducto Validation Integration Demo"
echo "========================================"
echo ""

# Test 1: Valid schema
echo "Test 1: Valid Schema ✅"
echo "----------------------"
curl -s -X POST http://localhost:8000/api/bulk/validate-schema \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "Valid Invoice",
    "fields": [
      {
        "name": "invoice_number",
        "type": "text",
        "required": true,
        "description": "Unique invoice identifier from the document header",
        "extraction_hints": ["Invoice #:", "Invoice No:", "Invoice Number:"],
        "confidence_threshold": 0.8
      },
      {
        "name": "invoice_date",
        "type": "date",
        "required": true,
        "description": "Date the invoice was issued",
        "extraction_hints": ["Date:", "Invoice Date:", "Dated:"],
        "confidence_threshold": 0.75
      },
      {
        "name": "total_amount",
        "type": "number",
        "required": true,
        "description": "Total invoice amount including all taxes and fees",
        "extraction_hints": ["Total:", "Amount Due:", "Grand Total:"],
        "confidence_threshold": 0.85
      }
    ]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"✅ Success: {data['success']}\")
print(f\"✅ Compatible: {data['validation']['reducto_compatible']}\")
print(f\"   Errors: {len(data['validation']['errors'])}\")
print(f\"   Warnings: {len(data['validation']['warnings'])}\")
print(f\"   Message: {data['message']}\")
"

echo ""
echo "Test 2: Invalid Schema (Missing Descriptions) ❌"
echo "------------------------------------------------"
curl -s -X POST http://localhost:8000/api/bulk/validate-schema \
  -H "Content-Type: application/json" \
  -d '{
    "template_name": "Bad Schema",
    "fields": [
      {
        "name": "field1",
        "type": "text",
        "required": true,
        "extraction_hints": ["Value"],
        "confidence_threshold": 0.8
      },
      {
        "name": "date",
        "type": "date",
        "required": true,
        "description": "D",
        "extraction_hints": [],
        "confidence_threshold": 0.75
      }
    ]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Success: {data['success']}\")
print(f\"❌ Compatible: {data['validation']['reducto_compatible']}\")
print(f\"   Errors: {len(data['validation']['errors'])}\")
print(f\"   Warnings: {len(data['validation']['warnings'])}\")
print(f\"   Message: {data['message']}\")
print(\"\nErrors:\")
for err in data['validation']['errors'][:3]:
    print(f\"   • {err}\")
"

echo ""
echo "Test 3: Check Server Logs"
echo "-------------------------"
echo "Recent validation log entries:"
tail -10 server.log | grep -i "reducto\|validat" | tail -5

echo ""
echo "✅ Demo Complete!"
echo "================="
echo "The validation system is fully integrated and working!"
echo ""
echo "Available endpoints:"
echo "  • POST /api/bulk/validate-schema - Validate schema without creating"
echo "  • POST /api/bulk/generate-schema - Generate schema (includes validation)"
echo "  • POST /api/bulk/create-new-template - Create template (includes validation)"
echo "  • POST /api/onboarding/analyze-samples - Analyze samples (includes validation)"
echo ""
echo "API Documentation: http://localhost:8000/docs"
