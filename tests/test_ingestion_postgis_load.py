from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.ingestion.postgis_load import _database_available, load_processed_to_postgis
from atlas.storage import get_storage_paths


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _create_minimal_processed_file(tmp_path: Path) -> Path:
    processed = tmp_path / "test_output.jsonl"
    record = {
        "asset_id": "00000000-0000-0000-0000-000000000001",
        "dataset_key": "wri_global_power_plants",
        "source_key": "wri_global_power_plant_database",
        "name": "Test Plant",
        "country": "IT",
        "fuel_type": "solar",
        "capacity_mw": 10.5,
        "latitude": 41.8902,
        "longitude": 12.4924,
        "confidence": 0.95,
        "ingested_at": "2026-01-01T00:00:00+00:00",
    }
    processed.write_text(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return processed


def test_load_processed_to_postgis_skips_when_db_unavailable(tmp_path):
    processed = _create_minimal_processed_file(tmp_path)
    result = load_processed_to_postgis(processed)

    assert result.get("ok") is True
    assert result.get("skipped") is True
    assert "PostGIS database unavailable" in result.get("reason", "")


def test_load_processed_to_postgis_file_not_found(tmp_path):
    result = load_processed_to_postgis(tmp_path / "nonexistent.jsonl")

    assert result.get("ok") is False
    assert "not found" in result.get("error", "")


def test_database_available_returns_false_when_no_db():
    assert _database_available() is False


skip_if_db = pytest.mark.skipif(_database_available(), reason="Database is available, skipping skip test")


@skip_if_db
def test_load_processed_skips_properly_when_db_not_available(tmp_path):
    processed = _create_minimal_processed_file(tmp_path)
    result = load_processed_to_postgis(processed)
    assert result.get("skipped") is True
    assert result["records_loaded"] == 0
