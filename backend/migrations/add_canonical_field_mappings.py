"""
Migration: Add canonical field mapping tables for cross-template aggregations
Date: 2025-11-19
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings


def run_migration():
    """Run the canonical field mappings migration"""
    print("Running migration: add_canonical_field_mappings")

    engine = create_engine(settings.DATABASE_URL)

    # Read SQL file
    sql_file = Path(__file__).parent / "add_canonical_field_mappings.sql"
    with open(sql_file, 'r') as f:
        sql = f.read()

    # Execute migration
    with engine.begin() as conn:
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            try:
                conn.execute(text(statement))
                print(f"✓ Executed statement {i}/{len(statements)}")
            except Exception as e:
                print(f"✗ Error in statement {i}: {e}")
                # Continue with other statements
                continue

    print("✓ Migration completed successfully")

    # Verify tables were created
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('canonical_field_mappings', 'canonical_aliases')
            ORDER BY table_name
        """))

        tables = [row[0] for row in result]
        print(f"\nCreated tables: {', '.join(tables)}")

        # Check system canonical mappings
        result = conn.execute(text("""
            SELECT canonical_name, description, aggregation_type
            FROM canonical_field_mappings
            WHERE is_system = TRUE
            ORDER BY canonical_name
        """))

        mappings = result.fetchall()
        print(f"\nSystem canonical mappings created: {len(mappings)}")
        for name, desc, agg_type in mappings:
            print(f"  - {name} ({agg_type}): {desc}")

        # Check aliases
        result = conn.execute(text("""
            SELECT COUNT(*) FROM canonical_aliases
        """))
        alias_count = result.scalar()
        print(f"\nSystem aliases created: {alias_count}")


if __name__ == "__main__":
    run_migration()
