-- Migration: Add canonical field mapping tables
-- Purpose: Enable cross-template aggregations with user-defined semantic mappings
-- Date: 2025-11-19

-- Create canonical field mappings table
CREATE TABLE IF NOT EXISTS canonical_field_mappings (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR NOT NULL UNIQUE,
    description TEXT,
    field_mappings JSONB NOT NULL,  -- {template_name: field_name}
    aggregation_type VARCHAR NOT NULL,  -- sum, avg, count, terms, etc.
    is_system BOOLEAN DEFAULT FALSE,  -- System vs user-defined
    is_active BOOLEAN DEFAULT TRUE,  -- Soft delete
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_canonical_mappings_name ON canonical_field_mappings(canonical_name);
CREATE INDEX idx_canonical_mappings_active ON canonical_field_mappings(is_active);
CREATE INDEX idx_canonical_mappings_created_by ON canonical_field_mappings(created_by);

-- Create canonical aliases table
CREATE TABLE IF NOT EXISTS canonical_aliases (
    id SERIAL PRIMARY KEY,
    canonical_field_id INTEGER NOT NULL REFERENCES canonical_field_mappings(id) ON DELETE CASCADE,
    alias VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_canonical_aliases_field_id ON canonical_aliases(canonical_field_id);
CREATE INDEX idx_canonical_aliases_alias ON canonical_aliases(alias);
CREATE INDEX idx_canonical_aliases_active ON canonical_aliases(is_active);

-- Insert system-defined canonical mappings
-- These are common semantic mappings that work across typical document types

INSERT INTO canonical_field_mappings (canonical_name, description, field_mappings, aggregation_type, is_system) VALUES
(
    'revenue',
    'Total revenue/income across all document types',
    '{"Invoice": "invoice_total", "Receipt": "payment_amount", "Contract": "contract_value", "Purchase Order": "po_total"}'::jsonb,
    'sum',
    TRUE
),
(
    'vendor',
    'Vendor/supplier/company name across document types',
    '{"Invoice": "vendor", "Receipt": "vendor", "Contract": "vendor_name", "Purchase Order": "supplier"}'::jsonb,
    'terms',
    TRUE
),
(
    'date',
    'Primary date field across document types',
    '{"Invoice": "invoice_date", "Receipt": "transaction_date", "Contract": "contract_date", "Purchase Order": "order_date"}'::jsonb,
    'date_histogram',
    TRUE
),
(
    'amount',
    'Generic amount/cost field across document types',
    '{"Invoice": "invoice_total", "Receipt": "amount", "Contract": "contract_value", "Purchase Order": "total_amount"}'::jsonb,
    'sum',
    TRUE
),
(
    'status',
    'Status/state field across document types',
    '{"Invoice": "status", "Receipt": "status", "Contract": "contract_status", "Purchase Order": "order_status"}'::jsonb,
    'terms',
    TRUE
);

-- Insert common aliases for system canonical fields
INSERT INTO canonical_aliases (canonical_field_id, alias) VALUES
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'revenue'), 'sales'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'revenue'), 'income'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'revenue'), 'total'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'vendor'), 'supplier'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'vendor'), 'company'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'vendor'), 'customer'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'amount'), 'cost'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'amount'), 'price'),
((SELECT id FROM canonical_field_mappings WHERE canonical_name = 'amount'), 'value');

-- Add comment for documentation
COMMENT ON TABLE canonical_field_mappings IS 'User-defined semantic mappings for cross-template aggregations';
COMMENT ON TABLE canonical_aliases IS 'Aliases for canonical field names to improve NL understanding';
COMMENT ON COLUMN canonical_field_mappings.field_mappings IS 'JSON mapping of {template_name: field_name}';
COMMENT ON COLUMN canonical_field_mappings.aggregation_type IS 'Default aggregation type: sum, avg, count, terms, date_histogram';
COMMENT ON COLUMN canonical_field_mappings.is_system IS 'True for system-defined mappings, False for user-defined';
