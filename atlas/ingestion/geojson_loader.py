"""Load features from GeoJSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas.ingestion.geometry_utils import valid_lon_lat, valid_line_geometry


def load_geojson_features(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
    elif data.get("type") == "Feature":
        features = [data]
    else:
        features = []
    return features


def normalize_point_feature(feature: dict) -> dict | None:
    geom = feature.get("geometry")
    if not geom or geom.get("type") != "Point":
        return None
    coords = geom.get("coordinates")
    if not coords or len(coords) < 2:
        return None
    lon, lat = coords[0], coords[1]
    if not valid_lon_lat(lon, lat):
        return None
    props = feature.get("properties") or {}
    return {
        "type": "Point",
        "coordinates": [float(lon), float(lat)],
        "properties": dict(props),
    }


def normalize_line_feature(feature: dict) -> dict | None:
    geom = feature.get("geometry")
    if not geom:
        return None
    geom_type = geom.get("type")
    coords_raw = geom.get("coordinates", [])

    if geom_type == "LineString":
        if not valid_line_geometry(coords_raw):
            return None
        normalized = [[float(c[0]), float(c[1])] for c in coords_raw]
    elif geom_type == "MultiLineString":
        merged = []
        for line in coords_raw:
            if valid_line_geometry(line):
                merged.extend([[float(c[0]), float(c[1])] for c in line])
        if len(merged) < 2:
            return None
        normalized = merged
    else:
        return None

    props = feature.get("properties") or {}
    return {
        "type": "LineString",
        "coordinates": normalized,
        "properties": dict(props),
    }


def normalize_features(raw_features: list[dict], expected_geom: str = "Point") -> list[dict]:
    out = []
    for f in raw_features:
        if expected_geom == "Point":
            nf = normalize_point_feature(f)
        elif expected_geom == "LineString":
            nf = normalize_line_feature(f)
        else:
            nf = normalize_point_feature(f) or normalize_line_feature(f)
        if nf:
            out.append(nf)
    return out
