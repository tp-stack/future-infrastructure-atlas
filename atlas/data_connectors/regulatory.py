"""Regulatory data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_regulatory_data(country: str | None = None, lat: float | None = None, lon: float | None = None) -> dict[str, Any]:
    return {
        "data_sovereignty_score": None,
        "regulatory_stability_score": None,
        "political_risk_score": None,
        "security_risk_score": None,
        "data_source": "country-level proxy",
    }
