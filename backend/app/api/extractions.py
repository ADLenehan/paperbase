"""
API endpoints for extraction management.
Supports multi-template extraction and batch processing.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.services.file_service import FileService
from app.services.extraction_service import ExtractionService
from app.models.physical_file import PhysicalFile
from app.models.extraction import Extraction

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models
class UploadAndExtractRequest(BaseModel):
    template_ids: List[int]


class BatchExtractRequest(BaseModel):
    physical_file_ids: List[int]
    template_id: int
    batch_name: str


class ReprocessRequest(BaseModel):
    template_id: int


@router.post("/upload-and-extract")
async def upload_and_extract(
    files: List[UploadFile] = File(...),
    template_ids: List[int] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Upload files and create extractions with multiple templates.

    Example: Upload 1 file with 2 templates = 2 extractions
    If no template_ids provided, files are just uploaded without extraction.

    Returns:
        {
            "physical_files": [...],
            "extractions": [...],
            "duplicates_found": 2
        }
    """
    file_service = FileService()
    extraction_service = ExtractionService()

    # Default to empty list if not provided
    template_ids = template_ids or []

    results = {
        "physical_files": [],
        "extractions": [],
        "duplicates_found": 0
    }

    # Upload all files (with deduplication)
    for file in files:
        physical_file, is_new = await file_service.upload_file(file, db)

        if not is_new:
            results["duplicates_found"] += 1

        results["physical_files"].append({
            "id": physical_file.id,
            "filename": physical_file.filename,
            "file_hash": physical_file.file_hash[:8],
            "is_new": is_new,
            "file_size": physical_file.file_size
        })

        # Create extraction for each template
        if template_ids:
            for template_id in template_ids:
                extraction = await extraction_service.create_extraction(
                    physical_file, template_id, db
                )

                # Process extraction in background
                if background_tasks:
                    background_tasks.add_task(
                        extraction_service.process_extraction,
                        extraction.id,
                        db
                    )
                else:
                    # Process synchronously if no background tasks
                    await extraction_service.process_extraction(extraction.id, db)

                results["extractions"].append({
                    "id": extraction.id,
                    "physical_file_id": physical_file.id,
                    "filename": physical_file.filename,
                    "template_id": template_id,
                    "status": extraction.status,
                    "organized_path": extraction.organized_path
                })

    return results


