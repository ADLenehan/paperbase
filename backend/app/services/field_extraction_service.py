"""Service for extracting new fields from existing documents"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.background_job import BackgroundJob
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.verification import Verification
from app.services.claude_service import ClaudeService
from app.services.postgres_service import PostgresService
from app.services.reducto_service import ReductoService

logger = logging.getLogger(__name__)


class FieldExtractionService:
    """
    Service for extracting new fields from existing documents

    Used when a user adds a new field to a template and wants to
    extract it from all previously processed documents.
    """

    def __init__(self):
        self.claude_service = ClaudeService()
        self.reducto_service = ReductoService()
        self.postgres_service = ElasticsearchService()

    async def extract_field_from_all_docs(
        self,
        schema_id: int,
        field_config: Dict[str, Any],
        db: Session
    ) -> BackgroundJob:
        """
        Extract a single field from all documents using a schema/template

        Creates a background job and processes documents asynchronously.

        Args:
            schema_id: Schema ID to extract from
            field_config: Field configuration (name, type, description, hints)
            db: Database session

        Returns:
            BackgroundJob instance for tracking progress
        """
        # Get all documents for this schema
        documents = db.query(Document)\
            .filter(Document.schema_id == schema_id)\
            .all()

        logger.info(f"Starting field extraction: {field_config['name']} "
                   f"for {len(documents)} documents (schema {schema_id})")

        # Create background job
        job = BackgroundJob(
            type="field_extraction",
            status="running",
            total_items=len(documents),
            processed_items=0,
            job_data={
                "schema_id": schema_id,
                "field_name": field_config["name"],
                "started_at": datetime.utcnow().isoformat()
            }
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Run extraction in background
        asyncio.create_task(
            self._extract_field_background(
                background_job_id=job.id,
                documents=documents,
                field_config=field_config
            )
        )

        return job

    async def _extract_field_background(
        self,
        background_job_id: int,  # RENAMED to avoid collision
        documents: List[Document],
        field_config: Dict[str, Any]
    ):
        """
        Background task to extract field from documents

        This runs asynchronously without blocking the API response.

        Args:
            background_job_id: Background job ID for progress tracking
            documents: List of documents to process
            field_config: Field configuration
        """
        from app.core.database import SessionLocal

        db = SessionLocal()
        successful = 0
        failed = 0
        low_confidence_count = 0

        # Get schema to determine ES index name
        schema = None
        if documents:
            schema = db.query(Schema).filter(Schema.id == documents[0].schema_id).first()

        try:
            for i, doc in enumerate(documents):
                try:
                    # Try to use Reducto extraction with jobid:// pipeline for bbox data
                    reducto_job_id = None
                    doc_file_path = None

                    # Get Reducto job_id and file_path
                    if doc.physical_file:
                        reducto_job_id = doc.physical_file.reducto_job_id
                        doc_file_path = doc.physical_file.file_path
                    elif hasattr(doc, 'reducto_job_id') and doc.reducto_job_id:
                        reducto_job_id = doc.reducto_job_id
                        doc_file_path = doc.file_path if hasattr(doc, 'file_path') else None

                    # Create single-field schema for extraction
                    single_field_schema = {
                        "fields": [field_config]
                    }

                    # Extract using Reducto (with jobid:// pipeline if available, else file_path)
                    try:
                        extraction_result = await self.reducto_service.extract_structured(
                            schema=single_field_schema,
                            job_id=reducto_job_id,  # Preferred: uses jobid:// pipeline
                            file_path=doc_file_path if not reducto_job_id else None  # Fallback
                        )

                        # Get the extracted field data
                        extractions = extraction_result.get("extractions", {})
                        field_data = extractions.get(field_config["name"], {})

                        extracted_value = field_data.get("value")
                        confidence = field_data.get("confidence", 0.0)
                        source_page = field_data.get("source_page")
                        source_bbox = field_data.get("source_bbox")

                        logger.debug(f"Reducto extraction for {field_config['name']} (doc {doc.id}): "
                                   f"value={extracted_value}, conf={confidence:.2f}, "
                                   f"page={source_page}, has_bbox={bool(source_bbox)}")

                    except Exception as reducto_error:
                        # Fallback to Claude if Reducto fails (e.g., job_id expired)
                        logger.warning(f"Reducto extraction failed for doc {doc.id}, "
                                     f"falling back to Claude: {reducto_error}")

                        # Get parse result for Claude fallback
                        if doc.physical_file and doc.physical_file.reducto_parse_result:
                            parse_result = doc.physical_file.reducto_parse_result
                        elif hasattr(doc, 'reducto_parse_result') and doc.reducto_parse_result:
                            parse_result = doc.reducto_parse_result
                        else:
                            logger.warning(f"No parse result for document {doc.id}")
                            failed += 1
                            continue

                        # Extract using Claude (no bbox data)
                        extraction = await self.claude_service.extract_single_field(
                            parse_result=parse_result,
                            field_config=field_config
                        )

                        extracted_value = extraction.get("value")
                        confidence = extraction.get("confidence", 0.0)
                        source_page = None
                        source_bbox = None

                    # Create or update ExtractedField record
                    existing_field = db.query(ExtractedField).filter(
                        ExtractedField.document_id == doc.id,
                        ExtractedField.field_name == field_config["name"]
                    ).first()

                    if existing_field:
                        # Update existing field
                        if field_config["type"] in ["array", "table", "array_of_objects"]:
                            existing_field.field_value_json = extracted_value
                        else:
                            existing_field.field_value = str(extracted_value) if extracted_value else None
                        existing_field.confidence_score = confidence
                        existing_field.field_type = field_config["type"]
                        existing_field.source_page = source_page
                        existing_field.source_bbox = source_bbox
                        existing_field.needs_verification = (confidence < 0.6) if confidence else False
                    else:
                        # Create new field with bbox data
                        if field_config["type"] in ["array", "table", "array_of_objects"]:
                            new_field = ExtractedField(
                                document_id=doc.id,
                                field_name=field_config["name"],
                                field_type=field_config["type"],
                                field_value_json=extracted_value,
                                confidence_score=confidence,
                                needs_verification=(confidence < 0.6) if confidence else False,
                                source_page=source_page,
                                source_bbox=source_bbox
                            )
                        else:
                            new_field = ExtractedField(
                                document_id=doc.id,
                                field_name=field_config["name"],
                                field_type=field_config["type"],
                                field_value=str(extracted_value) if extracted_value else None,
                                confidence_score=confidence,
                                needs_verification=(confidence < 0.6) if confidence else False,
                                source_page=source_page,
                                source_bbox=source_bbox
                            )
                        db.add(new_field)

                    # Update Elasticsearch if schema and index exist
                    if schema:
                        try:
                            # Create ES service with schema-specific index
                            es_service = PostgresService(db)
                            es_service.index_name = f"docs_{schema.name.lower().replace(' ', '_')}"

                            await es_service.update_document(
                                document_id=doc.id,
                                updated_fields={field_config["name"]: extracted_value}
                            )
                        except Exception as es_error:
                            logger.warning(f"Failed to update ES for doc {doc.id}: {es_error}")
                            # Don't fail the job if ES update fails

                    # If low confidence, add to audit queue
                    if confidence < 0.6:
                        low_confidence_count += 1

                        # Check if verification already exists
                        existing_verification = db.query(Verification)\
                            .filter(
                                Verification.document_id == doc.id,
                                Verification.field_name == field_config["name"]
                            ).first()

                        if not existing_verification:
                            verification = Verification(
                                document_id=doc.id,
                                field_name=field_config["name"],
                                extracted_value=str(extracted_value) if extracted_value else None,
                                confidence=confidence,
                                status="pending"
                            )
                            db.add(verification)

                    successful += 1
                    logger.debug(f"Extracted {field_config['name']} from doc {doc.id}: "
                               f"{extracted_value} (confidence: {confidence:.2f})")

                except Exception as e:
                    logger.error(f"Error extracting field for document {doc.id}: {e}")
                    failed += 1

                # Update progress every document
                job = db.query(BackgroundJob).filter(BackgroundJob.id == background_job_id).first()
                if job:
                    job.processed_items = i + 1
                    # Update job_data and mark as modified for SQLAlchemy
                    job.job_data["successful"] = successful
                    job.job_data["failed"] = failed
                    job.job_data["low_confidence"] = low_confidence_count
                    flag_modified(job, "job_data")
                    db.commit()

            # Mark job as completed
            job = db.query(BackgroundJob).filter(BackgroundJob.id == background_job_id).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                # Update job_data and mark as modified for SQLAlchemy
                job.job_data["completed_at"] = datetime.utcnow().isoformat()
                job.job_data["success_rate"] = successful / len(documents) if documents else 0
                flag_modified(job, "job_data")
                db.commit()

                logger.info(f"Field extraction completed: {field_config['name']} "
                          f"({successful} successful, {failed} failed, "
                          f"{low_confidence_count} low confidence)")

        except Exception as e:
            logger.error(f"Fatal error in field extraction job {background_job_id}: {e}")
            job = db.query(BackgroundJob).filter(BackgroundJob.id == background_job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()

        finally:
            db.close()

    async def get_job_status(self, job_id: int, db: Session) -> Dict[str, Any]:
        """
        Get status of a background job

        Args:
            job_id: Background job ID
            db: Database session

        Returns:
            Job status dictionary
        """
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        return job.to_dict()

    async def cancel_job(self, job_id: int, db: Session) -> bool:
        """
        Cancel a running background job

        Note: This just marks the job as cancelled. The actual task
        may continue running until it checks the status.

        Args:
            job_id: Background job ID
            db: Database session

        Returns:
            True if cancelled, False if already completed/failed
        """
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status in ["completed", "failed", "cancelled"]:
            return False

        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Cancelled job {job_id}")
        return True
