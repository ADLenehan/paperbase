#!/usr/bin/env python3
"""
Test Prompt Caching Implementation

This script tests the prompt caching functionality added to Claude API calls.
Expected behavior:
- First call: Full token cost (cache miss)
- Second call: ~90% discount on cached system prompt (cache hit)
- Logs should show cache statistics
"""

import asyncio
import time
from datetime import datetime
from app.services.claude_service import ClaudeService
from app.core.config import settings

async def test_parse_natural_language_query():
    """Test prompt caching on NL query parsing (highest traffic)"""
    print("\n" + "="*80)
    print("TEST 1: Natural Language Query Parsing (parse_natural_language_query)")
    print("="*80)

    service = ClaudeService()

    # Test query
    query = "Show me all invoices from last month over $1000"
    available_fields = ["invoice_number", "invoice_date", "invoice_total", "vendor_name"]

    print(f"\nQuery: '{query}'")
    print(f"Available fields: {available_fields}")

    # First call (cache miss)
    print("\n[1/2] First call - expecting cache MISS...")
    start1 = time.time()
    try:
        result1 = await service.parse_natural_language_query(
            query=query,
            available_fields=available_fields
        )
        elapsed1 = time.time() - start1
        print(f"✅ Response received in {elapsed1:.2f}s")
        print(f"   Query type: {result1.get('query_type')}")
        print(f"   Explanation: {result1.get('explanation')[:80]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Wait a moment
    print("\n   Waiting 2 seconds before second call...")
    await asyncio.sleep(2)

    # Second call (cache hit)
    print("\n[2/2] Second call - expecting cache HIT (80-90% savings)...")
    start2 = time.time()
    try:
        result2 = await service.parse_natural_language_query(
            query=query,
            available_fields=available_fields
        )
        elapsed2 = time.time() - start2
        print(f"✅ Response received in {elapsed2:.2f}s")
        print(f"   Query type: {result2.get('query_type')}")

        # Performance comparison
        speedup = (elapsed1 / elapsed2) if elapsed2 > 0 else 0
        print(f"\n📊 Performance Comparison:")
        print(f"   First call:  {elapsed1:.2f}s")
        print(f"   Second call: {elapsed2:.2f}s")
        print(f"   Speedup:     {speedup:.1f}x faster")

        if speedup > 1.2:
            print(f"   ✅ PASS: Second call was faster (caching likely working)")
        else:
            print(f"   ⚠️  WARNING: Second call not significantly faster")
            print(f"   Check logs for cache statistics")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    return True


async def test_answer_generation():
    """Test prompt caching on answer generation (highest traffic)"""
    print("\n" + "="*80)
    print("TEST 2: Answer Generation (answer_question_about_results)")
    print("="*80)

    service = ClaudeService()

    # Mock search results
    query = "What are my recent invoices?"
    search_results = [
        {
            "id": 1,
            "data": {
                "filename": "invoice_001.pdf",
                "invoice_total": "1250.00",
                "vendor_name": "Acme Corp",
                "invoice_date": "2024-01-15"
            }
        },
        {
            "id": 2,
            "data": {
                "filename": "invoice_002.pdf",
                "invoice_total": "3450.00",
                "vendor_name": "Widget Inc",
                "invoice_date": "2024-01-20"
            }
        }
    ]
    total_count = 2

    print(f"\nQuery: '{query}'")
    print(f"Results: {total_count} documents")

    # First call (cache miss)
    print("\n[1/2] First call - expecting cache MISS...")
    start1 = time.time()
    try:
        result1 = await service.answer_question_about_results(
            query=query,
            search_results=search_results,
            total_count=total_count,
            include_confidence_metadata=False
        )
        elapsed1 = time.time() - start1
        print(f"✅ Response received in {elapsed1:.2f}s")
        print(f"   Answer: {result1.get('answer')[:80]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    # Wait a moment
    print("\n   Waiting 2 seconds before second call...")
    await asyncio.sleep(2)

    # Second call (cache hit)
    print("\n[2/2] Second call - expecting cache HIT...")
    start2 = time.time()
    try:
        result2 = await service.answer_question_about_results(
            query=query,
            search_results=search_results,
            total_count=total_count,
            include_confidence_metadata=False
        )
        elapsed2 = time.time() - start2
        print(f"✅ Response received in {elapsed2:.2f}s")

        # Performance comparison
        speedup = (elapsed1 / elapsed2) if elapsed2 > 0 else 0
        print(f"\n📊 Performance Comparison:")
        print(f"   First call:  {elapsed1:.2f}s")
        print(f"   Second call: {elapsed2:.2f}s")
        print(f"   Speedup:     {speedup:.1f}x faster")

        if speedup > 1.2:
            print(f"   ✅ PASS: Second call was faster")
        else:
            print(f"   ⚠️  WARNING: Second call not significantly faster")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    return True


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print(f"PROMPT CACHING TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    print("\n⚠️  IMPORTANT: Check backend logs for cache statistics:")
    print("   - 'Prompt cache: X tokens cached' (cache creation)")
    print("   - 'Prompt cache: X tokens read from cache (90% savings)' (cache hit)")

    results = []

    # Test 1: NL query parsing
    try:
        result1 = await test_parse_natural_language_query()
        results.append(("NL Query Parsing", result1))
    except Exception as e:
        print(f"\n❌ Test 1 failed with exception: {e}")
        results.append(("NL Query Parsing", False))

    # Test 2: Answer generation
    try:
        result2 = await test_answer_generation()
        results.append(("Answer Generation", result2))
    except Exception as e:
        print(f"\n❌ Test 2 failed with exception: {e}")
        results.append(("Answer Generation", False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n💡 Next steps:")
        print("   1. Check backend logs for cache hit statistics")
        print("   2. Monitor Anthropic dashboard for cost reduction")
        print("   3. Expected savings: 80-90% on cached calls")
    else:
        print("\n⚠️  Some tests failed. Check:")
        print("   1. Backend logs for errors")
        print("   2. Anthropic API key has caching enabled")
        print("   3. Using claude-sonnet-4+ model")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
