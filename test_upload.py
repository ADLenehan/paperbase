#!/usr/bin/env python3
"""Test script to debug the upload endpoint"""
import requests
import sys

def test_upload():
    print("Testing upload endpoint...")

    # Create a simple test file
    test_content = b"Test document content\nInvoice #123\nAmount: $500"

    files = {
        'files': ('test-document.txt', test_content, 'text/plain')
    }

    try:
        url = 'http://localhost:8000/api/bulk/upload-and-analyze'
        print(f"POST {url}")

        response = requests.post(url, files=files, timeout=30)

        print(f"\nStatus: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"\nResponse Body:")
        print(response.text)

        if response.status_code == 200:
            print("\n✓ SUCCESS: Upload completed")
            return 0
        else:
            print(f"\n✗ ERROR: Request failed with status {response.status_code}")
            return 1

    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ CONNECTION ERROR: Cannot connect to server")
        print(f"   Make sure the backend is running on port 8000")
        print(f"   Error: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_upload())
