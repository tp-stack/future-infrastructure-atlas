from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
PROCESSED_WEB = PROJECT_ROOT / "data" / "processed" / "web"

WRI_CSV = PROJECT_ROOT / "data" / "raw" / "wri_global_power_plants" / "manual_20260511" / "global_power_plant_database_wri_all.csv"
CABLES_CSV = PROJECT_ROOT / "data" / "raw" / "submarine_cable_lines" / "manual_20260511" / "global_submarine_cable_lines_scn_segments.csv"
DATACENTERS_CSV = PROJECT_ROOT / "data" / "raw" / "data_centers" / "manual_20260511" / "frontier_ai_data_centers_epoch_public.csv"

CABLE_GEOM_LOOKUP = PROJECT_ROOT / "config" / "cable_geometries.json"
CABLE_GEOMETRY_CSV_DEFAULT = (
    PROJECT_ROOT / "data/raw/submarine_cable_geometries/kmcd_manual_20260511"
    / "world_submarine_cable_geometries_kmcd.csv"
)
DC_COORD_LOOKUP = PROJECT_ROOT / "config" / "datacenter_locations.yaml"
PEERINGDB_COORDS_CSV = (
    PROJECT_ROOT / "data/raw/data_centers/peeringdb_manual_20260511"
    / "global_datacenters_public_peeringdb_coordinates.csv"
)

CABLE_SOURCE_DIRS = [
    PROJECT_ROOT / "data" / "raw" / "submarine_cables",
    PROJECT_ROOT / "data" / "raw" / "submarine_cable_lines",
]

DC_SOURCE_DIRS = [
    PROJECT_ROOT / "data" / "raw" / "data_centers",
]

VALID_FUELS = {
    "hydro", "solar", "wind", "nuclear", "coal", "natural gas",
    "oil", "biomass", "geothermal", "waste", "cogeneration",
    "wave and tidal", "petroleum", "gas", "other",
}

FUEL_NORMALIZE = {
    "natural gas": "Natural Gas",
    "natural gas with ccs": "Natural Gas",
    "natural gas with carbon capture": "Natural Gas",
    "gas": "Natural Gas",
    "hydro": "Hydro",
    "solar": "Solar",
    "solar pv": "Solar",
    "solar thermal": "Solar",
    "wind": "Wind",
    "wind onshore": "Wind",
    "wind offshore": "Wind",
    "nuclear": "Nuclear",
    "coal": "Coal",
    "oil": "Oil",
    "biomass": "Biomass",
    "geothermal": "Geothermal",
    "waste": "Waste",
    "cogeneration": "Cogeneration",
    "wave and tidal": "Wave and Tidal",
    "petroleum": "Oil",
    "other": "Other",
}


def _find_country_col(fieldnames: list[str]) -> str:
    for f in fieldnames:
        if f.strip().lower() == "country":
            return f
    for f in fieldnames:
        if "country" in f.lower() and "long" not in f.lower():
            return f
    return fieldnames[0]


def _valid_lat(lat_str: str) -> bool:
    try:
        v = float(lat_str)
        return -90 <= v <= 90
    except (ValueError, TypeError):
        return False


def _valid_lng(lng_str: str) -> bool:
    try:
        v = float(lng_str)
        return -180 <= v <= 180
    except (ValueError, TypeError):
        return False


def _valid_coord_pair(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _normalize_fuel(fuel: str) -> str:
    val = (fuel or "").strip()
    if not val:
        return "Other"
    key = val.lower()
    return FUEL_NORMALIZE.get(key, val)


import re
import unicodedata

def _normalize_key(name: str) -> str:
    n = name.strip().lower()
    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
    n = re.sub(r'[^a-z0-9]', '_', n)
    n = re.sub(r'_+', '_', n)
    return n.strip('_')


def _parse_lp_list(value: str) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split("|") if p.strip()]

def _merge_lp_lists(existing: list[str], incoming: str) -> list[str]:
    if not incoming:
        return existing
    parts = [p.strip() for p in incoming.split("|") if p.strip()]
    seen = {p.lower() for p in existing}
    for p in parts:
        if p.lower() not in seen:
            existing.append(p)
    return existing

