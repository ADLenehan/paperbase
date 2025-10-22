"""
Migration script to convert existing Document records to PhysicalFile + Extraction model.

This migration is backwards-compatible and can be run on a live system.

Usage:
    python -m app.migrations.migrate_to_extractions
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import SessionLocal, engine, Base
from app.models.document import Document, ExtractedField
from app.models.physical_file import PhysicalFile
from app.models.extraction import Extraction
from app.models.batch import Batch
from app.utils.hashing import calculate_file_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def infer_template_from_schema(schema_id: int, db: Session) -> int:
    """
    Infer template_id from schema by looking for matching template name.
    Falls back to first template if no match found.
    """
    from app.models.schema import Schema
    from app.models.template import SchemaTemplate

    if not schema_id:
        # Return first available template as fallback
        template = db.query(SchemaTemplate).first()
        return template.id if template else None

    schema = db.query(Schema).get(schema_id)
    if not schema:
        return None

    # Try to find template with matching name
    template = db.query(SchemaTemplate).filter(
        SchemaTemplate.name == schema.name
    ).first()

    if template:
        return template.id

    # Fallback to first template
    template = db.query(SchemaTemplate).first()
    return template.id if template else None


def generate_organized_path(doc: Document, template_id: int, db: Session) -> str:
    """
    Generate virtual folder path for an extraction.
    Format: {template_name}/{YYYY-MM-DD}/{filename}
    """
    from app.models.template import SchemaTemplate

    if not template_id:
        return f"Unmatched/{doc.filename}"

    template = db.query(SchemaTemplate).get(template_id)
    if not template:
        return f"Unmatched/{doc.filename}"

    # Use upload date for folder organization
    date_folder = doc.uploaded_at.strftime("%Y-%m-%d")
    return f"{template.name}/{date_folder}/{doc.filename}"


def migrate_documents_to_extractions(db: Session, dry_run: bool = False):
    """
    Migrate existing Document records to PhysicalFile + Extraction model.

    Args:
        db: Database session
        dry_run: If True, don't commit changes (for testing)
    """
    documents = db.query(Document).all()
    logger.info(f"Found {len(documents)} documents to migrate")

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for doc in documents:
        try:
            # 1. Create or find PhysicalFile
            if not doc.file_path:
                logger.warning(f"Document {doc.id} has no file_path, skipping")
                skipped_count += 1
                continue

            # Calculate file hash (or use placeholder if file doesn't exist)
            try:
                file_hash = calculate_file_hash(doc.file_path)
            except FileNotFoundError:
                logger.warning(f"File not found: {doc.file_path}, using placeholder hash")
                file_hash = f"missing_{doc.id}_{doc.filename}"

            # Check if PhysicalFile already exists
            physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

            if not physical_file:
                physical_file = PhysicalFile(
                    filename=doc.filename,
                    file_hash=file_hash,
                    file_path=doc.file_path,
                    reducto_job_id=doc.reducto_job_id,
                    reducto_parse_result=doc.reducto_parse_result,
                    uploaded_at=doc.uploaded_at
                )
                db.add(physical_file)
                db.flush()
                logger.info(f"Created PhysicalFile: {physical_file.filename} (hash: {file_hash[:8]}...)")

            # 2. Determine template_id
            template_id = doc.suggested_template_id
            if not template_id and doc.schema_id:
                template_id = infer_template_from_schema(doc.schema_id, db)

            # 3. Generate organized path
            organized_path = generate_organized_path(doc, template_id, db)

            # 4. Create Extraction
            extraction = Extraction(
                physical_file_id=physical_file.id,
                template_id=template_id,
                schema_id=doc.schema_id,
                status=doc.status,
                template_confidence=doc.template_confidence,
                organized_path=organized_path,
                elasticsearch_id=doc.elasticsearch_id,
                created_at=doc.uploaded_at,
                processed_at=doc.processed_at,
                error_message=doc.error_message
            )
            db.add(extraction)
            db.flush()

            # 5. Update ExtractedField references
            fields_updated = 0
            for field in doc.extracted_fields:
                field.extraction_id = extraction.id
                fields_updated += 1

            if not dry_run:
                db.commit()

            logger.info(
                f"✓ Migrated Document #{doc.id} → Extraction #{extraction.id} "
                f"({fields_updated} fields) - {organized_path}"
            )
            migrated_count += 1

        except Exception as e:
            logger.error(f"Error migrating document {doc.id}: {e}")
            db.rollback()
            error_count += 1

    logger.info("=" * 60)
    logger.info(f"Migration complete!")
    logger.info(f"  Migrated: {migrated_count}")
    logger.info(f"  Skipped:  {skipped_count}")
    logger.info(f"  Errors:   {error_count}")
    logger.info(f"  Dry run:  {dry_run}")
    logger.info("=" * 60)

    return migrated_count, skipped_count, error_count


def rollback_migration(db: Session):
    """
    Rollback migration by deleting all PhysicalFile and Extraction records
    and clearing extraction_id from ExtractedFields.
    """
    logger.warning("Rolling back migration...")

    # Clear extraction_id from extracted fields
    extracted_fields = db.query(ExtractedField).filter(
        ExtractedField.extraction_id.isnot(None)
    ).all()

    for field in extracted_fields:
        field.extraction_id = None

    # Delete extractions (this will cascade to batch_extractions)
    extraction_count = db.query(Extraction).count()
    db.query(Extraction).delete()

    # Delete physical files
    file_count = db.query(PhysicalFile).count()
    db.query(PhysicalFile).delete()

    # Delete batches
    batch_count = db.query(Batch).count()
    db.query(Batch).delete()

    db.commit()

    logger.info(f"Rollback complete:")
    logger.info(f"  Deleted {extraction_count} extractions")
    logger.info(f"  Deleted {file_count} physical files")
    logger.info(f"  Deleted {batch_count} batches")
    logger.info(f"  Cleared extraction_id from {len(extracted_fields)} fields")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate documents to extraction model")
    parser.add_argument("--dry-run", action="store_true", help="Test migration without committing")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")
    parser.add_argument("--create-tables", action="store_true", help="Create new tables first")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.create_tables:
            logger.info("Creating new tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Tables created successfully")

        if args.rollback:
            rollback_migration(db)
        else:
            migrate_documents_to_extractions(db, dry_run=args.dry_run)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
