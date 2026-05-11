"""Load data center coordinates from geospatial source files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas.ingestion.geojson_loader import load_geojson_features, normalize_features
from atlas.ingestion.geometry_utils import parse_lon, parse_lat


def load_datacenters_from_geojson(
    path: Path,
    source_name: str = "",
    coordinate_precision: str = "metro_level",
    source_license: str = "",
    confidence: float = 0.0,
) -> list[dict]:
    if not path.exists():
        return []
    features = load_geojson_features(path)
    normalized = normalize_features(features, expected_geom="Point")

    dcs = []
    seen_names: set[str] = set()
    for nf in normalized:
        props = nf["properties"]
        name = _get_dc_name(props)
        if not name:
            continue

        key = name.strip().lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        coords = nf["coordinates"]
        lon, lat = coords[0], coords[1]

        dc_precision = (
            props.get("coordinate_precision")
            or props.get("precision")
            or coordinate_precision
        )

        dcs.append({
            "n": name,
            "op": _get_dc_operator(props),
            "c": _get_dc_country(props),
            "city": _get_dc_city(props),
            "lat": float(lat),
            "lon": float(lon),
            "coordinate_precision": dc_precision,
            "mapped_status": "mapped",
            "coordinate_source": source_name or props.get("source", ""),
            "source_license": source_license,
            "confidence": confidence,
            "address": props.get("address", "") or "",
            "mw": _parse_mw(props),
        })
    return dcs


def load_datacenters_from_csv(
    path: Path,
    source_name: str = "",
    coordinate_precision: str = "metro_level",
    source_license: str = "",
    confidence: float = 0.0,
) -> list[dict]:
    if not path.exists():
        return []
    import csv
    dcs = []
    seen_names: set[str] = set()
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _get_dc_name_from_row(row)
            if not name:
                continue
            key = name.strip().lower()
            if key in seen_names:
                continue
            seen_names.add(key)

            lon = parse_lon(_field(row, "longitude", "lon", "lng", "x"))
            lat = parse_lat(_field(row, "latitude", "lat", "y"))
            if lon is None or lat is None:
                continue

            dc_precision = _field(row, "coordinate_precision", "precision") or coordinate_precision

            dcs.append({
                "n": name,
                "op": _field(row, "operator", "owner", "op"),
                "c": _field(row, "country", "country_code", "nation"),
                "city": _field(row, "city", "location", "metro"),
                "lat": lat,
                "lon": lon,
                "coordinate_precision": dc_precision,
                "mapped_status": "mapped",
                "coordinate_source": source_name or _field(row, "source", "source_dataset"),
                "source_license": source_license,
                "confidence": confidence,
                "address": _field(row, "address"),
                "mw": _parse_mw(row),
            })
    return dcs


def _get_dc_name(props: dict) -> str:
    for field in ("name", "facility_name", "title"):
        val = props.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _get_dc_name_from_row(row: dict) -> str:
    for field in ("name", "facility_name", "title"):
        val = row.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _get_dc_operator(props: dict) -> str:
    for field in ("operator", "owner", "op"):
        val = props.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _get_dc_country(props: dict) -> str:
    for field in ("country", "country_code", "nation"):
        val = props.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _get_dc_city(props: dict) -> str:
    for field in ("city", "location", "metro"):
        val = props.get(field, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _field(row: dict, *names: str) -> str:
    for n in names:
        val = row.get(n, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _parse_mw(row_or_props: dict) -> float | None:
    for field in ("capacity_mw", "mw", "current_power_mw", "power_mw"):
        val = row_or_props.get(field)
        if val is not None:
            try:
                return round(float(val), 1)
            except (ValueError, TypeError):
                pass
    return None
