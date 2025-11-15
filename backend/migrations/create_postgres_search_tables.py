"""
Database migration to create PostgreSQL search tables.
This replaces Elasticsearch indexes with PostgreSQL tables.

Run with: python -m migrations.create_postgres_search_tables
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.database import engine, Base
from app.models.search_index import DocumentSearchIndex, TemplateSignature


def create_extensions():
    """Create required PostgreSQL extensions"""
    print("Creating PostgreSQL extensions...")
    
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        print("✓ Created pg_trgm extension")
        
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gin"))
        print("✓ Created btree_gin extension")
        
        conn.commit()


def create_tables():
    """Create search index tables"""
    print("\nCreating search index tables...")
    
    Base.metadata.create_all(bind=engine, tables=[
        DocumentSearchIndex.__table__,
        TemplateSignature.__table__
    ])
    print("✓ Created document_search_index table")
    print("✓ Created template_signatures table")


def create_generated_columns():
    """Create generated tsvector columns"""
    print("\nCreating generated tsvector columns...")
    
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE document_search_index 
            ADD COLUMN IF NOT EXISTS full_text_tsv tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', COALESCE(full_text, ''))) STORED
        """))
        print("✓ Created full_text_tsv column")
        
        conn.execute(text("""
            ALTER TABLE document_search_index 
            ADD COLUMN IF NOT EXISTS all_text_tsv tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', COALESCE(all_text, ''))) STORED
        """))
        print("✓ Created all_text_tsv column")
        
        conn.execute(text("""
            ALTER TABLE template_signatures 
            ADD COLUMN IF NOT EXISTS field_names_tsv tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', COALESCE(field_names_text, ''))) STORED
        """))
        print("✓ Created field_names_tsv column")
        
        conn.execute(text("""
            ALTER TABLE template_signatures 
            ADD COLUMN IF NOT EXISTS sample_text_tsv tsvector 
            GENERATED ALWAYS AS (to_tsvector('english', COALESCE(sample_text, ''))) STORED
        """))
        print("✓ Created sample_text_tsv column")
        
        conn.commit()


def create_trigger_function():
    """Create trigger function for updated_at"""
    print("\nCreating trigger function...")
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        print("✓ Created update_updated_at_column() function")
        
        conn.execute(text("""
            DROP TRIGGER IF EXISTS update_document_search_index_updated_at 
            ON document_search_index
        """))
        
        conn.execute(text("""
            CREATE TRIGGER update_document_search_index_updated_at
                BEFORE UPDATE ON document_search_index
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
        """))
        print("✓ Created trigger on document_search_index")
        
        conn.commit()


def verify_setup():
    """Verify the setup"""
    print("\nVerifying setup...")
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT extname FROM pg_extension 
            WHERE extname IN ('pg_trgm', 'btree_gin')
        """))
        extensions = [row[0] for row in result]
        print(f"✓ Extensions installed: {', '.join(extensions)}")
        
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('document_search_index', 'template_signatures')
        """))
        tables = [row[0] for row in result]
        print(f"✓ Tables created: {', '.join(tables)}")
        
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('document_search_index', 'template_signatures')
        """))
        indexes = [row[0] for row in result]
        print(f"✓ Indexes created: {len(indexes)} indexes")


def main():
    """Run the migration"""
    print("=" * 60)
    print("PostgreSQL Search Tables Migration")
    print("=" * 60)
    
    try:
        if "postgresql" not in str(engine.url):
            print("\n⚠️  WARNING: Not using PostgreSQL!")
            print(f"Current database: {engine.url}")
            print("\nThis migration requires PostgreSQL.")
            print("Update DATABASE_URL in .env to use PostgreSQL:")
            print("  DATABASE_URL=postgresql://user:password@localhost:5432/paperbase")
            return
        
        create_extensions()
        create_tables()
        create_generated_columns()
        create_trigger_function()
        verify_setup()
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run data migration: python -m migrations.migrate_es_to_postgres")
        print("2. Update application to use PostgresService")
        print("3. Test search functionality")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
