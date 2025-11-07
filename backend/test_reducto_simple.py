#!/usr/bin/env python3
"""Test Reducto extraction with a simple schema."""

import asyncio
import json
from app.services.reducto_service import ReductoService

async def test_simple_extraction():
    """Test with minimal schema - just one text field."""
    reducto = ReductoService()

    file_path = "uploads/unmatched/1f4689ec_Pinecone-for-AWS-Onesheet.pdf"

    print("1. Parsing document...")
    parse_result = await reducto.parse_document(file_path)
    job_id = parse_result["job_id"]
    print(f"   Job ID: {job_id}")
    print(f"   Chunks: {len(parse_result['result'].get('chunks', []))}")

    # Show first chunk content
    if parse_result['result'].get('chunks'):
        first_chunk = parse_result['result']['chunks'][0]
        print(f"   First chunk: {first_chunk.get('content', '')[:100]}...")

    print("\n2. Testing extraction with MINIMAL schema (just 1 field)...")
    minimal_schema = {
        "fields": [
            {
                "name": "product_name",
                "type": "text",
                "required": True,
                "extraction_hints": ["Pinecone", "product", "database"],
                "description": "Name of the product"
            }
        ]
    }

    extraction_result = await reducto.extract_structured(
        schema=minimal_schema,
        job_id=job_id
    )

    print(f"   Extraction result: {json.dumps(extraction_result, indent=2)}")

    if extraction_result.get("extractions"):
        print("\n✅ SUCCESS - Reducto extracted data!")
    else:
        print("\n❌ FAILED - No extractions returned")
        print("This suggests the Reducto API might need different parameters")

if __name__ == "__main__":
    asyncio.run(test_simple_extraction())
