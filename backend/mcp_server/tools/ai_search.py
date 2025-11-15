"""
AI-Powered Search Tool for MCP Server

Provides access to natural language search with AI-generated answers,
including confidence indicators and field citations.
"""

from typing import Optional, Dict, Any
import httpx
import logging
import re

logger = logging.getLogger(__name__)

# Backend API URL (should match main app)
API_BASE_URL = "http://localhost:8000"


def format_answer_for_claude(answer_text: str, audit_items: list) -> str:
    """
    Format answer text with inline field references for Claude to display.

    Converts [[FIELD:name:doc_id]] markers to human-readable confidence indicators.

    Args:
        answer_text: Answer with [[FIELD:...]] markers
        audit_items: List of audit items with confidence/bbox data

    Returns:
        Formatted text with confidence indicators like: "7 1/2 inches [75% confidence]"
    """
    if not answer_text:
        return answer_text

    # Build lookup map: (field_name, doc_id) -> audit_item
    audit_map = {}
    for item in audit_items or []:
        key = (item.get("field_name"), item.get("document_id"))
        audit_map[key] = item

    # Pattern: [[FIELD:field_name:document_id]]
    pattern = r'\[\[FIELD:([^:]+):(\d+)\]\]'

    def replace_marker(match):
        field_name = match.group(1)
        doc_id = int(match.group(2))

        # Look up confidence from audit items
        audit_item = audit_map.get((field_name, doc_id))

        if audit_item and audit_item.get("confidence") is not None:
            confidence = audit_item["confidence"]
            conf_pct = int(confidence * 100)

            # Color-code based on confidence
            if confidence >= 0.8:
                indicator = f"[{conf_pct}% ✓]"  # High confidence
            elif confidence >= 0.6:
                indicator = f"[{conf_pct}% ⚠️]"  # Medium confidence
            else:
                indicator = f"[{conf_pct}% ⚠️ LOW]"  # Low confidence

            return indicator
        else:
            # No confidence data, just remove marker
            return ""

    # Replace all markers with confidence indicators
    formatted = re.sub(pattern, replace_marker, answer_text)

    return formatted


async def ask_ai(
    query: str,
    folder_path: Optional[str] = None,
    template_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ask AI a natural language question about your documents.

    This tool uses Claude to generate intelligent answers based on your documents,
    with inline confidence indicators for data quality transparency.

    Args:
        query: Natural language question (e.g., "What is the back rise for size 2?")
        folder_path: Optional folder to search within
        template_id: Optional template filter (e.g., "schema_15" or "template_1")

    Returns:
        AI-generated answer with:
        - answer: Natural language response with confidence indicators
        - sources: List of documents used
        - confidence_summary: Overall data quality metrics
        - low_confidence_fields: Fields that may need verification
        - explanation: How the query was interpreted

    Example:
        >>> ask_ai("What is the back rise for size 2 in GLNLEG?")
        {
            "answer": "The back rise for size 2 is 7 1/2 inches [75% ⚠️]\n\n---\n\n📄 **Source Documents**: [View the 1 document used](http://localhost:3000/documents?query_id=123)",
            "sources": ["GLNLEG_tech_spec.pdf"],
            "confidence_summary": {"low": 1, "medium": 2, "high": 5},
            "needs_verification": [{"field": "back_rise_size_2", "confidence": "75%"}]
        }

    ⚠️ PRESENTATION: Present the 'answer' field VERBATIM to the user.
    Do NOT rephrase or summarize - the answer ALREADY includes:
        - Inline confidence indicators: [95% ✓] [72% ⚠️] [45% ⚠️ LOW]
        - Markdown link to source documents at the end
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/search",
                json={
                    "query": query,
                    "folder_path": folder_path,
                    "template_id": template_id,
                    "conversation_history": []  # Could add context in future
                }
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                return {
                    "error": f"Search failed: {error_detail}",
                    "answer": f"Sorry, I couldn't answer that question. Error: {error_detail}"
                }

            data = response.json()

            # Format answer with confidence indicators
            formatted_answer = format_answer_for_claude(
                data.get("answer", ""),
                data.get("audit_items", [])
            )

            # Extract key information for Claude to use
            audit_items = data.get("audit_items", [])
            confidence_summary = data.get("confidence_summary", {})

            # Build list of fields needing verification
            needs_verification = [
                {
                    "field": item["field_name"],
                    "value": item["field_value"],
                    "confidence": f"{int(item['confidence'] * 100)}%",
                    "document": item["filename"]
                }
                for item in audit_items
                if item.get("confidence", 1.0) < 0.7
            ]

            # Build source list
            sources_used = data.get("answer_metadata", {}).get("sources_used", [])
            source_docs = []
            for doc in data.get("results", []):
                if doc.get("id") in sources_used or doc.get("document_id") in sources_used:
                    source_docs.append(doc.get("filename", "Unknown"))

            # NEW: Extract query history information
            query_id = data.get("query_id")
            documents_link = data.get("documents_link")

            # Embed the documents link as markdown in the answer itself
            # This ensures Claude Desktop will render it as a clickable link
            answer_with_link = formatted_answer
            if documents_link and len(source_docs) > 0:
                doc_word = "document" if len(source_docs) == 1 else "documents"
                link_section = f"\n\n---\n\n📄 **Source Documents**: [View the {len(source_docs)} {doc_word} used in this answer]({documents_link})"
                answer_with_link += link_section

            return {
                "answer": answer_with_link,  # Answer with embedded markdown link
                "raw_answer": data.get("answer", ""),  # Include raw for debugging
                "sources": list(set(source_docs)),  # Deduplicate
                "source_count": len(source_docs),
                "total_documents": data.get("total", 0),
                "explanation": data.get("explanation", ""),
                "confidence_summary": {
                    "high_confidence_fields": confidence_summary.get("high_confidence_count", 0),
                    "medium_confidence_fields": confidence_summary.get("medium_confidence_count", 0),
                    "low_confidence_fields": confidence_summary.get("low_confidence_count", 0),
                    "average_confidence": f"{confidence_summary.get('avg_confidence', 0):.0%}" if confidence_summary.get('avg_confidence') else "N/A"
                },
                "needs_verification": needs_verification,
                "field_lineage": data.get("field_lineage", {}),
                "query_confidence": data.get("query_confidence", None),
                "cached": data.get("cached", False),
                # NEW: Query history fields (for programmatic access)
                "query_id": query_id,
                "documents_url": documents_link,  # Full absolute URL
                # Instructions for Claude to present the link
                "_presentation_note": "The answer includes a markdown link to view source documents. Present this as a clickable link to the user."
            }

    except httpx.TimeoutException:
        return {
            "error": "Request timed out after 30 seconds",
            "answer": "Sorry, the search took too long. This might happen if Elasticsearch is starting up. Please try again in a moment."
        }
    except httpx.ConnectError:
        return {
            "error": "Could not connect to backend API",
            "answer": "Sorry, I couldn't connect to the Paperbase backend. Make sure the server is running on http://localhost:8000"
        }
    except Exception as e:
        logger.error(f"Error in ask_ai: {e}", exc_info=True)
        return {
            "error": str(e),
            "answer": f"Sorry, an unexpected error occurred: {str(e)}"
        }
