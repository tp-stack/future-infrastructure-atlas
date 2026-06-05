"""Load Atlas data centers from FDE or the existing local map payload."""

from __future__ import annotations

from typing import Any

from atlas import settings
from atlas.loaders.map_assets import MapAssetLoadError, clean, coerce_float, first, load_configured_records, valid_lat_lon

DataCenterLoadError = MapAssetLoadError


def fde_row_to_data_center(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a materialized FDE row into the frontend data-center shape."""

    lat = coerce_float(first(row, "lat", "latitude"))
    lon = coerce_float(first(row, "lon", "lng", "longitude"))
    mapped = valid_lat_lon(lat, lon)
    record: dict[str, Any] = {
        "kind": "data_center",
        "id": clean(first(row, "id", "record_key", "source_row_id")),
        "n": clean(first(row, "n", "name", "record_key"), "Unnamed data center"),
        "op": clean(first(row, "op", "operator", "owner", "organization")),
        "c": clean(first(row, "c", "country")),
        "city": clean(first(row, "city", "metro", "region")),
        "mw": coerce_float(first(row, "mw", "capacity_mw", "current_power_mw")),
        "source": clean(first(row, "source", "source_dataset"), "FDE materialized table"),
        "coordinate_precision": clean(row.get("coordinate_precision"), "none" if not mapped else "unknown"),
        "mapped_status": "mapped" if mapped else "unmapped",
        "coordinate_source": clean(row.get("coordinate_source")),
        "source_license": clean(row.get("source_license")),
        "source_url": clean(row.get("source_url")),
        "confidence": coerce_float(row.get("confidence")),
        "address": clean(row.get("address")),
    }
    if mapped:
        record["lat"] = lat
        record["lon"] = lon
    else:
        record["unmapped_reason"] = "missing_or_invalid_coordinates"
    return record


def load_data_centers() -> dict[str, Any]:
    """Load data centers using configured FDE preference and local fallback."""

    table_name = settings.atlas_fde_data_centers_table or settings.atlas_fde_primary_table
    return load_configured_records(
        local_key="data_centers",
        configured_table=table_name,
        fallback_label="data center",
        converter=fde_row_to_data_center,
    )


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