def _merge_text_values(existing: str, incoming: str, separator: str = " | ") -> str:
    existing = (existing or "").strip()
    incoming = (incoming or "").strip()
    if not incoming:
        return existing
    if not existing:
        return incoming
    parts = [p.strip() for p in existing.split(separator) if p.strip()]
    if incoming in parts:
        return existing
    return f"{existing}{separator}{incoming}"


def _merge_csv_values(existing: str, incoming: str) -> str:
    existing_parts = [p.strip() for p in (existing or "").split(",") if p.strip()]
    seen = {p.lower() for p in existing_parts}
    for part in [p.strip() for p in (incoming or "").split(",") if p.strip()]:
        if part.lower() not in seen:
            existing_parts.append(part)
            seen.add(part.lower())
    return ", ".join(existing_parts)


def _read_wri(path: Path) -> tuple[list[dict], int]:
    records = []
    rejected = 0
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        country_col = _find_country_col(reader.fieldnames)

        for row in reader:
            lat_str = (row.get("latitude") or "").strip()
            lng_str = (row.get("longitude") or "").strip()
            name = (row.get("name") or "").strip()
            fuel_raw = (row.get("primary_fuel") or "").strip()

            if not name or not _valid_lat(lat_str) or not _valid_lng(lng_str):
                rejected += 1
                continue

            country_code = (row.get(country_col) or "").strip()
            country_long = (row.get("country_long") or "").strip()
            display_country = country_long or country_code

            cap_str = (row.get("capacity_mw") or "").strip()
            try:
                mw = round(float(cap_str), 2) if cap_str else 0.0
            except ValueError:
                mw = 0.0

            records.append({
                "n": name,
                "c": display_country,
                "f": _normalize_fuel(fuel_raw),
                "mw": round(float(cap_str)) if cap_str else 0,
                "lat": max(-90.0, min(90.0, round(float(lat_str), 2))),
                "lon": max(-180.0, min(180.0, round(float(lng_str), 2))),
            })

    return records, rejected


def _read_cables(path: Path) -> list[dict]:
    records_by_key: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("cable_system_name") or "").strip()
            if not name:
                continue
            key = _normalize_key(name)
            record = records_by_key.get(key)
            if record is None:
                records_by_key[key] = {
                    "n": name,
                    "operators": (row.get("operators") or "").strip(),
                    "landing_points": _parse_lp_list(row.get("landing_points") or ""),
                    "segment_endpoints": (row.get("segment_endpoints") or row.get("segment_endpoints_raw") or "").strip(),
                    "length_km": (row.get("system_length_km_raw") or row.get("segment_length_km_raw") or "").strip(),
                    "source": (row.get("source_dataset") or "").strip(),
                    "segment_count": 1,
                }
                continue

            record["operators"] = _merge_csv_values(record.get("operators", ""), row.get("operators") or "")
            record["landing_points"] = _merge_lp_lists(record.get("landing_points", []), row.get("landing_points") or "")
            record["segment_endpoints"] = _merge_text_values(
                record.get("segment_endpoints", ""),
                row.get("segment_endpoints") or row.get("segment_endpoints_raw") or "",
            )
            record["source"] = _merge_csv_values(record.get("source", ""), row.get("source_dataset") or "")
            if not record.get("length_km"):
                record["length_km"] = (row.get("system_length_km_raw") or row.get("segment_length_km_raw") or "").strip()
            record["segment_count"] = int(record.get("segment_count", 0)) + 1
    return list(records_by_key.values())


def _cable_geometry_to_lines(geometry: list) -> list[list[tuple[float, float]]]:
    if not geometry:
        return []
    if isinstance(geometry[0], list) and geometry[0] and isinstance(geometry[0][0], (list, tuple)):
        return [line for line in geometry if isinstance(line, list) and len(line) >= 2]
    return [geometry] if len(geometry) >= 2 else []


