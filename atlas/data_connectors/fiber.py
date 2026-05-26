"""Fiber data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_fiber_near_point(lat: float, lon: float, radius_km: float = 50.0) -> dict[str, Any]:
    return {
        "nearest_fiber_km": None,
        "fiber_diversity_score": None,
        "fiber_providers": [],
        "data_source": "proxy",
    }


def estimate_fiber_availability(lat: float, lon: float) -> float | None:
    return None
