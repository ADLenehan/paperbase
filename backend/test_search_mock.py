"""
Mock search endpoint for testing inline audit without Elasticsearch
Run with: python test_search_mock.py
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    conversation_history: Optional[List[Dict]] = []
    folder_path: Optional[str] = None

@app.post("/api/search")
async def search(request: SearchRequest):
    """Mock search endpoint that returns sample data with low-confidence fields"""

    # Mock response with low-confidence field for testing inline audit
    return {
        "answer": "The cloud platform used in the Pinecone-for-AWS-Onesheet diagram is AWS (Amazon Web Services).",
        "explanation": "Found 1 document matching your query",
        "results": [
            {
                "document_id": 1,
                "filename": "Pinecone-for-AWS-Onesheet.pdf",
                "schema_name": "One sheeter",
                "extracted_fields": {
                    "cloud_platform": "AWS",
                    "product_name": "Pinecone"
                }
            }
        ],
        "total": 1,
        # Audit metadata for inline audit modal
        "answer_metadata": {
            "field_citations": [
                {
                    "field_id": 101,
                    "field_name": "cloud_platform",
                    "field_value": "AWS",
                    "document_id": 1,
                    "filename": "Pinecone-for-AWS-Onesheet.pdf",
                    "confidence": 0.45,  # Low confidence to trigger audit
                    "source_page": 1,
                    "source_bbox": [100, 200, 300, 250],
                    "used_in_answer": True
                }
            ]
        },
        "audit_items": [
            {
                "field_id": 101,
                "document_id": 1,
                "filename": "Pinecone-for-AWS-Onesheet.pdf",
                "field_name": "cloud_platform",
                "field_value": "AWS",
                "field_type": "text",
                "confidence": 0.45,
                "source_page": 1,
                "source_bbox": [100, 200, 300, 250],
                "verified": False,
                "audit_url": "/audit?field_id=101&document_id=1&highlight=true"
            }
        ],
        "audit_items_filtered_count": 1,
        "audit_items_total_count": 1,
        "confidence_summary": {
            "low_confidence_count": 1,
            "medium_confidence_count": 0,
            "high_confidence_count": 1,
            "audit_recommended": True
        },
        "field_lineage": {
            "queried_fields": ["cloud_platform"],
            "fields_in_answer": ["cloud_platform"]
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "message": "Mock search API for testing"}

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🧪 MOCK SEARCH API RUNNING")
    print("="*60)
    print("Purpose: Test inline audit UI without Elasticsearch")
    print("URL: http://localhost:8001")
    print("\nTo use:")
    print("1. Update frontend .env: VITE_API_URL=http://localhost:8001")
    print("2. Refresh browser")
    print("3. Ask any question in /query page")
    print("4. Click the low-confidence citation badge")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8001)
