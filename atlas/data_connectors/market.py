"""Market demand data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_market_data(lat: float, lon: float) -> dict[str, Any]:
    return {
        "market_demand_score": None,
        "ai_cluster_score": None,
        "enterprise_proximity_score": None,
        "data_source": "proxy",
    }
