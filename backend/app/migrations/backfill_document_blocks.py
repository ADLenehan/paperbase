"""
Backfill document_blocks table from existing reducto_parse_result JSON

This script extracts blocks from the cached parse results and creates
structured DocumentBlock records for citation and future vector search.

Usage:
    python -m app.migrations.backfill_document_blocks

Options:
    --limit N : Process only N documents (for testing)
    --document-id ID : Process only specific document
    --dry-run : Show what would be done without committing
"""

import asyncio
import sys
import argparse
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.document import Document, DocumentBlock
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_blocks_from_parse_result(
    document: Document,
    parse_result: Dict[str, Any]
) -> List[DocumentBlock]:
    """
    Extract blocks from Reducto parse result JSON.

    Reducto parse result structure:
    {
        "chunks": [
            {
                "id": "chunk_0",
                "content": "Text content",
                "page": 1,
                "bbox": {"x": 100, "y": 200, "width": 300, "height": 50},
                "logprobs_confidence": 0.95,
                "type": "text",
                ...
            }
        ]
    }
    """
    blocks = []

    chunks = parse_result.get("chunks", [])
    logger.info(f"Document {document.id}: Found {len(chunks)} chunks in parse result")

    for index, chunk in enumerate(chunks):
        # Extract content - handle both 'content' and 'text' fields
        text_content = chunk.get("content", chunk.get("text", ""))

        if not text_content:
            logger.debug(f"Skipping empty chunk at index {index}")
            continue

        # Calculate context (previous and next chunks)
        context_before = ""
        context_after = ""

        if index > 0:
            prev_chunk = chunks[index - 1]
            prev_text = prev_chunk.get("content", prev_chunk.get("text", ""))
            context_before = prev_text[-200:] if prev_text else ""  # Last 200 chars

        if index < len(chunks) - 1:
            next_chunk = chunks[index + 1]
            next_text = next_chunk.get("content", next_chunk.get("text", ""))
            context_after = next_text[:200] if next_text else ""  # First 200 chars

        # Create DocumentBlock
        block = DocumentBlock(
            document_id=document.id,
            block_id=chunk.get("id", f"block_{index}"),
            block_type=chunk.get("type", "text"),
            block_index=index,
            text_content=text_content,
            confidence=chunk.get("logprobs_confidence", chunk.get("confidence")),
            page=chunk.get("page", 1),
            bbox=chunk.get("bbox"),
            context_before=context_before,
            context_after=context_after,
            parse_metadata=chunk  # Store full chunk for reference
        )

        blocks.append(block)

    logger.info(f"Document {document.id}: Created {len(blocks)} blocks")
    return blocks


def backfill_documents(
    db: Session,
    limit: int = None,
    document_id: int = None,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Backfill document_blocks for existing documents.

    Returns:
        Stats dictionary with counts
    """
    stats = {
        "total_documents": 0,
        "documents_with_parse_results": 0,
        "blocks_created": 0,
        "documents_skipped": 0,
        "errors": 0
    }

    # Build query
    query = db.query(Document)

    if document_id:
        query = query.filter(Document.id == document_id)
        logger.info(f"Processing specific document: {document_id}")
    else:
        # Only process documents with parse results
        query = query.filter(Document.reducto_parse_result.isnot(None))

        if limit:
            query = query.limit(limit)
            logger.info(f"Processing up to {limit} documents")

    documents = query.all()
    stats["total_documents"] = len(documents)

    logger.info(f"Found {len(documents)} documents to process")

    for doc in documents:
        try:
            # Check if already has blocks
            existing_blocks = db.query(DocumentBlock).filter(
                DocumentBlock.document_id == doc.id
            ).count()

            if existing_blocks > 0:
                logger.info(f"Document {doc.id} already has {existing_blocks} blocks, skipping")
                stats["documents_skipped"] += 1
                continue

            # Extract parse result
            if not doc.reducto_parse_result:
                logger.warning(f"Document {doc.id} has no parse result")
                stats["documents_skipped"] += 1
                continue

            stats["documents_with_parse_results"] += 1

            # Extract blocks
            blocks = extract_blocks_from_parse_result(doc, doc.reducto_parse_result)

            if dry_run:
                logger.info(f"[DRY RUN] Would create {len(blocks)} blocks for document {doc.id}")
                stats["blocks_created"] += len(blocks)
            else:
                # Add to database
                for block in blocks:
                    db.add(block)

                db.commit()
                stats["blocks_created"] += len(blocks)
                logger.info(f"✓ Created {len(blocks)} blocks for document {doc.id} ({doc.filename})")

        except Exception as e:
            logger.error(f"Error processing document {doc.id}: {str(e)}", exc_info=True)
            stats["errors"] += 1
            db.rollback()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill document_blocks table from existing parse results"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only N documents (for testing)"
    )
    parser.add_argument(
        "--document-id",
        type=int,
        help="Process only specific document ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without committing"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Document Blocks Backfill Script")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be committed")

    db = SessionLocal()

    try:
        stats = backfill_documents(
            db=db,
            limit=args.limit,
            document_id=args.document_id,
            dry_run=args.dry_run
        )

        logger.info("=" * 80)
        logger.info("Backfill Complete")
        logger.info("=" * 80)
        logger.info(f"Total documents found: {stats['total_documents']}")
        logger.info(f"Documents with parse results: {stats['documents_with_parse_results']}")
        logger.info(f"Documents skipped (already had blocks): {stats['documents_skipped']}")
        logger.info(f"Blocks created: {stats['blocks_created']}")
        logger.info(f"Errors: {stats['errors']}")

        if args.dry_run:
            logger.info("\nThis was a DRY RUN. Run without --dry-run to apply changes.")
        else:
            logger.info("\n✓ All changes committed to database")

        return 0 if stats["errors"] == 0 else 1

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
