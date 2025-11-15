import logging
import os
from pathlib import Path as PathLib

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{document_id}/preview")
async def get_document_preview(
    document_id: int = Path(..., description="Document ID"),
    db: Session = Depends(get_db)
):
    """
    Serve document file for preview (with PDF rendering).

    Security:
    - Validates document exists in database
    - Prevents directory traversal
    - Only serves files from upload directory
    """

    # Get document from database
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get file path (use actual_file_path property for PhysicalFile compatibility)
    file_path = document.actual_file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not found for document")

    # Security: Validate file path
    # Convert to absolute path and check it exists
    abs_path = PathLib(file_path).resolve()

    if not abs_path.exists():
        logger.error(f"File not found on disk: {abs_path}")
        raise HTTPException(status_code=404, detail="File not found on disk")

    if not abs_path.is_file():
        logger.error(f"Path is not a file: {abs_path}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Security: Prevent directory traversal
    # Ensure the file is within the expected upload directory
    try:
        # Get upload directory from environment or use default
        upload_dir = PathLib(os.getenv("UPLOAD_DIR", "uploads")).resolve()

        # Check if file is within upload directory
        abs_path.relative_to(upload_dir)
    except ValueError:
        logger.warning(f"Attempted access to file outside upload directory: {abs_path}")
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine media type
    file_ext = abs_path.suffix.lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.txt': 'text/plain',
        '.json': 'application/json',
        '.xml': 'application/xml'
    }

    media_type = media_type_map.get(file_ext, 'application/octet-stream')

    # Return file with proper headers for preview
    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=document.filename,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "Content-Disposition": f'inline; filename="{document.filename}"'  # Display inline (not download)
        }
    )


@router.get("/document/{document_id}/download")
async def download_document(
    document_id: int = Path(..., description="Document ID"),
    db: Session = Depends(get_db)
):
    """
    Download document file (forces download instead of preview).
    """

    # Get document from database
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get file path (use actual_file_path property for PhysicalFile compatibility)
    file_path = document.actual_file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File path not found for document")

    # Security: Validate file path
    abs_path = PathLib(file_path).resolve()

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    if not abs_path.is_file():
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Security: Prevent directory traversal
    try:
        upload_dir = PathLib(os.getenv("UPLOAD_DIR", "uploads")).resolve()
        abs_path.relative_to(upload_dir)
    except ValueError:
        logger.warning(f"Attempted download of file outside upload directory: {abs_path}")
        raise HTTPException(status_code=403, detail="Access denied")

    # Return file with download headers
    return FileResponse(
        path=str(abs_path),
        filename=document.filename,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"'
        }
    )
