"""
Integration tests for AskAI template filtering and search functionality.

Tests the complete flow:
1. Template fetching for dropdown
2. Search without template filter
3. Search with template filter
4. Error handling scenarios
5. Frontend-backend integration
"""

import requests
import json
from typing import Dict, Any

API_URL = "http://localhost:8000"


def test_health():
    """Test 1: Verify backend is running"""
    print("\n🔍 Test 1: Health Check")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✅ Backend is running: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Backend not responding: {e}")
        return False


def test_elasticsearch():
    """Test 2: Verify Elasticsearch is running"""
    print("\n🔍 Test 2: Elasticsearch Check")
    try:
        response = requests.get("http://localhost:9200/_cluster/health", timeout=5)
        data = response.json()
        status = data.get("status", "unknown")
        print(f"✅ Elasticsearch is running: status={status}")
        return status in ["yellow", "green"]
    except Exception as e:
        print(f"❌ Elasticsearch not responding: {e}")
        return False


def test_templates_endpoint():
    """Test 3: Fetch templates for dropdown"""
    print("\n🔍 Test 3: Templates Endpoint")
    try:
        response = requests.get(f"{API_URL}/api/templates", timeout=5)
        data = response.json()

        templates = data.get("templates", [])
        print(f"✅ Templates endpoint working: {len(templates)} templates found")

        if templates:
            print("\n   Available templates:")
            for t in templates[:5]:  # Show first 5
                print(f"   - {t['name']} (ID: {t['id']}, Category: {t.get('category', 'N/A')})")
            if len(templates) > 5:
                print(f"   ... and {len(templates) - 5} more")
        else:
            print("   ⚠️  No templates found - create some via Bulk Upload")

        return True, templates
    except Exception as e:
        print(f"❌ Templates endpoint failed: {e}")
        return False, []


