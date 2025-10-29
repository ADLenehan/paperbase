# Vector Search Quick Start

## You Already Have It! ✅

**Elasticsearch 8.11.0** includes native vector search. No external services needed!

## What You Need (2-3 hours)

### 1. Add Embedding Service (30 min)

Create `backend/app/services/embedding_service.py`:

```python
from anthropic import Anthropic
import numpy as np
from typing import List
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Generate embeddings using Claude or OpenAI"""

    def __init__(self):
        # Option 1: Use Anthropic (you already have the key)
        from app.core.config import settings
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Note: Anthropic doesn't have embeddings API yet.
        Use OpenAI or Cohere instead.
        """
        # TODO: Switch to OpenAI or Cohere
        # For now, using placeholder

        # OpenAI example (add to requirements.txt: openai)
        import openai
        response = openai.Embedding.create(
            model="text-embedding-3-small",  # $0.02 per 1M tokens
            input=text[:8000]  # Truncate to fit model
        )
        return response['data'][0]['embedding']

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        import openai
        response = openai.Embedding.create(
            model="text-embedding-3-small",
            input=[t[:8000] for t in texts]
        )
        return [item['embedding'] for item in response['data']]
```

**Cost:** ~$0.02 per 1M tokens = ~$0.001 per document

### 2. Update Elasticsearch Index (30 min)

Add to `backend/app/services/elastic_service.py`:

```python
async def create_index_with_vectors(self, schema: Dict[str, Any]) -> None:
    """Create index with vector field support"""

    # Existing properties...
    properties = { ... }

    # ADD THIS: Vector field for semantic search
    properties["content_embedding"] = {
        "type": "dense_vector",
        "dims": 1536,  # OpenAI text-embedding-3-small dimension
        "index": True,
        "similarity": "cosine"  # or "dot_product" or "l2_norm"
    }

    # For chunk-level search (better for long docs)
    properties["chunks"] = {
        "type": "nested",
        "properties": {
            "text": {"type": "text"},
            "embedding": {
                "type": "dense_vector",
                "dims": 1536,
                "index": True,
                "similarity": "cosine"
            },
            "chunk_index": {"type": "integer"}
        }
    }

    # Rest of index creation...
```

### 3. Index Documents with Embeddings (1 hour)

Update `index_document` method:

```python
async def index_document(
    self,
    document_id: int,
    filename: str,
    extracted_fields: Dict[str, Any],
    confidence_scores: Dict[str, float],
    full_text: str = "",
    schema: Optional[Dict[str, Any]] = None,
    field_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Index document with embeddings"""

    from app.services.embedding_service import EmbeddingService
    embedding_service = EmbeddingService()

    # Base document...
    doc = { ... }

    # ADD THIS: Generate embedding for full text
    if full_text:
        # For short docs: embed entire document
        doc["content_embedding"] = await embedding_service.embed_text(full_text[:8000])

        # For long docs: chunk and embed each chunk
        if len(full_text) > 8000:
            chunks = self._chunk_text(full_text, chunk_size=1000, overlap=200)
            chunk_embeddings = await embedding_service.embed_batch(chunks)

            doc["chunks"] = [
                {
                    "text": chunk_text,
                    "embedding": embedding,
                    "chunk_index": i
                }
                for i, (chunk_text, embedding) in enumerate(zip(chunks, chunk_embeddings))
            ]

    # Index as usual...
    response = await self.client.index(...)
    return response["_id"]

def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
```

### 4. Add Vector Search Method (30 min)

Add to `elastic_service.py`:

```python
async def vector_search(
    self,
    query_text: str,
    k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    hybrid: bool = True  # Combine with keyword search
) -> Dict[str, Any]:
    """
    Semantic vector search using kNN.

    Args:
        query_text: Text to search for semantically
        k: Number of results
        filters: Optional filters
        hybrid: If True, combines vector + keyword search
    """
    from app.services.embedding_service import EmbeddingService

    embedding_service = EmbeddingService()
    query_embedding = await embedding_service.embed_text(query_text)

    if hybrid:
        # Hybrid search: Vector + BM25
        query = {
            "bool": {
                "should": [
                    # Vector search (semantic)
                    {
                        "knn": {
                            "field": "content_embedding",
                            "query_vector": query_embedding,
                            "k": k,
                            "num_candidates": k * 10
                        }
                    },
                    # Keyword search (BM25)
                    {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["full_text", "_all_text"],
                            "boost": 0.5  # Weight keyword search less
                        }
                    }
                ]
            }
        }
    else:
        # Pure vector search
        query = {
            "knn": {
                "field": "content_embedding",
                "query_vector": query_embedding,
                "k": k,
                "num_candidates": k * 10
            }
        }

    # Add filters if provided
    if filters:
        if "bool" not in query:
            query = {"bool": {"must": [query]}}
        query["bool"]["filter"] = [
            {"term": {field: value}} for field, value in filters.items()
        ]

    response = await self.client.search(
        index=self.index_name,
        query=query,
        size=k
    )

    # Format results same as regular search
    return self._format_search_results(response)
```

