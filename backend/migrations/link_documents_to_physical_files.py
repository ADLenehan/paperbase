"""
Migration: Link existing Documents to PhysicalFiles

This migration:
1. Finds all Documents without physical_file_id
2. Calculates SHA256 hash for each document's file
3. Creates or reuses PhysicalFile based on hash
4. Links Document → PhysicalFile
5. Migrates parse cache from Document to PhysicalFile

Usage:
    # Dry run (shows what will happen)
    python -m migrations.link_documents_to_physical_files --dry-run

    # Actual migration
    python -m migrations.link_documents_to_physical_files

    # Force re-migration (even if already linked)
    python -m migrations.link_documents_to_physical_files --force
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.physical_file import PhysicalFile
from app.utils.hashing import calculate_file_hash
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def migrate_documents_to_physical_files(db: Session, dry_run: bool = False, force: bool = False):
    """
    Migrate existing Documents to use PhysicalFile deduplication.

    Args:
        db: Database session
        dry_run: If True, only show what would happen without making changes
        force: If True, re-migrate even if physical_file_id already set
    """

    # Get documents to migrate
    if force:
        documents = db.query(Document).all()
        logger.info(f"Force mode: Processing all {len(documents)} documents")
    else:
        documents = db.query(Document).filter(Document.physical_file_id == None).all()
        logger.info(f"Found {len(documents)} documents without physical_file_id")

    if not documents:
        logger.info("✓ No documents to migrate")
        return

    stats = {
        "total": len(documents),
        "linked_existing": 0,
        "created_new": 0,
        "missing_files": 0,
        "errors": 0
    }

    # Track PhysicalFiles by hash
    physical_files_by_hash = {}

    # Load existing PhysicalFiles into cache
    existing_pfs = db.query(PhysicalFile).all()
    for pf in existing_pfs:
        physical_files_by_hash[pf.file_hash] = pf
    logger.info(f"Loaded {len(existing_pfs)} existing PhysicalFiles into cache")

    for idx, doc in enumerate(documents, 1):
        logger.info(f"\n[{idx}/{len(documents)}] Processing Document #{doc.id}: {doc.filename}")

        try:
            # Check if file exists
            if not doc.file_path or not os.path.exists(doc.file_path):
                logger.warning(f"  ⚠️  File not found: {doc.file_path}")
                stats["missing_files"] += 1

                # Create placeholder PhysicalFile for missing files
                placeholder_hash = f"missing_{doc.id}_{doc.filename}"

                if placeholder_hash in physical_files_by_hash:
                    physical_file = physical_files_by_hash[placeholder_hash]
                    logger.info(f"  ✓ Reusing placeholder PhysicalFile #{physical_file.id}")
                    stats["linked_existing"] += 1
                else:
                    if not dry_run:
                        physical_file = PhysicalFile(
                            filename=doc.filename,
                            file_hash=placeholder_hash,
                            file_path=doc.file_path or f"missing/{doc.filename}",
                            file_size=0,
                            mime_type=None,
                            reducto_job_id=doc.reducto_job_id,
                            reducto_parse_result=doc.reducto_parse_result,
                            uploaded_at=doc.uploaded_at
                        )
                        db.add(physical_file)
                        db.flush()
                        physical_files_by_hash[placeholder_hash] = physical_file
                        logger.info(f"  ✓ Created placeholder PhysicalFile #{physical_file.id}")
                    else:
                        logger.info(f"  [DRY RUN] Would create placeholder PhysicalFile")
                    stats["created_new"] += 1

            else:
                # Calculate hash
                file_hash = calculate_file_hash(doc.file_path)
                file_size = os.path.getsize(doc.file_path)
                logger.info(f"  Hash: {file_hash[:16]}... ({file_size} bytes)")

                # Find or create PhysicalFile
                if file_hash in physical_files_by_hash:
                    physical_file = physical_files_by_hash[file_hash]
                    logger.info(f"  ✓ Found existing PhysicalFile #{physical_file.id}")
                    stats["linked_existing"] += 1

                    # Merge parse cache if needed
                    if not physical_file.reducto_parse_result and doc.reducto_parse_result:
                        if not dry_run:
                            physical_file.reducto_job_id = doc.reducto_job_id
                            physical_file.reducto_parse_result = doc.reducto_parse_result
                            logger.info(f"  ✓ Copied parse cache to PhysicalFile")
                        else:
                            logger.info(f"  [DRY RUN] Would copy parse cache to PhysicalFile")

                else:
                    if not dry_run:
                        physical_file = PhysicalFile(
                            filename=doc.filename,
                            file_hash=file_hash,
                            file_path=doc.file_path,
                            file_size=file_size,
                            mime_type=None,  # Could detect from file extension
                            reducto_job_id=doc.reducto_job_id,
                            reducto_parse_result=doc.reducto_parse_result,
                            uploaded_at=doc.uploaded_at
                        )
                        db.add(physical_file)
                        db.flush()
                        physical_files_by_hash[file_hash] = physical_file
                        logger.info(f"  ✓ Created PhysicalFile #{physical_file.id}")
                    else:
                        logger.info(f"  [DRY RUN] Would create PhysicalFile")
                    stats["created_new"] += 1

            # Link Document to PhysicalFile
            if not dry_run:
                doc.physical_file_id = physical_file.id
                logger.info(f"  ✓ Linked Document → PhysicalFile #{physical_file.id}")
            else:
                logger.info(f"  [DRY RUN] Would link Document → PhysicalFile")

        except Exception as e:
            logger.error(f"  ✗ Error processing Document #{doc.id}: {e}")
            stats["errors"] += 1

    # Commit changes
    if not dry_run:
        db.commit()
        logger.info("\n✓ Migration committed to database")
    else:
        logger.info("\n[DRY RUN] No changes made to database")

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("MIGRATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total documents:          {stats['total']}")
    logger.info(f"Linked to existing PF:    {stats['linked_existing']}")
    logger.info(f"Created new PF:           {stats['created_new']}")
    logger.info(f"Missing files:            {stats['missing_files']}")
    logger.info(f"Errors:                   {stats['errors']}")
    logger.info(f"{'='*60}")

    if stats["linked_existing"] > stats["created_new"]:
        dedup_savings = stats["linked_existing"]
        logger.info(f"\n✓ Deduplication saved {dedup_savings} file copies!")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate Documents to PhysicalFile deduplication")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--force", action="store_true", help="Re-migrate all documents (even if already linked)")
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("DOCUMENT → PHYSICALFILE MIGRATION")
    logger.info("="*60)

    if args.dry_run:
        logger.info("MODE: DRY RUN (no changes will be made)")
    else:
        logger.info("MODE: LIVE MIGRATION (changes will be saved)")

    if args.force:
        logger.info("FORCE: Re-migrating all documents")

    logger.info("")

    db = SessionLocal()
    try:
        migrate_documents_to_physical_files(db, dry_run=args.dry_run, force=args.force)
    finally:
        db.close()

    logger.info("\n✓ Migration complete")


if __name__ == "__main__":
    main()
