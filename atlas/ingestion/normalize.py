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

    confidence = 0.85 if dataset_key != "wri_global_power_plants" or record.get("gppd_idnr") else 0.95

    normalized: dict[str, Any] = {
        "asset_id": str(uuid4()),
        "dataset_key": dataset_key,
        "source_key": source_key,
        "name": record.get("name", ""),
        "country": record.get("country", ""),
        "fuel_type": record.get("fuel_type", ""),
        "capacity_mw": capacity_mw,
        "latitude": float(record["latitude"]),
        "longitude": float(record["longitude"]),
        "confidence": confidence,
        "ingested_at": _utc_now(),
    }

    for extra_field in ("country_long", "gppd_idnr", "commissioning_year", "owner", "source"):
        val = record.get(extra_field)
        if val is not None and str(val).strip():
            normalized[extra_field] = val

    return normalized


def normalize_records(
    records: list[dict[str, Any]],
    dataset_key: str,
    source_key: str,
) -> list[dict[str, Any]]:
    return [normalize_record(r, dataset_key, source_key) for r in records]
