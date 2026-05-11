"""Provenance manifest utilities for future ingestion workflows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from atlas.registry import get_dataset_by_key
from atlas.storage import atomic_write_text, sha256_file


MANIFEST_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _manifest_sha256(manifest: dict) -> str:
    import hashlib

    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


def build_raw_manifest(dataset_key: str, file_path: str | Path, original_url: str | None = None) -> dict:
    """Build a raw file provenance manifest for a registered dataset."""

    dataset = get_dataset_by_key(dataset_key)
    if dataset is None:
        raise ValueError(f"Unknown dataset_key: {dataset_key}")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Raw file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Raw manifest path must be a file: {path}")

    resolved_path = path.resolve()
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_key": dataset["dataset_key"],
        "source_key": dataset["source_key"],
        "file_name": resolved_path.name,
        "file_path": str(resolved_path),
        "file_size_bytes": resolved_path.stat().st_size,
        "sha256": sha256_file(resolved_path),
        "created_at": _utc_now(),
        "original_url": original_url,
        "license": dataset["license"],
        "sensitivity_level": dataset["sensitivity_level"],
        "allowed_precision": dataset["allowed_precision"],
    }


def build_ingestion_manifest(dataset_key: str, raw_manifest: dict, run_id: str | None = None) -> dict:
    """Build an ingestion manifest from a validated raw manifest."""

    dataset = get_dataset_by_key(dataset_key)
    if dataset is None:
        raise ValueError(f"Unknown dataset_key: {dataset_key}")

    raw_result = validate_raw_manifest(raw_manifest)
    if not raw_result["ok"]:
        raise ValueError(f"Invalid raw manifest: {raw_result['errors']}")
    if raw_manifest["dataset_key"] != dataset_key:
        raise ValueError("Raw manifest dataset_key does not match requested dataset_key")

    return {
        "manifest_version": MANIFEST_VERSION,
        "run_id": run_id or str(uuid4()),
        "dataset_key": dataset["dataset_key"],
        "source_key": dataset["source_key"],
        "raw_manifest_sha256": _manifest_sha256(raw_manifest),
        "started_at": _utc_now(),
        "status": "started",
        "validation_required": bool(dataset["validation_required"]),
        "checksum_verified": True,
        "target_layer": dataset["target_layer"],
        "expected_geometry_type": dataset["expected_geometry_type"],
        "expected_format": dataset["expected_format"],
    }


def validate_raw_manifest(manifest: dict) -> dict:
    """Validate required raw manifest fields and registry consistency."""

    required_fields = [
        "manifest_version",
        "dataset_key",
        "source_key",
        "file_name",
        "file_path",
        "file_size_bytes",
        "sha256",
        "created_at",
        "original_url",
        "license",
        "sensitivity_level",
        "allowed_precision",
    ]
    errors = [f"missing field: {field}" for field in required_fields if field not in manifest]

    dataset = get_dataset_by_key(manifest.get("dataset_key", ""))
    if dataset is None:
        errors.append(f"unknown dataset_key: {manifest.get('dataset_key')}")
    else:
        if manifest.get("source_key") != dataset["source_key"]:
            errors.append("source_key does not match dataset registry")
        if manifest.get("license") != dataset["license"]:
            errors.append("license does not match dataset registry")
        if manifest.get("sensitivity_level") != dataset["sensitivity_level"]:
            errors.append("sensitivity_level does not match dataset registry")
        if manifest.get("allowed_precision") != dataset["allowed_precision"]:
            errors.append("allowed_precision does not match dataset registry")

    file_path = Path(manifest.get("file_path", ""))
    if not file_path.exists():
        errors.append("file_path does not exist")
    elif file_path.is_file():
        expected_sha256 = sha256_file(file_path)
        if manifest.get("sha256") != expected_sha256:
            errors.append("sha256 does not match file contents")

    if not manifest.get("sha256"):
        errors.append("sha256 is required")

    return {"ok": not errors, "errors": errors, "warnings": []}


def validate_ingestion_manifest(manifest: dict) -> dict:
    """Validate required ingestion manifest fields and registry consistency."""

    required_fields = [
        "manifest_version",
        "run_id",
        "dataset_key",
        "source_key",
        "raw_manifest_sha256",
        "started_at",
        "status",
        "validation_required",
        "checksum_verified",
        "target_layer",
        "expected_geometry_type",
        "expected_format",
    ]
    errors = [f"missing field: {field}" for field in required_fields if field not in manifest]

    dataset = get_dataset_by_key(manifest.get("dataset_key", ""))
    if dataset is None:
        errors.append(f"unknown dataset_key: {manifest.get('dataset_key')}")
    else:
        for field in ["source_key", "target_layer", "expected_geometry_type", "expected_format"]:
            if manifest.get(field) != dataset[field]:
                errors.append(f"{field} does not match dataset registry")

    if manifest.get("status") not in {"started", "succeeded", "failed", "partially_succeeded"}:
        errors.append(f"invalid status: {manifest.get('status')}")
    if not manifest.get("raw_manifest_sha256"):
        errors.append("raw_manifest_sha256 is required")

    return {"ok": not errors, "errors": errors, "warnings": []}


def write_manifest(path: str | Path, manifest: dict) -> None:
    """Write a manifest as formatted JSON using atomic replacement."""

    content = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    atomic_write_text(path, content)


def read_manifest(path: str | Path) -> dict:
    """Read a JSON manifest."""

    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected manifest object in {path}")
    return data
