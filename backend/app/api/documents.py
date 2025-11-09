from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.config import settings
from app.models.schema import Schema
from app.models.template import SchemaTemplate
from app.models.document import Document, ExtractedField
from app.services.reducto_service import ReductoService
from app.services.elastic_service import ElasticsearchService
from app.utils.bbox_utils import normalize_bbox
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_documents(
    schema_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Upload documents for processing"""

    # Verify schema exists
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    # Create upload directory if not exists
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    uploaded_docs = []

    for file in files:
        # Save file
        file_path = os.path.join(upload_dir, f"{datetime.utcnow().timestamp()}_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create document record
        document = Document(
            schema_id=schema_id,
            filename=file.filename,
            file_path=file_path,
            status="pending"
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        uploaded_docs.append({
            "id": document.id,
            "filename": document.filename,
            "status": document.status
        })

        logger.info(f"Uploaded document: {file.filename} (ID: {document.id})")

    return {
        "success": True,
        "documents": uploaded_docs,
        "message": f"Uploaded {len(uploaded_docs)} documents"
    }


@router.post("/process")
async def process_documents(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process uploaded documents with Reducto extraction"""

    document_ids = request.get("document_ids", [])
    if not document_ids:
        raise HTTPException(status_code=400, detail="document_ids required")

    documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found")

    # Add processing tasks to background
    for doc in documents:
        background_tasks.add_task(process_single_document, doc.id)
        doc.status = "processing"

    db.commit()

    return {
        "success": True,
        "message": f"Processing {len(documents)} documents in background"
    }


async def process_single_document(document_id: int):
    """Background task to process a single document"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return

        schema = db.query(Schema).filter(Schema.id == document.schema_id).first()

        reducto_service = ReductoService()
        elastic_service = ElasticsearchService()

        logger.info(f"Processing document {document_id}: {document.filename}")

        # Build Reducto schema from our schema fields
        reducto_schema = {
            "type": "object",
            "properties": {}
        }

        for field_def in schema.fields:
            field_name = field_def["name"]
            field_type = field_def.get("type", "string")
            description = field_def.get("description", "")
            extraction_hints = field_def.get("extraction_hints", [])

            # Map our types to JSON schema types (including complex types)
            json_type = {
                "text": "string",
                "date": "string",
                "number": "number",
                "boolean": "boolean",
                "array": "array",
                "table": "array",  # Tables are arrays of objects
                "array_of_objects": "array"  # Arrays of objects
            }.get(field_type, "string")

            # Enhance description with extraction hints to guide Reducto
            if extraction_hints:
                # Add first 3 hints to help Reducto locate the field
                hints_text = ", ".join(f'"{hint}"' for hint in extraction_hints[:3])
                enhanced_description = f"{description}. Look for labels or patterns like: {hints_text}"
            else:
                enhanced_description = description

            reducto_schema["properties"][field_name] = {
                "type": json_type,
                "description": enhanced_description
            }

        # Log schema for debugging
        field_names = list(reducto_schema["properties"].keys())
        logger.info(f"Extraction schema for {document.filename}: {len(field_names)} fields")
        logger.debug(f"Field names: {field_names}")
        if field_names:
            sample_field = list(reducto_schema["properties"].values())[0]
            logger.debug(f"Sample field schema: {sample_field}")

        # PIPELINE: Use Reducto's structured extraction with job_id if available
        # Use actual_* properties (supports both PhysicalFile and legacy)
        job_id = document.actual_job_id
        file_path = document.actual_file_path

        extraction_result = None
        if job_id:
            try:
                # Try pipelined extraction (jobid://) - NO re-upload or re-parse!
                logger.info(f"Using pipelined extraction with job_id: {job_id}")
                extraction_result = await reducto_service.extract_structured(
                    schema=reducto_schema,
                    job_id=job_id
                )
            except Exception as e:
                # Job ID expired or invalid, clear it and fall back to file upload
                error_msg = str(e).lower()
                # Check for various error patterns indicating expired/missing job
                job_expired = any(pattern in error_msg for pattern in [
                    "job not found",
                    "parse job not found",
                    "expired",
                    "invalid job",
                    "job id expired",
                    "job does not exist"
                ])

                if job_expired:
                    logger.warning(f"Job ID expired/invalid: {error_msg}. Clearing and retrying with file upload.")
                    # Clear job ID (prefer PhysicalFile if available)
                    if document.physical_file:
                        document.physical_file.reducto_job_id = None
                        document.physical_file.reducto_parse_result = None
                    else:
                        document.reducto_job_id = None
                        document.reducto_parse_result = None
                    db.commit()
                    # Don't re-raise, fall through to file upload
                else:
                    # Different error, re-raise
                    logger.error(f"Extraction failed with non-job-related error: {error_msg}")
                    raise

        if extraction_result is None:
            # Fallback: extract with file_path (will upload and parse)
            logger.info(f"Extracting from file: {file_path}")
            extraction_result = await reducto_service.extract_structured(
                schema=reducto_schema,
                file_path=file_path
            )

            # Store new job_id from this extraction for future use
            if extraction_result.get("job_id"):
                new_job_id = extraction_result["job_id"]
                # Store in PhysicalFile if available, otherwise legacy fields
                if document.physical_file:
                    document.physical_file.reducto_job_id = new_job_id
                else:
                    document.reducto_job_id = new_job_id
                logger.info(f"Stored new job_id for future pipeline use: {new_job_id}")

        # Process extraction results
        extracted_fields = {}
        confidence_scores = {}

        extractions = extraction_result.get("extractions", {})

        # Warn if Reducto returned empty results
        if not extractions or (isinstance(extractions, (list, dict)) and len(extractions) == 0):
            logger.warning(
                f"⚠️  Reducto returned ZERO extractions for {document.filename}. "
                f"Schema had {len(reducto_schema['properties'])} fields. "
                f"This may indicate schema format issues or content mismatch."
            )
            # Log raw response for debugging
            logger.debug(f"Raw extraction result: {extraction_result}")

        # Handle both list and dict formats from Reducto
        if isinstance(extractions, list):
            # List format from Reducto: [{"field1": "value1", "field2": "value2"}]
            # or [{"field1": {"value": "...", "confidence": 0.9}}]
            # Take the first item (should be only one)
            if len(extractions) > 0 and isinstance(extractions[0], dict):
                extractions = extractions[0]  # Convert to dict format
            else:
                extractions = {}

        # Validate extracted fields BEFORE processing (NEW)
        validation_results = {}
        if isinstance(extractions, dict) and extractions:
            from app.services.validation_service import ExtractionValidator, should_flag_for_review

            # Prepare extractions dict for validation
            extractions_for_validation = {}
            for field_name, field_data in extractions.items():
                if isinstance(field_data, dict) and ("value" in field_data or "content" in field_data):
                    value = field_data.get("value", field_data.get("content", ""))
                    confidence = field_data.get("confidence", field_data.get("score", 0.85))
                else:
                    value = field_data
                    confidence = 0.85

                extractions_for_validation[field_name] = {
                    "value": value,
                    "confidence": confidence
                }

            # Run validation
            validator = ExtractionValidator()
            template_name = schema.name if schema else "unknown"
            validation_results = await validator.validate_extraction(
                extractions=extractions_for_validation,
                template_name=template_name,
                schema_config=schema.fields if schema else None
            )
            logger.info(f"Validated {len(validation_results)} fields for document {document_id}")

        # Now process as dict - handle both simple values and nested dicts
        if isinstance(extractions, dict):
            logger.info(f"Processing {len(extractions)} extracted fields for document {document_id}")
            for field_name, field_data in extractions.items():
                # Get field type from schema
                field_def = next((f for f in schema.fields if f["name"] == field_name), None)
                field_type = field_def.get("type", "text") if field_def else "text"

                # Check if value is nested dict with confidence
                if isinstance(field_data, dict) and ("value" in field_data or "content" in field_data):
                    # Dict format: {"field1": {"value": "...", "confidence": 0.9, "source_page": 1, "source_bbox": [...]}, ...}
                    value = field_data.get("value", field_data.get("content", ""))
                    confidence = field_data.get("confidence", field_data.get("score", 0.85))
                    source_page = field_data.get("source_page")
                    source_bbox = field_data.get("source_bbox")
                    logger.debug(f"  Field '{field_name}': value='{value}', confidence={confidence}")
                else:
                    # Simple value format: {"field1": "value1", "field2": "value2"}
                    value = field_data if field_data is not None else ""
                    confidence = 0.85  # Default confidence for simple values
                    source_page = None
                    source_bbox = None
                    logger.debug(f"  Field '{field_name}' (simple): value='{value}'")

                # Critical debug: Check why fields aren't being saved
                logger.info(f"  Checking field '{field_name}': value='{value}' (type={type(value)}, truthy={bool(value)})")

                if value:
                    # Get validation result for this field (NEW)
                    validation_result = validation_results.get(field_name)
                    validation_status = validation_result.status if validation_result else "valid"

                    # Determine if field needs verification (combines confidence + validation)
                    from app.services.validation_service import should_flag_for_review
                    needs_verification = should_flag_for_review(confidence, validation_status)

                    # Log validation issues
                    if validation_result and validation_result.errors:
                        logger.warning(
                            f"Field '{field_name}' has validation errors: {', '.join(validation_result.errors)}"
                        )

                    # Handle complex types (array, table, array_of_objects) vs simple types
                    if field_type in ["array", "table", "array_of_objects"]:
                        # Store complex types in field_value_json
                        extracted_fields[field_name] = value  # Keep original structure for ES
                        confidence_scores[field_name] = confidence

                        extracted_field = ExtractedField(
                            document_id=document.id,
                            field_name=field_name,
                            field_type=field_type,
                            field_value_json=value,  # Store as JSON for complex types
                            confidence_score=confidence,
                            needs_verification=needs_verification,
                            source_page=source_page,
                            source_bbox=source_bbox,
                            # NEW: Validation metadata
                            validation_status=validation_status,
                            validation_errors=validation_result.errors if validation_result else [],
                            validation_checked_at=datetime.utcnow()
                        )
                    else:
                        # Store simple types in field_value
                        extracted_fields[field_name] = str(value)
                        confidence_scores[field_name] = confidence

                        extracted_field = ExtractedField(
                            document_id=document.id,
                            field_name=field_name,
                            field_type=field_type,
                            field_value=str(value),
                            confidence_score=confidence,
                            needs_verification=needs_verification,
                            source_page=source_page,
                            source_bbox=source_bbox,
                            # NEW: Validation metadata
                            validation_status=validation_status,
                            validation_errors=validation_result.errors if validation_result else [],
                            validation_checked_at=datetime.utcnow()
                        )

                    db.add(extracted_field)

        logger.info(f"Extracted {len(extracted_fields)} fields from document {document_id}")

        # Index in Elasticsearch (optional - may not be running in dev)
        es_id = None
        try:
            # PIPELINE: Use cached parse result if available
            # Use actual_parse_result property (supports both PhysicalFile and legacy)
            parse_result = document.actual_parse_result

            if parse_result:
                logger.info(f"Using cached parse result for ES indexing")
            else:
                # Parse document to get full text for search
                parsed_result = await reducto_service.parse_document(file_path)
                parse_result = parsed_result["result"]
                # Cache for future use (prefer PhysicalFile if available)
                if document.physical_file:
                    document.physical_file.reducto_job_id = parsed_result.get("job_id")
                    document.physical_file.reducto_parse_result = parse_result
                else:
                    document.reducto_job_id = parsed_result.get("job_id")
                    document.reducto_parse_result = parse_result

            # Reducto uses 'content' field for text, fallback to 'text'
            full_text = "\n".join([
                chunk.get("content", chunk.get("text", ""))
                for chunk in parse_result.get("chunks", [])
            ])

            es_id = await elastic_service.index_document(
                document_id=document.id,
                filename=document.filename,
                extracted_fields=extracted_fields,
                confidence_scores=confidence_scores,
                full_text=full_text
            )
            logger.info(f"Indexed document {document_id} in Elasticsearch: {es_id}")
        except Exception as e:
            logger.warning(f"Failed to index document {document_id} in Elasticsearch: {e}. Continuing without search functionality.")

        # Update document status
        document.status = "completed"
        document.processed_at = datetime.utcnow()
        document.elasticsearch_id = es_id

        db.commit()
        logger.info(f"Successfully processed document {document_id}")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error processing document {document_id}: {e}\n{error_details}")

        # Provide more helpful error messages
        error_message = str(e)
        if "job not found" in error_message.lower() or "expired" in error_message.lower():
            error_message = "Reducto job expired. Please retry - the file will be re-uploaded and parsed."
        elif "file" in error_message.lower() and "not found" in error_message.lower():
            error_message = f"File not found at path. Please retry the upload."
        elif "api" in error_message.lower() or "connection" in error_message.lower():
            error_message = "Reducto API connection failed. Please check your API key and try again."
        elif "schema" in error_message.lower():
            error_message = "Schema validation failed. Please check template field definitions."

        document.status = "error"
        document.error_message = error_message
        db.commit()

    finally:
        db.close()


@router.get("")
async def list_documents(
    schema_id: Optional[int] = None,
    status: Optional[str] = None,
    query_id: Optional[str] = None,
    page: int = 1,
    size: int = 100,
    db: Session = Depends(get_db)
):
    """
    List documents with optional filters

    Args:
        schema_id: Filter by schema/template ID
        status: Filter by document status
        query_id: Filter by documents used in a specific Ask AI query
        page: Page number (1-indexed)
        size: Results per page
    """

    query = db.query(Document).order_by(Document.uploaded_at.desc())

    # Query ID filter - show only documents used in this AI query
    query_context = None
    if query_id:
        from app.models.query_history import QueryHistory

        query_history = db.query(QueryHistory).filter(QueryHistory.id == query_id).first()
        if query_history:
            # Filter to only documents used in this query
            if query_history.document_ids:
                query = query.filter(Document.id.in_(query_history.document_ids))

                # Build context for frontend to display
                query_context = {
                    "query_id": query_id,
                    "query_text": query_history.query_text,
                    "answer": query_history.answer,
                    "created_at": query_history.created_at,
                    "source": query_history.query_source,
                    "document_count": len(query_history.document_ids)
                }
        else:
            # Invalid query_id - return empty result
            return {
                "total": 0,
                "page": page,
                "size": size,
                "documents": [],
                "query_context": None,
                "error": "Query not found"
            }

    if schema_id:
        query = query.filter(Document.schema_id == schema_id)

    if status:
        query = query.filter(Document.status == status)

    # Pagination
    offset = (page - 1) * size
    total = query.count()
    documents = query.offset(offset).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "query_context": query_context,  # NEW: Query context for frontend banner
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "uploaded_at": doc.uploaded_at,
                "processed_at": doc.processed_at,
                "schema_id": doc.schema_id,
                "suggested_template_id": doc.suggested_template_id,
                "template_confidence": doc.template_confidence,
                "error_message": doc.error_message,
                "schema": {
                    "name": doc.schema.name,
                    "id": doc.schema.id
                } if doc.schema else None,
                "lowest_confidence_field": (
                    lambda fields: {
                        "field_name": fields[0].field_name,
                        "confidence": fields[0].confidence_score
                    } if fields else None
                )(
                    sorted(
                        [ef for ef in doc.extracted_fields if ef.confidence_score is not None],
                        key=lambda ef: ef.confidence_score
                    )
                ),
                "has_low_confidence_fields": any(
                    ef.confidence_score < 0.6 for ef in doc.extracted_fields
                    if ef.confidence_score is not None
                ),
                "extracted_fields": [
                    {
                        "id": ef.id,
                        "field_name": ef.field_name,
                        "field_value": ef.field_value,
                        "confidence_score": ef.confidence_score,
                        "needs_verification": ef.needs_verification,
                        "verified": ef.verified
                    }
                    for ef in doc.extracted_fields
                ]
            }
            for doc in documents
        ]
    }


@router.get("/{document_id}")
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get document details with extractions"""

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    extracted_fields = db.query(ExtractedField).filter(
        ExtractedField.document_id == document_id
    ).all()

    # Get template/schema info
    schema = None
    template_name = None
    if document.schema_id:
        schema = db.query(Schema).filter(Schema.id == document.schema_id).first()
        if schema:
            template_name = schema.name

    # Build extracted_fields dict for verification component
    extracted_fields_dict = {field.field_name: field.field_value for field in extracted_fields}
    confidence_scores_dict = {field.field_name: field.confidence_score for field in extracted_fields}

    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "uploaded_at": document.uploaded_at,
        "processed_at": document.processed_at,
        "schema_id": document.schema_id,
        "template_id": document.schema_id,  # Alias for frontend compatibility
        "template_name": template_name,
        "file_path": document.actual_file_path,  # Use accessor property for dedup compatibility
        "suggested_template_id": document.suggested_template_id,
        "template_confidence": document.template_confidence,
        "extracted_fields": extracted_fields_dict,
        "confidence_scores": confidence_scores_dict,
        "fields": [
            {
                "id": field.id,
                "name": field.field_name,
                "value": field.field_value,
                "field_value_json": field.field_value_json,  # For complex types (match frontend expectation)
                "field_type": field.field_type,  # Field type
                "confidence": field.confidence_score,
                "needs_verification": field.needs_verification,
                "verified": field.verified,
                # Source information for PDF highlighting
                "source_page": field.source_page,
                "source_bbox": normalize_bbox(field.source_bbox),  # Convert dict to array
                # Validation metadata
                "validation_status": field.validation_status,
                "validation_errors": field.validation_errors or [],
                "audit_priority": field.audit_priority,
                "priority_label": field.priority_label
            }
            for field in extracted_fields
        ]
    }


