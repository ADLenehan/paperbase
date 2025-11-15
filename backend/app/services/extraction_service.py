"""
Extraction service for multi-template document processing.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ProcessingError
from app.models.document import ExtractedField
from app.models.extraction import Extraction
from app.models.physical_file import PhysicalFile
from app.models.template import SchemaTemplate
from app.services.elastic_service import ElasticsearchService
from app.services.reducto_service import ReductoService
from app.services.settings_service import SettingsService
from app.services.validation_service import ExtractionValidator, should_flag_for_review

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Handles extraction jobs: processing physical files with specific templates.
    Supports multi-template extraction (same file, different templates).
    """

    def __init__(self):
        self.reducto_service = ReductoService()
        self.elastic_service = ElasticsearchService()

    async def create_extraction(
        self,
        physical_file: PhysicalFile,
        template_id: int,
        db: Session,
        confidence: float = None
    ) -> Extraction:
        """
        Create a new extraction job for a physical file + template combination.

        Args:
            physical_file: The physical file to extract from
            template_id: Template to use for extraction
            db: Database session
            confidence: Optional template confidence score

        Returns:
            Created Extraction record
        """
        template = db.query(SchemaTemplate).get(template_id)
        if not template:
            raise NotFoundError("SchemaTemplate", str(template_id))

        # Check if extraction already exists for this file + template
        existing = db.query(Extraction).filter_by(
            physical_file_id=physical_file.id,
            template_id=template_id
        ).first()

        if existing:
            logger.info(
                f"Extraction already exists: file #{physical_file.id} + "
                f"template #{template_id} → extraction #{existing.id}"
            )
            return existing

        # Generate virtual folder path
        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        organized_path = f"{template.name}/{date_folder}/{physical_file.filename}"

        # Create extraction record
        extraction = Extraction(
            physical_file_id=physical_file.id,
            template_id=template_id,
            status="pending",
            template_confidence=confidence,
            organized_path=organized_path
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)

        logger.info(
            f"Created extraction #{extraction.id}: "
            f"{physical_file.filename} → {template.name}"
        )

        return extraction

    async def process_extraction(
        self,
        extraction_id: int,
        db: Session
    ) -> Extraction:
        """
        Process an extraction: parse file (if needed) and extract fields.

        Args:
            extraction_id: Extraction ID to process
            db: Database session

        Returns:
            Updated Extraction record
        """
        extraction = db.query(Extraction).get(extraction_id)
        if not extraction:
            raise NotFoundError("Extraction", str(extraction_id))

        extraction.status = "processing"
        db.commit()

        try:
            physical_file = extraction.physical_file
            template = extraction.template

            # Step 1: Parse document (use cached result if available)
            if not physical_file.reducto_parse_result:
                logger.info(f"Parsing document for first time: {physical_file.filename}")
                parsed = await self.reducto_service.parse_document(physical_file.file_path)
                physical_file.reducto_job_id = parsed.get("job_id")
                physical_file.reducto_parse_result = parsed
                db.commit()
            else:
                logger.info(
                    f"Reusing cached parse result for: {physical_file.filename} "
                    f"(job_id: {physical_file.reducto_job_id})"
                )

            # Step 2: Extract fields using template + pipelined job_id
            logger.info(f"Extracting fields with template: {template.name}")

            # Build schema for Reducto extraction
            schema = {
                "name": template.name,
                "fields": template.fields
            }

            # Use pipelined extraction with jobid://
            if physical_file.reducto_job_id:
                extraction_result = await self.reducto_service.extract_structured(
                    schema=schema,
                    job_id=physical_file.reducto_job_id  # Reuse parse!
                )
            else:
                # Fallback: extract with file path
                extraction_result = await self.reducto_service.extract_structured(
                    schema=schema,
                    file_path=physical_file.file_path
                )

            # Step 3: Validate extracted fields (NEW)
            extracted_data = extraction_result.get("extracted_fields", {})
            confidence_scores = extraction_result.get("confidence_scores", {})

            # Prepare extractions dict for validation
            extractions_for_validation = {
                field_name: {
                    "value": field_value,
                    "confidence": confidence_scores.get(field_name, 0.0)
                }
                for field_name, field_value in extracted_data.items()
            }

            # Run validation (NEW: uses dynamic Pydantic validation + business rules)
            validator = ExtractionValidator()
            validation_results = await validator.validate_extraction(
                extractions=extractions_for_validation,
                template=template,  # Use template object for dynamic validation
                template_name=template.name,  # Also use name for business rules
                schema_config=None  # Schema is in template object
            )

            # Get review threshold from settings
            settings_service = SettingsService(db)
            org = settings_service.get_or_create_default_org()
            user = settings_service.get_or_create_default_user(org.id)
            review_threshold = settings_service.get_setting(
                key="review_threshold",
                user_id=user.id,
                org_id=org.id,
                default=0.6
            )

            # Step 4: Save extracted fields with validation metadata
            for field_name, field_value in extracted_data.items():
                confidence = confidence_scores.get(field_name, 0.0)
                validation_result = validation_results.get(field_name)

                # Determine if field needs verification
                validation_status = validation_result.status if validation_result else "valid"
                needs_verification = should_flag_for_review(confidence, validation_status)

                extracted_field = ExtractedField(
                    extraction_id=extraction.id,
                    field_name=field_name,
                    field_value=field_value,
                    confidence_score=confidence,
                    needs_verification=needs_verification,
                    # NEW: Validation metadata
                    validation_status=validation_status,
                    validation_errors=validation_result.errors if validation_result else [],
                    validation_checked_at=datetime.utcnow()
                )
                db.add(extracted_field)

                # Log validation issues
                if validation_result and validation_result.errors:
                    logger.warning(
                        f"Field '{field_name}' has validation errors: {', '.join(validation_result.errors)}"
                    )

            # Step 4: Index in Elasticsearch
            es_doc_id = f"extraction_{extraction.id}"
            await self.elastic_service.index_document(
                document_id=extraction.id,
                filename=physical_file.filename,
                extracted_fields=extracted_data,
                confidence_scores=confidence_scores,
                full_text=physical_file.reducto_parse_result.get("full_text", "")
            )
            extraction.elasticsearch_id = es_doc_id

            # Update extraction status
            extraction.status = "completed"
            extraction.processed_at = datetime.utcnow()
            db.commit()

            logger.info(
                f"✓ Extraction #{extraction.id} completed: "
                f"{len(extracted_data)} fields extracted"
            )

            return extraction

        except Exception as e:
            logger.error(f"Extraction #{extraction_id} failed: {e}")
            extraction.status = "error"
            extraction.error_message = str(e)
            db.commit()
            raise ProcessingError(str(extraction_id), str(e))

    async def batch_extract(
        self,
        physical_file_ids: List[int],
        template_id: int,
        batch_name: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Create and process extractions for multiple files with one template.

        Args:
            physical_file_ids: List of physical file IDs
            template_id: Template to apply to all files
            batch_name: Name for the batch job
            db: Database session

        Returns:
            Dict with batch info and extraction results
        """
        from app.models.batch import Batch

        # Create batch record
        batch = Batch(
            name=batch_name,
            template_id=template_id,
            total_files=len(physical_file_ids),
            status="processing"
        )
        db.add(batch)
        db.commit()

        logger.info(f"Starting batch extraction #{batch.id}: {batch_name}")

        extractions = []
        errors = []

        for file_id in physical_file_ids:
            try:
                physical_file = db.query(PhysicalFile).get(file_id)
                if not physical_file:
                    errors.append(f"File #{file_id} not found")
                    continue

                # Create extraction
                extraction = await self.create_extraction(
                    physical_file, template_id, db
                )

                # Process extraction
                await self.process_extraction(extraction.id, db)

                extractions.append(extraction)
                batch.processed_files += 1
                db.commit()

            except Exception as e:
                logger.error(f"Error processing file #{file_id}: {e}")
                errors.append(f"File #{file_id}: {str(e)}")

        # Update batch status
        batch.status = "completed" if not errors else "completed_with_errors"
        batch.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Batch extraction #{batch.id} complete: "
            f"{batch.processed_files}/{batch.total_files} successful"
        )

        return {
            "batch_id": batch.id,
            "batch_name": batch_name,
            "total_files": batch.total_files,
            "processed_files": batch.processed_files,
            "extractions": [
                {
                    "id": ext.id,
                    "filename": ext.physical_file.filename,
                    "status": ext.status
                }
                for ext in extractions
            ],
            "errors": errors
        }

    def list_extractions(
        self,
        physical_file_id: Optional[int] = None,
        template_id: Optional[int] = None,
        status: Optional[str] = None,
        db: Session = None
    ) -> List[Extraction]:
        """
        List extractions with optional filters.

        Args:
            physical_file_id: Filter by physical file
            template_id: Filter by template
            status: Filter by status
            db: Database session

        Returns:
            List of Extraction records
        """
        query = db.query(Extraction)

        if physical_file_id:
            query = query.filter_by(physical_file_id=physical_file_id)
        if template_id:
            query = query.filter_by(template_id=template_id)
        if status:
            query = query.filter_by(status=status)

        return query.order_by(Extraction.created_at.desc()).all()

    def get_extraction_stats(self, db: Session) -> Dict[str, Any]:
        """Get extraction statistics."""
        from sqlalchemy import func

        total = db.query(func.count(Extraction.id)).scalar()
        by_status = db.query(
            Extraction.status,
            func.count(Extraction.id)
        ).group_by(Extraction.status).all()

        by_template = db.query(
            SchemaTemplate.name,
            func.count(Extraction.id)
        ).join(Extraction).group_by(SchemaTemplate.name).all()

        return {
            "total_extractions": total,
            "by_status": {status: count for status, count in by_status},
            "by_template": {name: count for name, count in by_template}
        }
