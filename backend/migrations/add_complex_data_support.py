"""
Database migration: Add support for complex data types (arrays, tables)

This migration adds:
1. field_type, field_value_json columns to extracted_fields table
2. complexity_score, auto_generation_confidence, complexity_warnings, generation_mode to schemas table
3. complexity_overrides table for tracking user overrides

Run with: python backend/migrations/add_complex_data_support.py
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
        # 1. Add new columns to extracted_fields table
        print("\n1. Adding columns to extracted_fields table...")

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(extracted_fields)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if "field_type" not in existing_columns:
            cursor.execute("""
                ALTER TABLE extracted_fields
                ADD COLUMN field_type VARCHAR DEFAULT 'text' NOT NULL
            """)
            print("   ✓ Added field_type column")
        else:
            print("   - field_type column already exists")

        if "field_value_json" not in existing_columns:
            cursor.execute("""
                ALTER TABLE extracted_fields
                ADD COLUMN field_value_json JSON
            """)
            print("   ✓ Added field_value_json column")
        else:
            print("   - field_value_json column already exists")

        if "verified_value_json" not in existing_columns:
            cursor.execute("""
                ALTER TABLE extracted_fields
                ADD COLUMN verified_value_json JSON
            """)
            print("   ✓ Added verified_value_json column")
        else:
            print("   - verified_value_json column already exists")

        # 2. Add complexity tracking columns to schemas table
        print("\n2. Adding complexity tracking to schemas table...")

        cursor.execute("PRAGMA table_info(schemas)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if "complexity_score" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN complexity_score INTEGER
            """)
            print("   ✓ Added complexity_score column")
        else:
            print("   - complexity_score column already exists")

        if "auto_generation_confidence" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN auto_generation_confidence FLOAT
            """)
            print("   ✓ Added auto_generation_confidence column")
        else:
            print("   - auto_generation_confidence column already exists")

        if "complexity_warnings" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN complexity_warnings JSON
            """)
            print("   ✓ Added complexity_warnings column")
        else:
            print("   - complexity_warnings column already exists")

        if "generation_mode" not in existing_columns:
            cursor.execute("""
                ALTER TABLE schemas
                ADD COLUMN generation_mode VARCHAR
            """)
            print("   ✓ Added generation_mode column")
        else:
            print("   - generation_mode column already exists")

        # 3. Create complexity_overrides table
        print("\n3. Creating complexity_overrides table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complexity_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_id INTEGER NOT NULL,
                document_id INTEGER,
                complexity_score INTEGER NOT NULL,
                recommended_action VARCHAR NOT NULL,
                user_action VARCHAR NOT NULL,
                override_reason VARCHAR,
                schema_accuracy FLOAT,
                user_corrections_count INTEGER DEFAULT 0,
                extraction_success BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (schema_id) REFERENCES schemas(id) ON DELETE CASCADE,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
            )
        """)
        print("   ✓ Created complexity_overrides table")

        # 4. Create indexes for performance
        print("\n4. Creating indexes...")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_extracted_fields_type
            ON extracted_fields(field_type)
        """)
        print("   ✓ Created index on extracted_fields.field_type")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schemas_complexity
            ON schemas(complexity_score)
        """)
        print("   ✓ Created index on schemas.complexity_score")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_complexity_overrides_schema
            ON complexity_overrides(schema_id)
        """)
        print("   ✓ Created index on complexity_overrides.schema_id")

        # Commit changes
        conn.commit()
        print("\n✅ Migration completed successfully!")

        # Print summary
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print("\nAdded to extracted_fields:")
        print("  - field_type (VARCHAR) - Type of field: text, array, table, etc.")
        print("  - field_value_json (JSON) - For complex data structures")
        print("  - verified_value_json (JSON) - For verified complex data")
        print("\nAdded to schemas:")
        print("  - complexity_score (INTEGER) - 0-100+ complexity rating")
        print("  - auto_generation_confidence (FLOAT) - Claude confidence 0.0-1.0")
        print("  - complexity_warnings (JSON) - List of warning strings")
        print("  - generation_mode (VARCHAR) - auto/assisted/manual")
        print("\nNew table:")
        print("  - complexity_overrides - Track user overrides for analytics")
        print("\n" + "="*60)

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise

    finally:
        conn.close()


def rollback():
    """Rollback the migration (for development only)"""
    db_path = os.environ.get("DATABASE_URL", "sqlite:///./paperbase.db").replace("sqlite:///", "")

    print(f"Rolling back migration from: {db_path}")
    print("⚠️  WARNING: This will drop columns and tables!")

    response = input("Are you sure? (yes/no): ")
    if response.lower() != "yes":
        print("Rollback cancelled")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # SQLite doesn't support DROP COLUMN, so we'd need to recreate tables
        # For now, just drop the complexity_overrides table
        print("\nDropping complexity_overrides table...")
        cursor.execute("DROP TABLE IF EXISTS complexity_overrides")

        conn.commit()
        print("✅ Rollback completed (partial - new columns remain)")
        print("   Note: SQLite doesn't support DROP COLUMN")
        print("   New columns in extracted_fields and schemas will remain but unused")

    except Exception as e:
        conn.rollback()
        print(f"❌ Rollback failed: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()
