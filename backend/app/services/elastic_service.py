import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch

from app.core.config import settings

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
            field_name = field["name"]
            field_type = field.get("type", "text")

            # Handle complex types (array, table, array_of_objects)
            if field_type in ["array", "array_of_objects", "table"]:
                properties[field_name] = self._build_complex_field_mapping(field)
            else:
                # Simple types
                es_field_type = self._get_es_field_type(field_type)
                field_config = {"type": es_field_type}

                # Add keyword sub-field for text fields (exact matching)
                if es_field_type == "text":
                    field_config["fields"] = {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256  # Prevent indexing failures on long text
                        }
                        # Removed .raw sub-field (redundant, saves 30-40% storage)
                    }

                properties[field_name] = field_config

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
            },
            # NEW: Citation metadata for trustworthy AI answers
            "_citation_metadata": {
                "type": "object",
                "properties": {
                    "has_low_confidence_fields": {"type": "boolean"},
                    "low_confidence_field_names": {
                        "type": "keyword",
                        "ignore_above": 256
                    },
                    "audit_urls": {
                        "type": "object",
                        "enabled": False  # Dynamic field names (field_name -> url)
                    }
                }
            },
            # NEW: Confidence metrics for filtering/ranking
            "_confidence_metrics": {
                "type": "object",
                "properties": {
                    "min_confidence": {"type": "float"},
                    "max_confidence": {"type": "float"},
                    "avg_confidence": {"type": "float"},
                    "field_count": {"type": "integer"},
                    "verified_field_count": {"type": "integer"}
                }
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

    def _build_complex_field_mapping(self, field: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Elasticsearch mapping for complex field types (array, table, array_of_objects).

        Args:
            field: Field definition with type and schema information

        Returns:
            Elasticsearch mapping configuration
        """
        field_type = field.get("type")

        if field_type == "array":
            # Simple array (list of primitives)
            item_type = field.get("item_type", "text")
            es_item_type = self._get_es_field_type(item_type)

            # Arrays in ES are handled automatically - just define the item type
            mapping = {"type": es_item_type}

            # Add keyword sub-field for text arrays
            if es_item_type == "text":
                mapping["fields"] = {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }

            return mapping

        elif field_type == "array_of_objects":
            # Array of structured objects (e.g., invoice line items)
            # Use "object" type for simple nested structures
            object_schema = field.get("object_schema", {})
            properties = {}

            for obj_field_name, obj_field_def in object_schema.items():
                obj_type = obj_field_def.get("type", "text")
                es_type = self._get_es_field_type(obj_type)
                properties[obj_field_name] = {"type": es_type}

                # Add keyword sub-field for text fields
                if es_type == "text":
                    properties[obj_field_name]["fields"] = {
                        "keyword": {"type": "keyword", "ignore_above": 256}
                    }

            return {
                "type": "object",
                "properties": properties
            }

        elif field_type == "table":
            # Table with dynamic columns (e.g., grading specs)
            # Use "nested" type for independent row queries
            table_schema = field.get("table_schema", {})
            row_identifier = table_schema.get("row_identifier", "id")
            columns = table_schema.get("columns", [])
            value_type = table_schema.get("value_type", "string")
            dynamic_columns = table_schema.get("dynamic_columns", False)

            # Build properties for known columns
            properties = {
                row_identifier: {"type": "keyword"}
            }

            es_value_type = self._get_es_field_type(value_type)
            for col in columns:
                properties[col] = {"type": es_value_type}

            mapping = {
                "type": "nested",
                "properties": properties
            }

            # Enable dynamic templates for variable columns
            if dynamic_columns:
                column_pattern = table_schema.get("column_pattern", ".*")
                mapping["dynamic"] = "true"
                mapping["dynamic_templates"] = [
                    {
                        "dynamic_columns": {
                            "match_pattern": "regex",
                            "match": column_pattern,
                            "mapping": {
                                "type": es_value_type
                            }
                        }
                    }
                ]

            return mapping

        # Fallback for unknown types
        return {"type": "text"}

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

        # NEW: Calculate confidence metrics for filtering/ranking
        if confidence_scores:
            confidence_values = list(confidence_scores.values())
            doc["_confidence_metrics"] = {
                "min_confidence": min(confidence_values),
                "max_confidence": max(confidence_values),
                "avg_confidence": sum(confidence_values) / len(confidence_values),
                "field_count": len(confidence_values),
                "verified_field_count": 0  # Updated via update_document when verified
            }
        else:
            doc["_confidence_metrics"] = {
                "min_confidence": 1.0,
                "max_confidence": 1.0,
                "avg_confidence": 1.0,
                "field_count": 0,
                "verified_field_count": 0
            }

        # NEW: Build citation metadata for audit traceability
        # This will be populated by audit_helpers when needed
        # Using default threshold of 0.6 for low-confidence detection
        audit_threshold = 0.6
        low_confidence_fields = [
            field_name for field_name, conf in confidence_scores.items()
            if conf < audit_threshold
        ]

        doc["_citation_metadata"] = {
            "has_low_confidence_fields": len(low_confidence_fields) > 0,
            "low_confidence_field_names": low_confidence_fields,
            "audit_urls": {}  # Populated by audit_helpers.prepare_citation_metadata()
        }

        logger.info(f"Indexing document: {document_id} with enriched metadata (confidence: avg={doc['_confidence_metrics']['avg_confidence']:.2f})")
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
                    "filename": hit["_source"].get("filename"),  # Top-level for frontend
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

    async def delete_document(self, elasticsearch_id: str) -> None:
        """Delete a document from Elasticsearch by its ID"""
        try:
            logger.info(f"Deleting document from Elasticsearch: {elasticsearch_id}")
            await self.client.delete(
                index=self.index_name,
                id=elasticsearch_id
            )
        except Exception as e:
            logger.error(f"Failed to delete document {elasticsearch_id} from Elasticsearch: {e}")
            raise

    async def get_aggregations(
        self,
        field: str = None,
        agg_type: str = "terms",
        agg_config: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        custom_aggs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get aggregations for analytics with flexible configuration.

        Args:
            field: Field to aggregate (required unless custom_aggs provided)
            agg_type: Type of aggregation (terms, stats, date_histogram, range, cardinality)
            agg_config: Additional aggregation configuration
            filters: Optional query filters to apply before aggregation
            custom_aggs: Custom aggregation definition (overrides field/agg_type)

        Returns:
            Aggregation results with metadata
        """

        # Build aggregation definition
        if custom_aggs:
            aggs = custom_aggs
        else:
            if not field:
                raise ValueError("field is required when custom_aggs is not provided")

            agg_name = f"{field}_{agg_type}"

            # Build aggregation based on type
            if agg_type == "terms":
                aggs = {
                    agg_name: {
                        "terms": {
                            "field": f"{field}.keyword" if not field.endswith(".keyword") else field,
                            "size": agg_config.get("size", 100) if agg_config else 100,
                            "order": agg_config.get("order", {"_count": "desc"}) if agg_config else {"_count": "desc"}
                        }
                    }
                }
            elif agg_type == "stats":
                aggs = {
                    agg_name: {
                        "stats": {
                            "field": field
                        }
                    }
                }
            elif agg_type == "extended_stats":
                aggs = {
                    agg_name: {
                        "extended_stats": {
                            "field": field
                        }
                    }
                }
            elif agg_type == "date_histogram":
                aggs = {
                    agg_name: {
                        "date_histogram": {
                            "field": field,
                            "calendar_interval": agg_config.get("interval", "month") if agg_config else "month",
                            "format": agg_config.get("format", "yyyy-MM-dd") if agg_config else "yyyy-MM-dd"
                        }
                    }
                }
            elif agg_type == "range":
                if not agg_config or "ranges" not in agg_config:
                    raise ValueError("ranges must be provided in agg_config for range aggregation")
                aggs = {
                    agg_name: {
                        "range": {
                            "field": field,
                            "ranges": agg_config["ranges"]
                        }
                    }
                }
            elif agg_type == "cardinality":
                aggs = {
                    agg_name: {
                        "cardinality": {
                            "field": f"{field}.keyword" if not field.endswith(".keyword") else field
                        }
                    }
                }
            elif agg_type == "histogram":
                aggs = {
                    agg_name: {
                        "histogram": {
                            "field": field,
                            "interval": agg_config.get("interval", 100) if agg_config else 100
                        }
                    }
                }
            elif agg_type == "percentiles":
                aggs = {
                    agg_name: {
                        "percentiles": {
                            "field": field,
                            "percents": agg_config.get("percents", [25, 50, 75, 95, 99]) if agg_config else [25, 50, 75, 95, 99]
                        }
                    }
                }
            else:
                raise ValueError(f"Unsupported aggregation type: {agg_type}")

        # Build query with optional filters
        query = {"match_all": {}}
        if filters:
            filter_clauses = []
            for filter_field, filter_value in filters.items():
                if isinstance(filter_value, dict):
                    # Range or complex filter
                    filter_clauses.append({filter_field: filter_value})
                else:
                    # Term filter
                    filter_clauses.append({"term": {filter_field: filter_value}})

            query = {
                "bool": {
                    "filter": filter_clauses
                }
            }

        response = await self.client.search(
            index=self.index_name,
            size=0,
            query=query,
            aggs=aggs
        )

        return response["aggregations"]

    async def get_multi_aggregations(
        self,
        aggregations: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple aggregations in a single query.

        Args:
            aggregations: List of aggregation definitions, each with:
                - name: Aggregation name
                - field: Field to aggregate
                - type: Aggregation type
                - config: Optional configuration
            filters: Optional query filters

        Returns:
            Dictionary of aggregation results keyed by name

        Example:
            aggregations = [
                {"name": "status_breakdown", "field": "status", "type": "terms"},
                {"name": "amount_stats", "field": "total_amount", "type": "stats"},
                {"name": "monthly_uploads", "field": "uploaded_at", "type": "date_histogram",
                 "config": {"interval": "month"}}
            ]
        """

        aggs = {}
        for agg_def in aggregations:
            name = agg_def["name"]
            field = agg_def["field"]
            agg_type = agg_def["type"]
            config = agg_def.get("config", {})

            # Build individual aggregation
            if agg_type == "terms":
                aggs[name] = {
                    "terms": {
                        "field": f"{field}.keyword" if not field.endswith(".keyword") else field,
                        "size": config.get("size", 100),
                        "order": config.get("order", {"_count": "desc"})
                    }
                }
            elif agg_type == "stats":
                aggs[name] = {"stats": {"field": field}}
            elif agg_type == "extended_stats":
                aggs[name] = {"extended_stats": {"field": field}}
            elif agg_type == "date_histogram":
                aggs[name] = {
                    "date_histogram": {
                        "field": field,
                        "calendar_interval": config.get("interval", "month"),
                        "format": config.get("format", "yyyy-MM-dd")
                    }
                }
            elif agg_type == "range":
                if "ranges" not in config:
                    raise ValueError(f"ranges required for {name}")
                aggs[name] = {
                    "range": {
                        "field": field,
                        "ranges": config["ranges"]
                    }
                }
            elif agg_type == "cardinality":
                aggs[name] = {
                    "cardinality": {
                        "field": f"{field}.keyword" if not field.endswith(".keyword") else field
                    }
                }
            elif agg_type == "histogram":
                aggs[name] = {
                    "histogram": {
                        "field": field,
                        "interval": config.get("interval", 100)
                    }
                }
            elif agg_type == "percentiles":
                aggs[name] = {
                    "percentiles": {
                        "field": field,
                        "percents": config.get("percents", [25, 50, 75, 95, 99])
                    }
                }

        # Build query
        query = {"match_all": {}}
        if filters:
            filter_clauses = []
            for filter_field, filter_value in filters.items():
                if isinstance(filter_value, dict):
                    filter_clauses.append({filter_field: filter_value})
                else:
                    filter_clauses.append({"term": {filter_field: filter_value}})

            query = {
                "bool": {
                    "filter": filter_clauses
                }
            }

        response = await self.client.search(
            index=self.index_name,
            size=0,
            query=query,
            aggs=aggs
        )

        return response["aggregations"]

    async def get_nested_aggregations(
        self,
        parent_agg: Dict[str, Any],
        sub_aggs: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute nested (hierarchical) aggregations.

        Args:
            parent_agg: Parent aggregation definition
            sub_aggs: List of sub-aggregation definitions
            filters: Optional query filters

        Returns:
            Nested aggregation results

        Example:
            # Group by status, then get amount stats for each status
            parent_agg = {"name": "by_status", "field": "status", "type": "terms"}
            sub_aggs = [{"name": "amount_stats", "field": "total_amount", "type": "stats"}]
        """

        # Build sub-aggregations
        sub_agg_dict = {}
        for sub_agg in sub_aggs:
            name = sub_agg["name"]
            field = sub_agg["field"]
            agg_type = sub_agg["type"]
            config = sub_agg.get("config", {})

            if agg_type == "stats":
                sub_agg_dict[name] = {"stats": {"field": field}}
            elif agg_type == "terms":
                sub_agg_dict[name] = {
                    "terms": {
                        "field": f"{field}.keyword" if not field.endswith(".keyword") else field,
                        "size": config.get("size", 100)
                    }
                }
            elif agg_type == "cardinality":
                sub_agg_dict[name] = {
                    "cardinality": {
                        "field": f"{field}.keyword" if not field.endswith(".keyword") else field
                    }
                }

        # Build parent aggregation with sub-aggregations
        parent_name = parent_agg["name"]
        parent_field = parent_agg["field"]
        parent_type = parent_agg["type"]
        parent_config = parent_agg.get("config", {})

        if parent_type == "terms":
            aggs = {
                parent_name: {
                    "terms": {
                        "field": f"{parent_field}.keyword" if not parent_field.endswith(".keyword") else parent_field,
                        "size": parent_config.get("size", 100)
                    },
                    "aggs": sub_agg_dict
                }
            }
        elif parent_type == "date_histogram":
            aggs = {
                parent_name: {
                    "date_histogram": {
                        "field": parent_field,
                        "calendar_interval": parent_config.get("interval", "month")
                    },
                    "aggs": sub_agg_dict
                }
            }
        else:
            raise ValueError(f"Unsupported parent aggregation type: {parent_type}")

        # Build query
        query = {"match_all": {}}
        if filters:
            filter_clauses = []
            for filter_field, filter_value in filters.items():
                if isinstance(filter_value, dict):
                    filter_clauses.append({filter_field: filter_value})
                else:
                    filter_clauses.append({"term": {filter_field: filter_value}})

            query = {
                "bool": {
                    "filter": filter_clauses
                }
            }

        response = await self.client.search(
            index=self.index_name,
            size=0,
            query=query,
            aggs=aggs
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

    async def cluster_uploaded_documents(
        self,
        documents: List[Any],  # List[Document]
        similarity_threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Cluster uploaded documents using More-Like-This for intra-batch similarity.

        Algorithm:
        1. Start with all docs as unclustered
        2. Pick first doc as seed for cluster 1
        3. Find similar docs using MLT (min similarity threshold)
        4. Remove clustered docs from pool
        5. Repeat until all docs clustered

        Args:
            documents: List of Document objects with reducto_parse_result
            similarity_threshold: Minimum similarity score (0.0-1.0) to cluster together

        Returns:
            List of clusters:
            [
                {
                    "representative_doc_id": int,
                    "representative_filename": str,
                    "document_ids": [int, ...],
                    "filenames": [str, ...],
                    "cluster_size": int,
                    "avg_similarity": float
                },
                ...
            ]
        """

        if not documents:
            return []

        # Extract document text and metadata
        doc_data = []
        for doc in documents:
            # Use actual_parse_result property (supports both PhysicalFile and legacy)
            parse_result = doc.actual_parse_result
            if not parse_result:
                logger.warning(f"Skipping document {doc.id} - no parse result")
                continue

            chunks = parse_result.get("chunks", [])
            doc_text = "\n".join([c.get("content", "") for c in chunks[:10]])  # First 10 chunks

            doc_data.append({
                "id": doc.id,
                "filename": doc.filename,
                "text": doc_text[:5000]  # Limit to 5k chars for performance
            })

        if not doc_data:
            logger.warning("No documents with parse results to cluster")
            return []

        clusters = []
        unclustered_ids = {d["id"] for d in doc_data}
        doc_lookup = {d["id"]: d for d in doc_data}

        logger.info(f"Clustering {len(doc_data)} documents with threshold {similarity_threshold}")

        # Iteratively build clusters
        while unclustered_ids:
            # Pick first unclustered doc as seed
            seed_id = next(iter(unclustered_ids))
            seed_doc = doc_lookup[seed_id]

            cluster_doc_ids = [seed_id]
            unclustered_ids.remove(seed_id)

            # Find similar documents using text similarity
            similar_ids = []
            total_similarity = 0.0

            for candidate_id in list(unclustered_ids):
                candidate_doc = doc_lookup[candidate_id]

                # Simple text similarity using common words (fast approximation)
                # In production, could use ES MLT here, but this is faster for small batches
                similarity = self._calculate_text_similarity(
                    seed_doc["text"],
                    candidate_doc["text"]
                )

                if similarity >= similarity_threshold:
                    cluster_doc_ids.append(candidate_id)
                    unclustered_ids.remove(candidate_id)
                    total_similarity += similarity

            # Calculate average similarity
            avg_similarity = (total_similarity / len(cluster_doc_ids)) if len(cluster_doc_ids) > 1 else 1.0

            clusters.append({
                "representative_doc_id": seed_id,
                "representative_filename": seed_doc["filename"],
                "document_ids": cluster_doc_ids,
                "filenames": [doc_lookup[doc_id]["filename"] for doc_id in cluster_doc_ids],
                "cluster_size": len(cluster_doc_ids),
                "avg_similarity": round(avg_similarity, 2)
            })

            logger.info(
                f"Cluster {len(clusters)}: {len(cluster_doc_ids)} docs "
                f"(seed: {seed_doc['filename']}, avg similarity: {avg_similarity:.2f})"
            )

        logger.info(f"Created {len(clusters)} clusters from {len(doc_data)} documents")
        return clusters

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity using Jaccard similarity on word sets.

        Fast approximation for document clustering without ES query overhead.
        For production scale, consider using ES MLT or embeddings.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0.0-1.0
        """
        # Tokenize and normalize
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Remove common stopwords (basic filter)
        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
        words1 = {w for w in words1 if w not in stopwords and len(w) > 2}
        words2 = {w for w in words2 if w not in stopwords and len(w) > 2}

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity: intersection / union
        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

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
