from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from atlas.ingestion.csv_loader import read_csv_records
from atlas.ingestion.normalize import normalize_records
from atlas.ingestion.validators import validate_records
from atlas.provenance import build_raw_manifest, validate_raw_manifest
from atlas.registry import get_dataset_by_key
from atlas.storage import atomic_write_text, get_storage_paths

CACHE_DIR_NAME = "cache_dir"
PROCESSED_DIR_NAME = "processed_dir"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _manifest_sha256(manifest: dict) -> str:
    import hashlib

    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


def run_ingestion(dataset_key: str, file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    dataset = get_dataset_by_key(dataset_key)
    if dataset is None:
        raise ValueError(f"Unknown dataset_key: {dataset_key}")

    required_fields: list[str] = dataset.get("required_fields", [])
    if not required_fields:
        raise ValueError(f"dataset {dataset_key} has no required_fields configured")

    source_key: str = dataset["source_key"]
    run_id = str(uuid4())

    raw_manifest = build_raw_manifest(dataset_key, path)
    raw_validation = validate_raw_manifest(raw_manifest)
    if not raw_validation["ok"]:
        raise ValueError(f"Raw manifest validation failed: {raw_validation['errors']}")

    records = read_csv_records(path)
    records_raw = len(records)

    valid_records, rejected = validate_records(records, required_fields)
    records_loaded = len(valid_records)
    records_rejected = len(rejected)

    storage_paths = get_storage_paths()
    processed_dir = storage_paths[PROCESSED_DIR_NAME] / dataset_key
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_file = processed_dir / f"{run_id}.jsonl"

    lines = "\n".join(
        json.dumps(r, sort_keys=True, ensure_ascii=True) for r in normalize_records(valid_records, dataset_key, source_key)
    )
    atomic_write_text(processed_file, lines + "\n")

    cache_dir = storage_paths[CACHE_DIR_NAME]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{dataset_key}.ingestion_manifest.json"

    started_at = _utc_now()
    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "run_id": run_id,
        "dataset_key": dataset_key,
        "source_key": source_key,
        "raw_manifest_sha256": _manifest_sha256(raw_manifest),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "status": "succeeded" if records_rejected == 0 else "partially_succeeded",
        "records_raw": records_raw,
        "records_loaded": records_loaded,
        "records_rejected": records_rejected,
        "rejected_details": rejected,
        "output_path": str(processed_file.resolve()),
        "errors": [],
    }

    atomic_write_text(cache_path, json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n")

    return manifest
