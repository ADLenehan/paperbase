#!/usr/bin/env python3
"""
Fix document 75 extraction by re-running with the cached parse result.
This uses the jobid:// pipeline to avoid re-parsing.
"""

import asyncio
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.document import Document, ExtractedField
from app.models.physical_file import PhysicalFile
from app.models.schema import Schema
from app.services.reducto_service import ReductoService
from app.services.elastic_service import ElasticsearchService
from app.core.config import settings

# Database setup
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


async def fix_document_75():
    """Re-extract document 75 using cached parse result."""
    db = SessionLocal()
    try:
        # Get document
        doc = db.query(Document).filter(Document.id == 75).first()
        if not doc:
            print("❌ Document 75 not found")
            return False

        print(f"📄 Document: {doc.filename}")
        print(f"   Schema ID: {doc.schema_id}")
        print(f"   Status: {doc.status}")
        print(f"   Physical File ID: {doc.physical_file_id}")

        # Get physical file with cached parse
        if not doc.physical_file:
            print("❌ No PhysicalFile found")
            return False

        physical_file = doc.physical_file
        print(f"\n📦 PhysicalFile:")
        print(f"   Job ID: {physical_file.reducto_job_id}")
        print(f"   Has parse result: {bool(physical_file.reducto_parse_result)}")

        if not physical_file.reducto_job_id:
            print("❌ No job_id available for pipelining")
            return False

        # Get schema
        schema = db.query(Schema).filter(Schema.id == doc.schema_id).first()
        if not schema:
            print(f"❌ Schema {doc.schema_id} not found")
            return False

        print(f"\n📋 Schema: {schema.name}")
        print(f"   Fields: {len(schema.fields)}")
        for field in schema.fields:
            print(f"   - {field['name']} ({field.get('type', 'text')})")

        # Initialize services
        reducto_service = ReductoService()
        es_service = ElasticsearchService()

        # Try with fresh parse first (job_id might be expired)
        print(f"\n🔄 Re-parsing and extracting from file...")

        try:
            # Parse the document first
            print(f"   Parsing: {physical_file.file_path}")
            parse_result = await reducto_service.parse_document(physical_file.file_path)
            new_job_id = parse_result.get("job_id")
            print(f"   ✅ Parsed! New job_id: {new_job_id}")

            # Extract using fresh parse
            extraction_result = await reducto_service.extract_structured(
                schema={"fields": schema.fields},
                job_id=new_job_id
            )

            extractions = extraction_result.get("extractions", {})
            print(f"\n✅ Extraction successful!")
            print(f"   Fields extracted: {len(extractions)}")

            if not extractions:
                print("   ⚠️  WARNING: No fields were extracted!")
                print(f"   Extraction result: {extraction_result}")
                return False

            # Build extracted data and confidence scores
            extracted_data = {}
            confidence_scores = {}

            for field_name, field_data in extractions.items():
                value = field_data.get("value")
                confidence = field_data.get("confidence", 0.85)

                extracted_data[field_name] = value
                confidence_scores[field_name] = confidence

                # Show what was extracted
                value_preview = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
                print(f"   - {field_name}: {value_preview} (confidence: {confidence:.3f})")

            # Update document
            doc.error_message = None  # Clear error

            # Delete old ExtractedField records
            db.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()

            # Create ExtractedField records for audit queue
            print(f"\n📝 Creating ExtractedField records...")
            for field_name, field_data in extractions.items():
                value = field_data.get("value")
                confidence = field_data.get("confidence", 0.85)
                field_type = field_data.get("field_type", "text")
                source_page = field_data.get("source_page")
                source_bbox = field_data.get("source_bbox")

                # Determine if it's a simple or complex type
                is_complex = field_type in ["array", "array_of_objects", "table"]

                extracted_field = ExtractedField(
                    document_id=doc.id,
                    field_name=field_name,
                    field_value=None if is_complex else str(value),
                    field_value_json=value if is_complex else None,
                    field_type=field_type,
                    confidence_score=confidence,
                    needs_verification=confidence < 0.6,  # Mark low confidence for audit
                    verified=False,
                    source_page=source_page,
                    source_bbox=source_bbox
                )
                db.add(extracted_field)
                print(f"  - {field_name}: needs_verification={confidence < 0.6}")

            # Index in Elasticsearch
            print(f"\n📊 Indexing in Elasticsearch...")

            # Get full text from parse result
            full_text = ""
            if physical_file.reducto_parse_result:
                import json
                parse_result = physical_file.reducto_parse_result
                if isinstance(parse_result, str):
                    parse_result = json.loads(parse_result)
                chunks = parse_result.get("chunks", [])
                full_text = " ".join([c.get("content", "") for c in chunks])

            await es_service.index_document(
                document_id=doc.id,
                filename=doc.filename,
                extracted_fields=extracted_data,
                confidence_scores=confidence_scores,
                full_text=full_text,
                schema={"name": schema.name, "fields": schema.fields}
            )

            db.commit()
            print(f"✅ Document 75 fixed successfully!")

            # Show low confidence fields
            low_conf_fields = [
                (name, score) for name, score in confidence_scores.items()
                if score < 0.6
            ]

            if low_conf_fields:
                print(f"\n⚠️  Low confidence fields (will appear in audit queue):")
                for name, score in low_conf_fields:
                    print(f"   - {name}: {score:.3f}")
            else:
                print(f"\n✅ All fields have confidence ≥ 0.6 (won't appear in audit queue)")

            return True

        except Exception as e:
            print(f"❌ Extraction failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Fixing Document 75 Extraction\n")
    print("=" * 60)

    result = asyncio.run(fix_document_75())

    print("\n" + "=" * 60)
    if result:
        print("✅ SUCCESS - Document 75 has been fixed!")
        print("\nNext steps:")
        print("1. Check /api/audit/queue to see if any fields need review")
        print("2. View document in Audit page")
        print("3. Search for the document to test queries")
    else:
        print("❌ FAILED - See errors above")

    sys.exit(0 if result else 1)
