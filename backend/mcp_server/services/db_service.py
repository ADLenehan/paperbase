"""
Database Service for MCP Server

Provides async database access with connection pooling,
query optimization, and result formatting for MCP responses.
"""

from sqlalchemy import create_engine, select, func, and_, or_, desc
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.core.database import Base
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.verification import Verification
from mcp_server.config import config
from mcp_server.services.cache_service import cached, cache_service

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Async database service for MCP server operations.

    Provides optimized queries for documents, templates, extractions,
    and analytics with automatic caching and result pagination.
    """

    def __init__(self):
        """Initialize database connection"""
        # Convert sqlite:/// to sqlite+aiosqlite:/// for async support
        db_url = config.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

        self.engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=config.SQLITE_POOL_SIZE,
            pool_pre_ping=True
        )

        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        logger.info(f"Database service initialized: {db_url}")

    async def get_session(self) -> AsyncSession:
        """Get database session"""
        return self.async_session()

    @cached(category="documents", key_prefix="doc")
    async def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get document by ID with all extracted fields and metadata

        Args:
            document_id: Document ID

        Returns:
            Document dict with extracted fields, confidence scores, and metadata
        """
        async with self.async_session() as session:
            # Query with eager loading
            stmt = (
                select(Document)
                .options(
                    joinedload(Document.extracted_fields),
                    joinedload(Document.schema),
                    joinedload(Document.suggested_template)
                )
                .where(Document.id == document_id)
            )

            result = await session.execute(stmt)
            doc = result.scalars().first()

            if not doc:
                return None

            # Format for MCP response (token-efficient)
            return {
                "id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "template": {
                    "id": doc.schema.id if doc.schema else None,
                    "name": doc.schema.name if doc.schema else None
                },
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "fields": [
                    {
                        "name": field.field_name,
                        "value": field.field_value,
                        "confidence": field.confidence_score,
                        "verified": field.verified,
                        "needs_verification": field.needs_verification
                    }
                    for field in doc.extracted_fields
                ],
                "error": doc.error_message
            }

    async def search_documents(
        self,
        query: Optional[str] = None,
        template_id: Optional[int] = None,
        status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search documents with filters

        Args:
            query: Text search in filename
            template_id: Filter by template
            status: Filter by status
            min_confidence: Minimum confidence threshold
            date_from: Start date filter
            date_to: End date filter
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (results, total_count)
        """
        async with self.async_session() as session:
            # Build query
            stmt = select(Document).options(
                joinedload(Document.schema),
                joinedload(Document.extracted_fields)
            )

            # Apply filters
            conditions = []

            if query:
                conditions.append(Document.filename.contains(query))

            if template_id:
                conditions.append(Document.schema_id == template_id)

            if status:
                conditions.append(Document.status == status)

            if date_from:
                conditions.append(Document.uploaded_at >= date_from)

            if date_to:
                conditions.append(Document.uploaded_at <= date_to)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # Get total count
            count_stmt = select(func.count()).select_from(Document)
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))
            total_result = await session.execute(count_stmt)
            total_count = total_result.scalar()

            # Apply pagination
            stmt = stmt.order_by(desc(Document.uploaded_at)).limit(limit).offset(offset)

            result = await session.execute(stmt)
            docs = result.scalars().all()

            # Format results (optimized for MCP)
            formatted_docs = []
            for doc in docs:
                # Calculate average confidence
                if doc.extracted_fields:
                    confidences = [f.confidence_score for f in doc.extracted_fields if f.confidence_score]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
                else:
                    avg_confidence = 0.0

                # Apply min_confidence filter if specified
                if min_confidence and avg_confidence < min_confidence:
                    continue

                formatted_docs.append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "status": doc.status,
                    "template": doc.schema.name if doc.schema else None,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "avg_confidence": round(avg_confidence, 3),
                    "field_count": len(doc.extracted_fields)
                })

            return formatted_docs, total_count

    @cached(category="templates", key_prefix="templates_list")
    async def get_all_templates(self) -> List[Dict[str, Any]]:
        """
        Get all templates with field definitions

        Returns:
            List of templates with fields
        """
        async with self.async_session() as session:
            stmt = select(Schema).order_by(Schema.name)
            result = await session.execute(stmt)
            templates = result.scalars().all()

            return [
                {
                    "id": template.id,
                    "name": template.name,
                    "fields": template.fields,
                    "created_at": template.created_at.isoformat()
                }
                for template in templates
            ]

    @cached(category="templates", key_prefix="template")
    async def get_template(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Get template by ID with usage statistics"""
        async with self.async_session() as session:
            # Get template
            stmt = select(Schema).where(Schema.id == template_id)
            result = await session.execute(stmt)
            template = result.scalars().first()

            if not template:
                return None

            # Get usage stats
            doc_count_stmt = select(func.count()).select_from(Document).where(
                Document.schema_id == template_id
            )
            doc_count_result = await session.execute(doc_count_stmt)
            doc_count = doc_count_result.scalar()

            # Get average confidence for this template
            avg_confidence_stmt = select(func.avg(ExtractedField.confidence_score)).where(
                ExtractedField.document_id.in_(
                    select(Document.id).where(Document.schema_id == template_id)
                )
            )
            avg_confidence_result = await session.execute(avg_confidence_stmt)
            avg_confidence = avg_confidence_result.scalar() or 0.0

            return {
                "id": template.id,
                "name": template.name,
                "fields": template.fields,
                "created_at": template.created_at.isoformat(),
                "stats": {
                    "document_count": doc_count,
                    "avg_confidence": round(avg_confidence, 3)
                }
            }

    @cached(category="stats", key_prefix="audit_queue")
    async def get_audit_queue(
        self,
        confidence_threshold: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get fields needing verification (low confidence or flagged)

        Args:
            confidence_threshold: Max confidence for inclusion (default from settings)
            limit: Max results

        Returns:
            List of fields needing review with document context
        """
        if confidence_threshold is None:
            confidence_threshold = 0.6  # Default from settings

        async with self.async_session() as session:
            stmt = (
                select(ExtractedField)
                .options(joinedload(ExtractedField.document))
                .where(
                    and_(
                        ExtractedField.verified == False,
                        or_(
                            ExtractedField.confidence_score < confidence_threshold,
                            ExtractedField.needs_verification == True
                        )
                    )
                )
                .order_by(ExtractedField.confidence_score.asc())
                .limit(limit)
            )

            result = await session.execute(stmt)
            fields = result.scalars().all()

            return [
                {
                    "field_id": field.id,
                    "document_id": field.document.id,
                    "filename": field.document.filename,
                    "field_name": field.field_name,
                    "field_value": field.field_value,
                    "confidence": round(field.confidence_score, 3) if field.confidence_score else 0.0,
                    "extracted_at": field.extracted_at.isoformat() if field.extracted_at else None
                }
                for field in fields
            ]

    @cached(category="stats", key_prefix="daily_stats")
    async def get_daily_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get processing statistics for recent days

        Args:
            days: Number of days to include

        Returns:
            Stats including upload counts, confidence distribution, status breakdown
        """
        async with self.async_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Total documents
            total_stmt = select(func.count()).select_from(Document).where(
                Document.uploaded_at >= cutoff_date
            )
            total_result = await session.execute(total_stmt)
            total_docs = total_result.scalar()

            # By status
            status_stmt = (
                select(Document.status, func.count())
                .where(Document.uploaded_at >= cutoff_date)
                .group_by(Document.status)
            )
            status_result = await session.execute(status_stmt)
            status_counts = {status: count for status, count in status_result}

            # Average confidence
            avg_confidence_stmt = select(func.avg(ExtractedField.confidence_score)).where(
                ExtractedField.document_id.in_(
                    select(Document.id).where(Document.uploaded_at >= cutoff_date)
                )
            )
            avg_confidence_result = await session.execute(avg_confidence_stmt)
            avg_confidence = avg_confidence_result.scalar() or 0.0

            # Verification rate
            total_fields_stmt = select(func.count()).select_from(ExtractedField).where(
                ExtractedField.document_id.in_(
                    select(Document.id).where(Document.uploaded_at >= cutoff_date)
                )
            )
            total_fields_result = await session.execute(total_fields_stmt)
            total_fields = total_fields_result.scalar()

            verified_fields_stmt = select(func.count()).select_from(ExtractedField).where(
                and_(
                    ExtractedField.verified == True,
                    ExtractedField.document_id.in_(
                        select(Document.id).where(Document.uploaded_at >= cutoff_date)
                    )
                )
            )
            verified_fields_result = await session.execute(verified_fields_stmt)
            verified_fields = verified_fields_result.scalar()

            verification_rate = (verified_fields / total_fields * 100) if total_fields > 0 else 0.0

            return {
                "period_days": days,
                "total_documents": total_docs,
                "status_breakdown": status_counts,
                "avg_confidence": round(avg_confidence, 3),
                "total_fields": total_fields,
                "verified_fields": verified_fields,
                "verification_rate": round(verification_rate, 1)
            }

    async def close(self):
        """Close database connections"""
        await self.engine.dispose()
        logger.info("Database connections closed")


# Global database service instance
db_service = DatabaseService()
