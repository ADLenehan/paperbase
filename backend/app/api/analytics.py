import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.verification import Verification

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Get dashboard metrics"""

    # Total documents processed
    total_documents = db.query(Document).count()
    completed_documents = db.query(Document).filter(
        Document.status == "completed"
    ).count()
    processing_documents = db.query(Document).filter(
        Document.status == "processing"
    ).count()
    error_documents = db.query(Document).filter(
        Document.status == "error"
    ).count()

    # Average confidence by field
    avg_confidence = db.query(
        ExtractedField.field_name,
        func.avg(ExtractedField.confidence_score).label("avg_confidence")
    ).group_by(ExtractedField.field_name).all()

    # Verification queue size
    queue_size = db.query(ExtractedField).filter(
        ExtractedField.needs_verification == True,
        ExtractedField.verified == False
    ).count()

    # Processing time stats (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_docs = db.query(Document).filter(
        Document.processed_at >= yesterday,
        Document.processed_at.isnot(None),
        Document.uploaded_at.isnot(None)
    ).all()

    processing_times = []
    for doc in recent_docs:
        if doc.processed_at and doc.uploaded_at:
            time_diff = (doc.processed_at - doc.uploaded_at).total_seconds()
            processing_times.append(time_diff)

    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0

    # Error rate
    error_rate = (error_documents / total_documents * 100) if total_documents > 0 else 0

    # Verification accuracy
    total_verifications = db.query(Verification).count()
    correct_verifications = db.query(Verification).filter(
        Verification.verification_type == "correct"
    ).count()
    accuracy = (correct_verifications / total_verifications * 100) if total_verifications > 0 else 0

    return {
        "documents": {
            "total": total_documents,
            "completed": completed_documents,
            "processing": processing_documents,
            "errors": error_documents
        },
        "confidence": {
            "by_field": [
                {
                    "field": field_name,
                    "average": round(avg, 3)
                }
                for field_name, avg in avg_confidence
            ]
        },
        "verification": {
            "queue_size": queue_size,
            "total_verified": total_verifications,
            "accuracy": round(accuracy, 2)
        },
        "processing": {
            "avg_time_seconds": round(avg_processing_time, 2),
            "error_rate": round(error_rate, 2)
        }
    }


@router.get("/schemas")
async def get_schema_stats(db: Session = Depends(get_db)):
    """Get statistics for each schema"""

    schemas = db.query(Schema).all()
    stats = []

    for schema in schemas:
        doc_count = db.query(Document).filter(
            Document.schema_id == schema.id
        ).count()

        completed_count = db.query(Document).filter(
            Document.schema_id == schema.id,
            Document.status == "completed"
        ).count()

        avg_confidence = db.query(
            func.avg(ExtractedField.confidence_score)
        ).join(Document).filter(
            Document.schema_id == schema.id
        ).scalar()

        stats.append({
            "schema_id": schema.id,
            "schema_name": schema.name,
            "document_count": doc_count,
            "completed_count": completed_count,
            "average_confidence": round(avg_confidence or 0, 3),
            "field_count": len(schema.fields)
        })

    return {"schemas": stats}


@router.get("/trends")
async def get_trends(days: int = 7, db: Session = Depends(get_db)):
    """Get processing trends over time"""

    start_date = datetime.utcnow() - timedelta(days=days)

    # Documents processed per day
    docs_by_day = db.query(
        func.date(Document.processed_at).label("date"),
        func.count(Document.id).label("count")
    ).filter(
        Document.processed_at >= start_date,
        Document.processed_at.isnot(None)
    ).group_by(func.date(Document.processed_at)).all()

    # Confidence trends
    confidence_by_day = db.query(
        func.date(ExtractedField.extracted_at).label("date"),
        func.avg(ExtractedField.confidence_score).label("avg_confidence")
    ).filter(
        ExtractedField.extracted_at >= start_date
    ).group_by(func.date(ExtractedField.extracted_at)).all()

    return {
        "documents_processed": [
            {
                "date": str(date),
                "count": count
            }
            for date, count in docs_by_day
        ],
        "confidence_trend": [
            {
                "date": str(date),
                "average": round(avg, 3)
            }
            for date, avg in confidence_by_day
        ]
    }
