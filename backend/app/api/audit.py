import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document, ExtractedField
from app.models.verification import Verification
from app.services.claude_service import ClaudeService
from app.services.elastic_service import ElasticsearchService
from app.services.settings_service import SettingsService
from app.utils.bbox_utils import normalize_bbox

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


class BulkVerifyRequest(BaseModel):
    """Request model for bulk field verification (table mode)"""
    verifications: List[VerifyFieldRequest]


class VerifyAndRegenerateRequest(BaseModel):
    """Request model for inline verification with answer regeneration"""
    field_id: int
    action: str  # "correct", "incorrect", "not_found"
    corrected_value: Optional[str] = None
    notes: Optional[str] = None
    original_query: str  # The original NL query
    document_ids: List[int]  # Document IDs from the original search results


@router.get("/queue")
async def get_audit_queue(
    template_id: Optional[int] = Query(None, description="Filter by template ID"),
    priority: Optional[str] = Query(None, description="Filter by priority: critical, high, medium, low"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Max confidence threshold (uses settings default if not provided)"),
    include_validation_errors: bool = Query(True, description="Include fields with validation errors"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    count_only: bool = Query(False, description="Return only count"),
    db: Session = Depends(get_db)
):
    """
    Get audit queue of low-confidence extractions with enhanced priority filtering.

    Returns fields that need human review, sorted by priority then confidence.
    Can be filtered by template, confidence range, and validation status.

    Priority levels:
    - critical: Low confidence + validation error (both issues present)
    - high: Low confidence OR validation error (one major issue)
    - medium: Medium confidence or validation warning
    - low: High confidence but optional review

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

    # Base query: unverified fields
    query = db.query(ExtractedField).filter(
        ExtractedField.verified == False
    ).join(Document)

    # Filter by template if specified
    if template_id:
        query = query.filter(Document.schema_id == template_id)

    # Fetch all fields for priority calculation
    all_fields = query.all()

    # Calculate priority for each field and filter
    filtered_fields = []
    for field in all_fields:
        # Calculate priority using model property
        field_priority = field.audit_priority
        priority_label = field.priority_label

        # Apply priority filter if specified
        if priority and priority_label != priority:
            continue

        # Apply confidence filter
        if field.confidence_score < min_confidence or field.confidence_score > max_confidence:
            continue

        # Apply validation filter
        if not include_validation_errors and field.validation_status in ["error", "warning"]:
            continue

        filtered_fields.append(field)

    # Count only mode (for badges)
    if count_only:
        # Also return counts by priority
        priority_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for field in filtered_fields:
            priority_counts[field.priority_label] += 1

        return {
            "count": len(filtered_fields),
            "priority_counts": priority_counts
        }

    # Sort by priority (lowest=most urgent) then confidence
    filtered_fields.sort(key=lambda f: (f.audit_priority, f.confidence_score))

    # Pagination
    total = len(filtered_fields)
    offset = (page - 1) * size
    paginated_fields = filtered_fields[offset:offset + size]

    # Format response with validation metadata
    items = []
    for field in paginated_fields:
        items.append({
            "field_id": field.id,
            "document_id": field.document_id,
            "filename": field.document.filename,
            "file_path": field.document.actual_file_path,
            "template_name": field.document.schema.name if field.document.schema else None,
            "field_name": field.field_name,
            "field_value": field.field_value,
            "field_value_json": field.field_value_json,
            "field_type": field.field_type,
            "confidence": field.confidence_score,
            "source_page": field.source_page,
            "source_bbox": normalize_bbox(field.source_bbox),  # Convert dict to array
            # NEW: Validation metadata
            "validation_status": field.validation_status,
            "validation_errors": field.validation_errors or [],
            "audit_priority": field.audit_priority,
            "priority_label": field.priority_label
        })

    # Calculate summary statistics
    priority_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for field in filtered_fields:
        priority_counts[field.priority_label] += 1

    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
        "items": items,
        "summary": {
            "priority_counts": priority_counts,
            "total_with_validation_errors": sum(1 for f in filtered_fields if f.validation_status in ["error", "warning"]),
            "total_low_confidence": sum(1 for f in filtered_fields if f.confidence_score < 0.6),
            "total_critical": priority_counts["critical"]
        }
    }


@router.get("/document/{document_id}")
async def get_document_audit_fields(
    document_id: int,
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Max confidence threshold (uses settings default if not provided)"),
    db: Session = Depends(get_db)
):
    """
    Get fields for a specific document that need audit.

    Used when navigating from Documents tab to audit a specific document.
    Respects the same confidence threshold as the main audit queue for consistency.
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

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get unverified fields for this document that meet confidence threshold
    fields = db.query(ExtractedField).filter(
        and_(
            ExtractedField.document_id == document_id,
            ExtractedField.verified == False,
            ExtractedField.confidence_score <= max_confidence  # Apply same threshold as main queue
        )
    ).order_by(ExtractedField.confidence_score.asc()).all()

    items = []
    for field in fields:
        items.append({
            "field_id": field.id,
            "document_id": field.document_id,
            "filename": document.filename,
            "file_path": document.actual_file_path,  # Use actual_file_path property
            "template_name": document.schema.name if document.schema else None,
            "field_name": field.field_name,
            "field_value": field.field_value,
            "field_value_json": field.field_value_json,  # For complex types
            "field_type": field.field_type,  # Field type
            "confidence": field.confidence_score,
            "source_page": field.source_page,
            "source_bbox": normalize_bbox(field.source_bbox)  # Convert dict to array
        })

    return {
        "document_id": document_id,
        "filename": document.filename,
        "total_fields": len(items),
        "max_confidence_threshold": max_confidence,  # Show threshold used for filtering
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
            "file_path": next_field.document.actual_file_path,  # Use actual_file_path property
            "template_name": next_field.document.schema.name if next_field.document.schema else None,
            "field_name": next_field.field_name,
            "field_value": next_field.field_value,
            "field_value_json": next_field.field_value_json,  # For complex types
            "field_type": next_field.field_type,  # Field type
            "confidence": next_field.confidence_score,
            "source_page": next_field.source_page,
            "source_bbox": next_field.source_bbox
        }

    return {
        "success": True,
        "message": "Field verified successfully",
        "next_item": next_item
    }


@router.post("/verify-and-regenerate")
async def verify_field_and_regenerate_answer(
    request: VerifyAndRegenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Verify a field extraction and regenerate the answer with updated data.

    This endpoint is used by the inline audit modal to:
    1. Verify the field (like /verify)
    2. Re-fetch documents from Elasticsearch with updated data
    3. Regenerate the answer using Claude
    4. Return the updated answer along with next field to review

    This provides a seamless inline audit experience where users can
    see the impact of their verifications in real-time.
    """

    # Step 1: Verify the field (reuse existing logic from /verify)
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
    elastic_service = ElasticsearchService()
    if verified_value != field.field_value:
        try:
            await elastic_service.update_document(
                document_id=field.document_id,
                updated_fields={field.field_name: verified_value}
            )
            logger.info(f"Updated ES for document {field.document_id}, field {field.field_name}")
        except Exception as e:
            logger.warning(f"Failed to update Elasticsearch: {e}")

    db.commit()

    # Step 2: Re-fetch documents from Elasticsearch with updated data
    updated_documents = []
    try:
        for doc_id in request.document_ids:
            es_doc = await elastic_service.get_document_by_id(doc_id)
            if es_doc:
                updated_documents.append(es_doc)
    except Exception as e:
        logger.error(f"Failed to fetch updated documents from ES: {e}")
        # Continue without regenerating answer
        updated_documents = []

    # Step 3: Regenerate answer with Claude (if we got updated documents)
    updated_answer = None
    answer_metadata = None

    if updated_documents:
        try:
            claude_service = ClaudeService()
            answer_response = await claude_service.answer_question_about_results(
                query=request.original_query,
                search_results=updated_documents,
                total_count=len(updated_documents),
                include_confidence_metadata=True
            )

            updated_answer = answer_response.get("answer")
            answer_metadata = {
                "sources_used": answer_response.get("sources_used", []),
                "low_confidence_warnings": answer_response.get("low_confidence_warnings", []),
                "confidence_level": answer_response.get("confidence_level", "unknown")
            }

            logger.info(f"Regenerated answer for query: {request.original_query}")
        except Exception as e:
            logger.error(f"Failed to regenerate answer: {e}")
            # Continue without updated answer

    # Step 4: Get next field in queue
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
            "file_path": next_field.document.actual_file_path,  # Use actual_file_path property
            "template_name": next_field.document.schema.name if next_field.document.schema else None,
            "field_name": next_field.field_name,
            "field_value": next_field.field_value,
            "field_value_json": next_field.field_value_json,  # For complex types
            "field_type": next_field.field_type,  # Field type
            "confidence": next_field.confidence_score,
            "source_page": next_field.source_page,
            "source_bbox": next_field.source_bbox
        }

    return {
        "success": True,
        "message": "Field verified successfully",
        "verification": {
            "field_id": field.id,
            "field_name": field.field_name,
            "original_value": field.field_value,
            "verified_value": verified_value,
            "action": request.action
        },
        "updated_answer": updated_answer,
        "answer_metadata": answer_metadata,
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


@router.post("/bulk-verify")
async def bulk_verify_fields(
    request: BulkVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk verify multiple fields at once (for table mode).

    This is used by the Audit table view to verify multiple fields
    in one operation, providing a better UX for batch corrections.

    Returns:
        Summary of verifications including success count and any errors
    """

    elastic_service = ElasticsearchService()
    results = {
        "total": len(request.verifications),
        "successful": 0,
        "failed": 0,
        "errors": []
    }

    # Group updates by document for batch ES operations
    es_updates_by_doc = {}

    for verification_req in request.verifications:
        try:
            # Get field
            field = db.query(ExtractedField).filter(
                ExtractedField.id == verification_req.field_id
            ).first()

            if not field:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Field not found"
                })
                continue

            # Validate action
            if verification_req.action not in ["correct", "incorrect", "not_found"]:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Invalid action"
                })
                continue

            # For incorrect, require corrected value
            if verification_req.action == "incorrect" and not verification_req.corrected_value:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Corrected value required for 'incorrect' action"
                })
                continue

            # Determine verified value
            if verification_req.action == "correct":
                verified_value = field.field_value
                verification_type = "correct"
            elif verification_req.action == "incorrect":
                verified_value = verification_req.corrected_value
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
                reviewer_notes=verification_req.notes
            )
            db.add(verification)

            # Update field
            field.verified = True
            field.verified_value = verified_value
            field.verified_at = datetime.utcnow()

            # Track ES updates for batch operation
            if verified_value != field.field_value:
                if field.document_id not in es_updates_by_doc:
                    es_updates_by_doc[field.document_id] = {}
                es_updates_by_doc[field.document_id][field.field_name] = verified_value

            results["successful"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "field_id": verification_req.field_id,
                "error": str(e)
            })
            logger.error(f"Failed to verify field {verification_req.field_id}: {e}")

    # Commit all database changes
    db.commit()

    # Batch update Elasticsearch
    es_update_count = 0
    for document_id, updated_fields in es_updates_by_doc.items():
        try:
            await elastic_service.update_document(
                document_id=document_id,
                updated_fields=updated_fields
            )
            es_update_count += 1
        except Exception as e:
            logger.warning(f"Failed to update ES for document {document_id}: {e}")

    logger.info(f"Bulk verified {results['successful']}/{results['total']} fields, updated {es_update_count} ES documents")

    return {
        "success": results["failed"] == 0,
        "results": results,
        "elasticsearch_updates": es_update_count,
        "message": f"Verified {results['successful']} of {results['total']} fields"
    }


