"""
Add validation metadata to extracted_fields table

This migration adds columns to track validation status and errors for each extracted field.
Validation results are used to enrich the audit queue with priority information.

Revision ID: add_validation_metadata
Created: 2025-11-05
"""

from sqlalchemy import Column, String, JSON, DateTime, text
from sqlalchemy.sql import table, column
from datetime import datetime


def upgrade(op, sa):
    """Add validation metadata columns to extracted_fields table"""

    # Add validation status column (valid, warning, error)
    op.add_column(
        'extracted_fields',
        sa.Column('validation_status', sa.String(), nullable=True, server_default='valid')
    )

    # Add validation errors column (JSON array of error messages)
    op.add_column(
        'extracted_fields',
        sa.Column('validation_errors', sa.JSON(), nullable=True)
    )

    # Add timestamp for when validation was checked
    op.add_column(
        'extracted_fields',
        sa.Column('validation_checked_at', sa.DateTime(), nullable=True)
    )

    # Backfill existing rows with "valid" status
    extracted_fields = table('extracted_fields',
        column('validation_status', String)
    )
    op.execute(
        extracted_fields.update().values(validation_status='valid')
    )

    print("✅ Added validation metadata columns to extracted_fields")
    print("   - validation_status (valid/warning/error)")
    print("   - validation_errors (JSON array)")
    print("   - validation_checked_at (timestamp)")


def downgrade(op, sa):
    """Remove validation metadata columns"""

    op.drop_column('extracted_fields', 'validation_checked_at')
    op.drop_column('extracted_fields', 'validation_errors')
    op.drop_column('extracted_fields', 'validation_status')

    print("⚠️  Removed validation metadata columns from extracted_fields")


# Standalone execution for manual migration
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/adlenehan/Projects/paperbase/backend')

    from app.core.database import engine
    from sqlalchemy import MetaData
    import sqlalchemy as sa

    print("Running migration: add_validation_metadata")
    print("=" * 50)

    # Create a simple operation executor
    class Op:
        def add_column(self, table_name, column):
            with engine.begin() as conn:
                conn.execute(text(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN {column.name} {column.type.compile(engine.dialect)}
                    {'DEFAULT ' + column.server_default.arg if column.server_default else ''}
                """))
                print(f"✅ Added column {table_name}.{column.name}")

        def drop_column(self, table_name, column_name):
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))
                print(f"⚠️  Dropped column {table_name}.{column_name}")

        def execute(self, statement):
            with engine.begin() as conn:
                conn.execute(statement)

    op = Op()

    # Run upgrade
    try:
        upgrade(op, sa)
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
