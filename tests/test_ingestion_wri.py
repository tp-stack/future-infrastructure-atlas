from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.ingestion.csv_loader import read_csv_records, read_csv_stream
from atlas.ingestion.normalize import normalize_record
from atlas.ingestion.run import run_ingestion
from atlas.ingestion.validators import validate_records
from atlas.registry import get_dataset_by_key
from atlas.storage import get_storage_paths


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRI_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "sample_wri_power_plants.csv"


def test_wri_fixture_has_expected_columns():
    records = read_csv_records(WRI_FIXTURE)
    assert len(records) == 3
    assert "primary_fuel" in records[0]
    assert "gppd_idnr" in records[0]
    assert "country_long" in records[0]
    assert "commissioning_year" in records[0]
    assert "owner" in records[0]


def test_field_map_transforms_primary_fuel():
    dataset = get_dataset_by_key("wri_global_power_plants")
    assert dataset is not None
    field_map = dataset.get("field_map", {})
    assert "primary_fuel" in field_map
    assert field_map["primary_fuel"] == "fuel_type"

    raw = read_csv_records(WRI_FIXTURE)
    mapped = [{field_map.get(k, k): v for k, v in record.items()} for record in raw]
    assert "fuel_type" in mapped[0]
    assert "primary_fuel" not in mapped[0]
    assert mapped[0]["fuel_type"] == "Natural Gas"


def test_wri_records_pass_validation():
    dataset = get_dataset_by_key("wri_global_power_plants")
    required_fields = dataset["required_fields"]
    field_map = dataset.get("field_map", {})

    records = read_csv_records(WRI_FIXTURE)
    mapped = [{field_map.get(k, k): v for k, v in record.items()} for record in records]

    valid, rejected = validate_records(mapped, required_fields)
    assert len(valid) == 2
    assert len(rejected) == 1
    assert any("invalid latitude" in err for err in rejected[0]["errors"])


def test_full_ingestion_pipeline_with_wri_fixture():
    manifest = run_ingestion("wri_global_power_plants", WRI_FIXTURE)

    assert manifest["status"] == "partially_succeeded"
    assert manifest["dataset_key"] == "wri_global_power_plants"
    assert manifest["records_raw"] == 3
    assert manifest["records_loaded"] == 2
    assert manifest["records_rejected"] == 1

    output_path = Path(manifest["output_path"])
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8").strip()
    lines = content.split("\n")
    assert len(lines) == 2

    for line in lines:
        record = json.loads(line)
        assert record["dataset_key"] == "wri_global_power_plants"
        assert record["source_key"] == "wri_global_power_plant_database"
        assert "gppd_idnr" in record
        assert "country_long" in record

    cache_dir = get_storage_paths()["cache_dir"]
    manifest_path = cache_dir / "wri_global_power_plants.ingestion_manifest.json"
    assert manifest_path.exists()


def test_wri_normalized_record_has_gppd_idnr():
    dataset = get_dataset_by_key("wri_global_power_plants")
    field_map = dataset.get("field_map", {})

    records = read_csv_records(WRI_FIXTURE)
    mapped = [{field_map.get(k, k): v for k, v in record.items()} for record in records]

    normalized = normalize_record(mapped[0], "wri_global_power_plants", "wri_global_power_plant_database")
    assert normalized["gppd_idnr"] == "USA001"
    assert normalized["country_long"] == "United States"
    assert normalized["owner"] == "Acme Energy"
    assert normalized["commissioning_year"] == "2005"
    assert normalized["fuel_type"] == "Natural Gas"
    assert normalized["confidence"] == 0.85


def test_streaming_produces_same_output():
    result_batch = run_ingestion("wri_global_power_plants", WRI_FIXTURE)

    dataset = get_dataset_by_key("wri_global_power_plants")
    field_map = dataset.get("field_map", {})
    required_fields = dataset["required_fields"]
    source_key = dataset["source_key"]

    count = 0
    valid_count = 0
    rejected_count = 0
    for record in read_csv_stream(WRI_FIXTURE):
        count += 1
        mapped = {field_map.get(k, k): v for k, v in record.items()}
        valid, rejected = validate_records([mapped], required_fields)
        if valid:
            valid_count += 1
        else:
            rejected_count += 1

    assert count == 3
    assert valid_count == 2
    assert rejected_count == 1
    assert count == result_batch["records_raw"]
    assert valid_count == result_batch["records_loaded"]


def test_streaming_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        list(read_csv_stream(PROJECT_ROOT / "tests" / "fixtures" / "nonexistent.csv"))
