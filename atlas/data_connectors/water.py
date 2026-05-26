"""Water stress data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_water_stress_data(lat: float, lon: float) -> dict[str, Any]:
    return {
        "water_stress_score": None,
        "data_source": "proxy",
    }
