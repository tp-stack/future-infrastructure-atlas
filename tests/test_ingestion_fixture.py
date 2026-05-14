from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.ingestion.csv_loader import read_csv_records
from atlas.ingestion.normalize import normalize_record
from atlas.ingestion.run import run_ingestion
from atlas.ingestion.validators import validate_records
from atlas.ingestion.base import run_fixture_ingestion
from atlas.registry import get_dataset_by_key, load_yaml
from atlas.storage import get_storage_paths


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "sample_power_plants.csv"


def test_csv_loader_reads_fixture():
    records = read_csv_records(SAMPLE_FIXTURE)
    assert len(records) == 1
    assert records[0]["name"] == "Example Plant"
    assert records[0]["country"] == "IT"
    assert records[0]["fuel_type"] == "solar"
    assert records[0]["capacity_mw"] == "10.5"
    assert records[0]["latitude"] == "41.8902"
    assert records[0]["longitude"] == "12.4924"


def test_csv_loader_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        read_csv_records(PROJECT_ROOT / "nonexistent.csv")


def test_csv_loader_raises_on_empty_file(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("name\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        read_csv_records(empty_csv)


def test_dataset_has_required_fields_config():
    dataset = get_dataset_by_key("wri_global_power_plants")
    assert dataset is not None
    required = dataset.get("required_fields", [])
    assert "name" in required
    assert "country" in required
    assert "fuel_type" in required
    assert "capacity_mw" in required
    assert "latitude" in required
    assert "longitude" in required


def test_fixture_records_pass_validation():
    records = read_csv_records(SAMPLE_FIXTURE)
    dataset = get_dataset_by_key("wri_global_power_plants")
    required_fields = dataset["required_fields"]

    valid, rejected = validate_records(records, required_fields)
    assert len(valid) == 1
    assert rejected == []


def test_normalize_record_has_required_fields():
    raw = {"name": "Test", "country": "US", "fuel_type": "gas", "capacity_mw": "100", "latitude": "40.0", "longitude": "-75.0"}
    normalized = normalize_record(raw, "wri_global_power_plants", "wri_global_power_plant_database")

    assert normalized["dataset_key"] == "wri_global_power_plants"
    assert normalized["source_key"] == "wri_global_power_plant_database"
    assert normalized["name"] == "Test"
    assert normalized["country"] == "US"
    assert normalized["fuel_type"] == "gas"
    assert normalized["capacity_mw"] == 100.0
    assert normalized["latitude"] == 40.0
    assert normalized["longitude"] == -75.0
    assert isinstance(normalized["asset_id"], str)
    assert len(normalized["asset_id"]) > 0
    assert normalized["confidence"] == 0.95
    assert "ingested_at" in normalized


def test_full_ingestion_pipeline_with_fixture():
    manifest = run_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)

    assert manifest["status"] == "succeeded"
    assert manifest["dataset_key"] == "wri_global_power_plants"
    assert manifest["source_key"] == "wri_global_power_plant_database"
    assert manifest["records_raw"] == 1
    assert manifest["records_loaded"] == 1
    assert manifest["records_rejected"] == 0

    output_path = Path(manifest["output_path"])
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8").strip()
    lines = content.split("\n")
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["dataset_key"] == "wri_global_power_plants"
    assert record["source_key"] == "wri_global_power_plant_database"
    assert record["name"] == "Example Plant"
    assert record["country"] == "IT"
    assert record["fuel_type"] == "solar"
    assert record["capacity_mw"] == 10.5
    assert record["latitude"] == 41.8902
    assert record["longitude"] == 12.4924
    assert record["confidence"] == 0.95

    cache_dir = get_storage_paths()["cache_dir"]
    manifest_path = cache_dir / "wri_global_power_plants.ingestion_manifest.json"
    assert manifest_path.exists()

    loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded_manifest["dataset_key"] == "wri_global_power_plants"
    assert loaded_manifest["run_id"] == manifest["run_id"]


def test_ingestion_rejects_unknown_dataset():
    with pytest.raises(ValueError, match="Unknown dataset_key"):
        run_ingestion("nonexistent", SAMPLE_FIXTURE)


def test_ingestion_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        run_ingestion("wri_global_power_plants", PROJECT_ROOT / "tests" / "fixtures" / "missing.csv")


def test_datset_yaml_has_required_fields():
    datasets_yaml = load_yaml("datasets.yaml")
    datasets = datasets_yaml.get("datasets", [])
    wri = next((d for d in datasets if d.get("dataset_key") == "wri_global_power_plants"), None)
    assert wri is not None
    assert wri.get("required_fields") == ["name", "country", "fuel_type", "capacity_mw", "latitude", "longitude"]


def test_run_fixture_ingestion_succeeds():
    """Test run_fixture_ingestion with tiny fixture."""
    result = run_fixture_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)
    
    assert result.status == "succeeded"
    assert result.dataset_key == "wri_global_power_plants"
    assert result.records_raw == 1
    assert result.records_valid == 1
    assert result.records_rejected == 0
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.ingestion_manifest_path is not None
    assert result.ingestion_manifest_path.exists()


def test_run_fixture_ingestion_output_is_jsonl():
    """Test that output is valid JSONL format."""
    result = run_fixture_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)
    
    with open(result.output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["asset_type"] == "energy"
    assert record["asset_subtype"] == "power_plant"


def test_run_fixture_ingestion_normalized_record():
    """Test that normalized record has correct structure."""
    result = run_fixture_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)
    
    with open(result.output_path, "r", encoding="utf-8") as f:
        record = json.loads(f.readline())
    
    assert record["canonical_name"] == "Example Plant"
    assert record["raw_name"] == "Example Plant"
    assert record["country"] == "IT"
    assert record["longitude"] == 12.4924
    assert record["latitude"] == 41.8902
    assert isinstance(record["latitude"], float)
    assert isinstance(record["longitude"], float)
    assert record["confidence"] == 0.65
    assert record["source_dataset_key"] == "wri_global_power_plants"
    assert record["target_layer"] == "power_plants"
    assert record["properties"]["fuel_type"] == "solar"
    assert record["properties"]["capacity_mw"] == 10.5


def test_run_fixture_ingestion_output_in_processed_dir():
    """Test that output is in data/processed/ (Git-ignored safe location)."""
    result = run_fixture_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)
    
    # Check output path is in data/processed/
    assert "data" in result.output_path.parts
    assert "processed" in result.output_path.parts
    assert result.output_path.parent.name == "wri_global_power_plants"


def test_run_fixture_ingestion_manifest_in_cache_dir():
    """Test that manifest is in data/cache/ (Git-ignored safe location)."""
    result = run_fixture_ingestion("wri_global_power_plants", SAMPLE_FIXTURE)
    
    # Check manifest path is in data/cache/
    assert "data" in result.ingestion_manifest_path.parts
    assert "cache" in result.ingestion_manifest_path.parts
    assert "ingestion_manifest.json" in result.ingestion_manifest_path.name
