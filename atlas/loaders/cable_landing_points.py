"""Load Atlas cable landing points from FDE or the local infrastructure index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas import settings
from atlas.loaders.map_assets import MapAssetLoadError, clean, coerce_float, first, load_fde_records, valid_lat_lon

LOCAL_INFRASTRUCTURE_INDEX = settings.PROJECT_ROOT / "data" / "derived" / "site_selection" / "infrastructure_index.json"

CableLandingPointLoadError = MapAssetLoadError


def fde_row_to_cable_landing_point(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a materialized FDE row into a cable landing point record."""

    lat = coerce_float(first(row, "lat", "latitude"))
    lon = coerce_float(first(row, "lon", "lng", "longitude"))
    mapped = valid_lat_lon(lat, lon)
    record: dict[str, Any] = {
        "kind": "cable_landing_point",
        "id": clean(first(row, "id", "record_key", "source_row_id")),
        "cable_name": clean(first(row, "cable_name", "name", "id"), "Unnamed cable"),
        "landing_point_name": clean(first(row, "landing_point_name", "landing_point")),
        "country": clean(first(row, "country", "c")),
        "status": clean(first(row, "status", "q")),
        "source": clean(first(row, "source", "source_dataset"), "FDE materialized table"),
        "source_url": clean(row.get("source_url")),
        "mapped_status": "mapped" if mapped else "unmapped",
    }
    if mapped:
        record["lat"] = lat
        record["lon"] = lon
    else:
        record["unmapped_reason"] = "missing_or_invalid_coordinates"
    return record


def load_local_cable_landing_points(path: Path = LOCAL_INFRASTRUCTURE_INDEX) -> dict[str, Any]:
    """Load landing points from the derived local site-selection infrastructure index."""

    if not path.exists():
        raise CableLandingPointLoadError(f"Local infrastructure index not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_records = payload.get("features", {}).get("cable_landing_points", [])
    if not isinstance(raw_records, list):
        raise CableLandingPointLoadError(f"Local infrastructure index has invalid cable_landing_points shape: {path}")
    records = []
    for record in raw_records:
        if not isinstance(record, dict):
            continue
        local_record = dict(record)
        local_record.setdefault("source", "data/derived/site_selection/infrastructure_index.json")
        records.append(fde_row_to_cable_landing_point(local_record))
    return {
        "source": "local",
        "table_name": None,
        "count": len(records),
        "records": records,
        "source_path": str(path.relative_to(settings.PROJECT_ROOT)),
    }


def load_cable_landing_points() -> dict[str, Any]:
    """Load cable landing points using configured FDE preference and local fallback."""

    fallback = settings.atlas_fde_fallback_to_local
    if not settings.atlas_use_fde_tables:
        result = load_local_cable_landing_points()
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = False
        return result

    table_name = settings.atlas_fde_cable_landing_points_table
    if not table_name:
        if fallback:
            result = load_local_cable_landing_points()
            result["fallback_enabled"] = fallback
            result["fde_enabled"] = True
            result["fallback_reason"] = "ATLAS_FDE_CABLE_LANDING_POINTS_TABLE is not configured"
            return result
        raise CableLandingPointLoadError("ATLAS_FDE_CABLE_LANDING_POINTS_TABLE is required when FDE tables are enabled.")

    try:
        result = load_fde_records(table_name, fde_row_to_cable_landing_point, "cable landing point")
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        return result
    except CableLandingPointLoadError:
        if not fallback:
            raise
        result = load_local_cable_landing_points()
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        result["fallback_reason"] = f"FDE table unavailable: {table_name}"
        return result


def cable_landing_point_loader_status() -> dict[str, Any]:
    """Return a compact status summary for validation scripts."""

    result = load_cable_landing_points()
    mapped = sum(1 for record in result["records"] if record.get("mapped_status") in (None, "mapped"))
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
