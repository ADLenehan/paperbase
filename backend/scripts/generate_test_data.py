#!/usr/bin/env python3
"""
Generate test documents with intentionally low-confidence extractions
for testing/demoing the inline audit workflow.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from datetime import datetime

def generate_test_data():
    """Create 5 test documents with low-confidence fields"""
    db = SessionLocal()
    
    try:
        # Get or create a test schema
        schema = db.query(Schema).filter(Schema.name == "Test Invoices").first()
        if not schema:
            schema = Schema(
                name="Test Invoices",
                description="Test schema for audit workflow",
                fields={
                    "invoice_number": {"type": "text", "required": True},
                    "vendor_name": {"type": "text", "required": True},
                    "total_amount": {"type": "number", "required": True},
                    "invoice_date": {"type": "date", "required": True},
                    "payment_terms": {"type": "text", "required": False}
                },
                created_at=datetime.utcnow()
            )
            db.add(schema)
            db.commit()
        
        # Create 5 test documents
        test_docs = [
            {
                "filename": "invoice_test_001.pdf",
                "fields": {
                    "invoice_number": ("INV-2024-001", 0.95),
                    "vendor_name": ("Acme Corporation", 0.42),
                    "total_amount": ("1234.56", 0.58),
                    "invoice_date": ("2024-01-15", 0.88),
                    "payment_terms": ("Net 30", 0.35)
                }
            },
            {
                "filename": "invoice_test_002.pdf",
                "fields": {
                    "invoice_number": ("INV-2024-002", 0.92),
                    "vendor_name": ("TechSupply Inc", 0.51),
                    "total_amount": ("2845.99", 0.45),
                    "invoice_date": ("2024-01-20", 0.91),
                    "payment_terms": ("Net 45", 0.89)
                }
            },
            {
                "filename": "invoice_test_003.pdf",
                "fields": {
                    "invoice_number": ("INV-2024-003", 0.88),
                    "vendor_name": ("Global Services LLC", 0.38),
                    "total_amount": ("567.80", 0.55),
                    "invoice_date": ("2024-02-01", 0.82),
                    "payment_terms": ("Due on receipt", 0.48)
                }
            },
            {
                "filename": "invoice_test_004.pdf",
                "fields": {
                    "invoice_number": ("INV-2024-004", 0.95),
                    "vendor_name": ("MegaCorp Industries", 0.44),
                    "total_amount": ("8921.34", 0.39),
                    "invoice_date": ("2024-02-10", 0.93),
                    "payment_terms": ("Net 60", 0.92)
                }
            },
            {
                "filename": "invoice_test_005.pdf",
                "fields": {
                    "invoice_number": ("INV-2024-005", 0.90),
                    "vendor_name": ("StartupCo", 0.52),
                    "total_amount": ("4567.12", 0.47),
                    "invoice_date": ("2024-02-15", 0.85),
                    "payment_terms": ("Net 30", 0.41)
                }
            }
        ]
        
        created_count = 0
        for doc_data in test_docs:
            doc = Document(
                filename=doc_data["filename"],
                file_path=f"/test/documents/{doc_data['filename']}",
                schema_id=schema.id,
                status="completed",
                created_at=datetime.utcnow(),
                parsed_at=datetime.utcnow(),
                extracted_at=datetime.utcnow()
            )
            db.add(doc)
            db.flush()
            
            for field_name, (field_value, confidence) in doc_data["fields"].items():
                extracted_field = ExtractedField(
                    document_id=doc.id,
                    field_name=field_name,
                    field_value=field_value,
                    confidence_score=confidence,
                    verified=False,
                    source_page=1,
                    source_bbox=[100, 100, 200, 120] if confidence < 0.6 else None,
                    created_at=datetime.utcnow()
                )
                db.add(extracted_field)
            
            created_count += 1
        
        db.commit()
        print(f"✅ Created {created_count} test documents with low-confidence fields")
        print(f"📊 Expected audit queue items: ~15-18 fields")
        print(f"🔗 Test: curl http://localhost:8000/api/audit/queue")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_test_data()
