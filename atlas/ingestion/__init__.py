"""Ingestion pipeline for registering, validating, normalizing, and loading datasets."""

from atlas.ingestion.base import IngestionPipeline, IngestionResult
from atlas.ingestion.csv_loader import read_csv_records
from atlas.ingestion.normalize import normalize_record
from atlas.ingestion.run import run_ingestion
from atlas.ingestion.validators import validate_latitude, validate_longitude, validate_records

__all__ = [
    "IngestionPipeline",
    "IngestionResult",
    "read_csv_records",
    "normalize_record",
    "run_ingestion",
    "validate_latitude",
    "validate_longitude",
    "validate_records",
]
