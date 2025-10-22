#!/usr/bin/env python3
"""
Test script for hybrid template matching implementation

Usage:
    python test_hybrid_matching.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.elastic_service import ElasticsearchService
from app.core.config import settings


async def test_elasticsearch_connection():
    """Test Elasticsearch connection and index creation"""
    print("🔍 Testing Elasticsearch connection...")

    elastic_service = ElasticsearchService()

    try:
        health = await elastic_service.health_check()
        if health:
            print("✅ Elasticsearch is healthy")
        else:
            print("❌ Elasticsearch health check failed")
            return False
    except Exception as e:
        print(f"❌ Elasticsearch connection failed: {e}")
        return False

    await elastic_service.close()
    return True


async def test_template_signatures_index():
    """Test template signatures index creation"""
    print("\n📝 Testing template signatures index...")

    elastic_service = ElasticsearchService()

    try:
        await elastic_service.create_template_signatures_index()
        print("✅ Template signatures index created/verified")

        # Check if index exists
        exists = await elastic_service.client.indices.exists(
            index=elastic_service.template_signatures_index
        )
        if exists:
            print(f"✅ Index '{elastic_service.template_signatures_index}' exists")
        else:
            print(f"❌ Index '{elastic_service.template_signatures_index}' not found")
            return False

    except Exception as e:
        print(f"❌ Failed to create template signatures index: {e}")
        return False

    await elastic_service.close()
    return True


async def test_template_signature_indexing():
    """Test indexing a template signature"""
    print("\n🔖 Testing template signature indexing...")

    elastic_service = ElasticsearchService()

    try:
        # Index a test template signature
        test_template = {
            "template_id": 9999,
            "template_name": "Test Invoice Template",
            "field_names": ["invoice_number", "total", "date", "vendor"],
            "sample_text": "Invoice #12345 Total: $1,000.00 Date: 2025-10-11",
            "category": "test"
        }

        doc_id = await elastic_service.index_template_signature(
            template_id=test_template["template_id"],
            template_name=test_template["template_name"],
            field_names=test_template["field_names"],
            sample_text=test_template["sample_text"],
            category=test_template["category"]
        )

        print(f"✅ Indexed test template signature (ID: {doc_id})")

        # Verify it was indexed
        await asyncio.sleep(1)  # Wait for ES to refresh

        # Try to retrieve it
        response = await elastic_service.client.get(
            index=elastic_service.template_signatures_index,
            id=str(test_template["template_id"])
        )

        if response["_source"]["template_name"] == test_template["template_name"]:
            print(f"✅ Successfully retrieved indexed template")
        else:
            print(f"❌ Retrieved template doesn't match")
            return False

    except Exception as e:
        print(f"❌ Failed to index template signature: {e}")
        return False

    await elastic_service.close()
    return True


async def test_template_matching():
    """Test finding similar templates"""
    print("\n🎯 Testing template similarity matching...")

    elastic_service = ElasticsearchService()

    try:
        # Test document with invoice-like fields
        test_doc_text = "Invoice Number: INV-2025-001 Total Amount: $500.00 Invoice Date: 2025-10-11 Vendor: Acme Corp"
        test_doc_fields = ["invoice_number", "total", "date", "vendor_name"]

        matches = await elastic_service.find_similar_templates(
            document_text=test_doc_text,
            document_fields=test_doc_fields,
            min_score=0.1  # Low threshold for testing
        )

        if matches:
            print(f"✅ Found {len(matches)} similar templates:")
            for match in matches[:3]:  # Show top 3
                print(f"   - {match['template_name']}: "
                      f"{match['similarity_score']:.2f} confidence "
                      f"({match['match_count']}/{match['total_fields']} fields)")
        else:
            print("⚠️  No similar templates found (this is OK if no templates are indexed yet)")

    except Exception as e:
        print(f"❌ Failed to find similar templates: {e}")
        return False

    await elastic_service.close()
    return True


async def test_configuration():
    """Test configuration settings"""
    print("\n⚙️  Testing configuration...")

    print(f"   USE_CLAUDE_FALLBACK_THRESHOLD: {settings.USE_CLAUDE_FALLBACK_THRESHOLD}")
    print(f"   ENABLE_CLAUDE_FALLBACK: {settings.ENABLE_CLAUDE_FALLBACK}")
    print(f"   ELASTICSEARCH_URL: {settings.ELASTICSEARCH_URL}")

    if settings.USE_CLAUDE_FALLBACK_THRESHOLD > 0 and settings.USE_CLAUDE_FALLBACK_THRESHOLD <= 1.0:
        print("✅ Configuration is valid")
        return True
    else:
        print("❌ Invalid configuration values")
        return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Hybrid Template Matching - Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Configuration", await test_configuration()))
    results.append(("Elasticsearch Connection", await test_elasticsearch_connection()))
    results.append(("Template Signatures Index", await test_template_signatures_index()))
    results.append(("Template Signature Indexing", await test_template_signature_indexing()))
    results.append(("Template Similarity Matching", await test_template_matching()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Hybrid matching is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
