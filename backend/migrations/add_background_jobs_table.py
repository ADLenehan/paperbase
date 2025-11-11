"""
Migration: Add background_jobs table

Creates the background_jobs table for tracking long-running field extraction tasks.

Usage:
    python migrations/add_background_jobs_table.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.models.background_job import BackgroundJob
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Create background_jobs table"""
    logger.info("Starting migration: add_background_jobs_table")

    # Create all tables (will only create missing ones)
    from app.core.database import Base
    Base.metadata.create_all(bind=engine)

    logger.info("✅ Migration completed: background_jobs table created")


def rollback_migration():
    """Drop background_jobs table"""
    logger.warning("Rolling back migration: add_background_jobs_table")

    db = SessionLocal()
    try:
        db.execute(text("DROP TABLE IF EXISTS background_jobs"))
        db.commit()
        logger.info("✅ Rollback completed: background_jobs table dropped")
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add background_jobs table")
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (drop table)"
    )
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()
