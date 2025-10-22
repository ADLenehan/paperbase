from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.database import get_db
from app.models.schema import Schema
from app.services.reducto_service import ReductoService
from app.services.claude_service import ClaudeService
from app.services.elastic_service import ElasticsearchService
import logging
import os
import tempfile
from datetime import datetime

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
    elastic_service = ElasticsearchService()

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
            "message": f"Schema '{schema_name}' created successfully"
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
        elastic_service = ElasticsearchService()
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
        "message": f"Schema '{name}' created successfully"
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
        elastic_service = ElasticsearchService()
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
    from app.models.document import Document
    from app.api.documents import process_single_document

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