def _lines_to_cable_geometry(lines: list[list[tuple[float, float]]]) -> list:
    return lines[0] if len(lines) == 1 else lines


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_landing_points(value: str) -> list[str]:
    """Parse landing_points_json from CSV and return a list of landing point names."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    names = []
    for item in parsed:
        if isinstance(item, dict):
            name = item.get("name") or item.get("landing_point") or item.get("city")
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return names


def _source_cable_from_geometry_entry(entry: dict) -> dict:
    return {
        "n": entry.get("cable_name", ""),
        "source": entry.get("source_name", "KMCD Internet Infrastructure Map"),
        "geometry": entry.get("geometry", []),
        "geometry_precision": entry.get("geometry_precision", "generalized_public_geometry"),
        "mapped_status": "mapped",
        "coordinate_source": entry.get("source_name", ""),
        "source_license": entry.get("source_license", ""),
        "source_url": entry.get("source_url", ""),
        "confidence": entry.get("confidence", 0.0),
        "operators": entry.get("owners", ""),
        "landing_points": _format_landing_points(entry.get("landing_points_json", "")),
        "length_km": entry.get("length", ""),
        "source_only_geometry": True,
    }


def _append_geometry_only_cables(cables: list[dict], lookup: dict) -> list[dict]:
    existing_keys = {_normalize_key(c.get("n", "")) for c in cables}
    combined = list(cables)
    for key, entry in sorted(lookup.items(), key=lambda item: item[1].get("cable_name", item[0]).lower()):
        if key in existing_keys:
            continue
        combined.append(_source_cable_from_geometry_entry(entry))
        existing_keys.add(key)
    return combined


def _apply_cable_geometry_supplement(cables: list[dict]) -> None:
    """Apply supplemental geometries (fuzzy match bridge + schematic) to
    cables that remain unmapped after the primary KMCD lookup."""
    supp_path = PROJECT_ROOT / "config" / "cable_geometry_supplement.json"
    if not supp_path.exists():
        return
    with open(supp_path, encoding="utf-8") as f:
        supplement = json.load(f)

    applied = 0
    for cable in cables:
        if cable.get("mapped_status") != "unmapped":
            continue
        key = _normalize_key(cable.get("n", ""))
        entry = supplement.get(key)
        if not entry or not entry.get("geometry"):
            continue
        cable["geometry"] = entry["geometry"]
        cable["mapped_status"] = "mapped"
        srctype = entry.get("source", "supplemental")
        if srctype == "fuzzy_match_kmcd":
            cable["coordinate_source"] = "KMCD Internet Infrastructure Map (fuzzy name match)"
            cable["geometry_precision"] = entry.get("precision", "generalized_public_geometry")
        else:
            cable["coordinate_source"] = "schematic from SCN landing points"
            cable["geometry_precision"] = "schematic_landing_points"
        applied += 1

    if applied:
        print(f"[build] Applied supplemental geometries to {applied} unmapped cables")


def _merge_geometry_lookup_entry(lookup: dict, key: str, entry: dict) -> None:
    incoming_lines = _cable_geometry_to_lines(entry["geometry"])
    if not incoming_lines:
        return

    existing = lookup.get(key)
    if existing is None:
        entry["_geometry_lines"] = incoming_lines
        lookup[key] = entry
        return

    existing_lines = existing.get("_geometry_lines")
    if existing_lines is None:
        existing_lines = _cable_geometry_to_lines(existing.get("geometry", []))
        existing["_geometry_lines"] = existing_lines

    existing_lines.extend(incoming_lines)
    existing["geometry"] = _lines_to_cable_geometry(existing_lines)
    existing["geometry_type"] = "MultiLineString" if len(existing_lines) > 1 else "LineString"
    existing["owners"] = _merge_csv_values(existing.get("owners", ""), entry.get("owners", ""))
    existing["landing_points_json"] = existing.get("landing_points_json") or entry.get("landing_points_json", "")
    if not existing.get("length"):
        existing["length"] = entry.get("length", "")


def _finalize_geometry_lookup(lookup: dict) -> dict:
    for entry in lookup.values():
        lines = entry.pop("_geometry_lines", None)
        if lines is not None:
            entry["geometry"] = _lines_to_cable_geometry(lines)
            entry["geometry_type"] = "MultiLineString" if len(lines) > 1 else "LineString"
    return lookup


def _read_datacenters(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            power_str = (row.get("current_power_mw") or "").strip()
            try:
                mw = round(float(power_str), 1) if power_str else None
            except ValueError:
                mw = None
            records.append({
                "n": name,
                "op": (row.get("owner") or "").strip(),
                "c": (row.get("country") or "").strip(),
                "address": (row.get("address") or "").strip(),
                "mw": mw,
                "source": (row.get("source_dataset") or "").strip(),
            })
    return records


def _load_cable_geom_lookup(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    lookup = {}
    for key, entry in raw.items():
        geom = entry.get("geometry", [])
        valid_geom = [(p[0], p[1]) for p in geom if isinstance(p, (list, tuple)) and len(p) >= 2 and _valid_coord_pair(p[0], p[1])]
        if len(valid_geom) >= 2:
            entry["geometry"] = valid_geom
            lookup[_normalize_key(key)] = entry
    return lookup


def _load_dc_coord_lookup(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not raw:
        return {}
    lookup = {}
    for key, entry in raw.items():
        lat = entry.get("latitude")
        lon = entry.get("longitude")
        if lat is not None and lon is not None and _valid_coord_pair(lon, lat):
            lookup[_normalize_key(key)] = entry
    return lookup


def _load_cable_geometry_csv(path: Path) -> dict:
    """Load cable geometry CSV and return name-keyed lookup."""
    if not path.exists():
        return {}
    import csv
    lookup: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("cable_name") or "").strip()
            if not name:
                continue
            geom_json = (row.get("geometry_json") or "").strip()
            if not geom_json:
                continue
            try:
                geom = json.loads(geom_json)
            except json.JSONDecodeError:
                continue
            if not isinstance(geom, dict):
                continue
            gtype = geom.get("type")
            coords = geom.get("coordinates", [])
            if gtype == "LineString":
                valid = [(round(p[0], 1), round(p[1], 1)) for p in coords if isinstance(p, (list, tuple)) and len(p) >= 2 and _valid_coord_pair(p[0], p[1])]
                if len(valid) < 2:
                    continue
                geom_out = valid
            elif gtype == "MultiLineString":
                cleaned = []
                for line in coords:
                    valid_line = [(round(p[0], 1), round(p[1], 1)) for p in line if isinstance(p, (list, tuple)) and len(p) >= 2 and _valid_coord_pair(p[0], p[1])]
                    if len(valid_line) >= 2:
                        cleaned.append(valid_line)
                if not cleaned:
                    continue
                geom_out = cleaned
            else:
                continue
            key = _normalize_key(name)
            entry = {
                "geometry": geom_out,
                "geometry_type": gtype,
                "geometry_precision": row.get("geometry_precision", "generalized_public_geometry"),
                "source_name": row.get("source_name", "KMCD Internet Infrastructure Map"),
                "source_url": row.get("source_url", ""),
                "source_license": row.get("source_license", "to_verify"),
                "confidence": _parse_float(row.get("confidence", ""), 0.65),
                "license_review_required": row.get("license_review_required", "true") == "true",
                "cable_name": name,
                "owners": row.get("owners", ""),
                "length": row.get("length", ""),
                "landing_points_json": row.get("landing_points_json", ""),
            }
            _merge_geometry_lookup_entry(lookup, key, entry)
    return _finalize_geometry_lookup(lookup)


def _enrich_cable_geometry(cables: list[dict], lookup: dict) -> list[dict]:
    enriched = []
    for cable in cables:
        key = _normalize_key(cable["n"])
        entry = lookup.get(key)
        if entry:
            geom = entry.get("geometry", [])
            enriched.append({
                "n": cable["n"],
                "source": cable["source"],
                "geometry": geom,
                "geometry_precision": entry.get("geometry_precision", "generalized_public_geometry"),
                "mapped_status": "mapped",
                "coordinate_source": entry.get("source_name", ""),
                "source_license": entry.get("source_license", ""),
                "confidence": entry.get("confidence", 0.0),
                "operators": cable["operators"],
                "landing_points": cable["landing_points"],
                "length_km": cable["length_km"],
                "segment_count": cable.get("segment_count", 1),
            })
        else:
            enriched.append({
                "n": cable["n"],
                "source": cable["source"],
                "geometry": [],
                "mapped_status": "unmapped",
                "unmapped_reason": "no_verified_geometry_in_lookup",
                "operators": cable["operators"],
                "landing_points": cable["landing_points"],
                "length_km": cable["length_km"],
                "segment_count": cable.get("segment_count", 1),
            })
    return enriched


def _enrich_dc_coordinates(dcs: list[dict], lookup: dict) -> list[dict]:
    enriched = []
    for dc in dcs:
        key = _normalize_key(dc["n"])
        entry = lookup.get(key)
        if entry:
            enriched.append({
                "n": dc["n"],
                "op": dc["op"],
                "c": dc["c"],
                "city": "",
                "lat": float(entry["latitude"]),
                "lon": float(entry["longitude"]),
                "mw": dc["mw"],
                "source": dc["source"],
                "coordinate_precision": entry.get("coordinate_precision", "metro_level"),
                "mapped_status": "mapped",
                "coordinate_source": entry.get("coordinate_source", ""),
                "source_license": entry.get("source_license", ""),
                "confidence": entry.get("confidence", 0.0),
                "address": dc["address"],
            })
        else:
            enriched.append({
                "n": dc["n"],
                "op": dc["op"],
                "c": dc["c"],
                "city": "",
                "mw": dc["mw"],
                "source": dc["source"],
                "mapped_status": "unmapped",
                "unmapped_reason": "no_verified_coordinates_in_lookup",
                "coordinate_precision": "none",
                "confidence": 0.0,
                "address": dc["address"],
            })
    return enriched


def _load_peeringdb_datacenters(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    dcs = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lat_str = (row.get("latitude") or "").strip()
            lon_str = (row.get("longitude") or "").strip()
            confidence = (row.get("confidence") or "").strip()
            if not lat_str or not lon_str:
                continue
            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except (ValueError, TypeError):
                continue
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue
            dcs.append({
                "n": (row.get("name") or "").strip(),
                "op": (row.get("operator") or row.get("organization") or "").strip(),
                "c": (row.get("country") or "").strip(),
                "city": (row.get("city") or "").strip(),
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "source": "PeeringDB",
                "mapped_status": "mapped",
            })
    return dcs if dcs else None


def _discover_geojson_files(search_dirs: list[Path]) -> list[Path]:
    found = []
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in ("*.geojson", "*.json"):
            found.extend(sorted(d.rglob(ext)))
    return found


def _load_geospatial_cables(
    cable_geo_path: Path | None,
    allow_licensed: bool,
    config_path: Path | None,
) -> list[dict] | None:
    path = cable_geo_path
    if path is None:
        found = _discover_geojson_files(CABLE_SOURCE_DIRS)
        if not found:
            return None
        path = found[0]
        print(f"[build] Discovered cable GeoJSON: {path}")

    if not path.exists():
        print(f"[build] Cable GeoJSON not found: {path}", file=sys.stderr)
        return None

    from atlas.ingestion.cable_loader import has_license_restriction, load_cables_from_geojson

    if config_path and config_path.exists():
        import yaml
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    else:
        cfg = None

    if has_license_restriction(path.name, cfg) and not allow_licensed:
        print(
            "ERROR: Licensed source detected for cables. "
            "Re-run with --allow-licensed-sources only if you have rights to use this file.",
            file=sys.stderr,
        )
        sys.exit(1)

    cables = load_cables_from_geojson(path)
    print(f"[build] Loaded {len(cables)} cables from geospatial source")
    return cables


def _load_geospatial_datacenters(
    dc_geo_path: Path | None,
    allow_licensed: bool,
    config_path: Path | None,
) -> list[dict] | None:
    path = dc_geo_path
    if path is None:
        found = _discover_geojson_files(DC_SOURCE_DIRS)
        if not found:
            return None
        path = found[0]
        print(f"[build] Discovered DC GeoJSON: {path}")

    if not path.exists():
        print(f"[build] DC source not found: {path}", file=sys.stderr)
        return None

    from atlas.ingestion.datacenter_loader import load_datacenters_from_geojson, load_datacenters_from_csv

    if path.suffix.lower() in (".geojson", ".json"):
        dcs = load_datacenters_from_geojson(path)
    elif path.suffix.lower() == ".csv":
        dcs = load_datacenters_from_csv(path)
    else:
        print(f"[build] Unsupported DC format: {path.suffix}", file=sys.stderr)
        return None

    print(f"[build] Loaded {len(dcs)} data centers from geospatial source")
    return dcs


def build_web_data(
    max_public_mb: float = 5.0,
    cable_geo_path: Path | None = None,
    dc_geo_path: Path | None = None,
    allow_licensed_sources: bool = False,
    cable_geometry_csv_path: Path | None = None,
    allow_license_review: bool = False,
    peeringdb_csv_path: Path | None = None,
) -> bool:
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)
    PROCESSED_WEB.mkdir(parents=True, exist_ok=True)

    sources = [
        {
            "key": "wri_global_power_plant_database",
            "name": "WRI Global Power Plant Database",
            "url": "https://datasets.wri.org/dataset/globalpowerplantdatabase",
            "license": "Creative Commons Attribution 4.0 (CC BY 4.0)",
        },
        {
            "key": "scn_submarine_cables",
            "name": "SCN Submarine Cable Network Data",
            "url": "https://github.com/miaw-net/scn-data",
            "license": "Public research dataset",
        },
        {
            "key": "epoch_ai_data_centers",
            "name": "Epoch AI Frontier Data Centers",
            "url": "https://epoch.ai/data/data-centers",
            "license": "Creative Commons Attribution (CC BY)",
        },
    ]

    pp, pp_rej = _read_wri(WRI_CSV)
    cables_raw = _read_cables(CABLES_CSV)
    dcs_raw = _read_datacenters(DATACENTERS_CSV)

    cable_geom_lookup = _load_cable_geom_lookup(CABLE_GEOM_LOOKUP)
    dc_coord_lookup = _load_dc_coord_lookup(DC_COORD_LOOKUP)

    config_path = PROJECT_ROOT / "config" / "sources.yaml"

    # Cable geometry CSV path (KMCD or similar)
    cable_geometry_csv_used = None
    if cable_geometry_csv_path is not None:
        csv_path = cable_geometry_csv_path
        if csv_path.exists():
            # Check license review requirement
            with open(csv_path, encoding="utf-8-sig") as f:
                import csv as _csv
                reader = _csv.DictReader(f)
                first_row = next(reader, None)
                if first_row:
                    lrr = (first_row.get("license_review_required") or "true").strip().lower()
                    if lrr == "true" and not allow_license_review:
                        print(
                            "ERROR: Cable geometry source requires license review. "
                            "Re-run with --allow-license-review only for internal/prototype use.",
                            file=sys.stderr,
                        )
                        sys.exit(1)
            geom_lookup = _load_cable_geometry_csv(csv_path)
            cables = _enrich_cable_geometry(cables_raw, geom_lookup)
            cables = _append_geometry_only_cables(cables, geom_lookup)
            cable_geometry_csv_used = csv_path
            print(f"[build] Enriched cables from geometry CSV: {csv_path.name} ({len(geom_lookup)} entries)")

            # ── Apply supplemental geometries (fuzzy bridge + schematic) ──
            _apply_cable_geometry_supplement(cables)
        else:
            print(f"[build] Cable geometry CSV not found: {csv_path}", file=sys.stderr)

    if cable_geometry_csv_used is None:
        # Try geospatial cables (GeoJSON loader)
        geo_cables = _load_geospatial_cables(cable_geo_path, allow_licensed_sources, config_path)
        if geo_cables is not None:
            cables = geo_cables
            geo_cable_source = cable_geo_path or (_discover_geojson_files(CABLE_SOURCE_DIRS)[:1] or [None])[0]
            if geo_cable_source:
                sources.append({
                    "key": "geospatial_cables",
                    "name": f"Geospatial cable source ({geo_cable_source.name})",
                    "url": "",
                    "license": "User-provided",
                })
        else:
            cables = _enrich_cable_geometry(cables_raw, cable_geom_lookup)

    # Try PeeringDB data centers from coordinates CSV
    peeringdb_dcs = None
    peeringdb_csv = peeringdb_csv_path or PEERINGDB_COORDS_CSV
    if peeringdb_csv.exists():
        peeringdb_dcs = _load_peeringdb_datacenters(peeringdb_csv)
    if peeringdb_dcs is not None:
        dcs = peeringdb_dcs
        sources.append({
            "key": "peeringdb_facilities",
            "name": "PeeringDB facilities / interconnection data centers",
            "url": "https://www.peeringdb.com/",
            "license": "PeeringDB public/user-maintained facility data — verify terms before commercial redistribution",
        })
    else:
        # Try geospatial data centers
        geo_dcs = _load_geospatial_datacenters(dc_geo_path, allow_licensed_sources, config_path)
        if geo_dcs is not None:
            dcs = geo_dcs
            geo_dc_source = dc_geo_path or (_discover_geojson_files(DC_SOURCE_DIRS)[:1] or [None])[0]
            if geo_dc_source:
                sources.append({
                    "key": "geospatial_data_centers",
                    "name": f"Geospatial DC source ({geo_dc_source.name})",
                    "url": "",
                    "license": "User-provided",
                })
        else:
            dcs = _enrich_dc_coordinates(dcs_raw, dc_coord_lookup)

    # Add supplement source if it contributed geometry
    supp_path_local = PROJECT_ROOT / "config" / "cable_geometry_supplement.json"
    if supp_path_local.exists():
        with open(supp_path_local) as _f:
            _supp = json.load(_f)
        _fuzzy_count = sum(1 for v in _supp.values() if v.get("source") == "fuzzy_match_kmcd")
        _schematic_count = sum(1 for v in _supp.values() if v.get("source") == "schematic_landing_points")
        if _fuzzy_count:
            sources.append({
                "key": "cable_geometry_supplement_fuzzy",
                "name": f"KMCD cable geometries ({_fuzzy_count} fuzzy name-match entries)",
                "url": "https://map.kmcd.dev/data/all_cables.json",
                "license": "to_verify — requires license review before production/commercial use",
            })
        if _schematic_count:
            sources.append({
                "key": "cable_geometry_supplement_schematic",
                "name": f"Schematic cable geometries ({_schematic_count} landing-point-based entries)",
                "url": "",
                "license": "Derived from SCN landing point data — schematic/generalized routes",
            })

    cables_mapped = sum(1 for c in cables if c.get("mapped_status") == "mapped")
    cables_unmapped = sum(1 for c in cables if c.get("mapped_status") == "unmapped")
    dcs_mapped = sum(1 for d in dcs if d.get("mapped_status") == "mapped")
    dcs_unmapped = sum(1 for d in dcs if d.get("mapped_status") == "unmapped")

    cable_geometry_license_status = "to_verify"
    cable_geometry_review_required = False
    if cable_geometry_csv_used:
        cable_geometry_license_status = "to_verify"
        cable_geometry_review_required = True
        sources.append({
            "key": "cable_geometry_csv",
            "name": f"KMCD Internet Infrastructure Map — cable geometries",
            "url": "https://map.kmcd.dev/data/all_cables.json",
            "license": "to_verify — requires license review before production/commercial use",
        })

    unmapped_cables = [
        {
            "n": c["n"],
            "source": c.get("source", ""),
            "operators": c.get("operators", ""),
            "landing_points": c.get("landing_points", ""),
            "length_km": c.get("length_km", ""),
            "unmapped_reason": c.get("unmapped_reason", ""),
        }
        for c in cables if c.get("mapped_status") == "unmapped"
    ]
    unmapped_dcs = [
        {
            "n": d["n"],
            "op": d.get("op", ""),
            "c": d.get("c", ""),
            "address": d.get("address", ""),
            "mw": d.get("mw"),
            "source": d.get("source", ""),
            "unmapped_reason": d.get("unmapped_reason", ""),
        }
        for d in dcs if d.get("mapped_status") == "unmapped"
    ]

    data = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "disclaimer": (
                "This atlas uses public or redistribution-safe data. Some infrastructure layers are "
                "metadata-only where public geometries or coordinates are unavailable. No coordinates "
                "are inferred or invented. Submarine cable routes are generalized public geometries "
                "or schematic arcs, not exact surveyed trench routes. This layer uses PeeringDB public "
                "facility data. It includes interconnection facilities, colocation sites, and data centers "
                "with coordinates. It is not exhaustive of every global data center."
            ),
            "counts": {
                "power_plants_total": len(pp) + pp_rej,
                "power_plants_mapped": len(pp),
                "power_plants_rejected": pp_rej,
                "submarine_cables_total": len(cables),
                "submarine_cables_mapped": cables_mapped,
                "submarine_cables_unmapped": cables_unmapped,
                "cables_total": len(cables),
                "cables_mapped": cables_mapped,
                "cables_unmapped": cables_unmapped,
                "data_centers_total": len(dcs),
                "data_centers_mapped": dcs_mapped,
                "data_centers_unmapped": dcs_unmapped,
                "data_center_source": "PeeringDB public facility data" if peeringdb_dcs is not None else "Epoch AI + manual lookup",
                "data_center_license_status": "PeeringDB terms/AUP review required" if peeringdb_dcs is not None else "CC BY",
                "data_center_review_required": False,
                "geometry_lookup_count": len(cable_geom_lookup),
                "cable_geometry_source": "KMCD Internet Infrastructure Map" if cable_geometry_csv_used else "legacy_lookup",
                "cable_geometry_license_status": cable_geometry_license_status,
                "cable_geometry_review_required": cable_geometry_review_required,
            },
            "unmapped": {
                "submarine_cables": unmapped_cables,
                "data_centers": unmapped_dcs,
            },
        },
        "power_plants": pp,
        "cables": cables,
        "data_centers": dcs,
    }

    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    size_mb = len(raw.encode("utf-8")) / (1024 * 1024)

    if size_mb <= max_public_mb:
        output_path = FRONTEND_DATA / "atlas_web_data.json"
        output_path.write_text(raw, encoding="utf-8")
        print(f"atlas_web_data.json written to {output_path} ({size_mb:.2f} MB)")
        return True
    else:
        output_path = PROCESSED_WEB / "atlas_web_data.json"
        output_path.write_text(raw, encoding="utf-8")
        print(
            f"ERROR: Payload exceeds public limit ({size_mb:.2f} MB > {max_public_mb} MB). "
            f"Written to {output_path} instead of frontend/public/data/.",
            file=sys.stderr,
        )
        print("Use PMTiles/object storage or reduce frontend dataset.", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact web map data from raw CSVs and optional geospatial sources")
    parser.add_argument("--max-public-mb", type=float, default=5.0, help="Maximum size in MB for frontend public data (default: 5.0)")
    parser.add_argument("--cable-geo-path", type=str, default=None, help="Path to cable GeoJSON/JSON file")
    parser.add_argument("--datacenter-geo-path", type=str, default=None, help="Path to data center GeoJSON/JSON/CSV file")
    parser.add_argument("--allow-licensed-sources", action="store_true", default=False, help="Allow ingestion from licensed sources")
    parser.add_argument("--cable-geometry-csv", type=str, default=None, help=('Path to cable geometry CSV (e.g. data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv)'))
    parser.add_argument("--allow-license-review", action="store_true", default=False, help="Allow sources requiring license review (internal/prototype use only)")
    parser.add_argument("--peeringdb-csv", type=str, default=None, help="Path to PeeringDB facilities CSV (default: data/processed/global_datacenters_public_peeringdb.csv)")
    args = parser.parse_args()

    cable_path = Path(args.cable_geo_path) if args.cable_geo_path else None
    dc_path = Path(args.datacenter_geo_path) if args.datacenter_geo_path else None
    cable_csv_path = Path(args.cable_geometry_csv) if args.cable_geometry_csv else None
    peeringdb_path = Path(args.peeringdb_csv) if args.peeringdb_csv else None

    success = build_web_data(
        max_public_mb=args.max_public_mb,
        cable_geo_path=cable_path,
        dc_geo_path=dc_path,
        allow_licensed_sources=args.allow_licensed_sources,
        cable_geometry_csv_path=cable_csv_path,
        allow_license_review=args.allow_license_review,
        peeringdb_csv_path=peeringdb_path,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
