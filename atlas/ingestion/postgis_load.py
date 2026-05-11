from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas.registry import get_dataset_by_key, get_source_by_key


def _psycopg_available() -> bool:
    try:
        import psycopg  # noqa: F401
        from psycopg.rows import dict_row  # noqa: F401

        return True
    except ImportError:
        return False


def _database_available() -> bool:
    if not _psycopg_available():
        return False
    try:
        from atlas.db import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


def _load_record_to_db(record: dict[str, Any], source_dataset: dict[str, Any]) -> dict[str, str]:
    from atlas.loaders.postgis import insert_infra_asset_minimal

    precision = source_dataset.get("allowed_precision", "generalized")
    sensitivity = source_dataset.get("sensitivity_level", "medium")
    confidence = record.get("confidence", 0.5)
    if confidence is None:
        confidence = 0.5

    asset_id = insert_infra_asset_minimal(
        asset_type=source_dataset["target_layer"],
        asset_subtype=source_dataset.get("expected_format", "csv"),
        canonical_name=record.get("name", ""),
        source_key=source_dataset["source_key"],
        sensitivity_level=sensitivity,
        geometry_precision=precision,
        confidence=float(confidence),
        longitude=float(record["longitude"]),
        latitude=float(record["latitude"]),
        properties={
            "dataset_key": source_dataset["dataset_key"],
            "fuel_type": record.get("fuel_type"),
            "capacity_mw": record.get("capacity_mw"),
            "country": record.get("country"),
        },
    )
    return {"asset_id": asset_id, "status": "loaded"}


def load_processed_to_postgis(processed_path: str | Path) -> dict[str, Any]:
    path = Path(processed_path)
    if not path.exists():
        return {"ok": False, "error": f"Processed file not found: {path}", "records_loaded": 0}

    if not _database_available():
        return {"ok": True, "skipped": True, "reason": "PostGIS database unavailable", "records_loaded": 0}

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        return {"ok": True, "skipped": False, "records_loaded": 0, "note": "No records in processed file"}

    dataset_key = records[0].get("dataset_key", "")
    source_dataset = get_dataset_by_key(dataset_key)
    if source_dataset is None:
        return {"ok": False, "error": f"Unknown dataset_key in processed records: {dataset_key}", "records_loaded": 0}

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for record in records:
        try:
            result = _load_record_to_db(record, source_dataset)
            results.append(result)
        except Exception as exc:
            errors.append(f"Failed to load record {record.get('asset_id', '?' )}: {exc}")
            results.append({"asset_id": None, "status": "failed", "error": str(exc)})

    loaded_count = sum(1 for r in results if r.get("status") == "loaded")
    failed_count = sum(1 for r in results if r.get("status") == "failed")

    return {
        "ok": failed_count == 0,
        "skipped": False,
        "records_loaded": loaded_count,
        "records_failed": failed_count,
        "errors": errors,
    }
