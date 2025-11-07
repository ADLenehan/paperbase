#!/usr/bin/env python3
"""Debug Reducto extraction response."""

import asyncio
import json
from reducto import Reducto
from app.core.config import settings

async def test_debug():
    """Test with detailed debugging."""
    client = Reducto(api_key=settings.REDUCTO_API_KEY)

    file_path = "uploads/unmatched/1f4689ec_Pinecone-for-AWS-Onesheet.pdf"

    print("1. Upload and parse...")
    def upload_file():
        with open(file_path, "rb") as f:
            return client.upload(file=f)

    upload_response = await asyncio.to_thread(upload_file)
    print(f"   File ID: {upload_response.file_id}")

    parse_response = await asyncio.to_thread(
        client.parse.run,
        document_url=upload_response.file_id
    )
    print(f"   Job ID: {parse_response.job_id}")

    print("\n2. Extract with minimal schema...")
    schema = {
        "type": "object",
        "properties": {
            "product_name": {
                "type": "string",
                "description": "Pinecone product database"
            }
        },
        "required": ["product_name"]
    }

    print(f"   Schema: {json.dumps(schema, indent=2)}")

    extract_response = await asyncio.to_thread(
        client.extract.run,
        document_url=f"jobid://{parse_response.job_id}",
        schema=schema,
        generate_citations=True
    )

    print(f"\n3. Response type: {type(extract_response)}")
    print(f"   Has result attr: {hasattr(extract_response, 'result')}")
    print(f"   Dir: {[x for x in dir(extract_response) if not x.startswith('_')]}")

    if hasattr(extract_response, 'result'):
        result = extract_response.result
        print(f"\n4. Result type: {type(result)}")
        print(f"   Result: {result}")

        if isinstance(result, dict):
            print(f"   Keys: {result.keys()}")
        elif isinstance(result, list):
            print(f"   List length: {len(result)}")
            if result:
                print(f"   First item: {result[0]}")
        else:
            # Try to convert to dict
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
                print(f"   Result dict: {json.dumps(result_dict, indent=2)}")
            elif hasattr(result, 'dict'):
                result_dict = result.dict()
                print(f"   Result dict: {json.dumps(result_dict, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_debug())
