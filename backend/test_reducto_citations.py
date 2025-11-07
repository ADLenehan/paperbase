#!/usr/bin/env python3
"""Check if Reducto returns confidence scores in citations or elsewhere."""

import asyncio
import json
from reducto import Reducto
from app.core.config import settings

async def test_citations():
    """Test extraction response structure."""
    client = Reducto(api_key=settings.REDUCTO_API_KEY)

    file_path = "uploads/unmatched/1f4689ec_Pinecone-for-AWS-Onesheet.pdf"

    print("1. Upload and parse...")
    def upload_file():
        with open(file_path, "rb") as f:
            return client.upload(file=f)

    upload_response = await asyncio.to_thread(upload_file)
    parse_response = await asyncio.to_thread(
        client.parse.run,
        document_url=upload_response.file_id
    )

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

    extract_response = await asyncio.to_thread(
        client.extract.run,
        document_url=f"jobid://{parse_response.job_id}",
        schema=schema,
        generate_citations=True
    )

    print(f"\n3. Extract Response Structure:")
    print(f"   Type: {type(extract_response)}")
    print(f"   Has citations: {hasattr(extract_response, 'citations')}")
    print(f"   Has result: {hasattr(extract_response, 'result')}")

    # Check result
    result = extract_response.result
    print(f"\n4. Result: {result}")

    # Check citations
    if hasattr(extract_response, 'citations'):
        citations = extract_response.citations
        print(f"\n5. Citations type: {type(citations)}")
        print(f"   Citations content:")

        if hasattr(citations, 'model_dump'):
            citations_dict = citations.model_dump()
            print(json.dumps(citations_dict, indent=2))
        elif isinstance(citations, dict):
            print(json.dumps(citations, indent=2))
        else:
            print(f"   {citations}")

    # Check full response dump
    print(f"\n6. Full extract_response dump:")
    if hasattr(extract_response, 'model_dump'):
        full_dump = extract_response.model_dump()
        print(json.dumps(full_dump, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(test_citations())
