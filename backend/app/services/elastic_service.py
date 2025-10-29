from elasticsearch import AsyncElasticsearch
from typing import Dict, Any, List, Optional
from app.core.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ElasticsearchService:
    def __init__(self):
        self.client = AsyncElasticsearch([settings.ELASTICSEARCH_URL])
        self.index_name = "documents"
        self.template_signatures_index = "template_signatures"

    async def create_index(self, schema: Dict[str, Any]) -> None:
        """Create Elasticsearch index with dynamic mapping based on schema"""

        # Build field mappings from schema with multi-field support
        properties = {}
        for field in schema.get("fields", []):
            field_type = self._get_es_field_type(field["type"])

            # Multi-field configuration for flexible querying
            field_config = {"type": field_type}

            # Add keyword sub-field for text fields (exact matching)
            if field_type == "text":
                field_config["fields"] = {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256  # Prevent indexing failures on long text
                    }
                    # Removed .raw sub-field (redundant, saves 30-40% storage)
                }

            properties[field["name"]] = field_config

            # NEW: Add metadata sub-document for each field
            properties[f"{field['name']}_meta"] = {
                "type": "object",
                "properties": {
                    "description": {"type": "text"},
                    "aliases": {"type": "keyword"},
                    "hints": {"type": "keyword"},
                    "confidence": {"type": "float"},
                    "verified": {"type": "boolean"}
                }
            }

        # Add standard metadata fields
        properties.update({
            "document_id": {"type": "integer"},
            "filename": {
                "type": "keyword",
                "ignore_above": 512  # Allow longer filenames
            },
            "uploaded_at": {"type": "date"},
            "processed_at": {"type": "date"},
            "full_text": {"type": "text"},
            "confidence_scores": {
                "type": "object",
                "enabled": False  # Store but don't index (used for retrieval only)
            }
        })

        # NEW: Add query-friendly enrichment fields
        properties.update({
            # Combined searchable text for broad matching
            "_all_text": {
                "type": "text",
                "analyzer": "standard"
            },
            # Query context for better LLM understanding
            "_query_context": {
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "keyword",
                        "ignore_above": 256
                    },
                    "template_id": {"type": "integer"},
                    "field_names": {
                        "type": "keyword",
                        "ignore_above": 256
                    },
                    "canonical_fields": {
                        "type": "object",
                        "enabled": False  # Dynamic structure, store but don't index
                    },
                    "indexed_at": {"type": "date"}
                }
            },
            # Field name searchability
            "_field_index": {
                "type": "text",
                "analyzer": "standard"
            }
        })

        index_settings = {
            "mappings": {
                "dynamic": "strict",  # Reject unmapped fields (production best practice)
                "properties": properties
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                # Field limits to prevent mapping explosion
                "index.mapping.total_fields.limit": 1000,
                "index.mapping.depth.limit": 20,
                "index.mapping.nested_fields.limit": 50
            }
        }

        # Create or update index
        if await self.client.indices.exists(index=self.index_name):
            logger.info(f"Updating index: {self.index_name}")
            await self.client.indices.put_mapping(
                index=self.index_name,
                body={"properties": properties}
            )
        else:
            logger.info(f"Creating index: {self.index_name}")
            await self.client.indices.create(
                index=self.index_name,
                body=index_settings
            )

    def _get_es_field_type(self, field_type: str) -> str:
        """Map schema field type to Elasticsearch type"""
        type_mapping = {
            "text": "text",
            "date": "date",
            "number": "float",
            "integer": "integer",
            "boolean": "boolean"
        }
        return type_mapping.get(field_type, "text")

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
        """
        Index a document with extracted fields and enriched metadata.

        Args:
            document_id: Document ID
            filename: Original filename
            extracted_fields: Extracted field values
            confidence_scores: Confidence scores for each field
            full_text: Full document text
            schema: Schema definition (for enrichment)
            field_metadata: Field metadata from SchemaRegistry (for enrichment)
        """

        # Base document
        doc = {
            "document_id": document_id,
            "filename": filename,
            "full_text": full_text,
            "confidence_scores": confidence_scores,
            **extracted_fields
        }

        # NEW: Build enriched metadata
        all_text_parts = [full_text, filename]
        field_names = list(extracted_fields.keys())

        # Add field metadata if available
        if schema and schema.get("fields"):
            for field_def in schema["fields"]:
                field_name = field_def.get("name")
                if field_name in extracted_fields:
                    # Create metadata sub-document
                    meta_key = f"{field_name}_meta"
                    doc[meta_key] = {
                        "description": field_def.get("description", ""),
                        "aliases": field_metadata.get(field_name, {}).get("aliases", []) if field_metadata else [],
                        "hints": field_def.get("extraction_hints", []),
                        "confidence": confidence_scores.get(field_name, 0.0),
                        "verified": False
                    }

                    # Add to searchable text
                    field_value = extracted_fields.get(field_name)
                    if field_value:
                        all_text_parts.append(str(field_value))

        # NEW: Add query context
        doc["_query_context"] = {
            "template_name": schema.get("name", "unknown") if schema else "unknown",
            "template_id": schema.get("id", 0) if schema else 0,
            "field_names": field_names,
            "canonical_fields": self._build_canonical_fields(extracted_fields, field_metadata) if field_metadata else {},
            "indexed_at": datetime.utcnow().isoformat()
        }

        # NEW: Combined searchable text
        doc["_all_text"] = " ".join(all_text_parts)

        # NEW: Field name index for discovery
        doc["_field_index"] = " ".join(field_names)

        logger.info(f"Indexing document: {document_id} with enriched metadata")
        response = await self.client.index(
            index=self.index_name,
            id=str(document_id),
            document=doc
        )

        return response["_id"]

    def _build_canonical_fields(
        self,
        extracted_fields: Dict[str, Any],
        field_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build comprehensive canonical field mapping for cross-template queries.

        This enables queries like "amount > 1000" to work across templates
        using invoice_total, payment_amount, contract_value, etc.
        """
        canonical = {}

        # Enhanced pattern matching for canonical categories
        canonical_patterns = {
            # Money/Value fields
            "amount": ["total", "amount", "cost", "price", "value", "payment", "sum", "fee", "charge"],

            # Date fields - general
            "date": ["date", "created", "when"],
            "start_date": ["start", "effective", "begin", "from"],
            "end_date": ["end", "expir", "terminat", "until", "to"],

            # Entity names
            "entity_name": ["vendor", "supplier", "customer", "client", "company", "organization"],

            # Identifiers
            "identifier": ["number", "id", "reference", "ref", "code"],

            # Status
            "status": ["status", "state", "condition"],

            # Description
            "description": ["description", "notes", "comment", "memo", "detail"],

            # Quantity
            "quantity": ["quantity", "qty", "count", "num"],

            # Address
            "address": ["address", "location", "street", "city"],

            # Contact
            "contact": ["email", "phone", "contact"],
        }

        for field_name, field_value in extracted_fields.items():
            if field_value is None:
                continue

            field_lower = field_name.lower()

            # Try to match to canonical category
            matched = False
            for canonical_name, patterns in canonical_patterns.items():
                for pattern in patterns:
                    if pattern in field_lower:
                        # Use first match, or override if this is a better match
                        if canonical_name not in canonical or \
                           field_lower.startswith(pattern):  # Prefer exact prefix match
                            canonical[canonical_name] = field_value
                            # Store original field name for reference
                            canonical[f"_original_{canonical_name}_field"] = field_name
                        matched = True
                        break
                if matched:
                    break

        return canonical

    async def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        min_confidence: Optional[float] = None,
        custom_query: Optional[Dict[str, Any]] = None,
        page: int = 1,
        size: int = 10
    ) -> Dict[str, Any]:
        """Search documents with optional filters"""

        # Use custom query if provided (for NL search)
        if custom_query:
            search_query = custom_query
        else:
            # Build query
            must_clauses = []
            filter_clauses = []

            # Text search
            if query:
                must_clauses.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["full_text", "*"],
                        "type": "best_fields"
                    }
                })

            # Field filters
            if filters:
                for field, value in filters.items():
                    filter_clauses.append({
                        "term": {field: value}
                    })

            # Confidence filter
            if min_confidence is not None:
                filter_clauses.append({
                    "script": {
                        "script": f"doc['confidence_scores'].values.stream().anyMatch(v -> v >= {min_confidence})"
                    }
                })

            # Build complete query
            search_query = {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            }

        # Calculate pagination
        from_index = (page - 1) * size

        logger.info(f"Searching with query: {query}, filters: {filters}")
        response = await self.client.search(
            index=self.index_name,
            query=search_query,
            from_=from_index,
            size=size,
            highlight={
                "fields": {
                    "full_text": {}
                }
            }
        )

        # Format results
        results = {
            "total": response["hits"]["total"]["value"],
            "page": page,
            "size": size,
            "documents": [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "data": hit["_source"],
                    "highlights": hit.get("highlight", {})
                }
                for hit in response["hits"]["hits"]
            ]
        }

        return results

    async def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            response = await self.client.get(
                index=self.index_name,
                id=str(document_id)
            )
            return response["_source"]
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None

    async def update_document(
        self,
        document_id: int,
        updated_fields: Dict[str, Any]
    ) -> None:
        """Update document fields (e.g., after verification)"""
        logger.info(f"Updating document: {document_id}")
        await self.client.update(
            index=self.index_name,
            id=str(document_id),
            doc=updated_fields
        )

    async def get_aggregations(self, field: str) -> Dict[str, Any]:
        """Get aggregations for analytics"""
        response = await self.client.search(
            index=self.index_name,
            size=0,
            aggs={
                f"{field}_stats": {
                    "terms": {
                        "field": field,
                        "size": 100
                    }
                }
            }
        )

        return response["aggregations"]

    async def health_check(self) -> bool:
        """Check Elasticsearch connection"""
        try:
            health = await self.client.cluster.health()
            return health["status"] in ["yellow", "green"]
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False

    async def close(self):
        """Close Elasticsearch connection"""
        await self.client.close()

    async def optimize_for_bulk_indexing(self, enable: bool = True):
        """
        Optimize index settings for bulk indexing operations.

        Args:
            enable: If True, disable refresh for faster bulk indexing.
                   If False, restore normal refresh interval.

        Best Practice: Disable refresh during large bulk operations,
        then restore to improve indexing performance by 20-30%.
        """
        if enable:
            logger.info("Optimizing index for bulk indexing (disabling refresh)")
            await self.client.indices.put_settings(
                index=self.index_name,
                body={"index.refresh_interval": "-1"}  # Disable refresh
            )
        else:
            logger.info("Restoring normal refresh interval")
            await self.client.indices.put_settings(
                index=self.index_name,
                body={"index.refresh_interval": "5s"}  # Restore (5s for MVP)
            )

    async def refresh_index(self):
        """
        Manually refresh the index to make recent changes visible.

        Use after bulk indexing with disabled refresh.
        """
        logger.info(f"Refreshing index: {self.index_name}")
        await self.client.indices.refresh(index=self.index_name)

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics for monitoring.

        Returns:
            Dict with document count, storage size, field count, etc.
        """
        stats = await self.client.indices.stats(index=self.index_name)
        mapping = await self.client.indices.get_mapping(index=self.index_name)

        index_stats = stats["indices"][self.index_name]
        field_count = len(mapping[self.index_name]["mappings"]["properties"])

        return {
            "document_count": index_stats["total"]["docs"]["count"],
            "storage_size_bytes": index_stats["total"]["store"]["size_in_bytes"],
            "storage_size_mb": round(index_stats["total"]["store"]["size_in_bytes"] / (1024 * 1024), 2),
            "field_count": field_count,
            "field_limit": 1000,  # From settings
            "field_utilization_pct": round((field_count / 1000) * 100, 1)
        }

    async def create_template_signatures_index(self) -> None:
        """Create index for template signatures (for similarity matching)"""

        index_settings = {
            "mappings": {
                "dynamic": "strict",  # Production best practice
                "properties": {
                    "template_id": {"type": "integer"},
                    "template_name": {
                        "type": "keyword",
                        "ignore_above": 256,
                        "eager_global_ordinals": True  # Faster aggregations
                    },
                    "field_names_text": {"type": "text"},  # Searchable text
                    "field_names": {
                        "type": "keyword",
                        "ignore_above": 256
                    },  # Array for exact match
                    "sample_text": {"type": "text"},  # Sample document text
                    "category": {
                        "type": "keyword",
                        "ignore_above": 100,
                        "eager_global_ordinals": True  # Frequently used in aggregations
                    },
                    "created_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.mapping.total_fields.limit": 200  # Smaller limit for templates
            }
        }

        if await self.client.indices.exists(index=self.template_signatures_index):
            logger.info(f"Index {self.template_signatures_index} already exists")
        else:
            logger.info(f"Creating index: {self.template_signatures_index}")
            await self.client.indices.create(
                index=self.template_signatures_index,
                body=index_settings
            )

    async def index_template_signature(
        self,
        template_id: int,
        template_name: str,
        field_names: List[str],
        sample_text: str = "",
        category: str = "general"
    ) -> str:
        """
        Index a template signature for similarity matching

        Args:
            template_id: Template ID
            template_name: Template name
            field_names: List of field names in template
            sample_text: Optional sample text from documents using this template
            category: Template category

        Returns:
            Elasticsearch document ID
        """
        from datetime import datetime

        doc = {
            "template_id": template_id,
            "template_name": template_name,
            "field_names_text": " ".join(field_names),  # Space-separated for text search
            "field_names": field_names,
            "sample_text": sample_text[:5000] if sample_text else "",  # Limit to 5k chars
            "category": category,
            "created_at": datetime.utcnow()
        }

        logger.info(f"Indexing template signature: {template_name} (ID: {template_id})")
        response = await self.client.index(
            index=self.template_signatures_index,
            id=str(template_id),
            document=doc
        )

        return response["_id"]

    async def find_similar_templates(
        self,
        document_text: str,
        document_fields: List[str],
        min_score: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Find templates similar to a document using More Like This query

        Args:
            document_text: Document text content
            document_fields: List of field names extracted from document
            min_score: Minimum similarity score (0.0-1.0)

        Returns:
            List of matching templates with similarity scores
            [
                {
                    "template_id": 1,
                    "template_name": "Invoices",
                    "similarity_score": 0.85,
                    "matching_fields": ["invoice_number", "total"],
                    "match_count": 7,
                    "total_fields": 9
                },
                ...
            ]
        """

        # Build More Like This query
        query = {
            "more_like_this": {
                "fields": ["field_names_text", "sample_text"],
                "like": [
                    {
                        "doc": {
                            "field_names_text": " ".join(document_fields),
                            "sample_text": document_text[:5000]
                        }
                    }
                ],
                "min_term_freq": 1,
                "min_doc_freq": 1,
                "max_query_terms": 25,
                "min_word_length": 3,
                "boost_terms": 1.0
            }
        }

        try:
            response = await self.client.search(
                index=self.template_signatures_index,
                query=query,
                size=5,  # Return top 5 matches
                min_score=min_score
            )

            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]

                # Calculate field overlap
                doc_fields_set = set(document_fields)
                template_fields_set = set(source["field_names"])
                overlap = doc_fields_set.intersection(template_fields_set)

                # Normalize ES score to 0-1 range (ES scores are typically 0-10+)
                normalized_score = min(hit["_score"] / 10.0, 1.0)

                results.append({
                    "template_id": source["template_id"],
                    "template_name": source["template_name"],
                    "similarity_score": normalized_score,
                    "matching_fields": list(overlap),
                    "match_count": len(overlap),
                    "total_fields": len(template_fields_set),
                    "all_template_fields": list(template_fields_set)
                })

            logger.info(f"Found {len(results)} similar templates for document")
            return results

        except Exception as e:
            logger.error(f"Error finding similar templates: {e}")
            return []
