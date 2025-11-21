#!/usr/bin/env python3
"""
Fix document indexing issues after PostgreSQL migration.

Issues fixed:
1. Documents with schema_id=null → link to actual schemas
2. Search index with template_name="unknown" → update to real schema names
3. Update document status from "analyzing" to "completed"
"""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.document import Document
from app.models.schema import Schema
from app.models.search_index import DocumentSearchIndex

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fix_document_indexing():
    """Fix document indexing issues."""

    # Create database connection
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Get all schemas
        schemas = db.query(Schema).all()
        logger.info(f"Found {len(schemas)} schemas")

        # Get all documents
        documents = db.query(Document).all()
        logger.info(f"Found {len(documents)} documents")

        # Get all search index entries
        search_indices = db.query(DocumentSearchIndex).all()
        logger.info(f"Found {len(search_indices)} search index entries")

        fixed_count = 0

        for search_idx in search_indices:
            # Get the document
            doc = db.query(Document).filter(Document.id == search_idx.document_id).first()
            if not doc:
                logger.warning(f"Document {search_idx.document_id} not found for search index {search_idx.id}")
                continue

            # Check if document has schema_id
            if doc.schema_id:
                # Get the schema
                schema = db.query(Schema).filter(Schema.id == doc.schema_id).first()
                if schema:
                    # Update search index with correct template name
                    query_context = search_idx.query_context or {}
                    old_template_name = query_context.get("template_name", "unknown")
                    new_template_name = schema.name.strip()  # Remove trailing spaces

                    if old_template_name != new_template_name:
                        logger.info(f"Updating document {doc.id}: '{old_template_name}' → '{new_template_name}'")
                        query_context["template_name"] = new_template_name
                        query_context["template_id"] = schema.id
                        # Mark as modified so SQLAlchemy knows to update the JSONB column
                        from sqlalchemy.orm.attributes import flag_modified
                        search_idx.query_context = query_context
                        flag_modified(search_idx, "query_context")
                        fixed_count += 1

                    # Update document status if needed
                    if doc.status in ["analyzing", "pending"]:
                        logger.info(f"Updating document {doc.id} status: {doc.status} → completed")
                        doc.status = "completed"
            else:
                logger.warning(f"Document {doc.id} ({doc.filename}) has no schema_id - skipping")

        # Commit changes
        db.commit()
        logger.info(f"✅ Fixed {fixed_count} document indices")

        # Show summary
        logger.info("\n" + "="*50)
        logger.info("SUMMARY:")
        logger.info("="*50)

        # Count documents by status
        status_counts = {}
        for doc in documents:
            status_counts[doc.status] = status_counts.get(doc.status, 0) + 1

        logger.info(f"Documents by status:")
        for status, count in sorted(status_counts.items()):
            logger.info(f"  {status}: {count}")

        # Count search indices by template
        template_counts = {}
        for search_idx in db.query(DocumentSearchIndex).all():
            query_context = search_idx.query_context or {}
            template_name = query_context.get("template_name", "unknown")
            template_counts[template_name] = template_counts.get(template_name, 0) + 1

        logger.info(f"\nSearch indices by template:")
        for template, count in sorted(template_counts.items()):
            logger.info(f"  {template}: {count}")

    except Exception as e:
        logger.error(f"Error fixing document indexing: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_document_indexing()
