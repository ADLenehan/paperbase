from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional, List
from app.core.database import get_db
from app.core.config import settings as app_settings
from app.models.document import Document, ExtractedField
from app.models.verification import Verification
from app.services.elastic_service import ElasticsearchService
from app.services.settings_service import SettingsService
from datetime import datetime
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditFieldResponse(BaseModel):
    """Response model for audit queue items"""
    field_id: int
    document_id: int
    filename: str
    file_path: str
    template_name: Optional[str]
    field_name: str
    field_value: Optional[str]
    confidence: float
    source_page: Optional[int]
    source_bbox: Optional[List[float]]


class VerifyFieldRequest(BaseModel):
    """Request model for field verification"""
    field_id: int
    action: str  # "correct", "incorrect", "not_found"
    corrected_value: Optional[str] = None
    notes: Optional[str] = None


@router.get("/queue")
async def get_audit_queue(
    template_id: Optional[int] = Query(None, description="Filter by template ID"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Max confidence threshold (uses settings default if not provided)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    count_only: bool = Query(False, description="Return only count"),
    db: Session = Depends(get_db)
):
    """
    Get audit queue of low-confidence extractions.

    Returns fields that need human review, sorted by confidence (lowest first).
    Can be filtered by template and confidence range.

    If max_confidence is not provided, uses the configurable threshold from settings.
    """

    # Get max_confidence from settings if not provided
    if max_confidence is None:
        settings_service = SettingsService(db)
        # For MVP, use default org/user (will be created on startup)
        org = settings_service.get_or_create_default_org()
        user = settings_service.get_or_create_default_user(org.id)
        max_confidence = settings_service.get_setting(
            key="review_threshold",
            user_id=user.id,
            org_id=org.id,
            default=0.6
        )

    # Base query: unverified fields within confidence range
    query = db.query(ExtractedField).filter(
        and_(
            ExtractedField.verified == False,
            ExtractedField.confidence_score >= min_confidence,
            ExtractedField.confidence_score <= max_confidence
        )
    ).join(Document)

    # Filter by template if specified
    if template_id:
        query = query.filter(Document.schema_id == template_id)

    # Count only mode (for badges)
    if count_only:
        count = query.count()
        return {"count": count}

    # Sort by confidence (lowest first)
    query = query.order_by(ExtractedField.confidence_score.asc())

    # Pagination
    total = query.count()
    offset = (page - 1) * size
    fields = query.offset(offset).limit(size).all()

    # Format response
    items = []
    for field in fields:
        items.append({
            "field_id": field.id,
            "document_id": field.document_id,
            "filename": field.document.filename,
            "file_path": field.document.file_path,
            "template_name": field.document.schema.name if field.document.schema else None,
            "field_name": field.field_name,
            "field_value": field.field_value,
            "confidence": field.confidence_score,
            "source_page": field.source_page,
            "source_bbox": field.source_bbox
        })

    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
        "items": items
    }