@router.post("/{document_id}/assign-template")
async def assign_template(
    document_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """Assign a template/schema to a document with optional custom fields"""

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        template_id = request.get("template_id")
        if not template_id:
            raise HTTPException(status_code=400, detail="template_id required")

        # Verify template exists
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Use custom fields if provided, otherwise use template fields
        custom_fields = request.get("custom_fields")
        template_name = request.get("template_name")

        # Make schema name unique by appending document ID
        # This prevents UNIQUE constraint violations when assigning same template to multiple documents
        unique_schema_name = f"{template_name or template.name}_{document_id}"

        # Create schema from template for this document
        schema = Schema(
            name=unique_schema_name,
            fields=custom_fields if custom_fields else template.fields
        )
        db.add(schema)
        db.flush()

        # Assign schema to document
        document.schema_id = schema.id
        document.status = "ready_to_process"

        db.commit()
        db.refresh(document)

        logger.info(f"Assigned template {template_id} to document {document_id}, created schema {schema.id} with {len(schema.fields)} fields")

        return {
            "success": True,
            "document_id": document.id,
            "schema_id": schema.id,
            "message": "Template assigned successfully"
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning template to document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to assign template: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and its associated data"""

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get file path and physical_file reference BEFORE deleting (use accessor property for compatibility)
        file_path = document.actual_file_path
        physical_file = document.physical_file
        physical_file_id = document.physical_file_id

        # IMPORTANT: Count remaining documents BEFORE deleting this document
        remaining_docs_count = 0
        if physical_file_id:
            remaining_docs_count = db.query(Document).filter(
                Document.physical_file_id == physical_file_id,
                Document.id != document_id  # Exclude the document we're about to delete
            ).count()
            logger.info(f"Found {remaining_docs_count} other documents sharing physical_file_id {physical_file_id}")

        # NOTE: ExtractedField records will be deleted automatically via cascade="all, delete-orphan"
        # on the Document.extracted_fields relationship, so no need to manually delete them

        # Delete from Elasticsearch if indexed
        if document.elasticsearch_id:
            try:
                elastic_service = ElasticsearchService()
                await elastic_service.delete_document(document.elasticsearch_id)
                logger.info(f"Deleted document {document_id} from Elasticsearch")
            except Exception as e:
                logger.warning(f"Failed to delete document from Elasticsearch: {e}")

        # Delete the document record
        db.delete(document)
        db.commit()

        # Delete physical file if it exists and not shared with other documents
        if file_path and os.path.exists(file_path):
            # Check if file is shared with other documents (via PhysicalFile)
            if physical_file_id:
                # Only delete file if no other documents reference it
                if remaining_docs_count == 0:
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted physical file: {file_path}")

                        # Re-query PhysicalFile to avoid detached object issues
                        from app.models.physical_file import PhysicalFile
                        pf = db.query(PhysicalFile).filter(PhysicalFile.id == physical_file_id).first()
                        if pf:
                            db.delete(pf)
                            db.commit()
                            logger.info(f"Deleted PhysicalFile record: {physical_file_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete physical file or record: {e}")
                        db.rollback()
                else:
                    logger.info(f"Skipped deleting shared file (used by {remaining_docs_count} other documents)")
            else:
                # Legacy document without PhysicalFile - safe to delete
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted physical file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete physical file: {e}")

        logger.info(f"Successfully deleted document {document_id}")

        return {
            "success": True,
            "message": "Document deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        db.rollback()
        logger.error(f"Error deleting document {document_id}: {e}")
        logger.error(f"Full traceback: {error_trace}")

        # Return more specific error message
        error_msg = str(e)
        if "foreign key constraint" in error_msg.lower():
            error_msg = "Cannot delete: document has dependent records"
        elif "not found" in error_msg.lower():
            error_msg = "Document not found"

        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/{document_id}/verify")
async def mark_document_verified(
    document_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Mark a document as verified.

    This endpoint allows users to mark a document as verified/approved
    for use, even if some fields have low confidence scores.

    Args:
        document_id: ID of the document to verify
        request: { "force": bool } - If true, verify even if fields need review

    Returns:
        Success status and updated document status
    """
    try:
        # Get document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Check if force flag is needed
        force = request.get("force", False)

        # Count fields that need review (if any)
        from app.models.settings import Settings
        audit_threshold_setting = db.query(Settings).filter(
            Settings.key == "audit_confidence_threshold",
            Settings.level == "system"
        ).first()

        audit_threshold = float(audit_threshold_setting.value) if audit_threshold_setting else 0.6

        # Get all fields for this document
        fields = db.query(ExtractedField).filter(
            ExtractedField.document_id == document_id
        ).all()

        needs_review_count = sum(
            1 for field in fields
            if field.confidence_score and field.confidence_score < audit_threshold and not field.verified
        )

        # If fields need review and force is not set, return error
        if needs_review_count > 0 and not force:
            raise HTTPException(
                status_code=400,
                detail=f"{needs_review_count} fields need review before verification"
            )

        # Update document status to verified
        document.status = "verified"
        document.processed_at = datetime.utcnow()

        db.commit()

        # Update Elasticsearch to keep status in sync
        try:
            elastic_service = ElasticsearchService()
            await elastic_service.update_document(
                doc_id=document.elasticsearch_id,
                updates={"status": "verified"}
            )
            logger.info(f"Updated ES status for document {document_id} to verified")
        except Exception as e:
            logger.warning(
                f"Failed to update ES status for document {document_id}: {e}. "
                "SQLite updated successfully, ES will be eventually consistent."
            )
            # Don't fail the whole request - SQLite is source of truth, ES is secondary

        logger.info(
            f"Document {document_id} marked as verified "
            f"({needs_review_count} fields needed review, force={force})"
        )

        return {
            "success": True,
            "message": "Document marked as verified",
            "status": "verified",
            "fields_needing_review": needs_review_count
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error verifying document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
