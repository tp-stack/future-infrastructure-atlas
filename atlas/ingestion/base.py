from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    
    dataset_key: str
    status: str = "started"
    records_raw: int = 0
    records_valid: int = 0
    records_rejected: int = 0
    output_path: Path | None = None
    ingestion_manifest_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)
    
    # Legacy compatibility
    records_loaded: int = 0
    rejected_details: list[dict[str, Any]] = field(default_factory=list)
    processed_path: Path | None = None
    cache_path: Path | None = None


def require_registered_dataset(dataset_key: str) -> dict[str, Any]:
    """Require that a dataset is registered, else raise ValueError."""
    from atlas.registry import get_dataset_by_key
    
    dataset = get_dataset_by_key(dataset_key)
    if dataset is None:
        raise ValueError(f"Unknown dataset_key: {dataset_key}")
    return dataset


def get_target_layer_config(dataset_key: str) -> dict[str, Any]:
    """Get the target layer configuration for a dataset."""
    from atlas.registry import get_dataset_by_key, get_layer_by_id
    
    dataset = require_registered_dataset(dataset_key)
    target_layer_id = dataset.get("target_layer")
    if not target_layer_id:
        raise ValueError(f"Dataset {dataset_key} has no target_layer configured")
    
    layer = get_layer_by_id(target_layer_id)
    if layer is None:
        raise ValueError(f"Target layer {target_layer_id} not found")
    return layer


def build_processed_output_path(dataset_key: str, suffix: str = ".jsonl") -> Path:
    """Build the path for processed output for a dataset."""
    from uuid import uuid4
    from atlas.storage import get_storage_paths
    
    storage_paths = get_storage_paths()
    processed_dir = storage_paths["processed_dir"] / dataset_key
    processed_dir.mkdir(parents=True, exist_ok=True)
    return processed_dir / f"{dataset_key}.processed{suffix}"


def _asset_subtype_for_layer(target_layer: str) -> str:
    known = {
        "power_plants": "power_plant",
        "data_centers": "data_center",
        "submarine_cables": "submarine_cable",
    }
    return known.get(target_layer, target_layer.rstrip("s"))


def _to_fixture_canonical_record(
    record: dict[str, Any],
    dataset_key: str,
    source_key: str,
    target_layer: str,
    asset_type: str,
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key in ("fuel_type", "capacity_mw", "owner", "source", "commissioning_year"):
        if key in record and record[key] is not None:
            properties[key] = record[key]

    return {
        "asset_id": record.get("asset_id"),
        "asset_type": asset_type,
        "asset_subtype": _asset_subtype_for_layer(target_layer),
        "canonical_name": record.get("name", ""),
        "raw_name": record.get("name", ""),
        "country": record.get("country", ""),
        "longitude": float(record["longitude"]),
        "latitude": float(record["latitude"]),
        "confidence": 0.65,
        "source_key": source_key,
        "source_dataset_key": dataset_key,
        "target_layer": target_layer,
        "properties": properties,
        "ingested_at": record.get("ingested_at"),
    }


def run_fixture_ingestion(
    dataset_key: str,
    file_path: str | Path,
    output_format: str = "jsonl",
) -> IngestionResult:
    """Run ingestion on a fixture file and return IngestionResult."""
    from atlas.ingestion.run import run_ingestion
    from atlas.storage import get_storage_paths
    
    dataset = require_registered_dataset(dataset_key)
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")
    
    try:
        manifest = run_ingestion(dataset_key, file_path)
    except Exception as exc:
        return IngestionResult(
            dataset_key=dataset_key,
            status="failed",
            errors=[str(exc)],
        )
    
    # Parse results from manifest
    records_raw = manifest.get("records_raw", 0)
    records_loaded = manifest.get("records_loaded", 0)
    records_rejected = manifest.get("records_rejected", 0)
    output_path = Path(manifest.get("output_path", "")) if manifest.get("output_path") else None

    target_layer = dataset.get("target_layer", "")
    source_key = dataset.get("source_key", "")
    asset_type = dataset.get("category", "")
    if output_path and output_path.exists() and output_format == "jsonl":
        canonical_lines = []
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                canonical = _to_fixture_canonical_record(record, dataset_key, source_key, target_layer, asset_type)
                canonical_lines.append(json.dumps(canonical, sort_keys=True, ensure_ascii=True))
        output_path.write_text("\n".join(canonical_lines) + ("\n" if canonical_lines else ""), encoding="utf-8")
    
    # Find ingestion manifest path
    storage_paths = get_storage_paths()
    cache_dir = storage_paths["cache_dir"]
    ingestion_manifest_path = cache_dir / f"{dataset_key}.ingestion_manifest.json"
    
    # Build result
    result = IngestionResult(
        dataset_key=dataset_key,
        status=manifest.get("status", "unknown"),
        records_raw=records_raw,
        records_valid=records_loaded,
        records_rejected=records_rejected,
        output_path=output_path,
        ingestion_manifest_path=ingestion_manifest_path,
        manifest=manifest,
        # Legacy compatibility
        records_loaded=records_loaded,
        rejected_details=manifest.get("rejected_details", []),
        processed_path=output_path,
        cache_path=ingestion_manifest_path,
    )
    
    return result


def ingest_local_file(
    dataset_key: str,
    file_path: str | Path,
    output_format: str = "jsonl",
) -> IngestionResult:
    """Ingest a local file and return IngestionResult."""
    return run_fixture_ingestion(dataset_key, file_path, output_format)


class IngestionPipeline:
    def __init__(self, dataset_key: str, file_path: str | Path) -> None:
        self.dataset_key = dataset_key
        self.file_path = Path(file_path)

    def run(self) -> IngestionResult:
        return run_fixture_ingestion(self.dataset_key, self.file_path)