### 5. Add MCP Vector Search Tool (30 min)

Add to `backend/app/api/mcp_search.py`:

```python
@router.post("/semantic-search")
async def semantic_search_mcp(
    query: str = Query(..., description="Semantic search query"),
    max_results: int = Query(default=10, ge=1, le=50),
    hybrid: bool = Query(default=True, description="Combine with keyword search"),
    filters: Optional[Dict[str, Any]] = None
):
    """
    Semantic vector search - finds documents by meaning, not just keywords.

    Examples:
    - "documents about contract termination" (finds even if text says "agreement ending")
    - "financial reports showing losses" (finds "revenue decline", "negative earnings")

    Better than keyword search for:
    - Conceptual queries
    - Synonyms and related terms
    - Cross-language similarity
    """

    elastic_service = ElasticsearchService()

    try:
        results = await elastic_service.vector_search(
            query_text=query,
            k=max_results,
            filters=filters,
            hybrid=hybrid
        )

        return {
            "success": True,
            "query": query,
            "search_type": "hybrid" if hybrid else "vector",
            "total_results": results.get("total", 0),
            "documents": results.get("documents", [])
        }

    except Exception as e:
        logger.error(f"Semantic search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

### 6. Update Requirements (5 min)

Add to `backend/requirements.txt`:

```
openai>=1.0.0  # For embeddings
# OR
cohere>=4.0.0  # Alternative, slightly cheaper
```

## That's It!

**Total Time:** ~3 hours
**Total Cost:** ~$0.001 per document (one-time)

## Usage Example

```python
# Keyword search (current)
results = search_documents("contract termination clause")
# Finds: documents with exact words "contract", "termination", "clause"

# Vector search (new)
results = semantic_search("contract termination clause")
# Finds: "agreement ending provision", "cancellation terms", "exit conditions"
# Even if those exact words aren't in the query!

# Hybrid (best of both)
results = semantic_search("contract termination clause", hybrid=True)
# Combines keyword exactness + semantic understanding
```

## Why This Is Better Than I Said

In PRODUCTION_ROADMAP.md I said:
- ❌ "Vector storage (Elasticsearch vector fields or Pinecone/Weaviate)"
- ❌ "3-5 days to implement"

**Actually:**
- ✅ Elasticsearch 8.11 has native vectors (you already have it)
- ✅ 2-3 hours to implement (not days)
- ✅ No external services needed
- ✅ Lower cost (no Pinecone/Weaviate fees)

## Performance

**Elasticsearch 8.11 Vector Search:**
- 10-50ms for kNN search (up to 10M vectors)
- Hybrid search: 50-100ms
- Scales horizontally (add more ES nodes)

**Accuracy:**
- Cosine similarity: Best for text
- Dot product: Faster, similar accuracy
- L2 norm: Traditional distance metric

## Cost Comparison

**OpenAI text-embedding-3-small:**
- $0.02 per 1M tokens
- Average doc (5 pages): ~2000 tokens
- Cost per doc: ~$0.00004
- 1000 docs: ~$0.04 (one-time)

**Cohere embed-english-v3.0:**
- $0.01 per 1M tokens (50% cheaper)
- Same quality

**Anthropic:**
- No embeddings API yet (coming soon)

## Migration Strategy

### Option 1: Reindex Everything (Simple)
```python
# Script to reindex with embeddings
async def reindex_with_vectors():
    docs = db.query(Document).all()
    for doc in docs:
        # Get from ES
        es_doc = await elastic_service.get_document(doc.id)

        # Generate embedding
        embedding = await embedding_service.embed_text(es_doc["full_text"])

        # Update document
        await elastic_service.update_document(
            doc.id,
            {"content_embedding": embedding}
        )
```

### Option 2: Lazy Loading (Zero Downtime)
- New docs: Embed on upload
- Old docs: Embed on first vector search
- Gradually builds vector index

### Option 3: Background Job (Production)
- Celery task to embed documents
- Process in batches (100 at a time)
- Won't hit rate limits

## MCP Config Update

Add to `mcp-server-config.json`:

```json
{
  "name": "semantic_search",
  "description": "Semantic vector search - finds documents by meaning",
  "endpoint": "/api/mcp/search/semantic-search",
  "method": "POST",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "max_results": {"type": "integer", "default": 10},
      "hybrid": {"type": "boolean", "default": true},
      "filters": {"type": "object"}
    },
    "required": ["query"]
  }
}
```

## Testing

```python
# Test semantic search
def test_semantic_search():
    # Upload doc with "contract termination"
    upload_document("contract.pdf")

    # Search with synonym
    results = semantic_search("agreement cancellation")

    # Should find the contract doc!
    assert len(results) > 0
    assert "contract.pdf" in [r["filename"] for r in results]
```

## Summary

**What I Said:**
- Need external vector DB (Pinecone/Weaviate)
- 3-5 days of work
- Complex setup

**Reality:**
- ✅ You already have it (ES 8.11)
- ✅ 2-3 hours of work
- ✅ Just add embeddings + 1 search method

**You were right to question this!** 🎯
