"""
Database migration: Add pipeline optimization fields

Run this to update existing database:
    python backend/migrations/add_pipeline_fields.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, SessionLocal


def migrate():
    """Add pipeline fields to documents table"""

    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("PRAGMA table_info(documents)"))
        columns = [row[1] for row in result]

        if 'reducto_job_id' not in columns:
            print("Adding reducto_job_id column...")
            conn.execute(text("ALTER TABLE documents ADD COLUMN reducto_job_id VARCHAR"))
            conn.commit()
            print("✓ Added reducto_job_id")
        else:
            print("✓ reducto_job_id already exists")

        if 'reducto_parse_result' not in columns:
            print("Adding reducto_parse_result column...")
            conn.execute(text("ALTER TABLE documents ADD COLUMN reducto_parse_result JSON"))
            conn.commit()
            print("✓ Added reducto_parse_result")
        else:
            print("✓ reducto_parse_result already exists")

    print("\n✅ Migration complete!")


def rollback():
    """Remove pipeline fields (SQLite doesn't support DROP COLUMN easily)"""
    print("⚠️  SQLite doesn't support DROP COLUMN.")
    print("To rollback, you'll need to recreate the table or use a fresh database.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
