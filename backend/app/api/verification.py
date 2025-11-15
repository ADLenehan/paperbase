import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document, ExtractedField
from app.models.verification import Verification, VerificationSession
from app.services.elastic_service import ElasticsearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/verification", tags=["verification"])


@router.get("/queue")
async def get_verification_queue(
    schema_id: Optional[int] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    """Get items that need verification (low confidence)"""

    query = db.query(ExtractedField).filter(
        and_(
            ExtractedField.needs_verification == True,
            ExtractedField.verified == False
        )
    )

    if schema_id:
        query = query.join(Document).filter(Document.schema_id == schema_id)

    # Order by confidence (lowest first)
    query = query.order_by(ExtractedField.confidence_score.asc())

    # Pagination
    offset = (page - 1) * size
    total = query.count()
    items = query.offset(offset).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "id": item.id,
                "document_id": item.document_id,
                "field_name": item.field_name,
                "field_value": item.field_value,
                "confidence_score": item.confidence_score,
                "source_page": item.source_page,
                "document_filename": item.document.filename
            }
            for item in items
        ]
    }


@router.post("/verify")
async def verify_field(
    field_id: int,
    verification_data: dict,
    db: Session = Depends(get_db)
):
    """
    Verify an extracted field

    Args:
        field_id: ID of extracted field
        verification_data: {
            "verified_value": "...",
            "verification_type": "correct|incorrect|not_found|custom",
            "session_id": "...",
            "notes": "..."
        }
    """

    field = db.query(ExtractedField).filter(ExtractedField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    # Create verification record
    verification = Verification(
        extracted_field_id=field.id,
        original_value=field.field_value,
        original_confidence=field.confidence_score,
        verified_value=verification_data.get("verified_value"),
        verification_type=verification_data.get("verification_type"),
        session_id=verification_data.get("session_id"),
        reviewer_notes=verification_data.get("notes")
    )
    db.add(verification)

    # Update extracted field
    field.verified = True
    field.verified_value = verification_data.get("verified_value")
    field.verified_at = datetime.utcnow()

    # Update Elasticsearch
    elastic_service = ElasticsearchService()
    await elastic_service.update_document(
        document_id=field.document_id,
        updated_fields={
            field.field_name: verification_data.get("verified_value")
        }
    )

    # Update session stats if provided
    session_id = verification_data.get("session_id")
    if session_id:
        session = db.query(VerificationSession).filter(
            VerificationSession.session_id == session_id
        ).first()

        if session:
            session.completed_items += 1
            if verification_data.get("verification_type") == "correct":
                session.correct_count += 1
            else:
                session.incorrect_count += 1

    db.commit()

    # Get next item in queue
    next_item = db.query(ExtractedField).filter(
        and_(
            ExtractedField.needs_verification == True,
            ExtractedField.verified == False
        )
    ).order_by(ExtractedField.confidence_score.asc()).first()

    next_item_data = None
    if next_item:
        next_item_data = {
            "id": next_item.id,
            "document_id": next_item.document_id,
            "field_name": next_item.field_name,
            "field_value": next_item.field_value,
            "confidence_score": next_item.confidence_score,
            "source_page": next_item.source_page
        }

    return {
        "success": True,
        "message": "Field verified successfully",
        "next_item": next_item_data
    }


@router.get("/stats")
async def get_verification_stats(
    schema_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get verification statistics"""

    # Count items needing verification
    queue_query = db.query(ExtractedField).filter(
        and_(
            ExtractedField.needs_verification == True,
            ExtractedField.verified == False
        )
    )

    if schema_id:
        queue_query = queue_query.join(Document).filter(Document.schema_id == schema_id)

    queue_count = queue_query.count()

    # Count verified items
    verified_query = db.query(ExtractedField).filter(ExtractedField.verified == True)

    if schema_id:
        verified_query = verified_query.join(Document).filter(Document.schema_id == schema_id)

    verified_count = verified_query.count()

    # Get recent sessions
    recent_sessions = db.query(VerificationSession).order_by(
        VerificationSession.started_at.desc()
    ).limit(5).all()

    return {
        "queue_count": queue_count,
        "verified_count": verified_count,
        "total_items": queue_count + verified_count,
        "recent_sessions": [
            {
                "session_id": session.session_id,
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "total_items": session.total_items,
                "completed_items": session.completed_items,
                "correct_count": session.correct_count,
                "incorrect_count": session.incorrect_count
            }
            for session in recent_sessions
        ]
    }


@router.post("/sessions")
async def create_verification_session(
    schema_id: int,
    db: Session = Depends(get_db)
):
    """Create a new verification session"""

    session_id = str(uuid.uuid4())

    # Count items to verify
    total_items = db.query(ExtractedField).filter(
        and_(
            ExtractedField.needs_verification == True,
            ExtractedField.verified == False
        )
    ).join(Document).filter(Document.schema_id == schema_id).count()

    session = VerificationSession(
        session_id=session_id,
        schema_id=schema_id,
        total_items=total_items
    )
    db.add(session)
    db.commit()

    return {
        "session_id": session_id,
        "total_items": total_items
    }


@router.put("/sessions/{session_id}/complete")
async def complete_verification_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Mark verification session as complete"""

    session = db.query(VerificationSession).filter(
        VerificationSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.completed_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "session": {
            "session_id": session.session_id,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "total_items": session.total_items,
            "completed_items": session.completed_items,
            "accuracy": session.correct_count / session.completed_items if session.completed_items > 0 else 0
        }
    }
