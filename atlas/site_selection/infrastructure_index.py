"""Runtime loader for the derived infrastructure index (compact JSON).

Loads the compact infrastructure index once and caches it in memory.
Provides typed accessor methods for each feature category.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from threading import Lock
from typing import Any

_INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "derived" / "site_selection"
_INDEX_FILE = _INDEX_DIR / "infrastructure_index.json"
_TELECOM_FILE = _INDEX_DIR / "telecom_index.json"

_index_cache: dict[str, Any] | None = None
_index_lock = Lock()
_index_load_error: str | None = None

_telecom_cache: dict[str, Any] | None = None
_telecom_lock = Lock()
_telecom_load_error: str | None = None


def get_index_path() -> str:
    return str(_INDEX_FILE)


def get_index_size_bytes() -> int:
    """Return the on-disk size of the index file, or 0 if not found."""
    if _INDEX_FILE.exists():
        return _INDEX_FILE.stat().st_size
    return 0


def load_infrastructure_index(force_reload: bool = False) -> dict[str, Any]:
    """Load the infrastructure index from disk, caching it in memory."""
    global _index_cache, _index_load_error

    if not force_reload and _index_cache is not None:
        return _index_cache

    with _index_lock:
        if not force_reload and _index_cache is not None:
            return _index_cache

        if not _INDEX_FILE.exists():
            _index_load_error = f"Infrastructure index not found at {_INDEX_FILE}"
            _index_cache = {
                "metadata": {
                    "error": _index_load_error,
                    "feature_counts": {},
                },
                "features": {},
            }
            return _index_cache

        try:
            with open(_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _index_cache = data
            _index_load_error = None
        except Exception as e:
            _index_load_error = str(e)
            _index_cache = {
                "metadata": {
                    "error": _index_load_error,
                    "feature_counts": {},
                },
                "features": {},
            }
        return _index_cache


def get_feature_counts() -> dict[str, int]:
    """Return the feature counts per category (safe, never raises)."""
    data = load_infrastructure_index()
    return data.get("metadata", {}).get("feature_counts", {})


def get_power_plant_points() -> list[dict[str, Any]]:
    """Return the list of power plant proxy points with compact keys.

    Each feature has keys:
      id, lat, lon, t (type = 'pp'), q (quality), c (country),
      mw (capacity), name
    """
    data = load_infrastructure_index()
    return data.get("features", {}).get("power_plant_points", [])


def get_data_center_points() -> list[dict[str, Any]]:
    """Return the list of data center proxy points.

    Each feature has keys:
      id, lat, lon, t (type = 'dc'), q (quality), c (country),
      city, name
    """
    data = load_infrastructure_index()
    return data.get("features", {}).get("data_center_points", [])


def get_cable_landing_points() -> list[dict[str, Any]]:
    """Return the list of submarine cable landing proxy points.

    Each feature has keys:
      id, lat, lon, t (type = 'cbl'), q (quality)
    """
    data = load_infrastructure_index()
    return data.get("features", {}).get("cable_landing_points", [])


def get_substation_points() -> list[dict[str, Any]]:
    """Return substation proxy points from OSM.

    Each feature has compact keys:
      id, lat, lon, t (type = 'ss'), q (quality = 'obs'), v (voltage_kv),
      c (country), name
    """
    data = load_infrastructure_index()
    return data.get("features", {}).get("substation_points", [])


def get_high_voltage_points() -> list[dict[str, Any]]:
    """Return high-voltage line proxy points from OSM.

    Each feature has compact keys:
      id, lat, lon, t (type = 'hv'), q (quality = 'der'), v (voltage_kv),
      c (country)

    Note: quality is 'der' (derived) because these are line-start proxy
    points, not actual observed substation/transformer coordinates.
    """
    data = load_infrastructure_index()
    return data.get("features", {}).get("high_voltage_points", [])


# Legacy/empty-category accessors (return empty lists for categories still missing)
def get_substation_proxy_points() -> list[dict[str, Any]]:
    """Alias for get_substation_points()."""
    return get_substation_points()


def get_high_voltage_proxy_points() -> list[dict[str, Any]]:
    """Alias for get_high_voltage_points()."""
    return get_high_voltage_points()


def get_fiber_proxy_points() -> list[dict[str, Any]]:
    """Return fiber proxy points (currently empty — placeholder)."""
    data = load_infrastructure_index()
    return data.get("features", {}).get("fiber_proxy_points", [])


def get_ixp_points() -> list[dict[str, Any]]:
    """Return IXP points (currently empty — placeholder)."""
    data = load_infrastructure_index()
    return data.get("features", {}).get("ixp_points", [])


def get_landing_station_points() -> list[dict[str, Any]]:
    """Return landing station points (currently empty — placeholder)."""
    data = load_infrastructure_index()
    return data.get("features", {}).get("landing_station_points", [])


def get_industrial_land_proxy_points() -> list[dict[str, Any]]:
    """Return industrial land proxy points (currently empty — placeholder)."""
    data = load_infrastructure_index()
    return data.get("features", {}).get("industrial_land_proxy_points", [])


def get_empty_categories() -> list[str]:
    """Return list of categories that have zero features (proxy gaps)."""
    counts = get_feature_counts()
    return [k for k, v in counts.items() if v == 0]


def has_power_plant_proxy_data() -> bool:
    """Return True if we have any power plant proxy points."""
    return len(get_power_plant_points()) > 0


def has_data_center_proxy_data() -> bool:
    """Return True if we have any data center proxy points."""
    return len(get_data_center_points()) > 0


def has_substation_data() -> bool:
    """Return True if we have any substation points."""
    return len(get_substation_points()) > 0


def has_high_voltage_data() -> bool:
    """Return True if we have any high-voltage line proxy points."""
    return len(get_high_voltage_points()) > 0


def get_grid_proxy_source_summary() -> str:
    """Return a human-readable summary of available grid proxy sources.

    Explains the proxy priority: substation > HV line > power plant.
    """
    ss = len(get_substation_points())
    hv = len(get_high_voltage_points())
    pp = len(get_power_plant_points())
    parts = []
    if ss > 0:
        parts.append(f"{ss} OSM substation points (>=100 kV)")
    if hv > 0:
        parts.append(f"{hv} high-voltage line proxy points (>=100 kV, derived)")
    if pp > 0:
        parts.append(f"{pp} power plant points (observed, weak grid proxy)")
    if not parts:
        return "No grid proxy data available."
    return "Grid proxy sources: " + "; ".join(parts) + "."


def get_proxy_source_notes() -> list[str]:
    """Return human-readable notes about what the index contains and what is missing."""
    data = load_infrastructure_index()
    metadata = data.get("metadata", {})
    notes = []

    source_notes = metadata.get("source_notes", {})
    for category, note in source_notes.items():
        notes.append(note)

    warning = metadata.get("empty_categories_warning", "")
    if warning:
        notes.append(warning)

    return notes


class InfrastructureIndex:
    """Simple container for all infrastructure index data."""

    def __init__(self, data: dict[str, Any]):
        self.metadata = data.get("metadata", {})
        self.features = data.get("features", {})
        self.power_plants: list[dict[str, Any]] = self.features.get("power_plant_points", [])
        self.data_centers: list[dict[str, Any]] = self.features.get("data_center_points", [])
        self.cable_landing_points: list[dict[str, Any]] = self.features.get("cable_landing_points", [])
        self.substations: list[dict[str, Any]] = self.features.get("substation_points", [])
        self.high_voltage_points: list[dict[str, Any]] = self.features.get("high_voltage_points", [])
        self.fiber_points: list[dict[str, Any]] = self.features.get("fiber_proxy_points", [])
        self.ixp_points: list[dict[str, Any]] = self.features.get("ixp_points", [])
        self.landing_stations: list[dict[str, Any]] = self.features.get("landing_station_points", [])
        self.industrial_land: list[dict[str, Any]] = self.features.get("industrial_land_proxy_points", [])


# ═══════════════════════════════════════════════════════════════════
# Telecom Index (separate shard)
# ═══════════════════════════════════════════════════════════════════


def get_telecom_index_path() -> str:
    return str(_TELECOM_FILE)


def get_telecom_index_size_bytes() -> int:
    if _TELECOM_FILE.exists():
        return _TELECOM_FILE.stat().st_size
    return 0


def load_telecom_index(force_reload: bool = False) -> dict[str, Any]:
    """Load the telecom interconnection index from disk, caching it in memory."""
    global _telecom_cache, _telecom_load_error

    if not force_reload and _telecom_cache is not None:
        return _telecom_cache

    with _telecom_lock:
        if not force_reload and _telecom_cache is not None:
            return _telecom_cache

        if not _TELECOM_FILE.exists():
            _telecom_load_error = f"Telecom index not found at {_TELECOM_FILE}"
            _telecom_cache = {"metadata": {"error": _telecom_load_error, "feature_counts": {}}, "features": {}}
            return _telecom_cache

        try:
            with open(_TELECOM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _telecom_cache = data
            _telecom_load_error = None
        except Exception as e:
            _telecom_load_error = str(e)
            _telecom_cache = {"metadata": {"error": _telecom_load_error, "feature_counts": {}}, "features": {}}
        return _telecom_cache


def get_telecom_feature_counts() -> dict[str, int]:
    """Return the telecom index feature counts per category."""
    data = load_telecom_index()
    return data.get("metadata", {}).get("feature_counts", {})


def get_facility_points() -> list[dict[str, Any]]:
    """Return PeeringDB facility points (all facilities with coordinates).

    Compact keys: id, lat, lon, t='fac', q='obs', c (country), city, name, op, ix, net
    """
    data = load_telecom_index()
    return data.get("features", {}).get("facility_points", [])


def get_ixp_proxy_points() -> list[dict[str, Any]]:
    """Return IXP proxy points (PeeringDB facilities with ix_count > 0).

    Compact keys: id, lat, lon, t='ixp', q='obs', c (country), city, name, ix
    """
    data = load_telecom_index()
    return data.get("features", {}).get("ixp_proxy_points", [])


def has_facility_data() -> bool:
    return len(get_facility_points()) > 0


def has_ixp_proxy_data() -> bool:
    return len(get_ixp_proxy_points()) > 0


def get_telecom_proxy_source_summary() -> str:
    """Return a human-readable summary of available telecom proxy sources."""
    fac = len(get_facility_points())
    ixp = len(get_ixp_proxy_points())
    dc = len(get_data_center_points())
    cbl = len(get_cable_landing_points())
    parts = []
    if ixp > 0:
        parts.append(f"{ixp} IXP proxy points (PeeringDB facilities with ix_count>0)")
    if fac > 0:
        parts.append(f"{fac} PeeringDB facility points (telecom density)")
    if dc > 0:
        parts.append(f"{dc} data center points (observed)")
    if cbl > 0:
        parts.append(f"{cbl} cable landing proxy points")
    if not parts:
        return "No telecom proxy data available."
    return "Telecom proxy sources: " + "; ".join(parts) + "."