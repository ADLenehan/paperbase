#!/usr/bin/env python3
"""
Test MCP Structured URL Responses

This script tests that MCP tools return structured responses with:
- summary field
- web_ui_access object with audit_dashboard and instructions
- suggested_next_steps array

Expected format follows MCP best practices for URL presentation.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.tools.audit import get_audit_queue, get_audit_stats
from mcp_server.config import config
from datetime import datetime


async def test_audit_queue_response():
    """Test get_audit_queue returns structured URLs"""
    print("\n" + "="*80)
    print("TEST 1: Audit Queue Response Structure")
    print("="*80)

    print(f"\nCalling get_audit_queue()...")
    print(f"Expected FRONTEND_URL: {config.FRONTEND_URL}")

    try:
        result = await get_audit_queue(limit=10)

        print(f"\n✅ Response received")
        print(f"\nChecking response structure...")

        # Check required fields
        checks = []

        # 1. Summary field
        if "summary" in result:
            print(f"   ✅ Has 'summary' field: {result['summary']}")
            checks.append(True)
        else:
            print(f"   ❌ Missing 'summary' field")
            checks.append(False)

        # 2. web_ui_access object
        if "web_ui_access" in result:
            web_ui = result["web_ui_access"]
            print(f"   ✅ Has 'web_ui_access' object")

            # Check sub-fields
            if "audit_dashboard" in web_ui:
                url = web_ui["audit_dashboard"]
                print(f"      ✅ audit_dashboard: {url}")
                if config.FRONTEND_URL in url:
                    print(f"      ✅ URL contains FRONTEND_URL")
                    checks.append(True)
                else:
                    print(f"      ❌ URL missing FRONTEND_URL")
                    checks.append(False)
            else:
                print(f"      ❌ Missing 'audit_dashboard'")
                checks.append(False)

            if "instructions" in web_ui:
                print(f"      ✅ instructions: {web_ui['instructions'][:60]}...")
                checks.append(True)
            else:
                print(f"      ❌ Missing 'instructions'")
                checks.append(False)
        else:
            print(f"   ❌ Missing 'web_ui_access' object")
            checks.append(False)

        # 3. suggested_next_steps array
        if "suggested_next_steps" in result:
            steps = result["suggested_next_steps"]
            if isinstance(steps, list):
                print(f"   ✅ Has 'suggested_next_steps' array ({len(steps)} items)")
                if len(steps) > 0:
                    print(f"      First step: {steps[0][:60]}...")
                    checks.append(True)
                else:
                    print(f"      ⚠️  Array is empty (might be ok if no audit items)")
                    checks.append(True)  # Empty is acceptable
            else:
                print(f"   ❌ suggested_next_steps is not an array")
                checks.append(False)
        else:
            print(f"   ❌ Missing 'suggested_next_steps'")
            checks.append(False)

        # 4. Legacy fields still present (backward compatibility)
        if "queue" in result and "total" in result and "threshold" in result:
            print(f"   ✅ Legacy fields preserved (backward compatible)")
            print(f"      Queue items: {len(result.get('queue', []))}")
            print(f"      Total: {result.get('total')}")
            print(f"      Threshold: {result.get('threshold')}")
            checks.append(True)
        else:
            print(f"   ❌ Missing legacy fields")
            checks.append(False)

        # Summary
        if all(checks):
            print(f"\n✅ PASS: All structure checks passed ({len(checks)}/{len(checks)})")
            return True
        else:
            passed = sum(checks)
            print(f"\n⚠️  PARTIAL PASS: {passed}/{len(checks)} checks passed")
            return False

    except Exception as e:
        print(f"\n❌ FAIL: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_audit_stats_response():
    """Test get_audit_stats returns structured URLs"""
    print("\n" + "="*80)
    print("TEST 2: Audit Stats Response Structure")
    print("="*80)

    print(f"\nCalling get_audit_stats()...")

    try:
        result = await get_audit_stats()

        print(f"\n✅ Response received")
        print(f"\nChecking response structure...")

        checks = []

        # 1. Summary field
        if "summary" in result:
            print(f"   ✅ Has 'summary' field: {result['summary']}")
            checks.append(True)
        else:
            print(f"   ❌ Missing 'summary' field")
            checks.append(False)

        # 2. web_ui_access (conditional on pending items)
        pending = result.get("pending_review", 0)
        if pending > 0:
            if "web_ui_access" in result:
                print(f"   ✅ Has 'web_ui_access' object (pending items exist)")
                checks.append(True)
            else:
                print(f"   ❌ Missing 'web_ui_access' object (but has pending items)")
                checks.append(False)
        else:
            print(f"   ⚠️  No pending items, web_ui_access may be null (acceptable)")
            checks.append(True)

        # 3. suggested_next_steps
        if "suggested_next_steps" in result:
            steps = result["suggested_next_steps"]
            if isinstance(steps, list):
                print(f"   ✅ Has 'suggested_next_steps' array ({len(steps)} items)")
                checks.append(True)
            else:
                print(f"   ❌ suggested_next_steps is not an array")
                checks.append(False)
        else:
            print(f"   ❌ Missing 'suggested_next_steps'")
            checks.append(False)

        # 4. Legacy stats fields
        if "pending_review" in result and "total_fields" in result:
            print(f"   ✅ Legacy stats fields preserved")
            print(f"      Pending review: {result.get('pending_review')}")
            print(f"      Total fields: {result.get('total_fields')}")
            checks.append(True)
        else:
            print(f"   ❌ Missing legacy stats fields")
            checks.append(False)

        # Summary
        if all(checks):
            print(f"\n✅ PASS: All structure checks passed ({len(checks)}/{len(checks)})")
            return True
        else:
            passed = sum(checks)
            print(f"\n⚠️  PARTIAL PASS: {passed}/{len(checks)} checks passed")
            return False

    except Exception as e:
        print(f"\n❌ FAIL: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_url_format():
    """Test that URLs are properly formatted"""
    print("\n" + "="*80)
    print("TEST 3: URL Format Validation")
    print("="*80)

    print(f"\nChecking URL configuration...")
    print(f"   FRONTEND_URL: {config.FRONTEND_URL}")

    checks = []

    # Test URL is valid
    if config.FRONTEND_URL.startswith("http://") or config.FRONTEND_URL.startswith("https://"):
        print(f"   ✅ URL has valid protocol")
        checks.append(True)
    else:
        print(f"   ❌ URL missing http:// or https://")
        checks.append(False)

    # Test URL doesn't have trailing slash
    if not config.FRONTEND_URL.endswith("/"):
        print(f"   ✅ URL has no trailing slash (correct)")
        checks.append(True)
    else:
        print(f"   ⚠️  URL has trailing slash (may cause double slashes)")
        checks.append(False)

    # Get actual audit queue response
    try:
        result = await get_audit_queue(limit=1)
        if "web_ui_access" in result and "audit_dashboard" in result["web_ui_access"]:
            url = result["web_ui_access"]["audit_dashboard"]
            print(f"\n   Generated audit URL: {url}")

            # Check for double slashes
            if "//" not in url.replace("http://", "").replace("https://", ""):
                print(f"   ✅ No double slashes in path")
                checks.append(True)
            else:
                print(f"   ❌ Double slashes detected")
                checks.append(False)

            # Check URL structure
            if "/audit" in url:
                print(f"   ✅ Contains /audit path")
                checks.append(True)
            else:
                print(f"   ❌ Missing /audit path")
                checks.append(False)

        else:
            print(f"   ⚠️  Could not extract URL from response")
            checks.append(False)

    except Exception as e:
        print(f"   ❌ Error getting audit queue: {e}")
        checks.append(False)

    if all(checks):
        print(f"\n✅ PASS: URL format validation passed ({len(checks)}/{len(checks)})")
        return True
    else:
        passed = sum(checks)
        print(f"\n⚠️  PARTIAL PASS: {passed}/{len(checks)} checks passed")
        return False


async def main():
    """Run all MCP structured URL tests"""
    print("\n" + "="*80)
    print(f"MCP STRUCTURED URL RESPONSE TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    results = []

    # Test 1: Audit queue response structure
    try:
        result1 = await test_audit_queue_response()
        results.append(("Audit Queue Response", result1))
    except Exception as e:
        print(f"\n❌ Test 1 failed with exception: {e}")
        results.append(("Audit Queue Response", False))

    # Test 2: Audit stats response structure
    try:
        result2 = await test_audit_stats_response()
        results.append(("Audit Stats Response", result2))
    except Exception as e:
        print(f"\n❌ Test 2 failed with exception: {e}")
        results.append(("Audit Stats Response", False))

    # Test 3: URL format validation
    try:
        result3 = await test_url_format()
        results.append(("URL Format Validation", result3))
    except Exception as e:
        print(f"\n❌ Test 3 failed with exception: {e}")
        results.append(("URL Format Validation", False))

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
        print("\n✅ MCP tools now provide:")
        print("   - Clear summary messages")
        print("   - web_ui_access with audit dashboard URLs")
        print("   - suggested_next_steps for user guidance")
        print("   - Backward compatible legacy fields")
        print("\n💡 These responses follow MCP best practices for URL presentation")
    else:
        print("\n⚠️  Some tests failed. Check:")
        print("   1. FRONTEND_URL is configured correctly")
        print("   2. Audit tools are returning correct structure")
        print("   3. Backend database is accessible")

    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
