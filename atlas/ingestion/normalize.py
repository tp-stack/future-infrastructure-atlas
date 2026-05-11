from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_record(
    record: dict[str, Any],
    dataset_key: str,
    source_key: str,
) -> dict[str, Any]:
    capacity_raw = record.get("capacity_mw")
    try:
        capacity_mw = float(capacity_raw) if capacity_raw is not None and str(capacity_raw).strip() != "" else None
    except (ValueError, TypeError):
        capacity_mw = None

    return {
        "asset_id": str(uuid4()),
        "dataset_key": dataset_key,
        "source_key": source_key,
        "name": record.get("name", ""),
        "country": record.get("country", ""),
        "fuel_type": record.get("fuel_type", ""),
        "capacity_mw": capacity_mw,
        "latitude": float(record["latitude"]),
        "longitude": float(record["longitude"]),
        "confidence": 0.95,
        "ingested_at": _utc_now(),
    }


def normalize_records(
    records: list[dict[str, Any]],
    dataset_key: str,
    source_key: str,
) -> list[dict[str, Any]]:
    return [normalize_record(r, dataset_key, source_key) for r in records]
