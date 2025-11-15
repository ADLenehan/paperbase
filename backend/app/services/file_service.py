"""
File upload service with deduplication support.
"""

import logging
import os
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import FileUploadError
from app.models.physical_file import PhysicalFile
from app.utils.hashing import calculate_content_hash

logger = logging.getLogger(__name__)
settings = Settings()


class FileService:
    """
    Handles file uploads with automatic deduplication based on file hash.
    """

    def __init__(self, upload_dir: str = None):
        self.upload_dir = upload_dir or settings.UPLOAD_DIR

    async def upload_file(
        self,
        file: UploadFile,
        db: Session
    ) -> tuple[PhysicalFile, bool]:
        """
        Upload file and create PhysicalFile record.
        Automatically deduplicates based on file hash.

        Args:
            file: Uploaded file
            db: Database session

        Returns:
            Tuple of (PhysicalFile, is_new)
            - PhysicalFile: The physical file record
            - is_new: True if this is a new file, False if deduplicated

        Raises:
            FileUploadError: If upload fails
        """
        try:
            # Read file content
            content = await file.read()
            if not content:
                raise FileUploadError("Empty file uploaded")

            # Calculate hash for deduplication
            file_hash = calculate_content_hash(content)

            # Check for existing file with same hash
            existing = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()
            if existing:
                logger.info(
                    f"File deduplicated: {file.filename} → existing file #{existing.id} "
                    f"(hash: {file_hash[:8]}...)"
                )
                # Reset file position for potential re-read
                await file.seek(0)
                return existing, False

            # Generate unique file path using hash prefix
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{file_hash[:8]}_{file.filename}"
            file_path = os.path.join(self.upload_dir, unique_filename)

            # Ensure upload directory exists
            os.makedirs(self.upload_dir, exist_ok=True)

            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(content)

            # Create PhysicalFile record
            physical_file = PhysicalFile(
                filename=file.filename,
                file_hash=file_hash,
                file_path=file_path,
                file_size=len(content),
                mime_type=file.content_type
            )
            db.add(physical_file)
            db.commit()
            db.refresh(physical_file)

            logger.info(
                f"File uploaded: {file.filename} → {file_path} "
                f"(size: {len(content)} bytes, hash: {file_hash[:8]}...)"
            )

            # Reset file position for potential re-read
            await file.seek(0)

            return physical_file, True

        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise FileUploadError(f"Failed to upload file: {str(e)}")

    async def upload_multiple(
        self,
        files: list[UploadFile],
        db: Session
    ) -> list[tuple[PhysicalFile, bool]]:
        """
        Upload multiple files with deduplication.

        Args:
            files: List of uploaded files
            db: Database session

        Returns:
            List of (PhysicalFile, is_new) tuples
        """
        results = []
        for file in files:
            result = await self.upload_file(file, db)
            results.append(result)
        return results

    def get_file(self, file_id: int, db: Session) -> Optional[PhysicalFile]:
        """Get physical file by ID."""
        return db.query(PhysicalFile).get(file_id)

    def get_file_by_hash(self, file_hash: str, db: Session) -> Optional[PhysicalFile]:
        """Get physical file by hash."""
        return db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

    def delete_file(self, file_id: int, db: Session) -> bool:
        """
        Delete physical file and its record.
        Only deletes if no extractions reference it.

        Args:
            file_id: Physical file ID
            db: Database session

        Returns:
            True if deleted, False if still referenced
        """
        physical_file = db.query(PhysicalFile).get(file_id)
        if not physical_file:
            return False

        # Check if any extractions still reference this file
        if physical_file.extractions:
            logger.warning(
                f"Cannot delete file #{file_id}: still referenced by "
                f"{len(physical_file.extractions)} extractions"
            )
            return False

        # Delete physical file from disk
        try:
            if os.path.exists(physical_file.file_path):
                os.remove(physical_file.file_path)
        except Exception as e:
            logger.error(f"Failed to delete physical file: {e}")

        # Delete database record
        db.delete(physical_file)
        db.commit()

        logger.info(f"Deleted physical file #{file_id}: {physical_file.filename}")
        return True

    def get_storage_stats(self, db: Session) -> dict:
        """Get storage statistics."""
        from sqlalchemy import func

        from app.models.extraction import Extraction

        total_files = db.query(func.count(PhysicalFile.id)).scalar()
        total_size = db.query(func.sum(PhysicalFile.file_size)).scalar() or 0
        total_extractions = db.query(func.count(Extraction.id)).scalar()

        # Calculate deduplication savings
        # (total extractions - unique files) = duplicates avoided
        duplicates_avoided = max(0, total_extractions - total_files)

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_extractions": total_extractions,
            "duplicates_avoided": duplicates_avoided,
            "avg_file_size_mb": round(total_size / max(total_files, 1) / (1024 * 1024), 2)
        }