class BulkVerifyAndRegenerateRequest(BaseModel):
    """Request model for bulk verification with answer regeneration"""
    verifications: List[VerifyFieldRequest]
    original_query: str
    document_ids: List[int]


@router.post("/bulk-verify-and-regenerate")
async def bulk_verify_and_regenerate(
    request: BulkVerifyAndRegenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk verify multiple fields and regenerate the answer with updated data.

    This endpoint combines bulk verification with answer regeneration,
    providing an efficient workflow for the batch audit modal.

    Workflow:
    1. Verify all fields (like /bulk-verify)
    2. Update Elasticsearch with all changes
    3. Re-fetch updated documents from ES
    4. Regenerate answer using Claude with updated data
    5. Return updated answer and verification results
    """

    elastic_service = ElasticsearchService()
    results = {
        "total": len(request.verifications),
        "successful": 0,
        "failed": 0,
        "errors": []
    }

    # Track ES updates by document for batch operations
    es_updates_by_doc = {}
    verified_field_ids = []

    # Step 1: Process all verifications
    for verification_req in request.verifications:
        try:
            # Get field
            field = db.query(ExtractedField).filter(
                ExtractedField.id == verification_req.field_id
            ).first()

            if not field:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Field not found"
                })
                continue

            # Validate action
            if verification_req.action not in ["correct", "incorrect", "not_found"]:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Invalid action"
                })
                continue

            # For incorrect, require corrected value
            if verification_req.action == "incorrect" and not verification_req.corrected_value:
                results["failed"] += 1
                results["errors"].append({
                    "field_id": verification_req.field_id,
                    "error": "Corrected value required for 'incorrect' action"
                })
                continue

            # Determine verified value
            if verification_req.action == "correct":
                verified_value = field.field_value
                verification_type = "correct"
            elif verification_req.action == "incorrect":
                verified_value = verification_req.corrected_value
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
                reviewer_notes=verification_req.notes
            )
            db.add(verification)

            # Update field
            field.verified = True
            field.verified_value = verified_value
            field.verified_at = datetime.utcnow()

            # Track ES updates for batch operation
            if verified_value != field.field_value:
                if field.document_id not in es_updates_by_doc:
                    es_updates_by_doc[field.document_id] = {}
                es_updates_by_doc[field.document_id][field.field_name] = verified_value

            verified_field_ids.append(field.id)
            results["successful"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "field_id": verification_req.field_id,
                "error": str(e)
            })
            logger.error(f"Failed to verify field {verification_req.field_id}: {e}")

    # Commit all database changes
    db.commit()

    # Step 2: Batch update Elasticsearch
    es_update_count = 0
    for document_id, updated_fields in es_updates_by_doc.items():
        try:
            await elastic_service.update_document(
                document_id=document_id,
                updated_fields=updated_fields
            )
            es_update_count += 1
        except Exception as e:
            logger.warning(f"Failed to update ES for document {document_id}: {e}")

    logger.info(f"Bulk verified {results['successful']}/{results['total']} fields, updated {es_update_count} ES documents")

    # Step 3: Re-fetch updated documents from Elasticsearch
    updated_documents = []
    try:
        for doc_id in request.document_ids:
            es_doc = await elastic_service.get_document_by_id(doc_id)
            if es_doc:
                updated_documents.append(es_doc)
    except Exception as e:
        logger.error(f"Failed to fetch updated documents from ES: {e}")
        # Continue without regenerating answer
        updated_documents = []

    # Step 4: Regenerate answer with Claude (if we got updated documents)
    updated_answer = None
    answer_metadata = None

    if updated_documents and results["successful"] > 0:
        try:
            claude_service = ClaudeService()
            answer_response = await claude_service.answer_question_about_results(
                query=request.original_query,
                search_results=updated_documents,
                total_count=len(updated_documents),
                include_confidence_metadata=True
            )

            updated_answer = answer_response.get("answer")
            answer_metadata = {
                "sources_used": answer_response.get("sources_used", []),
                "low_confidence_warnings": answer_response.get("low_confidence_warnings", []),
                "confidence_level": answer_response.get("confidence_level", "unknown")
            }

            logger.info(f"Regenerated answer after {results['successful']} verifications for query: {request.original_query}")
        except Exception as e:
            logger.error(f"Failed to regenerate answer: {e}")
            # Continue without updated answer

    return {
        "success": results["failed"] == 0,
        "results": results,
        "elasticsearch_updates": es_update_count,
        "verified_count": results["successful"],
        "updated_answer": updated_answer,
        "answer_metadata": answer_metadata,
        "message": f"Verified {results['successful']} of {results['total']} fields"
    }
