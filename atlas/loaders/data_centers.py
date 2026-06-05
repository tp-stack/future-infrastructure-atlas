"""Load Atlas data centers from FDE or the existing local map payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas import settings
from atlas.loaders.fde_tables import inspect_fde_table, load_fde_table, validate_table_name

LOCAL_ATLAS_WEB_DATA = settings.PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json"


class DataCenterLoadError(RuntimeError):
    """Raised when the configured data center source cannot be loaded."""


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_lat_lon(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def _clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def fde_row_to_data_center(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a materialized FDE row into the frontend data-center shape."""

    lat = _coerce_float(_first(row, "lat", "latitude"))
    lon = _coerce_float(_first(row, "lon", "lng", "longitude"))
    mapped = _valid_lat_lon(lat, lon)
    record: dict[str, Any] = {
        "kind": "data_center",
        "id": _clean(_first(row, "id", "record_key", "source_row_id")),
        "n": _clean(_first(row, "n", "name", "record_key"), "Unnamed data center"),
        "op": _clean(_first(row, "op", "operator", "owner", "organization")),
        "c": _clean(_first(row, "c", "country")),
        "city": _clean(_first(row, "city", "metro", "region")),
        "mw": _coerce_float(_first(row, "mw", "capacity_mw", "current_power_mw")),
        "source": _clean(_first(row, "source", "source_dataset"), "FDE materialized table"),
        "coordinate_precision": _clean(row.get("coordinate_precision"), "none" if not mapped else "unknown"),
        "mapped_status": "mapped" if mapped else "unmapped",
        "coordinate_source": _clean(row.get("coordinate_source")),
        "source_license": _clean(row.get("source_license")),
        "source_url": _clean(row.get("source_url")),
        "confidence": _coerce_float(row.get("confidence")),
        "address": _clean(row.get("address")),
    }
    if mapped:
        record["lat"] = lat
        record["lon"] = lon
    else:
        record["unmapped_reason"] = "missing_or_invalid_coordinates"
    return record


def load_fde_data_centers(table_name: str | None = None) -> dict[str, Any]:
    """Load data centers from the configured FDE materialized table."""

    table_name = validate_table_name(table_name or settings.atlas_fde_data_centers_table)
    if not inspect_fde_table(table_name):
        raise DataCenterLoadError(f"FDE data center table not found in {settings.database_schema}: {table_name}")
    rows = load_fde_table(table_name)
    records = [fde_row_to_data_center(row) for row in rows]
    return {
        "source": "fde",
        "table_name": table_name,
        "count": len(records),
        "records": records,
    }


def load_local_data_centers(path: Path = LOCAL_ATLAS_WEB_DATA) -> dict[str, Any]:
    """Load data centers from the existing local frontend map payload."""

    if not path.exists():
        raise DataCenterLoadError(f"Local Atlas data payload not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("data_centers", [])
    if not isinstance(records, list):
        raise DataCenterLoadError(f"Local Atlas data payload has invalid data_centers shape: {path}")
    return {
        "source": "local",
        "table_name": None,
        "count": len(records),
        "records": records,
        "source_path": str(path.relative_to(settings.PROJECT_ROOT)),
    }


def load_data_centers() -> dict[str, Any]:
    """Load data centers using configured FDE preference and local fallback."""

    fallback = settings.atlas_fde_fallback_to_local
    if not settings.atlas_use_fde_tables:
        result = load_local_data_centers()
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = False
        return result

    table_name = settings.atlas_fde_data_centers_table or settings.atlas_fde_primary_table
    if not table_name:
        if fallback:
            result = load_local_data_centers()
            result["fallback_enabled"] = fallback
            result["fde_enabled"] = True
            result["fallback_reason"] = "ATLAS_FDE_DATA_CENTERS_TABLE is not configured"
            return result
        raise DataCenterLoadError("ATLAS_FDE_DATA_CENTERS_TABLE is required when FDE tables are enabled.")

    try:
        result = load_fde_data_centers(table_name)
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        return result
    except DataCenterLoadError:
        if not fallback:
            raise
        result = load_local_data_centers()
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        result["fallback_reason"] = f"FDE table unavailable: {table_name}"
        return result


def data_center_loader_status() -> dict[str, Any]:
    """Return a compact status summary for validation scripts."""

    result = load_data_centers()
    mapped = sum(1 for record in result["records"] if record.get("mapped_status") == "mapped")
    unmapped = result["count"] - mapped
    return {
        "source": result["source"],
        "table_name": result.get("table_name"),
        "source_path": result.get("source_path"),
        "count": result["count"],
        "mapped": mapped,
        "unmapped": unmapped,
        "fallback_enabled": result.get("fallback_enabled"),
        "fallback_reason": result.get("fallback_reason"),
    }
