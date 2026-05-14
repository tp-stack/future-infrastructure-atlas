"""Ingestion pipeline for registering, validating, normalizing, loading, and geospatially enriching datasets."""

from atlas.ingestion.base import (
    IngestionPipeline,
    IngestionResult,
    ingest_local_file,
    require_registered_dataset,
    get_target_layer_config,
    build_processed_output_path,
    run_fixture_ingestion,
)
from atlas.ingestion.csv_loader import read_csv_records, read_csv_stream
from atlas.ingestion.normalize import normalize_record
from atlas.ingestion.run import run_ingestion
from atlas.ingestion.validators import validate_latitude, validate_longitude, validate_records

from atlas.ingestion.geometry_utils import (
    parse_lon,
    parse_lat,
    valid_lon_lat,
    valid_line_geometry,
    normalize_linestring_geometry,
    normalize_multilinestring_geometry,
    geometry_bounds,
    safe_slug_key,
)

from atlas.ingestion.geojson_loader import (
    load_geojson_features,
    normalize_point_feature,
    normalize_line_feature,
    normalize_features,
)

from atlas.ingestion.cable_loader import (
    load_cables_from_geojson,
    has_license_restriction,
)

from atlas.ingestion.datacenter_loader import (
    load_datacenters_from_geojson,
    load_datacenters_from_csv,
)

__all__ = [
    "IngestionPipeline",
    "IngestionResult",
    "ingest_local_file",
    "require_registered_dataset",
    "get_target_layer_config",
    "build_processed_output_path",
    "run_fixture_ingestion",
    "read_csv_records",
    "read_csv_stream",
    "normalize_record",
    "run_ingestion",
    "validate_latitude",
    "validate_longitude",
    "validate_records",
    "parse_lon",
    "parse_lat",
    "valid_lon_lat",
    "valid_line_geometry",
    "normalize_linestring_geometry",
    "normalize_multilinestring_geometry",
    "geometry_bounds",
    "safe_slug_key",
    "load_geojson_features",
    "normalize_point_feature",
    "normalize_line_feature",
    "normalize_features",
    "load_cables_from_geojson",
    "has_license_restriction",
    "load_datacenters_from_geojson",
    "load_datacenters_from_csv",
]
