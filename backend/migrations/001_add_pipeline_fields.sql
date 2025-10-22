-- Migration: Add pipeline optimization fields to documents table
-- Date: 2025-10-10
-- Purpose: Support Reducto pipelining to reduce costs and latency

-- Add job_id and parse_result caching fields
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reducto_job_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reducto_parse_result JSON;

-- Add comment for documentation
COMMENT ON COLUMN documents.reducto_job_id IS 'Reducto parse job ID for pipelining with jobid:// prefix';
COMMENT ON COLUMN documents.reducto_parse_result IS 'Cached parse results to avoid re-parsing';
