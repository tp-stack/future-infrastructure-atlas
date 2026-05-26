"""Land use data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_land_use_data(lat: float, lon: float) -> dict[str, Any]:
    return {
        "industrial_land_score": None,
        "zoning_compatibility_score": None,
        "brownfield_score": None,
        "permitting_complexity_score": None,
        "data_source": "proxy",
    }
