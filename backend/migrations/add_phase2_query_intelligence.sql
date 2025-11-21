-- Migration: Phase 2 - Query Intelligence Enhancements
-- Date: 2025-11-19
-- Purpose: Add fuzzy matching and query expansion support

-- Enable pg_trgm extension for similarity matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add trigram indexes for fuzzy matching on key text fields
-- This enables spell correction and "did you mean" features

-- Index on all_text for fuzzy full-text matching
CREATE INDEX IF NOT EXISTS idx_document_search_alltext_trgm
ON document_search_index USING gin (all_text gin_trgm_ops);

-- Index on extracted fields for fuzzy field matching
-- This helps with typos in field values
CREATE INDEX IF NOT EXISTS idx_document_search_extracted_trgm
ON document_search_index USING gin ((extracted_fields::text) gin_trgm_ops);

-- Create helper function for fuzzy search fallback
CREATE OR REPLACE FUNCTION fuzzy_search_fallback(
    search_text text,
    min_similarity float DEFAULT 0.3
) RETURNS TABLE (
    document_id integer,
    similarity_score float,
    matched_text text
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dsi.document_id,
        similarity(dsi.all_text, search_text) as similarity_score,
        substring(dsi.all_text, 1, 200) as matched_text
    FROM document_search_index dsi
    WHERE similarity(dsi.all_text, search_text) > min_similarity
    ORDER BY similarity_score DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql STABLE;

-- Create function to find similar terms (for "did you mean")
CREATE OR REPLACE FUNCTION suggest_spelling(
    query_term text,
    min_similarity float DEFAULT 0.5
) RETURNS TABLE (
    suggested_term text,
    similarity_score float,
    frequency integer
) AS $$
BEGIN
    RETURN QUERY
    WITH field_terms AS (
        -- Extract unique terms from field_index array
        SELECT DISTINCT unnest(field_index) as term
        FROM document_search_index
    )
    SELECT
        ft.term as suggested_term,
        similarity(ft.term, query_term) as similarity_score,
        COUNT(*)::integer as frequency
    FROM field_terms ft
    WHERE similarity(ft.term, query_term) > min_similarity
        AND ft.term != query_term
    GROUP BY ft.term, similarity(ft.term, query_term)
    ORDER BY similarity_score DESC, frequency DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql STABLE;

-- Add query expansion cache table (optional, for performance)
CREATE TABLE IF NOT EXISTS query_expansion_cache (
    id SERIAL PRIMARY KEY,
    original_query text NOT NULL,
    expanded_query text NOT NULL,
    expansion_method varchar(50) NOT NULL, -- 'synonym', 'llm', 'hybrid'
    created_at timestamp NOT NULL DEFAULT NOW(),
    hit_count integer NOT NULL DEFAULT 0,
    last_used_at timestamp NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_expansion_cache_query
ON query_expansion_cache (original_query);

-- Function to get or create expanded query
CREATE OR REPLACE FUNCTION get_expanded_query(
    query text,
    method varchar(50) DEFAULT 'synonym'
) RETURNS text AS $$
DECLARE
    expanded text;
BEGIN
    -- Try to get from cache
    SELECT expanded_query INTO expanded
    FROM query_expansion_cache
    WHERE original_query = query
        AND expansion_method = method
        AND created_at > NOW() - INTERVAL '7 days';  -- Cache for 7 days

    IF FOUND THEN
        -- Update hit count and last used
        UPDATE query_expansion_cache
        SET hit_count = hit_count + 1,
            last_used_at = NOW()
        WHERE original_query = query
            AND expansion_method = method;

        RETURN expanded;
    ELSE
        -- Cache miss - return original (expansion happens in Python)
        RETURN query;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create view for query expansion analytics
CREATE OR REPLACE VIEW query_expansion_stats AS
SELECT
    expansion_method,
    COUNT(*) as total_queries,
    SUM(hit_count) as total_hits,
    AVG(hit_count) as avg_hits_per_query,
    MAX(hit_count) as max_hits,
    COUNT(CASE WHEN hit_count > 1 THEN 1 END) as cached_queries,
    ROUND(100.0 * COUNT(CASE WHEN hit_count > 1 THEN 1 END) / NULLIF(COUNT(*), 0), 2) as cache_hit_rate
FROM query_expansion_cache
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY expansion_method;

-- Performance tuning for trigram indexes
-- Set work_mem higher for better sort performance in fuzzy searches
-- (This is session-level, not persisted)
COMMENT ON INDEX idx_document_search_alltext_trgm IS
'Trigram GIN index for fuzzy full-text matching. Enables spell correction and typo tolerance.';

COMMENT ON INDEX idx_document_search_extracted_trgm IS
'Trigram GIN index for fuzzy field value matching. Helps with typos in structured data.';

COMMENT ON FUNCTION fuzzy_search_fallback IS
'Fuzzy search fallback when exact full-text search returns no results. Uses trigram similarity.';

COMMENT ON FUNCTION suggest_spelling IS
'Suggest spelling corrections for search terms based on indexed field names.';

-- Verify migration
DO $$
DECLARE
    trgm_installed boolean;
    trgm_index_count integer;
BEGIN
    -- Check pg_trgm extension
    SELECT COUNT(*) > 0 INTO trgm_installed
    FROM pg_extension
    WHERE extname = 'pg_trgm';

    -- Check trigram indexes
    SELECT COUNT(*) INTO trgm_index_count
    FROM pg_indexes
    WHERE indexname LIKE '%_trgm';

    RAISE NOTICE 'Phase 2 Migration Complete:';
    RAISE NOTICE '  pg_trgm extension: %', CASE WHEN trgm_installed THEN 'installed' ELSE 'missing' END;
    RAISE NOTICE '  Trigram indexes: %', trgm_index_count;
    RAISE NOTICE '  Fuzzy search: enabled';
    RAISE NOTICE '  Spell suggestions: enabled';
END $$;
