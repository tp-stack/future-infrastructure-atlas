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
DC_COORD_LOOKUP = PROJECT_ROOT / "config" / "datacenter_locations.yaml"

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


def _normalize_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


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
                "mw": mw,
                "lat": round(float(lat_str), 6),
                "lon": round(float(lng_str), 6),
            })

    return records, rejected


def _read_cables(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("cable_system_name") or "").strip()
            if not name:
                continue
            records.append({
                "n": name,
                "operators": (row.get("operators") or "").strip(),
                "landing_points": (row.get("landing_points") or "").strip(),
                "segment_endpoints": (row.get("segment_endpoints") or "").strip(),
                "length_km": (row.get("segment_length_km_raw") or "").strip(),
                "source": (row.get("source_dataset") or "").strip(),
            })
    return records


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


def build_web_data(max_public_mb: int = 5) -> None:
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

    cables = _enrich_cable_geometry(cables_raw, cable_geom_lookup)
    dcs = _enrich_dc_coordinates(dcs_raw, dc_coord_lookup)

    cables_mapped = sum(1 for c in cables if c["mapped_status"] == "mapped")
    cables_unmapped = sum(1 for c in cables if c["mapped_status"] == "unmapped")
    dcs_mapped = sum(1 for d in dcs if d["mapped_status"] == "mapped")
    dcs_unmapped = sum(1 for d in dcs if d["mapped_status"] == "unmapped")

    data = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "disclaimer": (
                "This atlas uses public or redistribution-safe data. Some infrastructure layers are "
                "metadata-only where public geometries or coordinates are unavailable. No coordinates "
                "are inferred or invented. Submarine cable routes are generalized public geometries "
                "or schematic arcs, not exact surveyed trench routes. Data center locations are "
                "metro-level and do not represent exact facility coordinates."
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
                "geometry_lookup_count": len(cable_geom_lookup),
                "datacenter_location_lookup_count": len(dc_coord_lookup),
            },
            "unmapped": {
                "submarine_cables": [
                    {
                        "n": c["n"],
                        "source": c["source"],
                        "operators": c.get("operators", ""),
                        "landing_points": c.get("landing_points", ""),
                        "length_km": c.get("length_km", ""),
                        "unmapped_reason": c.get("unmapped_reason", ""),
                    }
                    for c in cables if c["mapped_status"] == "unmapped"
                ],
                "data_centers": [
                    {
                        "n": d["n"],
                        "op": d["op"],
                        "c": d["c"],
                        "address": d.get("address", ""),
                        "mw": d.get("mw"),
                        "source": d["source"],
                        "unmapped_reason": d.get("unmapped_reason", ""),
                    }
                    for d in dcs if d["mapped_status"] == "unmapped"
                ],
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
            f"ERROR: atlas_web_data.json is {size_mb:.2f} MB, exceeds {max_public_mb} MB limit.",
            file=sys.stderr,
        )
        print(f"Written to {output_path} instead of frontend/public/data/", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact web map data from raw CSVs")
    parser.add_argument(
        "--max-public-mb",
        type=float,
        default=5.0,
        help="Maximum size in MB for frontend public data (default: 5.0)",
    )
    args = parser.parse_args()
    success = build_web_data(max_public_mb=args.max_public_mb)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
