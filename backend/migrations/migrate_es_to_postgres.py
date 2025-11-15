"""
Data migration script: Elasticsearch → PostgreSQL

Migrates all indexed documents from Elasticsearch to PostgreSQL search tables.

Run with: python -m migrations.migrate_es_to_postgres
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.services.elastic_service import ElasticsearchService
from app.services.postgres_service import PostgresService


async def migrate_documents(batch_size: int = 100):
    """
    Migrate all documents from Elasticsearch to PostgreSQL.
    
    Args:
        batch_size: Number of documents to process per batch
    """
    es_service = ElasticsearchService()
    db: Session = SessionLocal()
    pg_service = PostgresService(db)
    
    try:
        print("Starting document migration from Elasticsearch to PostgreSQL...")
        print(f"Batch size: {batch_size}")
        
        page = 1
        total_migrated = 0
        errors = 0
        
        while True:
            print(f"\nFetching batch {page}...")
            
            try:
                results = await es_service.search(
                    query=None,
                    filters=None,
                    page=page,
                    size=batch_size
                )
            except Exception as e:
                print(f"Error fetching from Elasticsearch: {e}")
                break
            
            documents = results.get("documents", [])
            
            if not documents:
                print("No more documents to migrate")
                break
            
            print(f"Processing {len(documents)} documents...")
            
            for doc in documents:
                try:
                    doc_data = doc.get("data", {})
                    document_id = int(doc.get("id"))
                    
                    extracted_fields = {}
                    confidence_scores = doc_data.get("confidence_scores", {})
                    
                    for key, value in doc_data.items():
                        if not key.startswith("_") and key not in [
                            "document_id", "filename", "full_text", 
                            "uploaded_at", "processed_at", "confidence_scores"
                        ]:
                            extracted_fields[key] = value
                    
                    await pg_service.index_document(
                        document_id=document_id,
                        filename=doc_data.get("filename", "Unknown"),
                        extracted_fields=extracted_fields,
                        confidence_scores=confidence_scores,
                        full_text=doc_data.get("full_text", ""),
                        schema=None,  # Will be loaded from DB if needed
                        field_metadata=None
                    )
                    
                    total_migrated += 1
                    
                    if total_migrated % 10 == 0:
                        print(f"  Migrated {total_migrated} documents...")
                    
                except Exception as e:
                    print(f"  Error migrating document {doc.get('id')}: {e}")
                    errors += 1
            
            page += 1
        
        print(f"\n{'=' * 60}")
        print(f"Migration Summary:")
        print(f"  Total migrated: {total_migrated}")
        print(f"  Errors: {errors}")
        print(f"{'=' * 60}")
        
        if errors > 0:
            print(f"\n⚠️  {errors} documents failed to migrate")
        else:
            print("\n✅ All documents migrated successfully!")
        
    finally:
        await es_service.close()
        db.close()


async def migrate_template_signatures():
    """
    Migrate template signatures from Elasticsearch to PostgreSQL.
    """
    es_service = ElasticsearchService()
    db: Session = SessionLocal()
    pg_service = PostgresService(db)
    
    try:
        print("\nMigrating template signatures...")
        
        try:
            response = await es_service.client.search(
                index=es_service.template_signatures_index,
                size=1000,
                query={"match_all": {}}
            )
        except Exception as e:
            print(f"Error fetching template signatures: {e}")
            print("Skipping template signature migration")
            return
        
        hits = response.get("hits", {}).get("hits", [])
        print(f"Found {len(hits)} template signatures")
        
        migrated = 0
        for hit in hits:
            source = hit["_source"]
            
            try:
                await pg_service.index_template_signature(
                    template_id=source["template_id"],
                    template_name=source["template_name"],
                    field_names=source["field_names"],
                    sample_text=source.get("sample_text", ""),
                    category=source.get("category", "general")
                )
                migrated += 1
            except Exception as e:
                print(f"  Error migrating template {source.get('template_name')}: {e}")
        
        print(f"✅ Migrated {migrated} template signatures")
        
    finally:
        await es_service.close()
        db.close()


async def verify_migration():
    """
    Verify the migration by comparing counts.
    """
    es_service = ElasticsearchService()
    db: Session = SessionLocal()
    pg_service = PostgresService(db)
    
    try:
        print("\nVerifying migration...")
        
        try:
            es_results = await es_service.search(query=None, page=1, size=1)
            es_count = es_results.get("total", 0)
        except Exception as e:
            print(f"Could not get ES count: {e}")
            es_count = "unknown"
        
        pg_stats = await pg_service.get_index_stats()
        pg_count = pg_stats.get("document_count", 0)
        
        print(f"\nDocument counts:")
        print(f"  Elasticsearch: {es_count}")
        print(f"  PostgreSQL: {pg_count}")
        
        if es_count != "unknown" and es_count == pg_count:
            print("✅ Counts match!")
        elif es_count != "unknown":
            print(f"⚠️  Count mismatch: {abs(es_count - pg_count)} documents difference")
        
    finally:
        await es_service.close()
        db.close()


async def main():
    """Run the migration"""
    print("=" * 60)
    print("Elasticsearch → PostgreSQL Data Migration")
    print("=" * 60)
    
    if "postgresql" not in str(engine.url):
        print("\n⚠️  WARNING: Not using PostgreSQL!")
        print(f"Current database: {engine.url}")
        print("\nThis migration requires PostgreSQL.")
        print("Update DATABASE_URL in .env to use PostgreSQL:")
        print("  DATABASE_URL=postgresql://user:password@localhost:5432/paperbase")
        return
    
    try:
        await migrate_documents(batch_size=100)
        
        await migrate_template_signatures()
        
        await verify_migration()
        
        print("\n" + "=" * 60)
        print("✅ Data migration completed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Test search functionality with PostgreSQL")
        print("2. Update application code to use PostgresService")
        print("3. Once verified, you can remove Elasticsearch")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
