#!/usr/bin/env python3
"""
End-to-end test for Paperbase bulk upload flow
Tests: Upload → Parse → Template Match → Confirm → Extract → Index
"""

import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def print_step(step_num, description):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {description}")
    print('='*60)

def print_result(success, message):
    status = "✅" if success else "❌"
    print(f"{status} {message}")

def test_e2e_flow():
    print("\n🚀 Starting End-to-End Test\n")

    # Step 1: Upload and analyze document
    print_step(1, "Upload and Analyze Document")

    # Use the PDF that's already in backend/uploads directory or test_documents
    test_file = None

    # First try backend/uploads
    upload_dir = Path("/Users/adlenehan/Projects/paperbase/backend/uploads")
    pdf_files = list(upload_dir.glob("*.pdf"))
    if pdf_files:
        test_file = pdf_files[0]

    # Fallback to test_documents with txt files
    if not test_file:
        test_dir = Path("/Users/adlenehan/Projects/paperbase/test_documents")
        txt_files = list(test_dir.glob("*.txt"))
        if txt_files:
            test_file = txt_files[0]

    if not test_file:
        print_result(False, "No test files found")
        return False

    print(f"Using test file: {test_file.name}")

    with open(test_file, 'rb') as f:
        files = {'files': (test_file.name, f, 'application/pdf')}
        response = requests.post(f"{BASE_URL}/api/bulk/upload-and-analyze", files=files)

    if response.status_code != 200:
        print_result(False, f"Upload failed: {response.status_code}")
        print(response.text)
        return False

    data = response.json()
    print_result(True, f"Uploaded and analyzed {data['total_documents']} document(s)")
    print(f"   Groups: {len(data['groups'])}")

    if not data['groups']:
        print_result(False, "No groups created")
        return False

    # Step 2: Check template matching
    print_step(2, "Verify Template Matching")

    group = data['groups'][0]
    print(f"   Group: {group['suggested_name']}")
    print(f"   Documents: {group['filenames']}")

    template_match = group['template_match']
    print(f"   Template ID: {template_match.get('template_id')}")
    print(f"   Confidence: {template_match.get('confidence')}")
    print(f"   Reasoning: {template_match.get('reasoning')}")

    has_template = template_match.get('template_id') is not None
    print_result(has_template, f"Template matching: {template_match.get('confidence', 0):.0%} confidence")

    # Step 3: Confirm template or create new one
    print_step(3, "Confirm Template")

    document_ids = group['document_ids']

    if has_template and template_match.get('confidence', 0) >= 0.6:
        # Use existing template
        confirm_data = {
            'document_ids': document_ids,
            'template_id': template_match['template_id']
        }
        response = requests.post(
            f"{BASE_URL}/api/bulk/confirm-template",
            json=confirm_data,
            headers={'Content-Type': 'application/json'}
        )
    else:
        # Create new template
        create_data = {
            'document_ids': document_ids,
            'template_name': group['suggested_name']
        }
        response = requests.post(
            f"{BASE_URL}/api/bulk/create-new-template",
            json=create_data,
            headers={'Content-Type': 'application/json'}
        )

    if response.status_code != 200:
        print_result(False, f"Template confirmation failed: {response.status_code}")
        print(response.text)
        return False

    result = response.json()
    schema_id = result['schema_id']
    print_result(True, f"Schema ID: {schema_id}")

    # Step 4: Wait for processing and check document status
    print_step(4, "Wait for Document Processing")

    time.sleep(5)  # Give it time to process

    response = requests.get(f"{BASE_URL}/api/documents?schema_id={schema_id}")
    if response.status_code != 200:
        print_result(False, f"Failed to fetch documents: {response.status_code}")
        return False

    docs_data = response.json()
    documents = docs_data.get('documents', [])

    if not documents:
        print_result(False, "No documents found")
        return False

    print_result(True, f"Found {len(documents)} document(s)")

    for doc in documents:
        print(f"   Document {doc['id']}: {doc['filename']}")
        print(f"      Status: {doc['status']}")
        fields = doc.get('extracted_fields', [])
        print(f"      Extracted fields: {len(fields)}")

        for field in fields[:3]:  # Show first 3 fields
            conf = field.get('confidence_score', 0)
            print(f"         {field['field_name']}: {field['field_value']} ({conf:.0%})")

    # Step 5: Check Elasticsearch indexing
    print_step(5, "Verify Elasticsearch Indexing")

    es_response = requests.get("http://localhost:9200/documents/_search")
    if es_response.status_code != 200:
        print_result(False, "Elasticsearch query failed")
        return False

    es_data = es_response.json()
    total_indexed = es_data['hits']['total']['value']
    print_result(total_indexed > 0, f"Documents in ES: {total_indexed}")

    if total_indexed > 0:
        hit = es_data['hits']['hits'][0]
        print(f"   Sample document: {json.dumps(hit['_source'], indent=2)[:200]}...")

    # Step 6: Test frontend accessibility
    print_step(6, "Verify Frontend Pages")

    pages = [
        (f"{FRONTEND_URL}/", "Home/Upload page"),
        (f"{FRONTEND_URL}/confirm?schema_id={schema_id}", "Confirmation page"),
        (f"{FRONTEND_URL}/documents", "Documents dashboard"),
    ]

    for url, name in pages:
        try:
            response = requests.get(url, timeout=5)
            accessible = response.status_code == 200
            print_result(accessible, f"{name}: {url}")
        except Exception as e:
            print_result(False, f"{name} failed: {e}")

    print("\n" + "="*60)
    print("✅ END-TO-END TEST COMPLETED SUCCESSFULLY")
    print("="*60 + "\n")

    return True

if __name__ == "__main__":
    try:
        success = test_e2e_flow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
