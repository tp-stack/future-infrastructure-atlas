"""Load Atlas power plants from FDE or the existing local map payload."""

from __future__ import annotations

from typing import Any

from atlas import settings
from atlas.loaders.map_assets import MapAssetLoadError, clean, coerce_float, first, load_configured_records, valid_lat_lon

PowerPlantLoadError = MapAssetLoadError


def fde_row_to_power_plant(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a materialized FDE row into the frontend power-plant shape."""

    lat = coerce_float(first(row, "lat", "latitude"))
    lon = coerce_float(first(row, "lon", "lng", "longitude"))
    mapped = valid_lat_lon(lat, lon)
    record: dict[str, Any] = {
        "kind": "power_plant",
        "id": clean(first(row, "id", "record_key", "source_row_id")),
        "n": clean(first(row, "n", "name", "record_key"), "Unnamed power plant"),
        "c": clean(first(row, "c", "country")),
        "f": clean(first(row, "f", "fuel", "type", "technology")),
        "mw": coerce_float(first(row, "mw", "capacity_mw", "capacity", "generation_mw")),
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


def load_power_plants() -> dict[str, Any]:
    """Load power plants using configured FDE preference and local fallback."""

    return load_configured_records(
        local_key="power_plants",
        configured_table=settings.atlas_fde_power_plants_table,
        fallback_label="power plant",
        converter=fde_row_to_power_plant,
    )


def power_plant_loader_status() -> dict[str, Any]:
    """Return a compact status summary for validation scripts."""

    result = load_power_plants()
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
