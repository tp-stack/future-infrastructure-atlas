from pathlib import Path

import pytest
import yaml

from atlas.provenance import (
    build_ingestion_manifest,
    build_raw_manifest,
    read_manifest,
    validate_ingestion_manifest,
    validate_raw_manifest,
    write_manifest,
)
from atlas.storage import get_file_size_mb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "sample_power_plants.csv"


def test_build_raw_manifest_creates_sha256():
    manifest = build_raw_manifest("wri_global_power_plants", SAMPLE_FIXTURE)

    assert manifest["dataset_key"] == "wri_global_power_plants"
    assert manifest["source_key"] == "wri_global_power_plant_database"
    assert len(manifest["sha256"]) == 64
    assert manifest["file_size_bytes"] == SAMPLE_FIXTURE.stat().st_size


def test_raw_manifest_validates():
    manifest = build_raw_manifest("wri_global_power_plants", SAMPLE_FIXTURE)

    result = validate_raw_manifest(manifest)

    assert result["ok"], result["errors"]


def test_ingestion_manifest_validates():
    raw_manifest = build_raw_manifest("wri_global_power_plants", SAMPLE_FIXTURE)
    ingestion_manifest = build_ingestion_manifest("wri_global_power_plants", raw_manifest, run_id="test-run")

    result = validate_ingestion_manifest(ingestion_manifest)

    assert result["ok"], result["errors"]
    assert ingestion_manifest["target_layer"] == "power_plants"


def test_unknown_dataset_key_fails():
    with pytest.raises(ValueError):
        build_raw_manifest("unknown_dataset", SAMPLE_FIXTURE)


def test_missing_file_fails():
    with pytest.raises(FileNotFoundError):
        build_raw_manifest("wri_global_power_plants", PROJECT_ROOT / "tests" / "fixtures" / "missing.csv")


def test_manifest_write_read_round_trip(tmp_path):
    manifest = build_raw_manifest("wri_global_power_plants", SAMPLE_FIXTURE)
    output_path = tmp_path / "sample.raw_manifest.json"

    write_manifest(output_path, manifest)
    loaded = read_manifest(output_path)

    assert loaded == manifest


def test_sample_fixture_is_under_max_test_fixture_size():
    storage_config = yaml.safe_load((PROJECT_ROOT / "config" / "storage.yaml").read_text(encoding="utf-8"))

    assert SAMPLE_FIXTURE.stat().st_size < 1024
    assert get_file_size_mb(SAMPLE_FIXTURE) < storage_config["max_test_fixture_size_mb"]