@router.get("/document/{document_id}")
async def get_document_audit_fields(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all fields for a specific document that need audit.

    Used when navigating from Documents tab to audit a specific document.
    """

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get all unverified fields for this document
    fields = db.query(ExtractedField).filter(
        and_(
            ExtractedField.document_id == document_id,
            ExtractedField.verified == False
        )
    ).order_by(ExtractedField.confidence_score.asc()).all()

    items = []
    for field in fields:
        items.append({
            "field_id": field.id,
            "document_id": field.document_id,
            "filename": document.filename,
            "file_path": document.file_path,
            "template_name": document.schema.name if document.schema else None,
            "field_name": field.field_name,
            "field_value": field.field_value,
            "confidence": field.confidence_score,
            "source_page": field.source_page,
            "source_bbox": field.source_bbox
        })

    return {
        "document_id": document_id,
        "filename": document.filename,
        "total_fields": len(items),
        "items": items
    }


@router.post("/verify")
async def verify_field(
    request: VerifyFieldRequest,
    db: Session = Depends(get_db)
):
    """
    Verify a field extraction.

    Actions:
    - "correct": Mark extraction as correct
    - "incorrect": Mark as incorrect and provide corrected value
    - "not_found": Mark field as not found in document
    """

    # Get field
    field = db.query(ExtractedField).filter(ExtractedField.id == request.field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    # Validate action
    if request.action not in ["correct", "incorrect", "not_found"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # For incorrect, require corrected value
    if request.action == "incorrect" and not request.corrected_value:
        raise HTTPException(status_code=400, detail="Corrected value required for 'incorrect' action")

    # Determine verified value
    if request.action == "correct":
        verified_value = field.field_value
        verification_type = "correct"
    elif request.action == "incorrect":
        verified_value = request.corrected_value
        verification_type = "incorrect"
    else:  # not_found
        verified_value = None
        verification_type = "not_found"

    # Create verification record
    verification = Verification(
        extracted_field_id=field.id,
        original_value=field.field_value,
        original_confidence=field.confidence_score,
        verified_value=verified_value,
        verification_type=verification_type,
        reviewer_notes=request.notes
    )
    db.add(verification)

    # Update field
    field.verified = True
    field.verified_value = verified_value
    field.verified_at = datetime.utcnow()

    # Update Elasticsearch if value changed
    if verified_value != field.field_value:
        try:
            elastic_service = ElasticsearchService()
            await elastic_service.update_document(
                document_id=field.document_id,
                updated_fields={field.field_name: verified_value}
            )
        except Exception as e:
            logger.warning(f"Failed to update Elasticsearch: {e}")

    db.commit()

    # Get next field in queue (same template preferred)
    next_field = db.query(ExtractedField).filter(
        and_(
            ExtractedField.verified == False,
            ExtractedField.document_id != field.document_id  # Different document
        )
    ).join(Document).filter(
        Document.schema_id == field.document.schema_id  # Same template
    ).order_by(ExtractedField.confidence_score.asc()).first()

    # If no same-template field, get any next field
    if not next_field:
        next_field = db.query(ExtractedField).filter(
            ExtractedField.verified == False
        ).order_by(ExtractedField.confidence_score.asc()).first()

    next_item = None
    if next_field:
        next_item = {
            "field_id": next_field.id,
            "document_id": next_field.document_id,
            "filename": next_field.document.filename,
            "file_path": next_field.document.file_path,
            "template_name": next_field.document.schema.name if next_field.document.schema else None,
            "field_name": next_field.field_name,
            "field_value": next_field.field_value,
            "confidence": next_field.confidence_score,
            "source_page": next_field.source_page,
            "source_bbox": next_field.source_bbox
        }

    return {
        "success": True,
        "message": "Field verified successfully",
        "next_item": next_item
    }


@router.get("/stats")
async def get_audit_stats(
    template_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get audit statistics"""

    # Get review threshold from settings
    settings_service = SettingsService(db)
    org = settings_service.get_or_create_default_org()
    user = settings_service.get_or_create_default_user(org.id)

    audit_threshold = settings_service.get_setting(
        key="review_threshold",
        user_id=user.id,
        org_id=org.id,
        default=0.6
    )

    # Hardcoded confidence label thresholds (for display only)
    high_threshold = 0.8
    medium_threshold = 0.6

    # Base queries
    base_query = db.query(ExtractedField)
    if template_id:
        base_query = base_query.join(Document).filter(Document.schema_id == template_id)

    # Count by status
    total_fields = base_query.count()
    verified_fields = base_query.filter(ExtractedField.verified == True).count()
    needs_audit = base_query.filter(
        and_(
            ExtractedField.verified == False,
            ExtractedField.confidence_score < audit_threshold
        )
    ).count()

    # Count by confidence range (using dynamic thresholds)
    high_confidence = base_query.filter(
        ExtractedField.confidence_score >= high_threshold
    ).count()

    medium_confidence = base_query.filter(
        and_(
            ExtractedField.confidence_score >= medium_threshold,
            ExtractedField.confidence_score < high_threshold
        )
    ).count()

    low_confidence = base_query.filter(
        ExtractedField.confidence_score < medium_threshold
    ).count()

    # Recent verifications
    recent_verifications = db.query(Verification).order_by(
        Verification.verified_at.desc()
    ).limit(10).all()

    verification_summary = []
    for v in recent_verifications:
        verification_summary.append({
            "field_name": v.extracted_field.field_name,
            "original_value": v.original_value,
            "verified_value": v.verified_value,
            "verification_type": v.verification_type,
            "verified_at": v.verified_at
        })

    return {
        "total_fields": total_fields,
        "verified_fields": verified_fields,
        "needs_audit": needs_audit,
        "completion_rate": (verified_fields / total_fields * 100) if total_fields > 0 else 0,
        "confidence_distribution": {
            "high": high_confidence,
            "medium": medium_confidence,
            "low": low_confidence
        },
        "recent_verifications": verification_summary
    }
