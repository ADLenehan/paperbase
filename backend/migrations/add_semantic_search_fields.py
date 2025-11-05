"""
Database migration: Add semantic search guidance fields to schemas table

This migration adds template-level search guidance fields:
1. description: What this template extracts (e.g., "Marketing one-sheets for cloud products")
2. search_hints: List of concepts covered by extracted fields
3. not_extracted: List of concepts NOT in fields, requiring full_text search

These fields help Claude route queries to the right search strategy (field-specific vs full-text).

Run with: python backend/migrations/add_semantic_search_fields.py
"""

import sqlite3
import os
from datetime import datetime


def migrate():
    """Run the migration"""
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./paperbase.db").replace("sqlite:///", "")

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add semantic search guidance columns to schemas table
        print("\nAdding semantic search fields to schemas table...")

        cursor.execute("PRAGMA table_info(schemas)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if "description" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN description VARCHAR
            """)
            print("   ✓ Added description column")
        else:
            print("   - description column already exists")

        if "search_hints" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN search_hints JSON
            """)
            print("   ✓ Added search_hints column")
        else:
            print("   - search_hints column already exists")

        if "not_extracted" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN not_extracted JSON
            """)
            print("   ✓ Added not_extracted column")
        else:
            print("   - not_extracted column already exists")

        conn.commit()
        print("\n✅ Migration completed successfully!")

        # Optionally populate example data for existing schemas
        print("\n📝 Note: You can populate these fields for existing schemas with:")
        print("   UPDATE schemas SET")
        print("     description = 'Description of what this template extracts',")
        print("     search_hints = '[\"concept1\", \"concept2\"]',")
        print("     not_extracted = '[\"concept3\", \"concept4\"]'")
        print("   WHERE name = 'Your Template Name';")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def rollback():
    """Rollback the migration (optional)"""
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./paperbase.db").replace("sqlite:///", "")

    print(f"Rolling back migration...")
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # SQLite doesn't support DROP COLUMN directly in older versions
        # You would need to create new table, copy data, drop old, rename new
        print("\n⚠️  SQLite doesn't support DROP COLUMN easily.")
        print("To rollback, you would need to:")
        print("1. Create new schemas table without these columns")
        print("2. Copy data from old table")
        print("3. Drop old table")
        print("4. Rename new table")
        print("\nSince these columns are nullable, they won't break existing code.")
        print("It's safe to leave them in place.")

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
