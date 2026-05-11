CREATE TABLE IF NOT EXISTS dim_dataset (
    dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_key TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    source_id UUID REFERENCES dim_source(source_id),
    category TEXT NOT NULL,
    target_layer TEXT,
    expected_geometry_type TEXT,
    expected_format TEXT,
    update_frequency TEXT,
    license TEXT NOT NULL,
    sensitivity_level TEXT NOT NULL,
    allowed_precision TEXT NOT NULL,
    ingestion_status TEXT NOT NULL,
    checksum_required BOOLEAN DEFAULT true,
    validation_required BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT dim_dataset_ingestion_status_check
        CHECK (ingestion_status IN (
            'not_started',
            'metadata_ready',
            'ingestion_ready',
            'ingested',
            'blocked_license',
            'blocked_quality',
            'deprecated'
        ))
);

CREATE TABLE IF NOT EXISTS dataset_manifest (
    manifest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_key TEXT NOT NULL,
    source_key TEXT NOT NULL,
    manifest_type TEXT NOT NULL,
    manifest_json JSONB NOT NULL,
    file_sha256 TEXT,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT dataset_manifest_manifest_type_check
        CHECK (manifest_type IN ('raw', 'ingestion', 'processed'))
);

CREATE INDEX IF NOT EXISTS idx_dataset_manifest_dataset_key
    ON dataset_manifest (dataset_key);
CREATE INDEX IF NOT EXISTS idx_dataset_manifest_source_key
    ON dataset_manifest (source_key);
CREATE INDEX IF NOT EXISTS idx_dataset_manifest_file_sha256
    ON dataset_manifest (file_sha256);
CREATE INDEX IF NOT EXISTS idx_dataset_manifest_manifest_type
    ON dataset_manifest (manifest_type);