@router.post("/batch-extract")
async def batch_extract(
    request: BatchExtractRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Apply one template to multiple files (bulk processing).

    Request:
        {
            "physical_file_ids": [1, 2, 3],
            "template_id": 5,
            "batch_name": "Q3 2025 Invoices"
        }

    Returns:
        {
            "batch_id": 123,
            "batch_name": "Q3 2025 Invoices",
            "total_files": 3,
            "extractions": [...]
        }
    """
    extraction_service = ExtractionService()

    # Run batch extraction in background
    result = await extraction_service.batch_extract(
        physical_file_ids=request.physical_file_ids,
        template_id=request.template_id,
        batch_name=request.batch_name,
        db=db
    )

    return result


@router.get("/extractions/{physical_file_id}")
async def list_extractions(
    physical_file_id: int,
    db: Session = Depends(get_db)
):
    """
    List all extractions for a physical file.

    Shows how the same file has been processed with different templates.
    """
    extraction_service = ExtractionService()

    extractions = extraction_service.list_extractions(
        physical_file_id=physical_file_id,
        db=db
    )

    if not extractions:
        physical_file = db.query(PhysicalFile).get(physical_file_id)
        if not physical_file:
            raise HTTPException(status_code=404, detail="Physical file not found")

        return {
            "physical_file_id": physical_file_id,
            "filename": physical_file.filename,
            "extractions": []
        }

    return {
        "physical_file_id": physical_file_id,
        "filename": extractions[0].physical_file.filename,
        "extractions": [
            {
                "id": ext.id,
                "template_id": ext.template_id,
                "template_name": ext.template.name if ext.template else "Unknown",
                "confidence": ext.template_confidence,
                "status": ext.status,
                "organized_path": ext.organized_path,
                "created_at": ext.created_at.isoformat(),
                "processed_at": ext.processed_at.isoformat() if ext.processed_at else None,
                "field_count": len(ext.extracted_fields)
            }
            for ext in extractions
        ]
    }


@router.get("/extractions/detail/{extraction_id}")
async def get_extraction_detail(
    extraction_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific extraction.
    """
    extraction = db.query(Extraction).get(extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    return {
        "id": extraction.id,
        "physical_file": {
            "id": extraction.physical_file.id,
            "filename": extraction.physical_file.filename,
            "file_size": extraction.physical_file.file_size,
            "uploaded_at": extraction.physical_file.uploaded_at.isoformat()
        },
        "template": {
            "id": extraction.template.id if extraction.template else None,
            "name": extraction.template.name if extraction.template else "Unknown",
            "category": extraction.template.category if extraction.template else None
        },
        "status": extraction.status,
        "confidence": extraction.template_confidence,
        "organized_path": extraction.organized_path,
        "created_at": extraction.created_at.isoformat(),
        "processed_at": extraction.processed_at.isoformat() if extraction.processed_at else None,
        "error_message": extraction.error_message,
        "fields": [
            {
                "id": field.id,
                "name": field.field_name,
                "value": field.field_value,
                "confidence": field.confidence_score,
                "needs_verification": field.needs_verification,
                "verified": field.verified,
                "verified_value": field.verified_value
            }
            for field in extraction.extracted_fields
        ]
    }


@router.post("/extractions/{extraction_id}/reprocess")
async def reprocess_extraction(
    extraction_id: int,
    request: ReprocessRequest = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Reprocess an extraction, optionally with a different template.

    If template_id provided, creates a new extraction with new template.
    Otherwise, reprocesses existing extraction.
    """
    extraction_service = ExtractionService()

    extraction = db.query(Extraction).get(extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    # If new template specified, create new extraction
    if request and request.template_id != extraction.template_id:
        new_extraction = await extraction_service.create_extraction(
            extraction.physical_file,
            request.template_id,
            db
        )

        if background_tasks:
            background_tasks.add_task(
                extraction_service.process_extraction,
                new_extraction.id,
                db
            )
        else:
            await extraction_service.process_extraction(new_extraction.id, db)

        return {
            "message": "Created new extraction with different template",
            "original_extraction_id": extraction_id,
            "new_extraction_id": new_extraction.id
        }

    # Otherwise, reprocess existing extraction
    extraction.status = "pending"
    db.commit()

    if background_tasks:
        background_tasks.add_task(
            extraction_service.process_extraction,
            extraction_id,
            db
        )
    else:
        await extraction_service.process_extraction(extraction_id, db)

    return {
        "message": "Extraction reprocessing started",
        "extraction_id": extraction_id
    }


@router.get("/stats")
async def get_extraction_stats(db: Session = Depends(get_db)):
    """
    Get extraction statistics.
    """
    extraction_service = ExtractionService()
    file_service = FileService()

    extraction_stats = extraction_service.get_extraction_stats(db)
    storage_stats = file_service.get_storage_stats(db)

    return {
        "extractions": extraction_stats,
        "storage": storage_stats
    }


@router.delete("/extractions/{extraction_id}")
async def delete_extraction(
    extraction_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an extraction (and its fields).
    Does not delete the physical file unless it's the last extraction.
    """
    extraction = db.query(Extraction).get(extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    physical_file_id = extraction.physical_file_id
    db.delete(extraction)
    db.commit()

    # Check if physical file still has other extractions
    remaining = db.query(Extraction).filter_by(
        physical_file_id=physical_file_id
    ).count()

    return {
        "message": "Extraction deleted",
        "extraction_id": extraction_id,
        "physical_file_has_remaining_extractions": remaining > 0
    }
