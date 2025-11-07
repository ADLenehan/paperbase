from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.core.config import settings
from app.models.document import Document, ExtractedField
from app.models.physical_file import PhysicalFile
from app.models.schema import Schema
from app.models.template import SchemaTemplate
from app.services.reducto_service import ReductoService
from app.services.claude_service import ClaudeService
from app.services.elastic_service import ElasticsearchService
from app.services.file_service import FileService
from app.utils.file_organization import get_template_folder, organize_document_file
from app.utils.template_matching import hybrid_match_document
from app.utils.hashing import calculate_content_hash
from app.utils.reducto_validation import validate_schema_for_reducto, format_validation_report
import logging
import os
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bulk", tags=["bulk-upload"])


class ConfirmTemplateRequest(BaseModel):
    document_ids: List[int]
    template_id: int


class CreateTemplateRequest(BaseModel):
    document_ids: List[int]
    template_name: str
    fields: List[Dict[str, Any]] = None  # Optional: user-confirmed fields


class GenerateSchemaRequest(BaseModel):
    document_ids: List[int]
    template_name: str
    user_context: Optional[str] = None  # User-provided context about what to extract


class QuickAnalyzeRequest(BaseModel):
    document_id: int


def _validate_and_normalize_fields(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and normalize field definitions for complex types.
    Ensures array, table, and array_of_objects fields have required properties.

    Args:
        fields: List of field definitions

    Returns:
        Validated and normalized fields

    Raises:
        ValueError: If a field is missing required properties
    """
    validated_fields = []

    for field in fields:
        field_name = field.get("name", "")
        field_type = field.get("type", "text")

        # Normalize field type (handle uppercase, "ARR" → "array", etc.)
        field_type = field_type.lower()
        if field_type in ["arr", "list"]:
            field_type = "array"
        elif field_type in ["tbl", "grid"]:
            field_type = "table"

        normalized_field = {
            "name": field_name,
            "type": field_type,
            "required": field.get("required", False),
            "description": field.get("description", ""),
            "extraction_hints": field.get("extraction_hints", []),
            "confidence_threshold": field.get("confidence_threshold", 0.75)
        }

        # Validate complex types have required properties
        if field_type == "array":
            # Array needs item_type
            item_type = field.get("item_type")
            if not item_type:
                # Default to text if not specified
                logger.warning(f"Field '{field_name}' is array but missing item_type, defaulting to 'text'")
                item_type = "text"
            normalized_field["item_type"] = item_type

        elif field_type == "table":
            # Table needs table_schema
            table_schema = field.get("table_schema")
            if not table_schema:
                raise ValueError(
                    f"Field '{field_name}' is type 'table' but missing 'table_schema'. "
                    "Required properties: row_identifier, columns, value_type"
                )

            # Validate table_schema has minimum required fields
            if not table_schema.get("row_identifier"):
                raise ValueError(f"Field '{field_name}' table_schema missing 'row_identifier'")
            if not table_schema.get("columns"):
                raise ValueError(f"Field '{field_name}' table_schema missing 'columns'")
            if not table_schema.get("value_type"):
                logger.warning(f"Field '{field_name}' table_schema missing value_type, defaulting to 'string'")
                table_schema["value_type"] = "string"

            normalized_field["table_schema"] = table_schema

        elif field_type == "array_of_objects":
            # Array of objects needs object_schema
            object_schema = field.get("object_schema")
            if not object_schema:
                raise ValueError(
                    f"Field '{field_name}' is type 'array_of_objects' but missing 'object_schema'. "
                    "Required: dict of {field_name: {type, required}}"
                )
            normalized_field["object_schema"] = object_schema

        validated_fields.append(normalized_field)

    logger.info(f"Validated {len(validated_fields)} fields ({sum(1 for f in validated_fields if f['type'] in ['array', 'table', 'array_of_objects'])} complex)")
    return validated_fields


@router.post("/upload-and-analyze")
async def upload_and_analyze(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    auto_process: bool = False,
    auto_process_threshold: float = 0.85,
    db: Session = Depends(get_db)
):
    """
    New bulk upload flow with SHA256 deduplication:
    1. Upload files → Check hash → Reuse if exact match found
    2. Parse ONLY unique files without cached parse results
    3. Group similar documents by content (ES clustering)
    4. Match groups to templates OR suggest creating new template
    5. [AUTO] Auto-process high-confidence matches (if auto_process=True)

    Args:
        files: Uploaded files
        background_tasks: FastAPI background tasks
        auto_process: If True, automatically process groups with confidence >= auto_process_threshold
        auto_process_threshold: Minimum confidence for auto-processing (default: 0.85)
        db: Database session

    Returns:
        Document groups with template suggestions + deduplication stats
    """

    file_service = FileService()
    reducto_service = ReductoService()

    # PHASE 1: SHA256 deduplication - group files by hash
    hash_groups = defaultdict(list)
    exact_duplicates_in_batch = 0
    parse_calls_saved = 0

    logger.info(f"Starting bulk upload of {len(files)} files")

    for file in files:
        content = await file.read()
        file_hash = calculate_content_hash(content)

        # Check if this exact file exists (in DB or in current batch)
        existing_physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

        if file_hash in hash_groups:
            # Duplicate within THIS batch
            exact_duplicates_in_batch += 1
            logger.info(f"Duplicate in batch: {file.filename} (hash: {file_hash[:8]}...)")

        hash_groups[file_hash].append({
            "filename": file.filename,
            "content": content,
            "physical_file": existing_physical_file,
            "is_existing": existing_physical_file is not None,
            "has_cached_parse": existing_physical_file and existing_physical_file.reducto_parse_result is not None
        })

        # Track parse savings
        if existing_physical_file and existing_physical_file.reducto_parse_result:
            parse_calls_saved += 1

    logger.info(
        f"Dedup analysis: {len(files)} files → {len(hash_groups)} unique hashes "
        f"({exact_duplicates_in_batch} duplicates in batch, {parse_calls_saved} with cached parse)"
    )

    # PHASE 2: Process each unique hash (upload if new, parse if needed)
    uploaded_docs = []

    for file_hash, file_group in hash_groups.items():
        # Use first file in group as representative
        representative = file_group[0]

        # Get or create PhysicalFile
        if representative["physical_file"]:
            physical_file = representative["physical_file"]
            logger.info(
                f"Reusing PhysicalFile #{physical_file.id} for {len(file_group)} files "
                f"(hash: {file_hash[:8]}...)"
            )
        else:
            # Create new PhysicalFile
            upload_dir = get_template_folder(None)  # unmatched folder
            os.makedirs(upload_dir, exist_ok=True)

            # Save to disk with hash prefix
            unique_filename = f"{file_hash[:8]}_{representative['filename']}"
            file_path = os.path.join(upload_dir, unique_filename)

            with open(file_path, "wb") as f:
                f.write(representative["content"])

            physical_file = PhysicalFile(
                filename=representative["filename"],
                file_hash=file_hash,
                file_path=file_path,
                file_size=len(representative["content"]),
                mime_type=file_group[0].get("content_type") if hasattr(file_group[0], "get") else None
            )
            db.add(physical_file)
            db.flush()

            logger.info(f"Created PhysicalFile #{physical_file.id}: {unique_filename}")

        # Parse if needed
        if not physical_file.reducto_parse_result:
            try:
                logger.info(f"Parsing new file: {physical_file.filename}")
                parsed = await reducto_service.parse_document(physical_file.file_path)

                # Cache parse results on PhysicalFile (shared across all Documents)
                physical_file.reducto_job_id = parsed.get("job_id")
                physical_file.reducto_parse_result = parsed.get("result")
                db.flush()

                logger.info(
                    f"Parsed {physical_file.filename} → job_id: {parsed.get('job_id')}"
                )
            except Exception as e:
                logger.error(f"Failed to parse {physical_file.filename}: {e}")
                # Will mark Documents as error below
        else:
            logger.info(
                f"Using cached parse for {physical_file.filename} "
                f"(job_id: {physical_file.reducto_job_id})"
            )

        # Create Document records for each file in this hash group
        # This allows tracking: "user uploaded invoice.pdf 3 times"
        for file_info in file_group:
            document = Document(
                physical_file_id=physical_file.id,
                filename=file_info["filename"],
                file_path=physical_file.file_path,  # Backwards compatibility with NOT NULL constraint
                status="analyzing" if physical_file.reducto_parse_result else "error",
                error_message=None if physical_file.reducto_parse_result else "Parse failed"
            )
            db.add(document)
            db.flush()
            uploaded_docs.append(document)

            logger.info(
                f"Created Document #{document.id}: {file_info['filename']} "
                f"→ PhysicalFile #{physical_file.id}"
            )

    db.commit()

    logger.info(f"Created {len(uploaded_docs)} Document records from {len(hash_groups)} unique files")

    # Step 3: Cluster similar documents with Elasticsearch (FAST & FREE)
    elastic_service = ElasticsearchService()

    # Use ES clustering instead of Claude grouping (eliminates 1 guaranteed Claude call!)
    clusters = await elastic_service.cluster_uploaded_documents(
        documents=uploaded_docs,
        similarity_threshold=0.75  # Group docs with 75%+ similarity
    )

    logger.info(f"ES clustered {len(uploaded_docs)} docs into {len(clusters)} groups")

    # Step 4: Match each cluster to templates using HYBRID matching (ES + Claude fallback)
    claude_service = ClaudeService()
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

    for cluster in clusters:
        # Get representative document from cluster for template matching
        representative_doc = db.query(Document).filter(
            Document.id == cluster["representative_doc_id"]
        ).first()

        # Use hybrid matching (ES first, Claude fallback only if needed)
        match_result = await hybrid_match_document(
            document=representative_doc,
            elastic_service=elastic_service,
            claude_service=claude_service,
            available_templates=template_data,
            db=db
        )

        if match_result.get("match_source") == "claude":
            claude_fallback_count += 1

        # Extract common fields from representative doc for suggested template name
        # Use actual_parse_result property (supports both PhysicalFile and legacy)
        parse_result = representative_doc.actual_parse_result
        chunks = parse_result.get("chunks", []) if parse_result else []
        doc_text = "\n".join([c.get("content", "") for c in chunks[:5]])

        # Simple field extraction for suggested name (if no match found)
        from app.utils.template_matching import extract_field_names_from_parse
        common_fields = extract_field_names_from_parse(parse_result) if parse_result else []

        matched_groups.append({
            "document_ids": cluster["document_ids"],
            "filenames": cluster["filenames"],
            "suggested_name": match_result.get("template_name") or f"Template for {cluster['representative_filename']}",
            "template_match": match_result,
            "common_fields": common_fields[:10]  # Limit to 10 fields for display
        })

        # Update documents with template suggestion based on confidence
        for doc_id in cluster["document_ids"]:
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

    # NEW: Auto-process high-confidence matches
    auto_processed_groups = []
    auto_processed_count = 0

    if auto_process:
        logger.info(f"Auto-processing enabled with threshold: {auto_process_threshold}")

        for group in matched_groups:
            match_result = group["template_match"]

            # Check if confidence meets threshold and template exists
            if (match_result.get("template_id") and
                match_result.get("confidence", 0) >= auto_process_threshold):

                try:
                    # Auto-confirm and process this group
                    template_id = match_result["template_id"]
                    template = db.query(SchemaTemplate).filter(
                        SchemaTemplate.id == template_id
                    ).first()

                    if template:
                        # Get or create schema
                        schema = db.query(Schema).filter(
                            Schema.template_id == template_id
                        ).first()

                        if not schema:
                            schema = Schema(
                                template_id=template.id,
                                name=template.name,
                                fields=template.fields
                            )
                            db.add(schema)
                            db.commit()
                            db.refresh(schema)

                        # Process all documents in this group
                        for doc_id in group["document_ids"]:
                            doc = db.query(Document).filter(Document.id == doc_id).first()
                            if doc:
                                # Update document
                                doc.schema_id = schema.id
                                doc.status = "processing"

                                # Move file to template folder
                                # If using PhysicalFile, we need to handle shared files
                                if doc.physical_file:
                                    # Copy file instead of moving (preserve PhysicalFile for other Documents)
                                    from app.utils.file_organization import organize_document_file_copy
                                    new_path = organize_document_file_copy(
                                        doc.actual_file_path,
                                        doc.filename,
                                        template.name
                                    )

                                    # Check if PhysicalFile with this hash already exists (avoid UNIQUE constraint error)
                                    from app.utils.hashing import calculate_file_hash
                                    file_hash = calculate_file_hash(new_path)
                                    existing_physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

                                    if existing_physical_file:
                                        # Reuse existing PhysicalFile (same content already indexed)
                                        doc.physical_file_id = existing_physical_file.id
                                        logger.info(f"Reusing existing PhysicalFile #{existing_physical_file.id} for organized copy")
                                    else:
                                        # Create new PhysicalFile for organized copy
                                        new_physical_file = PhysicalFile(
                                            filename=doc.filename,
                                            file_hash=file_hash,
                                            file_path=new_path,
                                            file_size=os.path.getsize(new_path),
                                            mime_type=doc.physical_file.mime_type,
                                            reducto_job_id=doc.physical_file.reducto_job_id,
                                            reducto_parse_result=doc.physical_file.reducto_parse_result,
                                            uploaded_at=doc.physical_file.uploaded_at
                                        )
                                        db.add(new_physical_file)
                                        db.flush()
                                        doc.physical_file_id = new_physical_file.id
                                        logger.info(f"Created new PhysicalFile #{new_physical_file.id} for organized copy")
                                else:
                                    # Legacy path: move file directly
                                    old_path = doc.file_path
                                    new_filename = os.path.basename(old_path)
                                    new_path = organize_document_file(
                                        old_path,
                                        new_filename,
                                        template.name
                                    )
                                    doc.file_path = new_path

                                auto_processed_count += 1

                        db.commit()

                        # Mark group as auto-processed
                        group["auto_processed"] = True
                        auto_processed_groups.append(group)

                        # Queue background processing
                        if background_tasks:
                            for doc_id in group["document_ids"]:
                                background_tasks.add_task(
                                    process_single_document,
                                    doc_id,
                                    schema.id,
                                    db
                                )

                        logger.info(f"Auto-processed group with {len(group['document_ids'])} documents (confidence: {match_result['confidence']:.2f})")

                except Exception as e:
                    logger.error(f"Failed to auto-process group: {e}")
                    group["auto_processed"] = False
            else:
                group["auto_processed"] = False

    return {
        "success": True,
        "total_documents": len(uploaded_docs),
        "unique_files": len(hash_groups),
        "exact_duplicates_in_batch": exact_duplicates_in_batch,
        "parse_calls_saved": parse_calls_saved,
        "cost_saved": f"${parse_calls_saved * 0.02:.2f}",  # ~$0.02 per parse
        "groups": matched_groups,
        "analytics": {
            "total_groups": len(matched_groups),
            "elasticsearch_matches": len(matched_groups) - claude_fallback_count,
            "claude_fallback_matches": claude_fallback_count,
            "cost_estimate": f"${claude_fallback_count * 0.01:.3f}",
            # NEW: Auto-processing stats
            "auto_processed_groups": len(auto_processed_groups),
            "auto_processed_documents": auto_processed_count
        },
        "message": f"Uploaded {len(files)} files → {len(hash_groups)} unique → {len(matched_groups)} groups" +
                   (f" (saved {parse_calls_saved} parses, ${parse_calls_saved * 0.02:.2f})" if parse_calls_saved > 0 else "") +
                   (f" ({auto_processed_count} auto-processed)" if auto_processed_count > 0 else "")
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
            # If using PhysicalFile, we need to handle shared files
            if doc.physical_file:
                # Copy file instead of moving (preserve PhysicalFile for other Documents)
                from app.utils.file_organization import organize_document_file_copy
                new_path = organize_document_file_copy(
                    doc.actual_file_path,
                    doc.filename,
                    template.name
                )

                # Check if PhysicalFile with this hash already exists (avoid UNIQUE constraint error)
                from app.utils.hashing import calculate_file_hash
                file_hash = calculate_file_hash(new_path)
                existing_physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

                if existing_physical_file:
                    # Reuse existing PhysicalFile (same content already indexed)
                    doc.physical_file_id = existing_physical_file.id
                    logger.info(f"Reusing existing PhysicalFile #{existing_physical_file.id} for organized copy")
                else:
                    # Create new PhysicalFile for organized copy
                    new_physical_file = PhysicalFile(
                        filename=doc.filename,
                        file_hash=file_hash,
                        file_path=new_path,
                        file_size=os.path.getsize(new_path),
                        mime_type=doc.physical_file.mime_type,
                        reducto_job_id=doc.physical_file.reducto_job_id,
                        reducto_parse_result=doc.physical_file.reducto_parse_result,
                        uploaded_at=doc.physical_file.uploaded_at
                    )
                    db.add(new_physical_file)
                    db.flush()
                    doc.physical_file_id = new_physical_file.id
                    logger.info(f"Created new PhysicalFile #{new_physical_file.id} for organized copy")
            else:
                # Legacy path: move file directly
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


@router.post("/quick-analyze")
async def quick_analyze(
    request: QuickAnalyzeRequest,
    db: Session = Depends(get_db)
):
    """
    Quick document analysis to suggest context categories for schema generation.
    Analyzes the actual document structure to provide relevant context suggestions.

    This is called BEFORE generate-schema to help users provide better context.

    Returns:
        {
            "suggestions": [
                "Table with measurements (columns: Size, Chest, Waist, Hip)",
                "Repeated color/SKU information across sections",
                "Fabric composition and care instruction details"
            ],
            "document_structure": {
                "has_tables": true,
                "table_count": 2,
                "has_repeated_sections": true,
                "section_count": 5
            }
        }
    """

    # Get document
    document = db.query(Document).filter(Document.id == request.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Use cached parse result if available, otherwise parse
    reducto_service = ReductoService()
    claude_service = ClaudeService()

    if document.reducto_parse_result:
        parsed_doc = {
            "result": document.reducto_parse_result,
            "job_id": document.reducto_job_id
        }
        logger.info(f"Using cached parse for quick analysis: {document.filename}")
    else:
        # Parse document
        parsed_doc = await reducto_service.parse_document(document.file_path)
        document.reducto_job_id = parsed_doc.get("job_id")
        document.reducto_parse_result = parsed_doc.get("result")
        db.commit()

    # Quick analysis with Claude
    analysis = await claude_service.quick_analyze_document(parsed_doc)

    logger.info(
        f"Quick analysis for '{document.filename}': "
        f"{len(analysis.get('suggestions', []))} suggestions generated"
    )

    return {
        "success": True,
        "suggestions": analysis.get("suggestions", []),
        "document_structure": analysis.get("document_structure", {}),
        "message": "Document analyzed successfully"
    }


@router.post("/generate-schema")
async def generate_schema(
    request: GenerateSchemaRequest,
    db: Session = Depends(get_db)
):
    """
    Generate AI-suggested fields for a new template WITHOUT creating it yet.
    This allows users to review and edit fields before finalizing the template.

    Optionally accepts user_context from the quick-analyze suggestions to improve field generation.
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
        # Use actual_* properties (supports both PhysicalFile and legacy)
        parse_result = doc.actual_parse_result
        job_id = doc.actual_job_id
        file_path = doc.actual_file_path

        if parse_result:
            # Use cached parse result - wrap it to match parse_document format
            parsed_docs.append({
                "result": parse_result,
                "job_id": job_id
            })
            logger.info(f"Using cached parse for {doc.filename}")
        else:
            # Parse if not cached
            parsed = await reducto_service.parse_document(file_path)

            # Store parse result (prefer PhysicalFile if available)
            if doc.physical_file:
                doc.physical_file.reducto_job_id = parsed.get("job_id")
                doc.physical_file.reducto_parse_result = parsed.get("result")
            else:
                # Fall back to legacy fields
                doc.reducto_job_id = parsed.get("job_id")
                doc.reducto_parse_result = parsed.get("result")

            db.commit()
            # Append the full parse response (already wrapped)
            parsed_docs.append(parsed)

    # Generate schema with Claude (includes complexity assessment)
    # Pass user_context if provided to improve field suggestions
    schema_data = await claude_service.analyze_sample_documents(
        parsed_docs,
        user_context=request.user_context
    )

    # Extract complexity assessment
    complexity = schema_data.get("complexity_assessment", {})

    # NEW: Validate schema against Reducto requirements
    validation_result = validate_schema_for_reducto(
        {
            "name": request.template_name,
            "fields": schema_data["fields"]
        },
        strict=False  # Don't raise exception, just return warnings
    )

    # Log validation results
    if not validation_result["reducto_compatible"]:
        logger.warning(
            f"Schema '{request.template_name}' has Reducto compatibility issues: "
            f"{len(validation_result['errors'])} errors, {len(validation_result['warnings'])} warnings"
        )
        logger.debug(format_validation_report(validation_result))
    else:
        logger.info(
            f"Schema '{request.template_name}' is Reducto-compatible "
            f"({len(validation_result['warnings'])} warnings, {len(validation_result['recommendations'])} recommendations)"
        )

    logger.info(
        f"Generated schema for '{request.template_name}': "
        f"{len(schema_data['fields'])} fields, "
        f"complexity={complexity.get('score')}, "
        f"recommendation={complexity.get('recommendation')}"
    )

    return {
        "success": True,
        "suggested_fields": schema_data["fields"],
        "complexity": {
            "score": complexity.get("score", 0),
            "confidence": complexity.get("confidence", 0.0),
            "warnings": complexity.get("warnings", []),
            "recommendation": complexity.get("recommendation", "auto")
        },
        # NEW: Include Reducto validation results
        "reducto_validation": {
            "compatible": validation_result["reducto_compatible"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "recommendations": validation_result["recommendations"]
        },
        "message": f"Generated {len(schema_data['fields'])} field suggestions" +
                   (f" ⚠️ {len(validation_result['errors'])} compatibility issues found" if validation_result['errors'] else "")
    }


@router.post("/create-new-template")
async def create_new_template(
    request: CreateTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    User chooses to create a new template for documents that don't match
    Analyzes the documents with Claude to generate schema (if fields not provided)
    OR uses user-confirmed fields (if provided from field preview)
    """
    try:
        # Get documents
        documents = db.query(Document).filter(Document.id.in_(request.document_ids)).all()
        if not documents:
            raise HTTPException(status_code=404, detail="Documents not found")

        # Check if user provided pre-confirmed fields
        if request.fields:
            # User already reviewed and edited fields - use them directly
            # Validate and normalize complex field types
            validated_fields = _validate_and_normalize_fields(request.fields)

            schema_data = {
                "name": request.template_name,
                "fields": validated_fields,
                "complexity_assessment": {
                    "score": 0,
                    "confidence": 1.0,
                    "warnings": [],
                    "recommendation": "user_defined"
                }
            }
            complexity = schema_data["complexity_assessment"]
            logger.info(f"Using user-confirmed fields for '{request.template_name}' ({len(request.fields)} fields)")
        else:
            # Generate schema with Claude
            reducto_service = ReductoService()
            claude_service = ClaudeService()

            parsed_docs = []
            for doc in documents:
                # Use actual_* properties (supports both PhysicalFile and legacy)
                parse_result = doc.actual_parse_result
                job_id = doc.actual_job_id
                file_path = doc.actual_file_path

                if parse_result:
                    # Use cached parse result
                    parsed_docs.append({
                        "result": parse_result,
                        "job_id": job_id
                    })
                    logger.info(f"Using cached parse for {doc.filename}")
                else:
                    # Parse if not cached
                    parsed = await reducto_service.parse_document(file_path)

                    # Store parse result (prefer PhysicalFile if available)
                    if doc.physical_file:
                        doc.physical_file.reducto_job_id = parsed.get("job_id")
                        doc.physical_file.reducto_parse_result = parsed.get("result")
                    else:
                        # Fall back to legacy fields
                        doc.reducto_job_id = parsed.get("job_id")
                        doc.reducto_parse_result = parsed.get("result")

                    db.commit()
                    parsed_docs.append(parsed)

            # Generate schema with Claude (includes complexity assessment)
            schema_data = await claude_service.analyze_sample_documents(parsed_docs)
            schema_data["name"] = request.template_name  # Override with user's name

            # Validate and normalize Claude-generated fields
            schema_data["fields"] = _validate_and_normalize_fields(schema_data["fields"])

            # Extract complexity assessment
            complexity = schema_data.get("complexity_assessment", {})

        # Check if template name already exists
        existing_schema = db.query(Schema).filter_by(name=request.template_name).first()
        if existing_schema:
            raise HTTPException(
                status_code=400,
                detail=f"A template named '{request.template_name}' already exists. Please choose a different name."
            )

        # NEW: Validate schema against Reducto requirements BEFORE creating
        validation_result = validate_schema_for_reducto(
            {
                "name": request.template_name,
                "fields": schema_data["fields"]
            },
            strict=False  # Don't raise exception, allow creation with warnings
        )

        # Log validation results
        if not validation_result["reducto_compatible"]:
            logger.warning(
                f"Creating template '{request.template_name}' with Reducto compatibility issues: "
                f"{len(validation_result['errors'])} errors, {len(validation_result['warnings'])} warnings"
            )
            logger.warning(format_validation_report(validation_result))

            # If there are critical errors, consider blocking creation
            # For now, we'll allow it but return warnings to the user
            if validation_result['errors']:
                logger.error(
                    f"CRITICAL: Template '{request.template_name}' has {len(validation_result['errors'])} "
                    f"Reducto compatibility errors. Extraction may fail!"
                )
        else:
            logger.info(f"Template '{request.template_name}' validated successfully for Reducto")

        # Create new schema with fields and complexity tracking
        schema = Schema(
            name=request.template_name,
            fields=schema_data["fields"],  # Store fields as JSON
            complexity_score=complexity.get("score"),
            auto_generation_confidence=complexity.get("confidence"),
            complexity_warnings=complexity.get("warnings", []),
            generation_mode=complexity.get("recommendation", "auto")
        )
        db.add(schema)
        db.commit()
        db.refresh(schema)

        # Log complexity assessment
        logger.info(
            f"Template '{request.template_name}' complexity: "
            f"score={complexity.get('score')}, "
            f"recommendation={complexity.get('recommendation')}, "
            f"warnings={len(complexity.get('warnings', []))}"
        )

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
            # If using PhysicalFile, we need to handle shared files
            if doc.physical_file:
                # Copy file instead of moving (preserve PhysicalFile for other Documents)
                from app.utils.file_organization import organize_document_file_copy
                new_path = organize_document_file_copy(
                    doc.actual_file_path,
                    doc.filename,
                    request.template_name
                )

                # Check if PhysicalFile with this hash already exists (avoid UNIQUE constraint error)
                from app.utils.hashing import calculate_file_hash
                file_hash = calculate_file_hash(new_path)
                existing_physical_file = db.query(PhysicalFile).filter_by(file_hash=file_hash).first()

                if existing_physical_file:
                    # Reuse existing PhysicalFile (same content already indexed)
                    doc.physical_file_id = existing_physical_file.id
                    logger.info(f"Reusing existing PhysicalFile #{existing_physical_file.id} for organized copy")
                else:
                    # Create new PhysicalFile for organized copy
                    new_physical_file = PhysicalFile(
                        filename=doc.filename,
                        file_hash=file_hash,
                        file_path=new_path,
                        file_size=os.path.getsize(new_path),
                        mime_type=doc.physical_file.mime_type,
                        reducto_job_id=doc.physical_file.reducto_job_id,
                        reducto_parse_result=doc.physical_file.reducto_parse_result,
                        uploaded_at=doc.physical_file.uploaded_at
                    )
                    db.add(new_physical_file)
                    db.flush()
                    doc.physical_file_id = new_physical_file.id
                    logger.info(f"Created new PhysicalFile #{new_physical_file.id} for organized copy")
            else:
                # Legacy path: move file directly
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
            "complexity": {
                "score": complexity.get("score", 0),
                "confidence": complexity.get("confidence", 0.0),
                "warnings": complexity.get("warnings", []),
                "recommendation": complexity.get("recommendation", "auto")
            },
            # NEW: Include Reducto validation results
            "reducto_validation": {
                "compatible": validation_result["reducto_compatible"],
                "errors": validation_result["errors"],
                "warnings": validation_result["warnings"],
                "recommendations": validation_result["recommendations"]
            },
            "potential_matches": potential_matches,
            "rematch_count": len(potential_matches),
            "message": f"Created new template '{request.template_name}' with {len(schema_data['fields'])} fields" +
                       (f". Found {len(potential_matches)} potential matches!" if potential_matches else "") +
                       (f" ⚠️ {len(validation_result['errors'])} Reducto compatibility issues" if validation_result['errors'] else "")
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error creating template '{request.template_name}': {e}", exc_info=True)
        # Provide detailed error message
        error_msg = str(e)
        if "UNIQUE" in error_msg or "unique" in error_msg:
            detail = f"A template named '{request.template_name}' already exists"
        elif "item_type" in error_msg:
            detail = f"Invalid array field: {error_msg}"
        elif "table_schema" in error_msg:
            detail = f"Invalid table field: {error_msg}"
        else:
            detail = f"Failed to create template: {error_msg}"

        raise HTTPException(status_code=500, detail=detail)


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


class ValidateSchemaRequest(BaseModel):
    """Request model for schema validation endpoint"""
    template_name: str
    fields: List[Dict[str, Any]]


@router.post("/validate-schema")
async def validate_schema(request: ValidateSchemaRequest):
    """
    Validate a schema against Reducto API requirements without creating it.

    This endpoint allows users to test schema compatibility before finalizing a template.
    Useful for:
    - Testing field definitions
    - Checking Reducto compatibility
    - Getting recommendations for improvements

    Returns validation report with errors, warnings, and recommendations.
    """
    try:
        # Validate schema structure
        validation_result = validate_schema_for_reducto(
            {
                "name": request.template_name,
                "fields": request.fields
            },
            strict=False
        )

        # Generate human-readable report
        report = format_validation_report(validation_result)

        logger.info(
            f"Validated schema '{request.template_name}': "
            f"compatible={validation_result['reducto_compatible']}, "
            f"errors={len(validation_result['errors'])}, "
            f"warnings={len(validation_result['warnings'])}"
        )

        return {
            "success": True,
            "validation": validation_result,
            "report": report,
            "message": (
                f"✅ Schema is Reducto-compatible"
                if validation_result["reducto_compatible"]
                else f"❌ Schema has {len(validation_result['errors'])} compatibility issues"
            )
        }

    except Exception as e:
        logger.error(f"Error validating schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )
