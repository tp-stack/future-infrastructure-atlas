CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS dim_source (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    category TEXT NOT NULL,
    source_type TEXT NOT NULL,
    reliability_class TEXT NOT NULL,
    license TEXT NOT NULL,
    url TEXT,
    update_frequency TEXT,
    allowed_usage TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT dim_source_source_type_check
        CHECK (source_type IN ('official', 'open', 'community', 'premium', 'inferred')),
    CONSTRAINT dim_source_reliability_class_check
        CHECK (reliability_class IN ('A', 'B', 'C', 'D', 'P'))
);

CREATE TABLE IF NOT EXISTS dim_country (
    iso2 CHAR(2) PRIMARY KEY,
    iso3 CHAR(3),
    country_name TEXT NOT NULL,
    region TEXT,
    subregion TEXT
);

CREATE TABLE IF NOT EXISTS dim_operator (
    operator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    operator_type TEXT,
    country_iso2 CHAR(2) REFERENCES dim_country(iso2),
    aliases TEXT[],
    source_id UUID REFERENCES dim_source(source_id),
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS infra_asset (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type TEXT NOT NULL,
    asset_subtype TEXT,
    canonical_name TEXT,
    raw_name TEXT,
    operator_id UUID REFERENCES dim_operator(operator_id),
    country_iso2 CHAR(2) REFERENCES dim_country(iso2),
    status TEXT,
    source_id UUID NOT NULL REFERENCES dim_source(source_id),
    confidence NUMERIC(4,3),
    sensitivity_level TEXT NOT NULL,
    geometry_precision TEXT NOT NULL,
    geom GEOMETRY,
    properties JSONB DEFAULT '{}'::jsonb,
    first_seen DATE,
    last_updated DATE,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT infra_asset_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT infra_asset_sensitivity_level_check
        CHECK (sensitivity_level IN ('low', 'medium', 'high', 'restricted')),
    CONSTRAINT infra_asset_geometry_precision_check
        CHECK (geometry_precision IN ('exact_public', 'generalized', 'regional', 'inferred'))
);

CREATE INDEX IF NOT EXISTS idx_infra_asset_geom
    ON infra_asset USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_infra_asset_type_subtype
    ON infra_asset (asset_type, asset_subtype);
CREATE INDEX IF NOT EXISTS idx_infra_asset_country_iso2
    ON infra_asset (country_iso2);
CREATE INDEX IF NOT EXISTS idx_infra_asset_source_id
    ON infra_asset (source_id);
CREATE INDEX IF NOT EXISTS idx_infra_asset_confidence
    ON infra_asset (confidence);

CREATE TABLE IF NOT EXISTS energy_asset (
    asset_id UUID PRIMARY KEY REFERENCES infra_asset(asset_id) ON DELETE CASCADE,
    fuel_type TEXT,
    capacity_mw NUMERIC,
    generation_gwh NUMERIC,
    voltage_kv NUMERIC,
    pipeline_capacity TEXT,
    terminal_capacity TEXT,
    commodity TEXT
);

CREATE TABLE IF NOT EXISTS telecom_asset (
    asset_id UUID PRIMARY KEY REFERENCES infra_asset(asset_id) ON DELETE CASCADE,
    telecom_type TEXT,
    provider TEXT,
    ixp_members INTEGER,
    cable_count INTEGER,
    cloud_provider TEXT,
    region_code TEXT,
    facility_count INTEGER
);

CREATE TABLE IF NOT EXISTS resource_asset (
    asset_id UUID PRIMARY KEY REFERENCES infra_asset(asset_id) ON DELETE CASCADE,
    commodity TEXT,
    deposit_type TEXT,
    production_value NUMERIC,
    reserves_value NUMERIC,
    unit TEXT,
    estimate_flag BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS region_score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id TEXT NOT NULL,
    region_type TEXT NOT NULL,
    score_model_version TEXT NOT NULL,
    energy_availability NUMERIC,
    grid_density NUMERIC,
    fiber_presence NUMERIC,
    landing_station_proximity NUMERIC,
    data_center_presence NUMERIC,
    water_access NUMERIC,
    geopolitical_stability NUMERIC,
    climate_resilience NUMERIC,
    energy_cost_score NUMERIC,
    digital_sovereignty NUMERIC,
    industrial_demand NUMERIC,
    final_score NUMERIC,
    confidence NUMERIC,
    geom GEOMETRY,
    computed_at TIMESTAMP DEFAULT now(),
    CONSTRAINT region_score_region_type_check
        CHECK (region_type IN ('country', 'admin', 'nuts', 'h3')),
    CONSTRAINT region_score_final_score_check
        CHECK (final_score IS NULL OR (final_score >= 0 AND final_score <= 100)),
    CONSTRAINT region_score_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX IF NOT EXISTS idx_region_score_geom
    ON region_score USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_region_score_final_score_desc
    ON region_score (final_score DESC);
CREATE INDEX IF NOT EXISTS idx_region_score_region_id
    ON region_score (region_id);
CREATE INDEX IF NOT EXISTS idx_region_score_model_version
    ON region_score (score_model_version);

CREATE TABLE IF NOT EXISTS ingestion_log (
    ingestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES dim_source(source_id),
    dataset_name TEXT NOT NULL,
    source_version TEXT,
    raw_file_path TEXT,
    file_sha256 TEXT,
    records_raw INTEGER,
    records_loaded INTEGER,
    records_rejected INTEGER,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL,
    error_log TEXT,
    CONSTRAINT ingestion_log_status_check
        CHECK (status IN ('started', 'succeeded', 'failed', 'partially_succeeded'))
);

CREATE TABLE IF NOT EXISTS asset_relationship (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_asset_id UUID REFERENCES infra_asset(asset_id) ON DELETE CASCADE,
    to_asset_id UUID REFERENCES infra_asset(asset_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    distance_km NUMERIC,
    confidence NUMERIC,
    evidence JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT now(),
    CONSTRAINT asset_relationship_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX IF NOT EXISTS idx_asset_relationship_from_asset_id
    ON asset_relationship (from_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_relationship_to_asset_id
    ON asset_relationship (to_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_relationship_type
    ON asset_relationship (relationship_type);
