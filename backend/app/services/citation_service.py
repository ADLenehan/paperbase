"""
Citation Service for MCP-friendly source text tracking

This service provides utilities for:
1. Linking extractions to source blocks in parse results
2. Extracting source text and context for citations
3. Formatting citations for different audiences (humans, LLMs, academic)
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import re
import json

logger = logging.getLogger(__name__)


class CitationService:
    """Service for managing citations and source text linkage"""

    @staticmethod
    def find_source_block_for_extraction(
        field_name: str,
        field_value: str,
        parse_result: Dict[str, Any],
        bbox: Optional[Dict[str, Any]] = None,
        page: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the source block in parse result that contains this extraction.

        Strategy:
        1. If bbox provided, find block with matching/overlapping bbox
        2. If value is in block text, use text match
        3. Use field name as hint (look for "Invoice Total: 1500" pattern)

        Args:
            field_name: Name of the extracted field (e.g., "invoice_total")
            field_value: Extracted value (e.g., "1500.00")
            parse_result: Reducto parse result with chunks
            bbox: Optional bounding box from extraction
            page: Optional page number from extraction

        Returns:
            Block dict with 'content', 'page', 'bbox', etc. or None if not found
        """
        chunks = parse_result.get("chunks", [])

        if not chunks:
            logger.warning(f"No chunks found in parse result for field {field_name}")
            return None

        # Normalize field value for matching (remove $ , commas, etc.)
        normalized_value = str(field_value).strip().replace(",", "").replace("$", "")

        # Strategy 1: Exact bbox match (most reliable)
        if bbox and page:
            for chunk in chunks:
                chunk_bbox = chunk.get("bbox", {})
                chunk_page = chunk.get("page", 1)

                if chunk_page == page and CitationService._bbox_overlaps(bbox, chunk_bbox):
                    logger.debug(f"Found source block via bbox match for {field_name}")
                    return chunk

        # Strategy 2: Text content match on same page
        if page:
            page_chunks = [c for c in chunks if c.get("page", 1) == page]

            # Try exact value match first
            for chunk in page_chunks:
                content = chunk.get("content", chunk.get("text", ""))
                if normalized_value in content.replace(",", "").replace("$", ""):
                    logger.debug(f"Found source block via exact value match for {field_name}")
                    return chunk

        # Strategy 3: Text content match anywhere (fallback)
        for chunk in chunks:
            content = chunk.get("content", chunk.get("text", ""))

            # Exact value match
            if normalized_value in content.replace(",", "").replace("$", ""):
                logger.debug(f"Found source block via value match (any page) for {field_name}")
                return chunk

        # Strategy 4: Field name hint (e.g., "Total: 1500" for invoice_total)
        field_name_hint = field_name.replace("_", " ").title()
        pattern = f"{field_name_hint}[:\\s]*{re.escape(normalized_value)}"

        for chunk in chunks:
            content = chunk.get("content", chunk.get("text", ""))
            if re.search(pattern, content, re.IGNORECASE):
                logger.debug(f"Found source block via field name pattern for {field_name}")
                return chunk

        logger.warning(f"Could not find source block for {field_name}={field_value}")
        return None

    @staticmethod
    def _bbox_overlaps(bbox1: Dict, bbox2: Dict, threshold: float = 0.5) -> bool:
        """
        Check if two bounding boxes overlap significantly.

        Args:
            bbox1, bbox2: Dicts with x, y, width, height
            threshold: Minimum overlap ratio (0.5 = 50% overlap)

        Returns:
            True if boxes overlap more than threshold
        """
        if not bbox1 or not bbox2:
            return False

        # Handle different bbox formats
        x1 = bbox1.get("x", 0)
        y1 = bbox1.get("y", 0)
        w1 = bbox1.get("width", 0)
        h1 = bbox1.get("height", 0)

        x2 = bbox2.get("x", 0)
        y2 = bbox2.get("y", 0)
        w2 = bbox2.get("width", 0)
        h2 = bbox2.get("height", 0)

        # Calculate overlap rectangle
        x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))

        overlap_area = x_overlap * y_overlap

        if overlap_area == 0:
            return False

        # Calculate overlap ratio relative to smaller box
        area1 = w1 * h1
        area2 = w2 * h2
        min_area = min(area1, area2)

        if min_area == 0:
            return False

        overlap_ratio = overlap_area / min_area

        return overlap_ratio >= threshold

    @staticmethod
    def extract_source_text_and_context(
        block: Dict[str, Any],
        all_blocks: List[Dict[str, Any]],
        block_index: Optional[int] = None,
        context_chars: int = 200
    ) -> Tuple[str, str, str]:
        """
        Extract source text and surrounding context from block.

        Args:
            block: The source block containing the extraction
            all_blocks: All blocks from parse result (for context)
            block_index: Index of block in all_blocks (if known)
            context_chars: Number of characters to include before/after

        Returns:
            Tuple of (source_text, context_before, context_after)
        """
        source_text = block.get("content", block.get("text", "")).strip()

        # Find block index if not provided
        if block_index is None:
            block_id = block.get("id")
            for i, b in enumerate(all_blocks):
                if b.get("id") == block_id:
                    block_index = i
                    break

        context_before = ""
        context_after = ""

        if block_index is not None:
            # Get context from previous block
            if block_index > 0:
                prev_block = all_blocks[block_index - 1]
                prev_text = prev_block.get("content", prev_block.get("text", ""))
                context_before = prev_text[-context_chars:] if prev_text else ""

            # Get context from next block
            if block_index < len(all_blocks) - 1:
                next_block = all_blocks[block_index + 1]
                next_text = next_block.get("content", next_block.get("text", ""))
                context_after = next_text[:context_chars] if next_text else ""

        return source_text, context_before, context_after

    @staticmethod
    def format_citation(
        filename: str,
        page: Optional[int],
        source_text: Optional[str] = None,
        verified: bool = False,
        confidence: Optional[float] = None,
        format_type: str = "long"
    ) -> str:
        """
        Format citation string for different audiences.

        Args:
            filename: Document filename
            page: Page number
            source_text: Optional source text snippet
            verified: Whether extraction was verified
            confidence: Confidence score
            format_type: "short", "long", or "academic"

        Returns:
            Formatted citation string
        """
        if format_type == "short":
            # Short format: [Invoice-001.pdf, p.2]
            if page:
                return f"[{filename}, p.{page}]"
            else:
                return f"[{filename}]"

        elif format_type == "long":
            # Long format with source text: Invoice-001.pdf, Page 2: "Total: $1,500.00"
            parts = [filename]

            if page:
                parts.append(f"Page {page}")

            citation = ", ".join(parts)

            if source_text:
                # Truncate long source text
                text = source_text[:100] + "..." if len(source_text) > 100 else source_text
                citation += f': "{text}"'

            if verified:
                citation += " ✓"

            return citation

        elif format_type == "academic":
            # Academic format: Invoice-001.pdf (Page 2, verified Nov 15 2024, confidence: 0.96)
            parts = [filename]

            if page:
                parts.append(f"Page {page}")

            if verified:
                parts.append("verified")

            if confidence is not None:
                parts.append(f"confidence: {confidence:.2f}")

            return f"{filename} ({', '.join(parts[1:])})"

        else:
            # Default to long format
            return CitationService.format_citation(
                filename, page, source_text, verified, confidence, format_type="long"
            )

    @staticmethod
    def build_mcp_citation_object(
        field_name: str,
        field_value: Any,
        field_type: str,
        document_id: int,
        filename: str,
        source_text: Optional[str] = None,
        page: Optional[int] = None,
        bbox: Optional[Dict] = None,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        confidence: Optional[float] = None,
        verified: bool = False,
        verified_at: Optional[str] = None,
        verified_by: Optional[str] = None,
        extraction_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete MCP-compatible citation object.

        This format is designed for AI agents consuming via MCP to properly
        cite sources in their responses.

        Returns:
            Citation dict with field, source, extraction, and citation sections
        """
        return {
            "field": {
                "name": field_name,
                "value": str(field_value),
                "type": field_type
            },
            "source": {
                "document_id": document_id,
                "filename": filename,
                "page": page,
                "bbox": bbox,
                "text": source_text,
                "context": {
                    "before": context_before,
                    "after": context_after
                } if context_before or context_after else None
            },
            "extraction": {
                "method": extraction_method or "unknown",
                "confidence": confidence,
                "verified": verified,
                "verified_at": verified_at,
                "verified_by": verified_by
            },
            "citation": {
                "short": CitationService.format_citation(
                    filename, page, format_type="short"
                ),
                "long": CitationService.format_citation(
                    filename, page, source_text, verified, confidence, format_type="long"
                ),
                "academic": CitationService.format_citation(
                    filename, page, verified=verified, confidence=confidence, format_type="academic"
                )
            }
        }

    @staticmethod
    async def enrich_search_results_with_citations(
        results: List[Dict[str, Any]],
        db,
        citation_format: str = "long"
    ) -> List[Dict[str, Any]]:
        """
        Enrich search results with citation information.

        Args:
            results: Search results from ElasticsearchService
            db: Database session
            citation_format: Citation format (short/long/academic)

        Returns:
            Results with added 'citations' field
        """
        from app.models.document import Document, ExtractedField

        enriched = []

        for result in results:
            # Get document ID from result
            doc_id = result.get("id") or result.get("data", {}).get("document_id")

            if not doc_id:
                enriched.append(result)
                continue

            # Get document and fields
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                enriched.append(result)
                continue

            fields = db.query(ExtractedField).filter(
                ExtractedField.document_id == doc_id
            ).all()

            # Build citations for each field
            citations = {}
            for field in fields:
                citations[field.field_name] = CitationService.build_mcp_citation_object(
                    field_name=field.field_name,
                    field_value=field.field_value,
                    field_type="text",  # TODO: Get from schema
                    document_id=document.id,
                    filename=document.filename,
                    source_text=field.source_text,
                    page=field.source_page,
                    bbox=field.source_bbox,
                    context_before=field.context_before,
                    context_after=field.context_after,
                    confidence=field.confidence_score,
                    verified=field.verified,
                    verified_at=field.verified_at.isoformat() if field.verified_at else None,
                    extraction_method=field.extraction_method
                )

            # Add citations to result
            result["citations"] = citations

            # Add summary citation string for easy LLM consumption
            result["citation_summary"] = "; ".join([
                CitationService.format_citation(
                    document.filename,
                    field.source_page,
                    field.source_text,
                    field.verified,
                    field.confidence_score,
                    format_type=citation_format
                )
                for field in fields[:3]  # Top 3 fields
            ])

            enriched.append(result)

        return enriched
