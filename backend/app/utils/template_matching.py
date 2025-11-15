"""
Template matching utilities for hybrid Elasticsearch + Claude matching
"""
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.claude_service import ClaudeService
from app.services.postgres_service import PostgresService
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


async def hybrid_match_document(
    document: Document,
    postgres_service: PostgresService,
    claude_service: ClaudeService,
    available_templates: List[Dict[str, Any]],
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Simple hybrid template matching: Try ES first, fall back to Claude if confidence too low

    Args:
        document: Document to match
        postgres_service: Elasticsearch service instance
        claude_service: Claude service instance
        available_templates: List of available templates with fields

    Returns:
        {
            "template_id": int or None,
            "template_name": str or None,
            "confidence": float (0.0-1.0),
            "match_source": "elasticsearch" | "claude" | "none",
            "reasoning": str,
            "matching_fields": List[str],
            "needs_new_template": bool
        }
    """

    # Validate document has parse results
    if not document.actual_parse_result:
        return _no_match_result("No parse result available")

    # Get settings (with fallbacks for when db is not available)
    auto_match_threshold = 0.70  # Default
    enable_claude_fallback = True  # Default

    if db:
        settings_service = SettingsService(db)
        org = settings_service.get_or_create_default_org()
        user = settings_service.get_or_create_default_user(org.id)
        auto_match_threshold = settings_service.get_setting(
            key="auto_match_threshold",
            user_id=user.id,
            org_id=org.id,
            default=0.70
        )
        enable_claude_fallback = settings_service.get_setting(
            key="enable_claude_fallback",
            user_id=user.id,
            org_id=org.id,
            default=True
        )

    # Extract document characteristics
    chunks = document.actual_parse_result.get("chunks", [])
    doc_text = "\n".join([c.get("content", "") for c in chunks[:10]])
    doc_fields = extract_field_names_from_parse(document.actual_parse_result)

    logger.info(f"Matching document {document.filename} with {len(doc_fields)} fields")

    # STEP 1: Try Elasticsearch MLT
    es_matches = await postgres_service.find_similar_templates(
        document_text=doc_text,
        document_fields=doc_fields,
        min_score=0.4  # Low bar for ES to return something
    )

    if es_matches and es_matches[0]["similarity_score"] >= auto_match_threshold:
        # ES confidence is good enough - use it!
        best_match = es_matches[0]
        logger.info(
            f"✅ Elasticsearch match: {best_match['template_name']} "
            f"(confidence: {best_match['similarity_score']:.2f})"
        )
        return {
            "template_id": best_match["template_id"],
            "template_name": best_match["template_name"],
            "confidence": best_match["similarity_score"],
            "match_source": "elasticsearch",
            "reasoning": f"Matched {best_match['match_count']}/{best_match['total_fields']} fields",
            "matching_fields": best_match["matching_fields"],
            "needs_new_template": False
        }

    # STEP 2: ES confidence too low - fall back to Claude
    if enable_claude_fallback:
        logger.info(
            f"⚠️  ES confidence too low ({es_matches[0]['similarity_score']:.2f} < {auto_match_threshold}) "
            f"for {document.filename}. Falling back to Claude..."
        ) if es_matches else logger.info(f"No ES matches for {document.filename}. Using Claude...")

        try:
            claude_result = await claude_service.match_document_to_template(
                parsed_document=document.actual_parse_result,
                available_templates=available_templates
            )

            # Enrich Claude result
            claude_result["match_source"] = "claude"

            # Claude returns needs_new_template flag
            if not claude_result.get("needs_new_template"):
                claude_result["needs_new_template"] = (
                    claude_result["template_id"] is None or
                    claude_result["confidence"] < 0.70
                )

            # Add matching_fields if not present
            if "matching_fields" not in claude_result:
                claude_result["matching_fields"] = []

            logger.info(
                f"🧠 Claude match: {claude_result.get('template_name', 'none')} "
                f"(confidence: {claude_result['confidence']:.2f})"
            )

            return claude_result

        except Exception as e:
            logger.error(f"Claude fallback failed for {document.filename}: {e}")
            return _no_match_result("Claude fallback failed", error=str(e))

    # STEP 3: No match found (Claude fallback disabled or failed)
    logger.info(f"❌ No confident match found for {document.filename}")
    return _no_match_result(
        "No confident match found. Consider creating a new template."
    )


async def auto_match_documents(
    db: Session,
    documents: List[Document],
    postgres_service: PostgresService,
    claude_service: ClaudeService,
    available_templates: List[Dict[str, Any]],
    threshold: float = 0.70
) -> List[Dict[str, Any]]:
    """
    Auto-match multiple documents to templates (used after template creation)

    Args:
        db: Database session
        documents: List of documents to match
        postgres_service: Elasticsearch service
        claude_service: Claude service
        available_templates: Available templates
        threshold: Minimum confidence to suggest match

    Returns:
        List of potential matches with document info
    """
    matches = []

    for doc in documents:
        if not doc.actual_parse_result:
            continue

        # Use hybrid matching
        match_result = await hybrid_match_document(
            document=doc,
            postgres_service=elastic_service,
            claude_service=claude_service,
            available_templates=available_templates,
            db=db
        )

        # Only return matches above threshold
        if match_result["template_id"] and match_result["confidence"] >= threshold:
            # Update document with suggestion
            doc.suggested_template_id = match_result["template_id"]
            doc.template_confidence = match_result["confidence"]
            doc.status = "template_matched" if match_result["confidence"] >= 0.8 else "template_suggested"

            matches.append({
                "document_id": doc.id,
                "filename": doc.filename,
                "suggested_template": match_result["template_name"],
                "confidence": match_result["confidence"],
                "match_source": match_result["match_source"],
                "matching_fields": match_result.get("matching_fields", [])
            })

            logger.info(
                f"Auto-matched {doc.filename} to '{match_result['template_name']}' "
                f"(confidence: {match_result['confidence']:.2f}, source: {match_result['match_source']})"
            )

    db.commit()
    return matches


def extract_field_names_from_parse(parse_result: Dict[str, Any]) -> List[str]:
    """
    Extract likely field names from Reducto parse result
    Uses common patterns like "Label: Value" or bold text

    Args:
        parse_result: Reducto parse result dictionary

    Returns:
        List of extracted field names
    """
    field_names = []

    for chunk in parse_result.get("chunks", []):
        content = chunk.get("content", "")

        # Match patterns like "Invoice Number:", "Total Amount:", etc.
        # Looks for capitalized words followed by colon
        matches = re.findall(r'([A-Z][a-zA-Z\s]+):', content)
        field_names.extend([
            m.strip().lower().replace(" ", "_")
            for m in matches
        ])

    # Return unique field names, limited to 20
    unique_fields = list(set(field_names))[:20]
    logger.debug(f"Extracted {len(unique_fields)} field names from parse result")
    return unique_fields


def _no_match_result(reasoning: str, error: str = None) -> Dict[str, Any]:
    """Helper to return no-match result"""
    result = {
        "template_id": None,
        "template_name": None,
        "confidence": 0.0,
        "match_source": "none",
        "reasoning": reasoning,
        "matching_fields": [],
        "needs_new_template": True
    }
    if error:
        result["error"] = error
    return result
