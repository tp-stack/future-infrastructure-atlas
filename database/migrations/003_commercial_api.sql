CREATE TABLE IF NOT EXISTS api_plan (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_key TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    monthly_request_quota INTEGER NOT NULL DEFAULT 10000,
    monthly_export_quota_mb INTEGER NOT NULL DEFAULT 100,
    max_page_size INTEGER NOT NULL DEFAULT 100,
    max_export_rows INTEGER NOT NULL DEFAULT 10000,
    allowed_scopes TEXT[] NOT NULL DEFAULT ARRAY['assets:read', 'tiles:read', 'exports:create'],
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT api_plan_positive_quota_check
        CHECK (monthly_request_quota > 0 AND monthly_export_quota_mb >= 0 AND max_page_size > 0 AND max_export_rows >= 0)
);

CREATE TABLE IF NOT EXISTS api_customer (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_key TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    plan_id UUID REFERENCES api_plan(plan_id),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT api_customer_status_check
        CHECK (status IN ('active', 'suspended', 'closed'))
);

CREATE TABLE IF NOT EXISTS api_key (
    api_key_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES api_customer(customer_id) ON DELETE CASCADE,
    key_prefix TEXT NOT NULL,
    key_hash TEXT UNIQUE NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT ARRAY['assets:read'],
    status TEXT NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT api_key_status_check
        CHECK (status IN ('active', 'revoked', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_api_key_hash
    ON api_key (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_key_customer_id
    ON api_key (customer_id);

CREATE TABLE IF NOT EXISTS data_rights_grant (
    rights_grant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES dim_source(source_id) ON DELETE CASCADE,
    dataset_id UUID REFERENCES dim_dataset(dataset_id) ON DELETE CASCADE,
    layer_id TEXT,
    tile_url TEXT,
    tile_format TEXT,
    commercial_api_allowed BOOLEAN NOT NULL DEFAULT false,
    redistribution_allowed BOOLEAN NOT NULL DEFAULT false,
    attribution_required BOOLEAN NOT NULL DEFAULT true,
    share_alike_risk BOOLEAN NOT NULL DEFAULT true,
    license_review_status TEXT NOT NULL DEFAULT 'not_reviewed',
    rights_evidence_path TEXT,
    terms_url TEXT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT data_rights_grant_target_check
        CHECK (source_id IS NOT NULL OR dataset_id IS NOT NULL),
    CONSTRAINT data_rights_grant_status_check
        CHECK (license_review_status IN ('not_reviewed', 'pending', 'approved', 'rejected', 'expired')),
    CONSTRAINT data_rights_grant_tile_format_check
        CHECK (tile_format IS NULL OR tile_format IN ('pmtiles', 'mvt', 'geojson'))
);

CREATE INDEX IF NOT EXISTS idx_data_rights_grant_source_id
    ON data_rights_grant (source_id);
CREATE INDEX IF NOT EXISTS idx_data_rights_grant_dataset_id
    ON data_rights_grant (dataset_id);
CREATE INDEX IF NOT EXISTS idx_data_rights_grant_layer_id
    ON data_rights_grant (layer_id);
CREATE INDEX IF NOT EXISTS idx_data_rights_grant_commercial
    ON data_rights_grant (commercial_api_allowed, redistribution_allowed, license_review_status);

CREATE TABLE IF NOT EXISTS api_usage_event (
    usage_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES api_customer(customer_id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES api_key(api_key_id) ON DELETE SET NULL,
    endpoint TEXT NOT NULL,
    layer TEXT,
    records_returned INTEGER NOT NULL DEFAULT 0,
    bytes_served BIGINT NOT NULL DEFAULT 0,
    status_code INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_event_customer_created
    ON api_usage_event (customer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_event_endpoint
    ON api_usage_event (endpoint);

CREATE TABLE IF NOT EXISTS api_export_job (
    export_job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES api_customer(customer_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    format TEXT NOT NULL,
    requested_layers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    row_count INTEGER,
    size_bytes BIGINT,
    signed_url TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    CONSTRAINT api_export_job_status_check
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'rejected')),
    CONSTRAINT api_export_job_format_check
        CHECK (format IN ('geojson', 'csv', 'parquet'))
);

CREATE INDEX IF NOT EXISTS idx_api_export_job_customer_created
    ON api_export_job (customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_export_job_status
    ON api_export_job (status);

INSERT INTO api_plan (
    plan_key,
    display_name,
    monthly_request_quota,
    monthly_export_quota_mb,
    max_page_size,
    max_export_rows,
    allowed_scopes
) VALUES (
    'developer',
    'Developer',
    10000,
    100,
    100,
    10000,
    ARRAY['assets:read', 'tiles:read', 'exports:create']
) ON CONFLICT (plan_key) DO NOTHING;
