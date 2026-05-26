"""Incentives data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_incentive_data(country: str | None = None, region: str | None = None) -> dict[str, Any]:
    return {
        "incentive_score": 30.0,
        "incentive_programs": [],
        "data_source": "proxy",
    }
