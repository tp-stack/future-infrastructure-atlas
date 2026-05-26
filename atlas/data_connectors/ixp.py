"""Internet Exchange Point data connector for site selection."""

from __future__ import annotations

from typing import Any


def get_nearest_ixp(lat: float, lon: float) -> dict[str, Any]:
    return {"nearest_ixp_km": None, "ixp_name": None, "data_source": "proxy"}
