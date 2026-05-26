"""Climate risk data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_climate_risk_data(lat: float, lon: float) -> dict[str, Any]:
    return {
        "heat_risk_score": None,
        "flood_risk_score": None,
        "seismic_risk_score": None,
        "wildfire_risk_score": None,
        "data_source": "proxy",
    }
