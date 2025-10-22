"""
Endpoint for retroactively matching existing documents to templates
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Dict, Any, List
from app.core.database import get_db
from app.models.document import Document
from app.models.template import SchemaTemplate
from app.services.elastic_service import ElasticsearchService
from app.services.claude_service import ClaudeService
from app.utils.template_matching import hybrid_match_document
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rematch", tags=["rematch"])


@router.post("/all")
async def rematch_all_documents(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retroactively match all existing documents that need templates
    This applies hybrid matching to documents uploaded before the feature was added
    """

    # Find all documents that need template matching
    unmatched_docs = db.query(Document).filter(
        or_(
            Document.status == "template_needed",
            Document.status == "analyzing",
            Document.suggested_template_id == None
        )
    ).filter(
        Document.reducto_parse_result != None  # Must have been parsed
    ).all()

    if not unmatched_docs:
        return {
            "success": True,
            "matched_count": 0,
            "message": "No documents need rematching"
        }

    logger.info(f"Rematching {len(unmatched_docs)} documents")

    # Initialize services
    elastic_service = ElasticsearchService()
    claude_service = ClaudeService()

    # Get all available templates
    available_templates = db.query(SchemaTemplate).all()
    template_data = [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "fields": t.fields
        }
        for t in available_templates
    ]

    # Track results
    matched_count = 0
    claude_fallback_count = 0
    results = []

    for doc in unmatched_docs:
        try:
            # Use hybrid matching
            match_result = await hybrid_match_document(
                document=doc,
                elastic_service=elastic_service,
                claude_service=claude_service,
                available_templates=template_data,
                db=db
            )

            # Update document
            doc.suggested_template_id = match_result["template_id"]
            doc.template_confidence = match_result["confidence"]

            # Update status based on confidence
            if match_result["template_id"]:
                if match_result["confidence"] >= 0.75:
                    doc.status = "template_matched"
                elif match_result["confidence"] >= 0.60:
                    doc.status = "template_suggested"
                else:
                    doc.status = "template_needed"
                matched_count += 1
            else:
                doc.status = "template_needed"

            if match_result.get("match_source") == "claude":
                claude_fallback_count += 1

            results.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "template_name": match_result.get("template_name"),
                "confidence": match_result["confidence"],
                "match_source": match_result.get("match_source"),
                "status": doc.status
            })

            logger.info(
                f"Rematched {doc.filename}: "
                f"{match_result.get('template_name', 'none')} "
                f"({match_result['confidence']:.2f})"
            )

        except Exception as e:
            logger.error(f"Failed to rematch document {doc.id}: {e}")
            results.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "error": str(e)
            })

    db.commit()
    await elastic_service.close()

    return {
        "success": True,
        "total_processed": len(unmatched_docs),
        "matched_count": matched_count,
        "analytics": {
            "elasticsearch_matches": len(unmatched_docs) - claude_fallback_count,
            "claude_fallback_matches": claude_fallback_count,
            "cost_estimate": f"${claude_fallback_count * 0.01:.3f}"
        },
        "results": results,
        "message": f"Rematched {matched_count} of {len(unmatched_docs)} documents"
    }


@router.post("/document/{document_id}")
async def rematch_single_document(
    document_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Rematch a single document to templates
    """

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.reducto_parse_result:
        raise HTTPException(
            status_code=400,
            detail="Document has not been parsed yet"
        )

    # Initialize services
    elastic_service = ElasticsearchService()
    claude_service = ClaudeService()

    # Get all available templates
    available_templates = db.query(SchemaTemplate).all()
    template_data = [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "fields": t.fields
        }
        for t in available_templates
    ]

    try:
        # Use hybrid matching
        match_result = await hybrid_match_document(
            document=doc,
            elastic_service=elastic_service,
            claude_service=claude_service,
            available_templates=template_data,
            db=db
        )

        # Update document
        doc.suggested_template_id = match_result["template_id"]
        doc.template_confidence = match_result["confidence"]

        # Update status
        if match_result["template_id"]:
            if match_result["confidence"] >= 0.75:
                doc.status = "template_matched"
            elif match_result["confidence"] >= 0.60:
                doc.status = "template_suggested"
            else:
                doc.status = "template_needed"
        else:
            doc.status = "template_needed"

        db.commit()

        return {
            "success": True,
            "document_id": doc.id,
            "filename": doc.filename,
            "template_name": match_result.get("template_name"),
            "template_id": match_result["template_id"],
            "confidence": match_result["confidence"],
            "match_source": match_result.get("match_source"),
            "status": doc.status,
            "message": f"Document rematched successfully"
        }

    except Exception as e:
        logger.error(f"Failed to rematch document {document_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to rematch document: {str(e)}"
        )
    finally:
        await elastic_service.close()
