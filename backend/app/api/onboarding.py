import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.models.schema import Schema
from app.services.claude_service import ClaudeService
from app.services.postgres_service import PostgresService
from app.services.reducto_service import ReductoService
from app.utils.reducto_validation import format_validation_report, validate_schema_for_reducto

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class ModifySchemaRequest(BaseModel):
    prompt: str
    current_fields: List[Dict[str, Any]]


@router.post("/analyze-samples")
async def analyze_samples(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Analyze sample documents and generate extraction schema

    Steps:
    1. Save uploaded files temporarily
    2. Parse each with Reducto
    3. Send to Claude for schema generation
    4. Store schema in database
    5. Create Elasticsearch index
    """
    if len(files) < 1:
        raise HTTPException(
            status_code=400,
            detail="Please upload at least 1 sample document"
        )

    if len(files) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 sample documents allowed"
        )

    reducto_service = ReductoService()
    claude_service = ClaudeService()
    postgres_service = PostgresService(db)

    parsed_documents = []
    temp_files = []

    try:
        # Step 1 & 2: Save files and parse with Reducto
        logger.info(f"Processing {len(files)} sample documents")

        for file in files:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                tmp.write(content)
                temp_files.append(tmp.name)

                # Parse with Reducto
                logger.info(f"Parsing: {file.filename}")
                parsed = await reducto_service.parse_document(tmp.name)
                parsed_documents.append(parsed)

        # Step 3: Generate schema with Claude
        logger.info("Generating schema with Claude")
        schema_data = await claude_service.analyze_sample_documents(parsed_documents)

        # NEW: Validate schema against Reducto requirements
        validation_result = validate_schema_for_reducto(
            {
                "name": schema_data["name"],
                "fields": schema_data["fields"]
            },
            strict=False
        )

        # Log validation results
        if not validation_result["reducto_compatible"]:
            logger.warning(
                f"Schema '{schema_data['name']}' has Reducto compatibility issues: "
                f"{len(validation_result['errors'])} errors, {len(validation_result['warnings'])} warnings"
            )
            logger.debug(format_validation_report(validation_result))
        else:
            logger.info(f"Schema '{schema_data['name']}' is Reducto-compatible")

        # Step 4: Store schema in database
        schema_name = schema_data["name"]
        existing_schema = db.query(Schema).filter(Schema.name == schema_name).first()

        if existing_schema:
            # Update existing schema
            existing_schema.fields = schema_data["fields"]
            existing_schema.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Updated existing schema: {schema_name}")
            schema_id = existing_schema.id
        else:
            # Create new schema
            new_schema = Schema(
                name=schema_name,
                fields=schema_data["fields"]
            )
            db.add(new_schema)
            db.commit()
            db.refresh(new_schema)
            logger.info(f"Created new schema: {schema_name}")
            schema_id = new_schema.id

        # Step 5: Create Elasticsearch index
        await elastic_service.create_index(schema_data)

        # Generate Reducto config for future extractions
        reducto_config = await claude_service.generate_reducto_config(schema_data)

        return {
            "success": True,
            "schema_id": schema_id,
            "schema": schema_data,
            "reducto_config": reducto_config,
            # NEW: Include validation results
            "reducto_validation": {
                "compatible": validation_result["reducto_compatible"],
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"],
                "recommendations": validation_result["recommendations"]
            },
            "message": f"Schema '{schema_name}' created successfully" +
                       (f" ⚠️ {len(validation_result['errors'])} Reducto compatibility issues" if validation_result['errors'] else "")
        }

    except Exception as e:
        logger.error(f"Error analyzing samples: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup temp files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass


@router.get("/schemas")
async def list_schemas(db: Session = Depends(get_db)):
    """List all available schemas"""
    schemas = db.query(Schema).all()
    return {
        "schemas": [
            {
                "id": schema.id,
                "name": schema.name,
                "field_count": len(schema.fields),
                "created_at": schema.created_at,
                "updated_at": schema.updated_at
            }
            for schema in schemas
        ]
    }


@router.post("/schemas")
async def create_schema(
    schema_data: dict,
    db: Session = Depends(get_db)
):
    """Create a new schema (e.g., when saving as new template)"""
    name = schema_data.get("name")
    fields = schema_data.get("fields")

    if not name or not fields:
        raise HTTPException(status_code=400, detail="Name and fields are required")

    # Check if schema with this name already exists
    existing = db.query(Schema).filter(Schema.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Schema '{name}' already exists")

    # NEW: Validate schema against Reducto requirements
    validation_result = validate_schema_for_reducto(
        {
            "name": name,
            "fields": fields
        },
        strict=False
    )

    # Log validation results
    if not validation_result["reducto_compatible"]:
        logger.warning(
            f"Creating schema '{name}' with Reducto compatibility issues: "
            f"{len(validation_result['errors'])} errors, {len(validation_result['warnings'])} warnings"
        )
        logger.debug(format_validation_report(validation_result))
    else:
        logger.info(f"Schema '{name}' is Reducto-compatible")

    # Create new schema
    new_schema = Schema(
        name=name,
        fields=fields
    )
    db.add(new_schema)
    db.commit()
    db.refresh(new_schema)

    # Create Elasticsearch index
    try:
        postgres_service = PostgresService(db)
        await elastic_service.create_index({
            "name": new_schema.name,
            "fields": new_schema.fields
        })
        logger.info(f"Created Elasticsearch index for schema {new_schema.id}")
    except Exception as e:
        logger.warning(f"Failed to create Elasticsearch index: {e}")

    return {
        "success": True,
        "schema_id": new_schema.id,
        # NEW: Include validation results
        "reducto_validation": {
            "compatible": validation_result["reducto_compatible"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "recommendations": validation_result["recommendations"]
        },
        "message": f"Schema '{name}' created successfully" +
                   (f" ⚠️ {len(validation_result['errors'])} Reducto compatibility issues" if validation_result['errors'] else "")
    }


@router.get("/schemas/{schema_id}")
async def get_schema(schema_id: int, db: Session = Depends(get_db)):
    """Get schema details"""
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    return {
        "id": schema.id,
        "name": schema.name,
        "fields": schema.fields,
        "created_at": schema.created_at,
        "updated_at": schema.updated_at
    }


@router.get("/schemas/{schema_id}/document-count")
async def get_schema_document_count(schema_id: int, db: Session = Depends(get_db)):
    """Get count of documents using this schema"""
    from app.models.document import Document

    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    document_count = db.query(Document).filter(Document.schema_id == schema_id).count()

    return {
        "schema_id": schema_id,
        "schema_name": schema.name,
        "document_count": document_count
    }


@router.put("/schemas/{schema_id}")
async def update_schema(
    schema_id: int,
    schema_data: dict,
    db: Session = Depends(get_db)
):
    """Update schema fields (after manual editing)"""
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    schema.fields = schema_data.get("fields", schema.fields)
    schema.updated_at = datetime.utcnow()
    db.commit()

    # Update Elasticsearch mapping (optional - may not be running in dev)
    try:
        postgres_service = PostgresService(db)
        await elastic_service.create_index({
            "name": schema.name,
            "fields": schema.fields
        })
        logger.info(f"Updated Elasticsearch index for schema {schema_id}")
    except Exception as e:
        logger.warning(f"Failed to update Elasticsearch index: {e}. Continuing without search functionality.")

    return {
        "success": True,
        "message": "Schema updated successfully"
    }


@router.post("/schemas/{schema_id}/re-extract")
async def re_extract_documents(
    schema_id: int,
    db: Session = Depends(get_db)
):
    """
    Re-extract all documents using this schema after template changes
    Updates all documents with new field definitions
    """
    from app.api.documents import process_single_document
    from app.models.document import Document

    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    # Get all documents using this schema
    documents = db.query(Document).filter(Document.schema_id == schema_id).all()

    if not documents:
        return {
            "success": True,
            "message": "No documents to re-extract",
            "processed_count": 0
        }

    # Re-process each document
    processed_count = 0
    errors = []

    for doc in documents:
        try:
            # Reset status to processing
            doc.status = "processing"
            db.commit()

            # Trigger re-extraction
            await process_single_document(doc.id)
            processed_count += 1
            logger.info(f"Re-extracted document {doc.id}: {doc.filename}")

        except Exception as e:
            error_msg = f"Failed to re-extract {doc.filename}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            doc.status = "error"
            doc.error_message = str(e)
            db.commit()

    return {
        "success": True,
        "message": f"Re-extracted {processed_count} documents",
        "processed_count": processed_count,
        "total_documents": len(documents),
        "errors": errors if errors else None
    }


@router.post("/schemas/{schema_id}/add-field")
async def add_field_from_description(
    schema_id: int,
    description: dict,
    db: Session = Depends(get_db)
):
    """Add a field using natural language description"""
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    claude_service = ClaudeService()
    field_config = await claude_service.suggest_field_from_description(
        description.get("description", "")
    )

    # Add field to schema
    schema.fields.append(field_config)
    schema.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "field": field_config
    }


@router.post("/schemas/{schema_id}/modify-with-prompt")
async def modify_schema_with_prompt(
    schema_id: int,
    request_data: dict,
    db: Session = Depends(get_db)
):
    """Modify schema fields using natural language prompt"""
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    prompt = request_data.get("prompt", "")
    current_fields = request_data.get("current_fields", schema.fields)

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    claude_service = ClaudeService()
    modified_fields = await claude_service.modify_schema_with_prompt(
        prompt=prompt,
        current_fields=current_fields
    )

    # Update schema
    schema.fields = modified_fields
    schema.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "fields": modified_fields
    }


@router.post("/modify-schema-prompt")
async def modify_schema_with_prompt(
    request: ModifySchemaRequest,
    db: Session = Depends(get_db)
):
    """
    Modify schema fields using natural language prompt
    No schema_id required - just modifies the fields based on prompt
    """
    claude_service = ClaudeService()

    try:
        modified_fields = await claude_service.modify_schema_with_prompt(
            prompt=request.prompt,
            current_fields=request.current_fields
        )

        return {
            "success": True,
            "fields": modified_fields
        }
    except Exception as e:
        logger.error(f"Error modifying schema with prompt: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to modify schema: {str(e)}"
        )


@router.post("/schemas/{schema_id}/fields/suggest")
async def suggest_field_from_description(
    schema_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Step 1: Analyze existing docs and suggest field definition

    Request body:
        {
            "description": "I want to extract payment terms like Net 30"
        }

    Returns:
        {
            "field": {...field_config...},
            "sample_extractions": [...],
            "estimated_success_rate": 0.80,
            "estimated_cost": 2.34,
            "estimated_time_seconds": 120,
            "total_documents": 234
        }
    """
    from app.models.document import Document

    description = request.get("description", "")
    if not description:
        raise HTTPException(status_code=400, detail="Description required")

    # Get schema
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    # Get 3-5 sample documents with parse results
    sample_docs = db.query(Document)\
        .filter(Document.schema_id == schema_id)\
        .limit(5)\
        .all()

    if not sample_docs:
        raise HTTPException(
            status_code=400,
            detail="No documents found for this schema. Upload documents first."
        )

    # Get parsed documents (prefer PhysicalFile, fallback to legacy)
    parsed_samples = []
    for doc in sample_docs:
        if doc.physical_file and doc.physical_file.reducto_parse_result:
            parsed_samples.append(doc.physical_file.reducto_parse_result)
        elif hasattr(doc, 'reducto_parse_result') and doc.reducto_parse_result:
            parsed_samples.append(doc.reducto_parse_result)

    if not parsed_samples:
        raise HTTPException(
            status_code=400,
            detail="No parsed documents available. Documents may still be processing."
        )

    # Get total document count
    total_docs = db.query(Document)\
        .filter(Document.schema_id == schema_id)\
        .count()

    # Call Claude to suggest field
    claude_service = ClaudeService()
    try:
        suggestion = await claude_service.suggest_field_from_existing_docs(
            user_description=description,
            sample_documents=parsed_samples,
            total_document_count=total_docs
        )

        logger.info(f"Suggested field '{suggestion['field']['name']}' for schema {schema_id}")

        return suggestion

    except Exception as e:
        logger.error(f"Error suggesting field: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to suggest field: {str(e)}"
        )


@router.post("/schemas/{schema_id}/fields/add")
async def add_field_and_extract(
    schema_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Step 2: Add field to schema and optionally extract from existing docs

    Request body:
        {
            "field": {
                "name": "payment_terms",
                "type": "text",
                "description": "...",
                "extraction_hints": ["..."],
                "confidence_threshold": 0.75,
                "required": false
            },
            "extract_from_existing": true
        }

    Returns:
        {
            "success": true,
            "field": {...},
            "extraction_job_id": 123  // if extract_from_existing=true
        }
    """
    from app.services.field_extraction_service import FieldExtractionService

    field_config = request.get("field")
    extract_from_existing = request.get("extract_from_existing", False)

    if not field_config:
        raise HTTPException(status_code=400, detail="Field config required")

    # Validate field_config has required fields
    if "name" not in field_config or "type" not in field_config:
        raise HTTPException(
            status_code=400,
            detail="Field must have 'name' and 'type'"
        )

    # Get schema
    schema = db.query(Schema).filter(Schema.id == schema_id).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    # Check if field name already exists
    existing_fields = schema.fields or []
    if any(f["name"] == field_config["name"] for f in existing_fields):
        raise HTTPException(
            status_code=400,
            detail=f"Field '{field_config['name']}' already exists in this schema"
        )

    # Add field to schema
    schema.fields.append(field_config)
    flag_modified(schema, "fields")  # Mark JSON field as modified for SQLAlchemy
    schema.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"Added field '{field_config['name']}' to schema {schema_id}")

    # Update Elasticsearch mapping
    try:
        postgres_service = PostgresService(db)
        # For now, we'll recreate the index with the new field
        # In future, could use _mapping API to add field dynamically
        await elastic_service.create_index({
            "name": schema.name,
            "fields": schema.fields
        })
        logger.info(f"Updated Elasticsearch mapping for schema {schema_id}")
    except Exception as e:
        logger.warning(f"Failed to update Elasticsearch mapping: {e}")
        # Don't fail the request if ES update fails

    # Extract from existing docs if requested
    job_id = None
    if extract_from_existing:
        extraction_service = FieldExtractionService()
        job = await extraction_service.extract_field_from_all_docs(
            schema_id=schema_id,  # Fixed: use schema_id, not template_id
            field_config=field_config,
            db=db
        )
        job_id = job.id
        logger.info(f"Started field extraction job {job_id} for schema {schema_id}")

    return {
        "success": True,
        "field": field_config,
        "extraction_job_id": job_id
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get status of a background job

    Returns:
        {
            "id": 123,
            "type": "field_extraction",
            "status": "running",
            "total_items": 234,
            "processed_items": 45,
            "progress": 0.19,
            "metadata": {...},
            "created_at": "...",
            "updated_at": "...",
            "completed_at": null,
            "error_message": null
        }
    """
    from app.services.field_extraction_service import FieldExtractionService

    extraction_service = FieldExtractionService()
    try:
        status = await extraction_service.get_job_status(job_id, db)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """
    Cancel a running background job

    Returns:
        {
            "success": true,
            "message": "Job cancelled"
        }
    """
    from app.services.field_extraction_service import FieldExtractionService

    extraction_service = FieldExtractionService()
    try:
        cancelled = await extraction_service.cancel_job(job_id, db)
        if cancelled:
            return {"success": True, "message": "Job cancelled"}
        else:
            return {
                "success": False,
                "message": "Job already completed or failed"
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
