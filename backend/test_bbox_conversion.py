#!/usr/bin/env python3
"""
Test bounding box format conversion

Verifies that bbox data from Reducto (dict format) is correctly
converted to array format expected by the frontend.
"""

import sys
sys.path.insert(0, '/Users/adlenehan/Projects/paperbase/backend')

from app.utils.bbox_utils import normalize_bbox, format_bbox_for_frontend


def test_bbox_conversion():
    """Test various bbox format conversions"""

    print("=" * 60)
    print("BOUNDING BOX FORMAT CONVERSION TESTS")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: Dict format from Reducto
    print("\nTest 1: Dict format (Reducto API)")
    reducto_bbox = {
        "left": 100.5,
        "top": 200.3,
        "width": 300.0,
        "height": 150.7,
        "page": 2
    }
    result = normalize_bbox(reducto_bbox)
    expected = [100.5, 200.3, 300.0, 150.7]

    if result == expected:
        print(f"✅ PASS: {reducto_bbox} → {result}")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected {expected}, got {result}")
        tests_failed += 1

    # Test 2: Alternative dict format (x, y, w, h)
    print("\nTest 2: Alternative dict format")
    alt_bbox = {"x": 50, "y": 75, "w": 200, "h": 100}
    result = normalize_bbox(alt_bbox)
    expected = [50.0, 75.0, 200.0, 100.0]

    if result == expected:
        print(f"✅ PASS: {alt_bbox} → {result}")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected {expected}, got {result}")
        tests_failed += 1

    # Test 3: Array format (already correct)
    print("\nTest 3: Array format (passthrough)")
    array_bbox = [10, 20, 30, 40]
    result = normalize_bbox(array_bbox)
    expected = [10.0, 20.0, 30.0, 40.0]

    if result == expected:
        print(f"✅ PASS: {array_bbox} → {result}")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected {expected}, got {result}")
        tests_failed += 1

    # Test 4: None value (should return None)
    print("\nTest 4: None value")
    result = normalize_bbox(None)

    if result is None:
        print(f"✅ PASS: None → None")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected None, got {result}")
        tests_failed += 1

    # Test 5: Invalid bbox (missing fields)
    print("\nTest 5: Invalid bbox (missing fields)")
    invalid_bbox = {"left": 10, "top": 20}  # Missing width/height
    result = normalize_bbox(invalid_bbox)

    if result is None:
        print(f"✅ PASS: {invalid_bbox} → None (correctly rejected)")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected None for invalid bbox, got {result}")
        tests_failed += 1

    # Test 6: Format with page number
    print("\nTest 6: Format with page number")
    bbox_with_page = {
        "left": 150,
        "top": 250,
        "width": 400,
        "height": 200,
        "page": 3
    }
    result = format_bbox_for_frontend(bbox_with_page)
    expected = {
        "bbox": [150.0, 250.0, 400.0, 200.0],
        "page": 3
    }

    if result == expected:
        print(f"✅ PASS: With page → {result}")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Expected {expected}, got {result}")
        tests_failed += 1

    # Test 7: Real-world example from garment spec
    print("\nTest 7: Real-world table bbox")
    table_bbox = {
        "left": 93.6,
        "top": 157.2,
        "width": 1139.04,
        "height": 82.56,
        "page": 1
    }
    result = normalize_bbox(table_bbox)

    if result and len(result) == 4:
        print(f"✅ PASS: Table bbox converted")
        print(f"   Input:  {table_bbox}")
        print(f"   Output: {result}")
        tests_passed += 1
    else:
        print(f"❌ FAIL: Table bbox conversion failed")
        tests_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"Total:  {tests_passed + tests_failed}")

    if tests_failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {tests_failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(test_bbox_conversion())
