"""
PostgreSQL service replacing ElasticsearchService.
Provides full-text search, aggregations, and similarity matching using PostgreSQL.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, cast, Float, func, or_, select, text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.search_index import DocumentSearchIndex, TemplateSignature

logger = logging.getLogger(__name__)


class PostgresService:
    """
    PostgreSQL service for document search and indexing.
    Replaces ElasticsearchService with PostgreSQL full-text search.
    """

    def __init__(self, db: Session):
        self.db = db

    async def create_index(self, schema: Dict[str, Any]) -> None:
        """
        Create/update search index for a schema.
        In PostgreSQL, this is a no-op since tables are created via migrations.
        Schema-specific indexes are created dynamically as needed.
        """
        logger.info(f"Schema index ready (PostgreSQL tables exist): {schema.get('name')}")

    async def index_document(
        self,
        document_id: int,
        filename: str,
        extracted_fields: Dict[str, Any],
        confidence_scores: Dict[str, float],
        full_text: str = "",
        schema: Optional[Dict[str, Any]] = None,
        field_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
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
        
        Returns:
            Document search index ID
        """
        all_text_parts = [full_text, filename]
        field_names = list(extracted_fields.keys())

        field_meta = {}
        if schema and schema.get("fields"):
            for field_def in schema["fields"]:
                field_name = field_def.get("name")
                if field_name in extracted_fields:
                    field_meta[field_name] = {
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

        query_context = {
            "template_name": schema.get("name", "unknown") if schema else "unknown",
            "template_id": schema.get("id", 0) if schema else 0,
            "field_names": field_names,
            "canonical_fields": self._build_canonical_fields(extracted_fields, field_metadata) if field_metadata else {},
            "indexed_at": datetime.utcnow().isoformat()
        }

        all_text = " ".join(all_text_parts)

        if confidence_scores:
            confidence_values = list(confidence_scores.values())
            confidence_metrics = {
                "min_confidence": min(confidence_values),
                "max_confidence": max(confidence_values),
                "avg_confidence": sum(confidence_values) / len(confidence_values),
                "field_count": len(confidence_values),
                "verified_field_count": 0
            }
        else:
            confidence_metrics = {
                "min_confidence": 1.0,
                "max_confidence": 1.0,
                "avg_confidence": 1.0,
                "field_count": 0,
                "verified_field_count": 0
            }

        audit_threshold = 0.6
        low_confidence_fields = [
            field_name for field_name, conf in confidence_scores.items()
            if conf < audit_threshold
        ]

        citation_metadata = {
            "has_low_confidence_fields": len(low_confidence_fields) > 0,
            "low_confidence_field_names": low_confidence_fields,
            "audit_urls": {}
        }

        existing = self.db.query(DocumentSearchIndex).filter(
            DocumentSearchIndex.document_id == document_id
        ).first()

        if existing:
            existing.full_text = full_text
            existing.extracted_fields = extracted_fields
            existing.query_context = query_context
            existing.all_text = all_text
            existing.field_index = field_names
            existing.confidence_metrics = confidence_metrics
            existing.citation_metadata = citation_metadata
            existing.field_metadata = field_meta
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Updated document search index: {document_id}")
            return existing.id
        else:
            search_index = DocumentSearchIndex(
                document_id=document_id,
                full_text=full_text,
                extracted_fields=extracted_fields,
                query_context=query_context,
                all_text=all_text,
                field_index=field_names,
                confidence_metrics=confidence_metrics,
                citation_metadata=citation_metadata,
                field_metadata=field_meta
            )
            self.db.add(search_index)
            self.db.commit()
            self.db.refresh(search_index)
            logger.info(f"Indexed document: {document_id} (avg confidence: {confidence_metrics['avg_confidence']:.2f})")
            return search_index.id

    def _build_canonical_fields(
        self,
        extracted_fields: Dict[str, Any],
        field_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build comprehensive canonical field mapping for cross-template queries.
        """
        canonical = {}

        canonical_patterns = {
            "amount": ["total", "amount", "cost", "price", "value", "payment", "sum", "fee", "charge"],
            "date": ["date", "created", "when"],
            "start_date": ["start", "effective", "begin", "from"],
            "end_date": ["end", "expir", "terminat", "until", "to"],
            "entity_name": ["vendor", "supplier", "customer", "client", "company", "organization"],
            "identifier": ["number", "id", "reference", "ref", "code"],
            "status": ["status", "state", "condition"],
            "description": ["description", "notes", "comment", "memo", "detail"],
            "quantity": ["quantity", "qty", "count", "num"],
            "address": ["address", "location", "street", "city"],
            "contact": ["email", "phone", "contact"],
        }

        for field_name, field_value in extracted_fields.items():
            if field_value is None:
                continue

            field_lower = field_name.lower()

            for canonical_name, patterns in canonical_patterns.items():
                for pattern in patterns:
                    if pattern in field_lower:
                        if canonical_name not in canonical or field_lower.startswith(pattern):
                            canonical[canonical_name] = field_value
                            canonical[f"_original_{canonical_name}_field"] = field_name
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
        """
        Search documents with optional filters using PostgreSQL full-text search.
        
        Args:
            query: Text search query
            filters: Field filters
            min_confidence: Minimum confidence threshold
            custom_query: Custom SQL conditions (for NL search compatibility)
            page: Page number
            size: Results per page
        
        Returns:
            Search results with total count and documents
        """
        stmt = select(DocumentSearchIndex).join(Document)

        if custom_query:
            stmt = self._apply_custom_query(stmt, custom_query)
        else:
            if query:
                ts_query = func.plainto_tsquery('english', query)
                stmt = stmt.where(
                    DocumentSearchIndex.full_text_tsv.op('@@')(ts_query)
                ).order_by(
                    func.ts_rank(DocumentSearchIndex.full_text_tsv, ts_query).desc()
                )

            # Field filters
            if filters:
                for field, value in filters.items():
                    stmt = stmt.where(
                        DocumentSearchIndex.extracted_fields[field].astext == str(value)
                    )

            # Confidence filter
            if min_confidence is not None:
                stmt = stmt.where(
                    cast(DocumentSearchIndex.confidence_metrics['avg_confidence'].astext, Float) >= min_confidence
                )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar()

        offset = (page - 1) * size
        stmt = stmt.offset(offset).limit(size)

        results = self.db.execute(stmt).scalars().all()

        # Format results
        documents = []
        for result in results:
            doc_data = {
                "document_id": result.document_id,
                "filename": result.document.filename if result.document else "Unknown",
                "full_text": result.full_text,
                "confidence_scores": {
                    field: meta.get("confidence", 0.0)
                    for field, meta in result.field_metadata.items()
                },
                **result.extracted_fields,
                "_query_context": result.query_context,
                "_all_text": result.all_text,
                "_field_index": " ".join(result.field_index) if result.field_index else "",
                "_confidence_metrics": result.confidence_metrics,
                "_citation_metadata": result.citation_metadata
            }
            
            documents.append({
                "id": str(result.document_id),
                "score": 1.0,  # PostgreSQL doesn't provide scores in same way as ES
                "filename": doc_data["filename"],
                "data": doc_data,
                "highlights": {}
            })

        logger.info(f"Search completed: {total} total, returning {len(documents)} documents")

        return {
            "total": total,
            "page": page,
            "size": size,
            "documents": documents
        }

    def _apply_custom_query(self, stmt, custom_query: Dict[str, Any]):
        """
        Apply custom query conditions from NL search.
        Handles both legacy ES query format and new SQL conditions format.
        
        Args:
            stmt: SQLAlchemy select statement
            custom_query: Either {"query": {...}} (ES format) or {"where": "...", "order_by": "..."} (SQL format)
        
        Returns:
            Modified SQLAlchemy statement
        """
        if "where" in custom_query or "order_by" in custom_query:
            return self._apply_sql_conditions(stmt, custom_query)
        
        if "query" in custom_query:
            logger.warning("Received Elasticsearch query format - attempting to translate to SQL")
            return self._translate_es_query(stmt, custom_query.get("query", {}))
        
        logger.warning("Received raw Elasticsearch query - attempting to translate to SQL")
        return self._translate_es_query(stmt, custom_query)
    
    def _apply_sql_conditions(self, stmt, sql_conditions: Dict[str, Any]):
        """
        Apply SQL conditions from Claude's SQL generation.
        
        Args:
            sql_conditions: {"where": "...", "order_by": "...", "limit": 10}
        """
        where_clause = sql_conditions.get("where")
        order_by = sql_conditions.get("order_by")
        limit = sql_conditions.get("limit")
        
        if where_clause:
            stmt = stmt.where(text(where_clause))
        
        if order_by:
            stmt = stmt.order_by(text(order_by))
        
        if limit:
            stmt = stmt.limit(limit)
        
        return stmt
    
    def _translate_es_query(self, stmt, es_query: Dict[str, Any]):
        """
        Translate Elasticsearch query to SQLAlchemy (best effort).
        This is for backward compatibility during migration.
        """
        if not es_query:
            return stmt
        
        if "bool" in es_query:
            bool_query = es_query["bool"]
            
            if "must" in bool_query:
                for must_clause in bool_query["must"]:
                    stmt = self._translate_es_clause(stmt, must_clause)
            
            if "filter" in bool_query:
                filters = bool_query["filter"]
                if not isinstance(filters, list):
                    filters = [filters]
                for filter_clause in filters:
                    stmt = self._translate_es_clause(stmt, filter_clause)
            
            if "should" in bool_query:
                or_conditions = []
                for should_clause in bool_query["should"]:
                    stmt = self._translate_es_clause(stmt, should_clause)
                    break
        
        else:
            stmt = self._translate_es_clause(stmt, es_query)
        
        return stmt
    
    def _translate_es_clause(self, stmt, clause: Dict[str, Any]):
        """Translate a single ES clause to SQLAlchemy"""
        if "match" in clause:
            for field, value in clause["match"].items():
                if isinstance(value, dict):
                    query_text = value.get("query", "")
                else:
                    query_text = value
                
                if field == "full_text" or field == "_all_text":
                    ts_query = func.plainto_tsquery('english', query_text)
                    stmt = stmt.where(
                        DocumentSearchIndex.full_text_tsv.op('@@')(ts_query)
                    ).order_by(
                        func.ts_rank(DocumentSearchIndex.full_text_tsv, ts_query).desc()
                    )
        
        elif "multi_match" in clause:
            query_text = clause["multi_match"].get("query", "")
            ts_query = func.plainto_tsquery('english', query_text)
            stmt = stmt.where(
                or_(
                    DocumentSearchIndex.full_text_tsv.op('@@')(ts_query),
                    DocumentSearchIndex.all_text_tsv.op('@@')(ts_query)
                )
            ).order_by(
                func.ts_rank(DocumentSearchIndex.full_text_tsv, ts_query).desc()
            )
        
        elif "term" in clause:
            for field, value in clause["term"].items():
                if field.startswith("_query_context."):
                    context_field = field.replace("_query_context.", "").replace(".keyword", "")
                    stmt = stmt.where(
                        DocumentSearchIndex.query_context[context_field].astext == str(value)
                    )
                elif field == "folder_path.keyword" or field == "folder_path":
                    stmt = stmt.join(Document).where(
                        Document.folder_path.like(f"{value}%")
                    )
                else:
                    field_clean = field.replace(".keyword", "")
                    stmt = stmt.where(
                        DocumentSearchIndex.extracted_fields[field_clean].astext == str(value)
                    )
        
        elif "prefix" in clause:
            for field, value in clause["prefix"].items():
                if field == "folder_path.keyword" or field == "folder_path":
                    stmt = stmt.join(Document).where(
                        Document.folder_path.like(f"{value}%")
                    )
                else:
                    field_clean = field.replace(".keyword", "")
                    stmt = stmt.where(
                        DocumentSearchIndex.extracted_fields[field_clean].astext.like(f"{value}%")
                    )
        
        elif "range" in clause:
            for field, range_def in clause["range"].items():
                field_clean = field.replace(".keyword", "")
                field_expr = cast(
                    DocumentSearchIndex.extracted_fields[field_clean].astext,
                    Float
                )
                
                if "gte" in range_def:
                    stmt = stmt.where(field_expr >= range_def["gte"])
                if "lte" in range_def:
                    stmt = stmt.where(field_expr <= range_def["lte"])
                if "gt" in range_def:
                    stmt = stmt.where(field_expr > range_def["gt"])
                if "lt" in range_def:
                    stmt = stmt.where(field_expr < range_def["lt"])
        
        elif "exists" in clause:
            field = clause["exists"]["field"]
            stmt = stmt.where(
                DocumentSearchIndex.extracted_fields.has_key(field)
            )
        
        return stmt

    async def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        try:
            result = self.db.query(DocumentSearchIndex).filter(
                DocumentSearchIndex.document_id == document_id
            ).first()

            if not result:
                return None

            return {
                "document_id": result.document_id,
                "filename": result.document.filename if result.document else "Unknown",
                "full_text": result.full_text,
                "confidence_scores": {
                    field: meta.get("confidence", 0.0)
                    for field, meta in result.field_metadata.items()
                },
                **result.extracted_fields,
                "_query_context": result.query_context,
                "_all_text": result.all_text,
                "_field_index": " ".join(result.field_index) if result.field_index else "",
                "_confidence_metrics": result.confidence_metrics,
                "_citation_metadata": result.citation_metadata
            }

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
        
        result = self.db.query(DocumentSearchIndex).filter(
            DocumentSearchIndex.document_id == document_id
        ).first()

        if result:
            if "extracted_fields" in updated_fields:
                result.extracted_fields = updated_fields["extracted_fields"]
            
            for key, value in updated_fields.items():
                if key != "extracted_fields" and hasattr(result, key):
                    setattr(result, key, value)
            
            result.updated_at = datetime.utcnow()
            self.db.commit()

    async def delete_document(self, document_id: int) -> None:
        """Delete a document from search index"""
        try:
            logger.info(f"Deleting document from search index: {document_id}")
            self.db.query(DocumentSearchIndex).filter(
                DocumentSearchIndex.document_id == document_id
            ).delete()
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
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
        Get aggregations for analytics using SQL GROUP BY.
        
        Args:
            field: Field to aggregate
            agg_type: Type (terms, stats, date_histogram, range, cardinality)
            agg_config: Additional configuration
            filters: Optional query filters
            custom_aggs: Custom aggregation definition
        
        Returns:
            Aggregation results
        """
        if custom_aggs:
            logger.warning("Custom aggregations not yet fully implemented")
            return {}

        if not field:
            raise ValueError("field is required when custom_aggs is not provided")

        stmt = select(DocumentSearchIndex)

        if filters:
            stmt = self._apply_filters(stmt, filters)

        agg_name = f"{field}_{agg_type}"

        if agg_type == "terms":
            field_expr = DocumentSearchIndex.extracted_fields[field].astext
            agg_stmt = select(
                field_expr.label('key'),
                func.count().label('doc_count')
            ).select_from(stmt.subquery()).group_by(field_expr).order_by(
                func.count().desc()
            ).limit(agg_config.get('size', 100) if agg_config else 100)

            results = self.db.execute(agg_stmt).all()
            
            return {
                agg_name: {
                    "buckets": [
                        {"key": r.key, "doc_count": r.doc_count}
                        for r in results
                    ]
                }
            }

        elif agg_type == "stats":
            field_expr = cast(
                DocumentSearchIndex.extracted_fields[field].astext,
                Float
            )
            agg_stmt = select(
                func.count(field_expr).label('count'),
                func.sum(field_expr).label('sum'),
                func.avg(field_expr).label('avg'),
                func.min(field_expr).label('min'),
                func.max(field_expr).label('max')
            ).select_from(stmt.subquery())

            result = self.db.execute(agg_stmt).first()

            return {
                agg_name: {
                    "count": result.count or 0,
                    "sum": float(result.sum) if result.sum else 0.0,
                    "avg": float(result.avg) if result.avg else 0.0,
                    "min": float(result.min) if result.min else 0.0,
                    "max": float(result.max) if result.max else 0.0
                }
            }

        elif agg_type == "cardinality":
            field_expr = DocumentSearchIndex.extracted_fields[field].astext
            agg_stmt = select(
                func.count(func.distinct(field_expr)).label('value')
            ).select_from(stmt.subquery())

            result = self.db.execute(agg_stmt).scalar()

            return {
                agg_name: {
                    "value": result or 0
                }
            }

        else:
            logger.warning(f"Aggregation type '{agg_type}' not yet implemented")
            return {}

    def _apply_filters(self, stmt, filters: Dict[str, Any]):
        """Apply filters to query"""
        for field, value in filters.items():
            if isinstance(value, dict):
                # Range or complex filter
                for op, val in value.items():
                    if op == "gte":
                        stmt = stmt.where(
                            cast(DocumentSearchIndex.extracted_fields[field].astext, Float) >= val
                        )
                    elif op == "lte":
                        stmt = stmt.where(
                            cast(DocumentSearchIndex.extracted_fields[field].astext, Float) <= val
                        )
            else:
                # Term filter
                stmt = stmt.where(
                    DocumentSearchIndex.extracted_fields[field].astext == str(value)
                )
        return stmt

    async def get_multi_aggregations(
        self,
        aggregations: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple aggregations in a single query.
        
        Args:
            aggregations: List of aggregation definitions
            filters: Optional query filters
        
        Returns:
            Dictionary of aggregation results keyed by name
        """
        results = {}
        
        for agg_def in aggregations:
            name = agg_def["name"]
            field = agg_def["field"]
            agg_type = agg_def["type"]
            config = agg_def.get("config", {})

            try:
                agg_result = await self.get_aggregations(
                    field=field,
                    agg_type=agg_type,
                    agg_config=config,
                    filters=filters
                )
                
                agg_key = f"{field}_{agg_type}"
                if agg_key in agg_result:
                    results[name] = agg_result[agg_key]
                    
            except Exception as e:
                logger.error(f"Error executing aggregation '{name}': {e}")
                results[name] = {}

        return results

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
        """
        logger.warning("Nested aggregations not yet fully implemented in PostgreSQL service")
        return await self.get_aggregations(
            field=parent_agg["field"],
            agg_type=parent_agg["type"],
            agg_config=parent_agg.get("config", {}),
            filters=filters
        )

    async def health_check(self) -> bool:
        """Check PostgreSQL connection"""
        try:
            self.db.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    async def close(self):
        """Close database connection"""
        self.db.close()

    async def optimize_for_bulk_indexing(self, enable: bool = True):
        """
        Optimize for bulk indexing operations.
        In PostgreSQL, this could disable triggers or constraints temporarily.
        """
        if enable:
            logger.info("Optimizing for bulk indexing (PostgreSQL)")
        else:
            logger.info("Restoring normal indexing mode")

    async def refresh_index(self):
        """
        Refresh the index (PostgreSQL equivalent: VACUUM ANALYZE).
        """
        logger.info("Refreshing search index (VACUUM ANALYZE)")
        try:
            self.db.execute(text("VACUUM ANALYZE document_search_index"))
            self.db.execute(text("VACUUM ANALYZE template_signatures"))
        except Exception as e:
            logger.warning(f"Failed to vacuum tables: {e}")

    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics for monitoring.
        
        Returns:
            Dict with document count, storage size, field count, etc.
        """
        doc_count = self.db.query(func.count(DocumentSearchIndex.id)).scalar()

        size_query = text("""
            SELECT pg_total_relation_size('document_search_index') as size_bytes
        """)
        size_result = self.db.execute(size_query).first()
        size_bytes = size_result.size_bytes if size_result else 0

        return {
            "document_count": doc_count,
            "storage_size_bytes": size_bytes,
            "storage_size_mb": round(size_bytes / (1024 * 1024), 2),
            "field_count": 0,  # Dynamic in JSONB
            "field_limit": None,  # No limit in PostgreSQL
            "field_utilization_pct": 0
        }

    async def create_template_signatures_index(self) -> None:
        """
        Create template signatures table.
        In PostgreSQL, this is a no-op since tables are created via migrations.
        """
        logger.info("Template signatures table ready (created via migration)")

    async def index_template_signature(
        self,
        template_id: int,
        template_name: str,
        field_names: List[str],
        sample_text: str = "",
        category: str = "general"
    ) -> int:
        """
        Index a template signature for similarity matching.
        
        Args:
            template_id: Template ID
            template_name: Template name
            field_names: List of field names in template
            sample_text: Optional sample text
            category: Template category
        
        Returns:
            Template signature ID
        """
        existing = self.db.query(TemplateSignature).filter(
            TemplateSignature.template_id == template_id
        ).first()

        field_names_text = " ".join(field_names)

        if existing:
            existing.template_name = template_name
            existing.field_names = field_names
            existing.field_names_text = field_names_text
            existing.sample_text = sample_text[:5000] if sample_text else ""
            existing.category = category
            self.db.commit()
            logger.info(f"Updated template signature: {template_name} (ID: {template_id})")
            return existing.id
        else:
            signature = TemplateSignature(
                template_id=template_id,
                template_name=template_name,
                field_names=field_names,
                field_names_text=field_names_text,
                sample_text=sample_text[:5000] if sample_text else "",
                category=category
            )
            self.db.add(signature)
            self.db.commit()
            self.db.refresh(signature)
            logger.info(f"Indexed template signature: {template_name} (ID: {template_id})")
            return signature.id

    async def cluster_uploaded_documents(
        self,
        documents: List[Any],
        similarity_threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Cluster uploaded documents using Jaccard similarity.
        This uses the same Python implementation as Elasticsearch version.
        """
        if not documents:
            return []

        # Extract document text and metadata
        doc_data = []
        for doc in documents:
            parse_result = doc.actual_parse_result
            if not parse_result:
                logger.warning(f"Skipping document {doc.id} - no parse result")
                continue

            chunks = parse_result.get("chunks", [])
            doc_text = "\n".join([c.get("content", "") for c in chunks[:10]])

            doc_data.append({
                "id": doc.id,
                "filename": doc.filename,
                "text": doc_text[:5000]
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
            seed_id = next(iter(unclustered_ids))
            seed_doc = doc_lookup[seed_id]

            cluster_doc_ids = [seed_id]
            unclustered_ids.remove(seed_id)

            similar_ids = []
            total_similarity = 0.0

            for candidate_id in list(unclustered_ids):
                candidate_doc = doc_lookup[candidate_id]

                similarity = self._calculate_text_similarity(
                    seed_doc["text"],
                    candidate_doc["text"]
                )

                if similarity >= similarity_threshold:
                    cluster_doc_ids.append(candidate_id)
                    unclustered_ids.remove(candidate_id)
                    total_similarity += similarity

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
        Calculate Jaccard similarity on word sets.
        Same implementation as Elasticsearch version.
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
        words1 = {w for w in words1 if w not in stopwords and len(w) > 2}
        words2 = {w for w in words2 if w not in stopwords and len(w) > 2}

        if not words1 or not words2:
            return 0.0

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
        Find templates similar to a document using trigram similarity.
        
        Args:
            document_text: Document text content
            document_fields: List of field names extracted from document
            min_score: Minimum similarity score (0.0-1.0)
        
        Returns:
            List of matching templates with similarity scores
        """
        field_text = " ".join(document_fields)

        stmt = select(
            TemplateSignature,
            func.similarity(TemplateSignature.field_names_text, field_text).label('field_similarity'),
            func.similarity(TemplateSignature.sample_text, document_text[:5000]).label('text_similarity')
        ).where(
            func.similarity(TemplateSignature.field_names_text, field_text) > min_score
        ).order_by(
            text('field_similarity DESC')
        ).limit(5)

        try:
            results = self.db.execute(stmt).all()

            output = []
            for r in results:
                doc_fields_set = set(document_fields)
                template_fields_set = set(r.TemplateSignature.field_names)
                overlap = doc_fields_set.intersection(template_fields_set)

                combined_score = (r.field_similarity + r.text_similarity) / 2

                output.append({
                    "template_id": r.TemplateSignature.template_id,
                    "template_name": r.TemplateSignature.template_name,
                    "similarity_score": combined_score,
                    "matching_fields": list(overlap),
                    "match_count": len(overlap),
                    "total_fields": len(template_fields_set),
                    "all_template_fields": list(template_fields_set)
                })

            logger.info(f"Found {len(output)} similar templates for document")
            return output

        except Exception as e:
            logger.error(f"Error finding similar templates: {e}")
            return []
