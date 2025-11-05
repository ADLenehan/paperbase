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
    from app.services.citation_service import CitationService

    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return

        schema = db.query(Schema).filter(Schema.id == document.schema_id).first()

        reducto_service = ReductoService()
        elastic_service = ElasticsearchService()
        citation_service = CitationService()

        logger.info(f"Processing document {document_id}: {document.filename}")

        # Build Reducto schema from our schema fields
        reducto_schema = {
            "type": "object",
            "properties": {}
        }

        for field_def in schema.fields:
            field_name = field_def["name"]
            field_type = field_def.get("type", "string")

            # Map our types to JSON schema types
            json_type = {
                "text": "string",
                "date": "string",
                "number": "number",
                "boolean": "boolean"
            }.get(field_type, "string")

            reducto_schema["properties"][field_name] = {
                "type": json_type,
                "description": field_def.get("description", "")
            }

        # PIPELINE: Use Reducto's structured extraction with job_id if available
        extraction_result = None
        if document.reducto_job_id:
            try:
                # Try pipelined extraction (jobid://) - NO re-upload or re-parse!
                logger.info(f"Using pipelined extraction with job_id: {document.reducto_job_id}")
                extraction_result = await reducto_service.extract_structured(
                    schema=reducto_schema,
                    job_id=document.reducto_job_id
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
            logger.info(f"Extracting from file: {document.file_path}")
            extraction_result = await reducto_service.extract_structured(
                schema=reducto_schema,
                file_path=document.file_path
            )

            # Store new job_id from this extraction for future use
            if extraction_result.get("job_id"):
                document.reducto_job_id = extraction_result["job_id"]
                logger.info(f"Stored new job_id for future pipeline use: {document.reducto_job_id}")

        # Process extraction results
        extracted_fields = {}
        confidence_scores = {}

        extractions = extraction_result.get("extractions", {})

        # Handle both list and dict formats from Reducto
        if isinstance(extractions, list):
            # List format from Reducto: [{"field1": "value1", "field2": "value2"}]
            # or [{"field1": {"value": "...", "confidence": 0.9}}]
            # Take the first item (should be only one)
            if len(extractions) > 0 and isinstance(extractions[0], dict):
                extractions = extractions[0]  # Convert to dict format
            else:
                extractions = {}

        # Now process as dict - handle both simple values and nested dicts
        if isinstance(extractions, dict):
            for field_name, field_data in extractions.items():
                # Check if value is nested dict with confidence
                if isinstance(field_data, dict) and ("value" in field_data or "content" in field_data):
                    # Dict format: {"field1": {"value": "...", "confidence": 0.9, "source_page": 1, "source_bbox": [...]}, ...}
                    value = field_data.get("value", field_data.get("content", ""))
                    confidence = field_data.get("confidence", field_data.get("score", 0.85))
                    source_page = field_data.get("source_page")
                    source_bbox = field_data.get("source_bbox")
                else:
                    # Simple value format: {"field1": "value1", "field2": "value2"}
                    value = str(field_data) if field_data is not None else ""
                    confidence = 0.85  # Default confidence for simple values
                    source_page = None
                    source_bbox = None

                if value:
                    extracted_fields[field_name] = str(value)
                    confidence_scores[field_name] = confidence

                    # Create ExtractedField record
                    needs_verification = confidence < settings.CONFIDENCE_THRESHOLD_LOW

                    # NEW: Find source text and context for citations (MCP-friendly)
                    source_text = None
                    context_before = None
                    context_after = None
                    source_block_ids = []

                    # Try to get parse result for source text extraction
                    if document.reducto_parse_result:
                        try:
                            # Find source block in parse result
                            source_block = citation_service.find_source_block_for_extraction(
                                field_name=field_name,
                                field_value=str(value),
                                parse_result=document.reducto_parse_result,
                                bbox=source_bbox,
                                page=source_page
                            )

                            if source_block:
                                # Extract source text and context
                                all_blocks = document.reducto_parse_result.get("chunks", [])
                                source_text, context_before, context_after = citation_service.extract_source_text_and_context(
                                    block=source_block,
                                    all_blocks=all_blocks
                                )
                                source_block_ids = [source_block.get("id")]
                                logger.debug(f"Found source text for {field_name}: {source_text[:50]}...")
                        except Exception as e:
                            logger.warning(f"Could not extract source text for {field_name}: {e}")

                    extracted_field = ExtractedField(
                        document_id=document.id,
                        field_name=field_name,
                        field_value=str(value),
                        confidence_score=confidence,
                        needs_verification=needs_verification,
                        source_page=source_page,
                        source_bbox=source_bbox,
                        # NEW: Citation fields for MCP
                        source_text=source_text,
                        context_before=context_before,
                        context_after=context_after,
                        source_block_ids=source_block_ids,
                        extraction_method="reducto_structured"
                    )
                    db.add(extracted_field)

        logger.info(f"Extracted {len(extracted_fields)} fields from document {document_id}")

        # Index in Elasticsearch (optional - may not be running in dev)
        es_id = None
        try:
            # PIPELINE: Use cached parse result if available
            if document.reducto_parse_result:
                logger.info(f"Using cached parse result for ES indexing")
                parse_result = document.reducto_parse_result
            else:
                # Parse document to get full text for search
                parsed_result = await reducto_service.parse_document(document.file_path)
                parse_result = parsed_result["result"]
                # Cache for future use
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
        logger.error(f"Error processing document {document_id}: {e}")
        document.status = "error"
        document.error_message = str(e)
        db.commit()

    finally:
        db.close()


@router.get("")
async def list_documents(
    schema_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 100,
    db: Session = Depends(get_db)
):
    """List documents with optional filters"""

    query = db.query(Document).order_by(Document.uploaded_at.desc())

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
        "suggested_template_id": document.suggested_template_id,
        "template_confidence": document.template_confidence,
        "extracted_fields": extracted_fields_dict,
        "confidence_scores": confidence_scores_dict,
        "fields": [
            {
                "id": field.id,
                "name": field.field_name,
                "value": field.field_value,
                "confidence": field.confidence_score,
                "needs_verification": field.needs_verification,
                "verified": field.verified
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
