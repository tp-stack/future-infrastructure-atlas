"""Power grid data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_power_infrastructure_near_point(lat: float, lon: float, radius_km: float = 50.0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "nearest_substation_km": None,
        "nearest_power_line_km": None,
        "substation_voltage_kv": None,
        "estimated_grid_capacity_mw": None,
        "grid_congestion_score": None,
        "power_reliability_score": None,
    }
    return result


def get_substations_near_point(lat: float, lon: float, radius_km: float = 50.0) -> list[dict[str, Any]]:
    return []


def estimate_grid_capacity(substation_distance_km: float | None, profile_min_mw: float) -> float | None:
    if substation_distance_km is None:
        return None
    if substation_distance_km < 1:
        return profile_min_mw * 3
    if substation_distance_km < 5:
        return profile_min_mw * 2
    if substation_distance_km < 15:
        return profile_min_mw * 1
    if substation_distance_km < 25:
        return profile_min_mw * 0.5
    return None
