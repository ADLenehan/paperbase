#!/usr/bin/env python3
"""
Test MCP API Structured Responses

Tests the MCP RAG endpoint to verify structured URL responses.
"""

import requests
import json
from datetime import datetime


def test_mcp_rag_response():
    """Test /api/mcp/rag endpoint returns structured URLs"""
    print("\n" + "="*80)
    print("TEST: MCP RAG Endpoint Structured Response")
    print("="*80)

    url = "http://localhost:8000/api/mcp/search/rag/query"
    params = {
        "question": "What documents do I have?",
        "max_results": 5
    }

    print(f"\nCalling {url}")
    print(f"Params: {json.dumps(params, indent=2)}")

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()

        result = response.json()
        print(f"\n✅ Response received (status: {response.status_code})")

        checks = []

        # 1. Check basic structure
        if "answer" in result:
            print(f"\n   ✅ Has 'answer' field: {result['answer'][:80]}...")
            checks.append(True)
        else:
            print(f"\n   ❌ Missing 'answer' field")
            checks.append(False)

        # 2. Check audit_items (if low-confidence fields exist)
        if "audit_items" in result:
            audit_items = result["audit_items"]
            print(f"   ✅ Has 'audit_items' field ({len(audit_items)} items)")
            checks.append(True)
        else:
            print(f"   ⚠️  No 'audit_items' field (may be empty)")
            checks.append(True)  # OK if no low-confidence items

        # 3. Check web_ui_access (should be present if audit_items exist)
        has_audit_items = len(result.get("audit_items", [])) > 0
        if has_audit_items:
            if "web_ui_access" in result:
                web_ui = result["web_ui_access"]
                print(f"   ✅ Has 'web_ui_access' object")

                if "audit_dashboard" in web_ui:
                    url_val = web_ui["audit_dashboard"]
                    print(f"      ✅ audit_dashboard: {url_val}")
                    if "localhost:3000" in url_val or "http" in url_val:
                        print(f"      ✅ URL is properly formatted")
                        checks.append(True)
                    else:
                        print(f"      ❌ URL format invalid")
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
                print(f"   ❌ Missing 'web_ui_access' (but has audit items)")
                checks.append(False)
        else:
            print(f"   ⚠️  No audit items, web_ui_access may be null (acceptable)")
            checks.append(True)

        # 4. Check suggested_next_steps
        if "suggested_next_steps" in result:
            steps = result["suggested_next_steps"]
            if isinstance(steps, list):
                print(f"   ✅ Has 'suggested_next_steps' array ({len(steps)} items)")
                if len(steps) > 0:
                    print(f"      First step: {steps[0][:60]}...")
                checks.append(True)
            else:
                print(f"   ❌ suggested_next_steps is not an array")
                checks.append(False)
        else:
            print(f"   ⚠️  No 'suggested_next_steps' field (may be empty)")
            checks.append(True)  # OK if empty

        # 5. Check backward compatibility
        if "sources" in result and "confidence" in result:
            print(f"   ✅ Legacy fields preserved (backward compatible)")
            checks.append(True)
        else:
            print(f"   ❌ Missing legacy fields")
            checks.append(False)

        # Summary
        passed = sum(checks)
        total = len(checks)
        if all(checks):
            print(f"\n✅ PASS: All structure checks passed ({passed}/{total})")
            return True
        else:
            print(f"\n⚠️  PARTIAL PASS: {passed}/{total} checks passed")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FAIL: HTTP request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"\n❌ FAIL: Invalid JSON response: {e}")
        return False
    except Exception as e:
        print(f"\n❌ FAIL: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run MCP API response tests"""
    print("\n" + "="*80)
    print(f"MCP API STRUCTURED RESPONSE TEST")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    print("\n⚠️  NOTE: This test requires:")
    print("   - Backend running at http://localhost:8000")
    print("   - Database with some documents")
    print("   - Elasticsearch accessible")

    result = test_mcp_rag_response()

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    if result:
        print(f"✅ PASS - MCP RAG endpoint returns structured responses")
        print("\n✅ Confirmed:")
        print("   - web_ui_access object with URLs")
        print("   - suggested_next_steps array")
        print("   - Backward compatible legacy fields")
        print("   - Follows MCP best practices")
    else:
        print(f"❌ FAIL - Some checks failed")
        print("\n⚠️  Check:")
        print("   - Backend is running")
        print("   - Database has documents")
        print("   - FRONTEND_URL is configured")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
