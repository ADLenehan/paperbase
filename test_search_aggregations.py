#!/usr/bin/env python3
"""
Test Script for Search API and Aggregations

Run this after setting up the environment:
1. Install dependencies: pip install -r backend/requirements.txt
2. Start Elasticsearch: docker-compose up elasticsearch
3. Start backend: cd backend && uvicorn app.main:app --reload
4. Run this script: python test_search_aggregations.py
"""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def print_result(test_name: str, response: requests.Response):
    """Pretty print test results"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")

    try:
        data = response.json()
        print(json.dumps(data, indent=2)[:500])  # First 500 chars
    except:
        print(response.text[:500])


def test_health_check():
    """Test basic health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print_result("Health Check", response)
    return response.status_code == 200


def test_mcp_list_fields():
    """Test MCP list fields endpoint"""
    response = requests.get(f"{BASE_URL}/api/mcp/search/fields")
    print_result("MCP List Fields", response)
    return response.status_code == 200


def test_mcp_list_templates():
    """Test MCP list templates endpoint"""
    response = requests.get(f"{BASE_URL}/api/mcp/search/templates")
    print_result("MCP List Templates", response)
    return response.status_code == 200


def test_mcp_search_stats():
    """Test MCP search statistics"""
    response = requests.get(f"{BASE_URL}/api/mcp/search/stats")
    print_result("MCP Search Stats", response)
    return response.status_code == 200


def test_mcp_search_documents():
    """Test MCP document search"""
    payload = {
        "query": "test documents",
        "max_results": 5,
        "include_aggregations": True
    }
    response = requests.post(
        f"{BASE_URL}/api/mcp/search/documents",
        json=payload
    )
    print_result("MCP Search Documents", response)
    return response.status_code == 200


def test_mcp_explain_query():
    """Test MCP query explanation"""
    response = requests.post(
        f"{BASE_URL}/api/mcp/search/query/explain",
        params={"query": "invoices over $1000"}
    )
    print_result("MCP Explain Query", response)
    return response.status_code == 200


def test_aggregation_single():
    """Test single aggregation"""
    payload = {
        "field": "status",
        "agg_type": "terms",
        "agg_config": {"size": 10}
    }
    response = requests.post(
        f"{BASE_URL}/api/aggregations/single",
        json=payload
    )
    print_result("Single Aggregation (Terms)", response)
    return response.status_code == 200


def test_aggregation_multi():
    """Test multiple aggregations"""
    payload = {
        "aggregations": [
            {
                "name": "status_breakdown",
                "field": "status",
                "type": "terms",
                "config": {"size": 10}
            },
            {
                "name": "doc_count",
                "field": "document_id",
                "type": "cardinality"
            }
        ]
    }
    response = requests.post(
        f"{BASE_URL}/api/aggregations/multi",
        json=payload
    )
    print_result("Multi Aggregation", response)
    return response.status_code == 200


def test_aggregation_dashboard():
    """Test dashboard aggregations"""
    response = requests.get(f"{BASE_URL}/api/aggregations/dashboard")
    print_result("Dashboard Aggregations", response)
    return response.status_code == 200


def test_aggregation_nested():
    """Test nested aggregations"""
    payload = {
        "parent_agg": {
            "name": "by_status",
            "field": "status",
            "type": "terms",
            "config": {"size": 10}
        },
        "sub_aggs": [
            {
                "name": "unique_docs",
                "field": "document_id",
                "type": "cardinality"
            }
        ]
    }
    response = requests.post(
        f"{BASE_URL}/api/aggregations/nested",
        json=payload
    )
    print_result("Nested Aggregation", response)
    return response.status_code == 200


def test_original_search():
    """Test original search endpoint"""
    payload = {
        "query": "test",
        "folder_path": None,
        "conversation_history": None
    }
    response = requests.post(
        f"{BASE_URL}/api/search",
        json=payload
    )
    print_result("Original Search API", response)
    return response.status_code == 200


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PAPERBASE SEARCH & AGGREGATION TEST SUITE")
    print("="*60)

    tests = [
        ("Health Check", test_health_check),
        ("MCP List Fields", test_mcp_list_fields),
        ("MCP List Templates", test_mcp_list_templates),
        ("MCP Search Stats", test_mcp_search_stats),
        ("MCP Search Documents", test_mcp_search_documents),
        ("MCP Explain Query", test_mcp_explain_query),
        ("Single Aggregation", test_aggregation_single),
        ("Multi Aggregation", test_aggregation_multi),
        ("Dashboard Aggregation", test_aggregation_dashboard),
        ("Nested Aggregation", test_aggregation_nested),
        ("Original Search API", test_original_search),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ {test_name} FAILED: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
