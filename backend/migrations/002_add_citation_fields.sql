-- Migration: Add citation and provenance tracking fields
-- Date: 2025-11-05
-- Purpose: Enable MCP-friendly citations with source text and context

-- Add citation fields to extracted_fields table
ALTER TABLE extracted_fields
ADD COLUMN IF NOT EXISTS source_text TEXT,
ADD COLUMN IF NOT EXISTS source_block_ids JSON,
ADD COLUMN IF NOT EXISTS context_before TEXT,
ADD COLUMN IF NOT EXISTS context_after TEXT,
ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(50);

-- Create document_blocks table for structured parse results
CREATE TABLE IF NOT EXISTS document_blocks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Block identification
    block_id VARCHAR(255),
    block_type VARCHAR(50),
    block_index INTEGER NOT NULL,

    -- Content
    text_content TEXT,
    confidence FLOAT,

    -- Location
    page INTEGER NOT NULL,
    bbox JSON,

    -- Context for citation
    context_before TEXT,
    context_after TEXT,

    -- Metadata
    parse_metadata JSON,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_document_blocks_document_id ON document_blocks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_blocks_page ON document_blocks(page);
CREATE INDEX IF NOT EXISTS idx_document_blocks_block_id ON document_blocks(block_id);
CREATE INDEX IF NOT EXISTS idx_extracted_fields_extraction_method ON extracted_fields(extraction_method);

-- Comments for documentation
COMMENT ON COLUMN extracted_fields.source_text IS 'Actual text extracted from PDF for MCP citation';
COMMENT ON COLUMN extracted_fields.source_block_ids IS 'Array of block IDs this extraction came from';
COMMENT ON COLUMN extracted_fields.context_before IS '200 chars of text before the extraction';
COMMENT ON COLUMN extracted_fields.context_after IS '200 chars of text after the extraction';
COMMENT ON COLUMN extracted_fields.extraction_method IS 'How was this extracted: reducto_structured, reducto_parse, claude, manual';

COMMENT ON TABLE document_blocks IS 'Structured storage of Reducto parse blocks for citation and RAG retrieval';
