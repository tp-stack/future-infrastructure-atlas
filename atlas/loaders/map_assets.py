"""Load map asset records from FDE materialized tables or the local map payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from atlas import settings
from atlas.loaders.fde_tables import inspect_fde_table, load_fde_table, validate_table_name

LOCAL_ATLAS_WEB_DATA = settings.PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json"


class MapAssetLoadError(RuntimeError):
    """Raised when a configured map asset source cannot be loaded."""


def coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def valid_lat_lon(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def load_local_records(key: str, path: Path = LOCAL_ATLAS_WEB_DATA) -> dict[str, Any]:
    if not path.exists():
        raise MapAssetLoadError(f"Local Atlas data payload not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get(key, [])
    if not isinstance(records, list):
        raise MapAssetLoadError(f"Local Atlas data payload has invalid {key} shape: {path}")
    return {
        "source": "local",
        "table_name": None,
        "count": len(records),
        "records": records,
        "source_path": str(path.relative_to(settings.PROJECT_ROOT)),
    }


def load_fde_records(
    table_name: str,
    converter: Callable[[dict[str, Any]], dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    table_name = validate_table_name(table_name)
    if not inspect_fde_table(table_name):
        raise MapAssetLoadError(f"FDE {label} table not found in {settings.database_schema}: {table_name}")
    rows = load_fde_table(table_name)
    records = [converter(row) for row in rows]
    return {
        "source": "fde",
        "table_name": table_name,
        "count": len(records),
        "records": records,
    }


def load_configured_records(
    *,
    local_key: str,
    configured_table: str,
    fallback_label: str,
    converter: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    fallback = settings.atlas_fde_fallback_to_local
    if not settings.atlas_use_fde_tables:
        result = load_local_records(local_key)
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = False
        return result

    if not configured_table:
        if fallback:
            result = load_local_records(local_key)
            result["fallback_enabled"] = fallback
            result["fde_enabled"] = True
            result["fallback_reason"] = f"{fallback_label} FDE table is not configured"
            return result
        raise MapAssetLoadError(f"{fallback_label} FDE table is required when FDE tables are enabled.")

    try:
        result = load_fde_records(configured_table, converter, fallback_label)
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        return result
    except MapAssetLoadError:
        if not fallback:
            raise
        result = load_local_records(local_key)
        result["fallback_enabled"] = fallback
        result["fde_enabled"] = True
        result["fallback_reason"] = f"FDE table unavailable: {configured_table}"
        return result