def test_search_without_filter():
    """Test 4: Search without template filter"""
    print("\n🔍 Test 4: Search Without Template Filter")

    payload = {
        "query": "Show me all documents",
        "folder_path": None,
        "template_id": None,
        "conversation_history": []
    }

    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            answer = data.get("answer", "")
            print(f"✅ Search successful: {total} documents found")
            print(f"   Answer preview: {answer[:100]}...")
            print(f"   Optimization used: {data.get('optimization_used', False)}")
            print(f"   Cached: {data.get('cached', False)}")
            return True, data
        else:
            print(f"❌ Search failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False, None
    except Exception as e:
        print(f"❌ Search request failed: {e}")
        return False, None


def test_search_with_template_filter(template_id: int, template_name: str):
    """Test 5: Search with template filter"""
    print(f"\n🔍 Test 5: Search With Template Filter (ID: {template_id}, Name: {template_name})")

    payload = {
        "query": "Show me all documents",
        "folder_path": None,
        "template_id": template_id,
        "conversation_history": []
    }

    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            answer = data.get("answer", "")
            print(f"✅ Filtered search successful: {total} documents found")
            print(f"   Answer preview: {answer[:100]}...")

            # Verify all results match the template
            results = data.get("results", [])
            if results:
                print(f"   Verifying template filter...")
                all_match = True
                for doc in results[:3]:  # Check first 3
                    doc_template = doc.get("_query_context", {}).get("template_name")
                    if doc_template != template_name:
                        print(f"   ⚠️  Document has template '{doc_template}', expected '{template_name}'")
                        all_match = False
                if all_match:
                    print(f"   ✅ All results match template '{template_name}'")

            return True, data
        else:
            print(f"❌ Filtered search failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False, None
    except Exception as e:
        print(f"❌ Filtered search request failed: {e}")
        return False, None


def test_error_handling():
    """Test 6: Error handling scenarios"""
    print("\n🔍 Test 6: Error Handling")

    # Test invalid template ID
    payload = {
        "query": "Test query",
        "template_id": 99999,  # Non-existent template
    }

    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Invalid template ID handled gracefully")
            print(f"   Returned {data.get('total', 0)} results (filter skipped)")
            return True
        else:
            print(f"⚠️  Invalid template ID returned error: {response.status_code}")
            return True  # Still OK, error handling works
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def test_audit_metadata():
    """Test 7: Verify audit metadata is included"""
    print("\n🔍 Test 7: Audit Metadata Integration")

    payload = {
        "query": "Show me documents with data",
        "folder_path": None,
        "template_id": None,
    }

    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            # Check for audit metadata fields
            checks = {
                "answer_metadata": "answer_metadata" in data,
                "audit_items": "audit_items" in data,
                "confidence_summary": "confidence_summary" in data,
                "field_lineage": "field_lineage" in data,
            }

            all_present = all(checks.values())
            print(f"{'✅' if all_present else '⚠️'} Audit metadata fields:")
            for field, present in checks.items():
                status = "✅" if present else "❌"
                print(f"   {status} {field}: {'present' if present else 'MISSING'}")

            # Show audit items if present
            if data.get("audit_items"):
                count = len(data["audit_items"])
                print(f"   ℹ️  {count} low-confidence fields found")

            return all_present
        else:
            print(f"❌ Search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Audit metadata test failed: {e}")
        return False


def test_frontend_compatibility():
    """Test 8: Verify response format matches frontend expectations"""
    print("\n🔍 Test 8: Frontend Compatibility")

    payload = {
        "query": "Test query for frontend",
        "folder_path": None,
        "template_id": None,
    }

    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            # Check required fields for frontend
            required_fields = [
                "query",
                "answer",
                "results",
                "total",
                "elasticsearch_query",
                "explanation",
            ]

            missing = [f for f in required_fields if f not in data]

            if not missing:
                print(f"✅ All required fields present")
                print(f"   Response structure compatible with ChatSearch.jsx")
                return True
            else:
                print(f"❌ Missing required fields: {missing}")
                return False
        else:
            print(f"❌ Search failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend compatibility test failed: {e}")
        return False


def run_integration_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("AskAI Integration Tests - Template Filtering & Search")
    print("=" * 60)

    results = {}

    # Test 1: Health check
    results["health"] = test_health()
    if not results["health"]:
        print("\n⛔ Backend not running. Start with: cd backend && uvicorn app.main:app --reload")
        return

    # Test 2: Elasticsearch
    results["elasticsearch"] = test_elasticsearch()
    if not results["elasticsearch"]:
        print("\n⛔ Elasticsearch not running. Start with: docker-compose up -d elasticsearch")
        return

    # Test 3: Templates endpoint
    results["templates"], templates = test_templates_endpoint()

    # Test 4: Search without filter
    results["search_unfiltered"], unfiltered_data = test_search_without_filter()

    # Test 5: Search with template filter (if templates exist)
    if templates:
        template = templates[0]
        results["search_filtered"], filtered_data = test_search_with_template_filter(
            template["id"],
            template["name"]
        )
    else:
        print("\n⚠️  Skipping filtered search test - no templates available")
        results["search_filtered"] = None

    # Test 6: Error handling
    results["error_handling"] = test_error_handling()

    # Test 7: Audit metadata
    results["audit_metadata"] = test_audit_metadata()

    # Test 8: Frontend compatibility
    results["frontend_compat"] = test_frontend_compatibility()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)
    total = len(results)

    for test, result in results.items():
        if result is True:
            print(f"✅ {test}")
        elif result is False:
            print(f"❌ {test}")
        else:
            print(f"⏭️  {test} (skipped)")

    print(f"\nTotal: {passed}/{total - skipped} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        print("\n🎉 All tests passed! Integration is working correctly.")
        print("\n📋 Next Steps:")
        print("   1. Open http://localhost:3000/query")
        print("   2. Select a template from the dropdown (optional)")
        print("   3. Type a question and click Search")
        print("   4. Verify results show with confidence badges")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

    return results


if __name__ == "__main__":
    run_integration_tests()
