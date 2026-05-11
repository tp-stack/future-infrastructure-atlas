"""Geometry parsing, validation, and coordinate utilities."""

from __future__ import annotations

from typing import Any


def parse_lon(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return v if (-180 <= v <= 180) else None
    except (ValueError, TypeError):
        return None


def parse_lat(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return v if (-90 <= v <= 90) else None
    except (ValueError, TypeError):
        return None


def valid_lon_lat(lon: float, lat: float) -> bool:
    return (
        lon is not None and lat is not None
        and isinstance(lon, (int, float)) and isinstance(lat, (int, float))
        and -180 <= lon <= 180 and -90 <= lat <= 90
    )


def valid_line_geometry(coords: list) -> bool:
    if not coords or len(coords) < 2:
        return False
    for pt in coords:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            return False
        lon, lat = pt[0], pt[1]
        if not valid_lon_lat(lon, lat):
            return False
    return True


def normalize_linestring_geometry(geometry: dict) -> list[list[float]] | None:
    if geometry.get("type") != "LineString":
        return None
    coords = geometry.get("coordinates", [])
    if not valid_line_geometry(coords):
        return None
    return [[round(float(c[0]), 6), round(float(c[1]), 6)] for c in coords]


def normalize_multilinestring_geometry(geometry: dict) -> list[list[float]] | None:
    if geometry.get("type") != "MultiLineString":
        return None
    lines = geometry.get("coordinates", [])
    merged = []
    for line in lines:
        if valid_line_geometry(line):
            merged.extend([[round(float(c[0]), 6), round(float(c[1]), 6)] for c in line])
    if len(merged) < 2:
        return None
    return merged


def geometry_bounds(geometry: list[list[float]]) -> tuple[float, float, float, float] | None:
    if not geometry or len(geometry) < 2:
        return None
    lons = [pt[0] for pt in geometry if pt and len(pt) >= 2]
    lats = [pt[1] for pt in geometry if pt and len(pt) >= 2]
    if not lons or not lats:
        return None
    return min(lons), min(lats), max(lons), max(lats)


def safe_slug_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
