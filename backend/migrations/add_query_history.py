"""
Migration: Add QueryHistory Table

Creates the query_history table for tracking AI-generated answers
and their source documents.

This enables the "View Source Documents" feature where users can
see which documents were used to generate a specific answer.

Run with: python migrations/add_query_history.py
"""

import sys
import os
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import create_engine, text
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add query_history table to database"""

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Check if table already exists (works for both SQLite and PostgreSQL)
        if settings.DATABASE_URL.startswith("postgresql"):
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'query_history'
                )
            """))
        else:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='query_history'
            """))

        if result.fetchone()[0]:
            logger.info("✓ query_history table already exists")
            return

        # Create query_history table
        logger.info("Creating query_history table...")

        if settings.DATABASE_URL.startswith("postgresql"):
            conn.execute(text("""
                CREATE TABLE query_history (
                    id VARCHAR PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    query_source VARCHAR NOT NULL,
                    document_ids JSONB NOT NULL,
                    answer TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE query_history (
                    id TEXT PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    query_source TEXT NOT NULL,
                    document_ids TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP
                )
            """))

        # Create indexes for performance
        conn.execute(text("""
            CREATE INDEX idx_query_history_created_at
            ON query_history(created_at)
        """))

        conn.execute(text("""
            CREATE INDEX idx_query_history_query_text
            ON query_history(query_text)
        """))

        conn.commit()

        logger.info("✓ Created query_history table with indexes")
        logger.info("✓ Migration complete!")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
