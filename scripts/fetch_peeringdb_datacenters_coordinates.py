"""Fetch PeeringDB facility coordinates and produce structured coordinate CSV.

Two modes:
  Default: download PeeringDB KMZ export and extract coordinates.
  --use-api: use the PeeringDB REST API instead (fallback).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://www.peeringdb.com/api"
KMZ_URL = "https://www.peeringdb.com/export/kmz/"

CSV_COLUMNS = [
    "source", "source_id", "name", "operator", "organization",
    "address1", "address2", "city", "state", "zipcode", "country",
    "latitude", "longitude", "net_count", "ix_count", "status",
    "confidence", "source_url", "license_note",
]

LICENSE_NOTE = (
    "PeeringDB public/user-maintained facility data; "
    "verify downstream license and attribution requirements before commercial redistribution. "
    "Not exhaustive of every global data center."
)


def _fetch_url(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "FutureInfrastructureAtlas/1.0"})
    with urlopen(req, timeout=120) as resp:
        return resp.read()


def _valid_lat(v: float) -> bool:
    return isinstance(v, (int, float)) and -90 <= v <= 90


def _valid_lon(v: float) -> bool:
    return isinstance(v, (int, float)) and -180 <= v <= 180


def _clean_str(val: object) -> str:
    if val is None:
        return ""
    return str(val).strip()


# ---- KMZ mode ----

def _parse_kml_coordinates(kml_text: str) -> list[dict]:
    """Extract Placemark name + coordinates from KML text (simple parser)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(kml_text)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    places = []
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name_el = pm.find("kml:name", ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else ""

        point_el = pm.find("kml:Point", ns)
        coords_text = ""
        if point_el is not None:
            co_el = point_el.find("kml:coordinates", ns)
            if co_el is not None and co_el.text:
                coords_text = co_el.text.strip()

        if not coords_text:
            coords_el = pm.find(".//kml:coordinates", ns)
            if coords_el is not None and coords_el.text:
                coords_text = coords_el.text.strip()

        if coords_text:
            parts = coords_text.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    if _valid_lat(lat) and _valid_lon(lon):
                        places.append({"name": name, "latitude": lat, "longitude": lon})
                except (ValueError, IndexError):
                    continue

    return places


def fetch_from_kmz() -> list[dict]:
    """Download KMZ, extract KML, parse Placemark coordinates."""
    print(f"  Downloading KMZ from {KMZ_URL}...", end="", flush=True)
    try:
        data = _fetch_url(KMZ_URL)
    except Exception as e:
        print(f" Failed: {e}", flush=True)
        return []
    print(f" got {len(data)} bytes", flush=True)

    with tempfile.TemporaryFile() as tmp:
        tmp.write(data)
        tmp.seek(0)
        try:
            with zipfile.ZipFile(tmp) as zf:
                kml_files = [n for n in zf.namelist() if n.lower().endswith(".kml")]
                if not kml_files:
                    print("  No KML found in KMZ archive", flush=True)
                    return []
                kml_text = zf.read(kml_files[0]).decode("utf-8", errors="replace")
        except zipfile.BadZipFile:
            print("  Downloaded file is not a valid KMZ/zip", flush=True)
            return []

    places = _parse_kml_coordinates(kml_text)
    print(f"  Parsed {len(places)} Placemark entries from KML", flush=True)
    return places


# ---- API mode ----

def _fetch_json(url: str) -> dict | list:
    req = Request(url, headers={"User-Agent": "FutureInfrastructureAtlas/1.0"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_from_api() -> list[dict]:
    """Fetch all facilities from PeeringDB API."""
    url = f"{API_BASE}/fac?limit=0"
    print(f"  Fetching all facilities from {API_BASE}/fac...", end="", flush=True)
    try:
        data = _fetch_json(url)
    except HTTPError as e:
        print(f" HTTP {e.code}: {e.reason}", flush=True)
        return []
    except URLError as e:
        print(f" URL error: {e.reason}", flush=True)
        return []

    if isinstance(data, dict):
        results = data.get("data", [])
        if not isinstance(results, list):
            results = []
    elif isinstance(data, list):
        results = data
    else:
        results = []

    print(f" got {len(results)} facilities", flush=True)
    return results


def process_api_results(raw: list[dict]) -> list[dict]:
    rows = []
    seen_ids: set[int] = set()

    for fac in raw:
        fid = fac.get("id")
        if fid is None:
            continue
        fid = int(fid)
        if fid in seen_ids:
            continue
        seen_ids.add(fid)

        lat = fac.get("latitude")
        lon = fac.get("longitude")
        status = _clean_str(fac.get("status"))

        has_valid_coords = (
            lat is not None and lon is not None
            and _valid_lat(lat) and _valid_lon(lon)
        )

        if has_valid_coords and status == "ok":
            confidence = "high"
        elif has_valid_coords:
            confidence = "medium"
        else:
            continue

        org_name = _clean_str(fac.get("org_name"))

        rows.append({
            "source": "PeeringDB",
            "source_id": str(fid),
            "name": _clean_str(fac.get("name")),
            "operator": org_name,
            "organization": org_name,
            "address1": _clean_str(fac.get("address1")),
            "address2": _clean_str(fac.get("address2")),
            "city": _clean_str(fac.get("city")),
            "state": _clean_str(fac.get("state")),
            "zipcode": _clean_str(fac.get("zipcode")),
            "country": _clean_str(fac.get("country")),
            "latitude": str(lat),
            "longitude": str(lon),
            "net_count": str(fac.get("net_count", 0) or 0),
            "ix_count": str(fac.get("ix_count", 0) or 0),
            "status": status,
            "confidence": confidence,
            "source_url": f"https://www.peeringdb.com/fac/{fid}",
            "license_note": LICENSE_NOTE,
        })

    return rows


def process_kmz_places(places: list[dict]) -> list[dict]:
    rows = []
    seen_names: set[str] = set()

    for p in places:
        name = p["name"].strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        rows.append({
            "source": "PeeringDB",
            "source_id": "",
            "name": name,
            "operator": "",
            "organization": "",
            "address1": "",
            "address2": "",
            "city": "",
            "state": "",
            "zipcode": "",
            "country": "",
            "latitude": str(p["latitude"]),
            "longitude": str(p["longitude"]),
            "net_count": "0",
            "ix_count": "0",
            "status": "kmz_export",
            "confidence": "high",
            "source_url": "https://www.peeringdb.com/export/kmz/",
            "license_note": LICENSE_NOTE,
        })

    return rows


def write_csv(rows: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV written: {path} ({len(rows)} rows)")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PeeringDB facility coordinates and produce structured CSV",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="Use PeeringDB REST API instead of KMZ download",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=str(
            PROJECT_ROOT
            / "data/raw/data_centers/peeringdb_manual_20260511"
            / "global_datacenters_public_peeringdb_coordinates.csv"
        ),
        help="Output CSV path",
    )
    args = parser.parse_args()

    output_path = Path(args.output_csv)

    if args.use_api:
        print("Mode: PeeringDB API")
        raw = fetch_from_api()
        if not raw:
            print("ERROR: No facilities from API.", file=sys.stderr)
            sys.exit(1)
        rows = process_api_results(raw)
    else:
        print("Mode: PeeringDB KMZ export")
        places = fetch_from_kmz()
        if not places:
            print("KMZ mode failed. Re-run with --use-api for API fallback.", file=sys.stderr)
            sys.exit(1)
        rows = process_kmz_places(places)

    print(f"Total rows with coordinates: {len(rows)}")
    write_csv(rows, output_path)
    print("Done.")


if __name__ == "__main__":
    main()
