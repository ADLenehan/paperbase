from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.models.document import Document, ExtractedField
from app.models.schema import Schema
from app.models.template import SchemaTemplate
from app.services.reducto_service import ReductoService
from app.services.claude_service import ClaudeService
from app.services.elastic_service import ElasticsearchService
from app.utils.file_organization import get_template_folder, organize_document_file
from app.utils.template_matching import hybrid_match_document
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bulk", tags=["bulk-upload"])


class ConfirmTemplateRequest(BaseModel):
    document_ids: List[int]
    template_id: int


class CreateTemplateRequest(BaseModel):
    document_ids: List[int]
    template_name: str


@router.post("/upload-and-analyze")
async def upload_and_analyze(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    New bulk upload flow:
    1. Upload all documents
    2. Parse with Reducto (extract text)
    3. Group similar documents with Claude
    4. Match groups to templates OR suggest creating new template

    Returns document groups with template suggestions
    """

    # Create upload directory (use 'unmatched' folder initially)
    upload_dir = get_template_folder(None)  # None = unmatched folder

    # Step 1: Upload and create document records
    uploaded_docs = []
    for file in files:
        # Save file to unmatched folder initially
        timestamp = datetime.utcnow().timestamp()
        file_path = os.path.join(upload_dir, f"{timestamp}_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create document record (no schema yet)
        document = Document(
            schema_id=None,  # Will be set after template matching
            filename=file.filename,
            file_path=file_path,
            status="uploaded"
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        uploaded_docs.append(document)
        logger.info(f"Uploaded: {file.filename} (ID: {document.id})")

    # Step 2: Parse documents with Reducto (PIPELINE: Save job_id for later extraction)
    reducto_service = ReductoService()
    parsed_docs = []

    for doc in uploaded_docs:
        try:
            doc.status = "analyzing"
            db.commit()

            # Parse and save job_id + results for pipelining
            parsed = await reducto_service.parse_document(doc.file_path)

            # PIPELINE: Store job_id and parse results to avoid re-parsing
            doc.reducto_job_id = parsed.get("job_id")
            doc.reducto_parse_result = parsed.get("result")
            db.commit()

            parsed_docs.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "parsed_data": parsed,
                "job_id": parsed.get("job_id")
            })
            logger.info(f"Parsed: {doc.filename} (job_id: {parsed.get('job_id')})")
        except Exception as e:
            logger.error(f"Failed to parse {doc.filename}: {e}")
            doc.status = "error"
            doc.error_message = str(e)
            db.commit()

    # Step 3: Group similar documents with Claude
    claude_service = ClaudeService()

    parsed_data_only = [p["parsed_data"] for p in parsed_docs]
    groups = await claude_service.analyze_documents_for_grouping(parsed_data_only)

    # Step 4: Match each group to templates using HYBRID matching (ES + Claude fallback)
    elastic_service = ElasticsearchService()
    available_templates = db.query(SchemaTemplate).all()
    template_data = []
    for template in available_templates:
        template_data.append({
            "id": template.id,
            "name": template.name,
            "category": template.category,
            "fields": template.fields
        })

    matched_groups = []
    claude_fallback_count = 0  # Track Claude usage for analytics

    for group in groups:
        # Get first document from group for template matching
        first_doc_idx = group["document_indices"][0]
        first_doc = uploaded_docs[first_doc_idx]

        # NEW: Use hybrid matching (ES first, Claude fallback)
        match_result = await hybrid_match_document(
            document=first_doc,
            elastic_service=elastic_service,
            claude_service=claude_service,
            available_templates=template_data,
            db=db
        )

        if match_result.get("match_source") == "claude":
            claude_fallback_count += 1

        # Get document IDs for this group
        doc_ids = [parsed_docs[idx]["document_id"] for idx in group["document_indices"]]

        matched_groups.append({
            "document_ids": doc_ids,
            "filenames": [parsed_docs[idx]["filename"] for idx in group["document_indices"]],
            "suggested_name": group["suggested_name"],
            "template_match": match_result,
            "common_fields": group["common_fields"]
        })

        # Update documents with template suggestion based on confidence
        for doc_id in doc_ids:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.suggested_template_id = match_result["template_id"]
                doc.template_confidence = match_result["confidence"]

                # Status based on confidence
                if match_result["template_id"]:
                    if match_result["confidence"] >= 0.75:
                        doc.status = "template_matched"
                    elif match_result["confidence"] >= 0.60:
                        doc.status = "template_suggested"  # Medium confidence - review recommended
                    else:
                        doc.status = "template_needed"
                else:
                    doc.status = "template_needed"

        db.commit()

    return {
        "success": True,
        "total_documents": len(uploaded_docs),
        "groups": matched_groups,
        "analytics": {
            "total_groups": len(matched_groups),
            "elasticsearch_matches": len(matched_groups) - claude_fallback_count,
            "claude_fallback_matches": claude_fallback_count,
            "cost_estimate": f"${claude_fallback_count * 0.01:.3f}"
        },
        "message": f"Uploaded and analyzed {len(uploaded_docs)} documents into {len(matched_groups)} groups"
    }


@router.post("/confirm-template")
async def confirm_template(
    request: ConfirmTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    User confirms template match for a group of documents
    Updates documents to use the confirmed template
    """

    # Verify template exists
    template = db.query(SchemaTemplate).filter(SchemaTemplate.id == request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Get or create schema from template
    schema = db.query(Schema).filter(
        Schema.name == template.name
    ).first()

    if not schema:
        # Create schema from template - copy fields as JSON
        schema = Schema(
            name=template.name,
            fields=template.fields  # Copy fields from template
        )
        db.add(schema)
        db.commit()
        db.refresh(schema)

    # Update documents, organize files, and trigger processing
    updated_count = 0
    for doc_id in request.document_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            # Organize file into template folder
            new_path = organize_document_file(
                current_path=doc.file_path,
                filename=doc.filename,
                template_name=template.name
            )
            doc.file_path = new_path
            doc.schema_id = schema.id
            doc.status = "processing"
            updated_count += 1

    db.commit()

    # Trigger background processing (will use pipelined extraction)
    from app.api.documents import process_single_document
    for doc_id in request.document_ids:
        # Process in background
        # Note: In production, use Celery or similar
        try:
            await process_single_document(doc_id)
        except Exception as e:
            logger.error(f"Error processing doc {doc_id}: {e}")

    return {
        "success": True,
        "schema_id": schema.id,
        "updated_documents": updated_count,
        "message": f"Confirmed template and started processing {updated_count} documents"
    }


@router.post("/create-new-template")
async def create_new_template(
    request: CreateTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    User chooses to create a new template for documents that don't match
    Analyzes the documents with Claude to generate schema
    """

    # Get documents
    documents = db.query(Document).filter(Document.id.in_(request.document_ids)).all()
    if not documents:
        raise HTTPException(status_code=404, detail="Documents not found")

    # PIPELINE: Use cached parse results if available, otherwise parse
    reducto_service = ReductoService()
    claude_service = ClaudeService()

    parsed_docs = []
    for doc in documents:
        if doc.reducto_parse_result:
            # Use cached parse result
            parsed_docs.append({
                "result": doc.reducto_parse_result,
                "job_id": doc.reducto_job_id
            })
            logger.info(f"Using cached parse for {doc.filename}")
        else:
            # Parse if not cached
            parsed = await reducto_service.parse_document(doc.file_path)
            doc.reducto_job_id = parsed.get("job_id")
            doc.reducto_parse_result = parsed.get("result")
            db.commit()
            parsed_docs.append(parsed)

    # Generate schema with Claude
    schema_data = await claude_service.analyze_sample_documents(parsed_docs)
    schema_data["name"] = request.template_name  # Override with user's name

    # Create new schema with fields stored as JSON
    schema = Schema(
        name=request.template_name,
        fields=schema_data["fields"]  # Store fields as JSON
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)

    # NEW: Index template signature for future matching
    elastic_service = ElasticsearchService()
    field_names = [f["name"] for f in schema_data["fields"]]

    # Get sample text from first document
    sample_text = ""
    if documents and documents[0].reducto_parse_result:
        chunks = documents[0].reducto_parse_result.get("chunks", [])
        if chunks:
            sample_text = chunks[0].get("content", "")

    try:
        await elastic_service.index_template_signature(
            template_id=schema.id,
            template_name=request.template_name,
            field_names=field_names,
            sample_text=sample_text,
            category="user_created"
        )
        logger.info(f"Indexed template signature for '{request.template_name}'")
    except Exception as e:
        logger.error(f"Failed to index template signature: {e}")
        # Non-fatal - continue with template creation

    # Update documents to use new schema and organize into template folder
    for doc in documents:
        # Organize file into template folder
        new_path = organize_document_file(
            current_path=doc.file_path,
            filename=doc.filename,
            template_name=request.template_name
        )
        doc.file_path = new_path
        doc.schema_id = schema.id
        doc.status = "processing"

    db.commit()

    # Trigger processing for all documents (will use pipelined extraction)
    from app.api.documents import process_single_document
    for doc in documents:
        try:
            await process_single_document(doc.id)
        except Exception as e:
            logger.error(f"Error processing doc {doc.id}: {e}")

    # NEW: Check if any template_needed docs might match this new template
    from app.utils.template_matching import auto_match_documents

    unmatched_docs = db.query(Document).filter(
        Document.status == "template_needed"
    ).limit(50).all()  # Limit to prevent overwhelming response

    potential_matches = []
    if unmatched_docs:
        logger.info(f"Checking {len(unmatched_docs)} unmatched documents for matches with new template")

        # Refresh template_data to include the new template
        template_data = [{
            "id": schema.id,
            "name": request.template_name,
            "category": "user_created",
            "fields": schema_data["fields"]
        }]

        try:
            potential_matches = await auto_match_documents(
                db=db,
                documents=unmatched_docs,
                elastic_service=elastic_service,
                claude_service=claude_service,
                available_templates=template_data,
                threshold=0.70
            )
        except Exception as e:
            logger.error(f"Auto-match failed: {e}")

    return {
        "success": True,
        "schema_id": schema.id,
        "schema": schema_data,
        "potential_matches": potential_matches,
        "rematch_count": len(potential_matches),
        "message": f"Created new template '{request.template_name}' with {len(schema_data['fields'])} fields" +
                   (f". Found {len(potential_matches)} potential matches!" if potential_matches else "")
    }


@router.post("/verify")
async def bulk_verify(
    verifications: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """
    Bulk verification endpoint
    Accept multiple field verifications at once and update all documents
    """
    from app.models.verification import Verification, VerificationSession
    from app.services.elastic_service import ElasticsearchService

    # Create verification session
    session = VerificationSession(
        schema_id=None,  # Could extract from first document
        total_items=len(verifications),
        items_verified=len(verifications),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    elastic_service = ElasticsearchService()
    updated_count = 0

    for v in verifications:
        # Create verification record
        verification = Verification(
            session_id=session.id,
            extracted_field_id=v['field_id'],
            action='correct' if v['action'] == 'confirmed' else 'incorrect',
            corrected_value=v['verified_value'] if v['action'] == 'corrected' else None,
            verified_by='user'  # TODO: Add user auth
        )
        db.add(verification)

        # Update extracted field
        field = db.query(ExtractedField).filter(ExtractedField.id == v['field_id']).first()
        if field:
            field.verified = True
            field.verified_at = datetime.utcnow()
            if v['action'] == 'corrected':
                field.verified_value = v['verified_value']

            # Update in Elasticsearch
            doc = db.query(Document).filter(Document.id == field.document_id).first()
            if doc and doc.elasticsearch_id:
                try:
                    await elastic_service.update_document(
                        doc.elasticsearch_id,
                        {v['field_name']: v['verified_value']}
                    )
                except Exception as e:
                    logger.error(f"Failed to update ES: {e}")

            updated_count += 1

    db.commit()

    return {
        "success": True,
        "session_id": session.id,
        "verified_count": updated_count,
        "message": f"Verified {updated_count} fields"
    }
