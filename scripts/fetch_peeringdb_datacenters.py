"""Fetch PeeringDB facilities API, produce structured CSV of interconnection facilities."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data/raw/peeringdb"
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
FRONTEND_DATA_DIR = PROJECT_ROOT / "frontend/public/data"

API_BASE = "https://www.peeringdb.com/api"

CSV_COLUMNS = [
    "source",
    "source_id",
    "name",
    "name_long",
    "aka",
    "operator_org_id",
    "operator",
    "website",
    "address1",
    "address2",
    "city",
    "state",
    "zipcode",
    "country",
    "region_continent",
    "latitude",
    "longitude",
    "net_count",
    "ix_count",
    "status",
    "created",
    "updated",
    "facility_type",
    "confidence",
    "source_url",
    "license_note",
]

LICENSE_NOTE = (
    "PeeringDB public/user-maintained facility data; "
    "verify downstream license and attribution requirements before commercial redistribution."
)


def _fetch_json(url: str, api_key: str | None = None) -> dict | list:
    headers = {"User-Agent": "FutureInfrastructureAtlas/1.0"}
    if api_key:
        headers["Authorization"] = f"Api-Key {api_key}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_facilities(api_key: str | None = None) -> list[dict]:
    """Fetch all PeeringDB facilities (single request with limit=0)."""
    url = f"{API_BASE}/fac?limit=0"
    print(f"  Fetching all facilities from {API_BASE}/fac...", end="", flush=True)
    try:
        data = _fetch_json(url, api_key)
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


def _valid_lat(lat: float) -> bool:
    return isinstance(lat, (int, float)) and -90 <= lat <= 90


def _valid_lon(lon: float) -> bool:
    return isinstance(lon, (int, float)) and -180 <= lon <= 180


def process_facilities(raw: list[dict]) -> list[dict]:
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
        status = (fac.get("status") or "").strip()

        has_valid_coords = (
            lat is not None and lon is not None
            and _valid_lat(lat) and _valid_lon(lon)
        )

        if has_valid_coords and status == "ok":
            confidence = "high"
        elif has_valid_coords:
            confidence = "medium"
        else:
            confidence = "unmapped"

        org_name = str(fac.get("org_name", "") or "")
        org_id_raw = fac.get("org_id")
        org_id = str(int(org_id_raw)) if org_id_raw is not None else ""

        created_raw = fac.get("created")
        updated_raw = fac.get("updated")
        created_str = ""
        updated_str = ""
        if created_raw:
            try:
                created_str = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00")).isoformat()
            except (ValueError, TypeError):
                created_str = str(created_raw)
        if updated_raw:
            try:
                updated_str = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00")).isoformat()
            except (ValueError, TypeError):
                updated_str = str(updated_raw)

        rows.append({
            "source": "PeeringDB",
            "source_id": str(fid),
            "name": str(fac.get("name", "") or ""),
            "name_long": str(fac.get("name_long", "") or ""),
            "aka": str(fac.get("aka", "") or ""),
            "operator_org_id": org_id,
            "operator": org_name,
            "website": str(fac.get("website", "") or ""),
            "address1": str(fac.get("address1", "") or ""),
            "address2": str(fac.get("address2", "") or ""),
            "city": str(fac.get("city", "") or ""),
            "state": str(fac.get("state", "") or ""),
            "zipcode": str(fac.get("zipcode", "") or ""),
            "country": str(fac.get("country", "") or ""),
            "region_continent": str(fac.get("region_continent", "") or ""),
            "latitude": str(lat) if lat is not None else "",
            "longitude": str(lon) if lon is not None else "",
            "net_count": str(fac.get("net_count", 0) or 0),
            "ix_count": str(fac.get("ix_count", 0) or 0),
            "status": status,
            "created": created_str,
            "updated": updated_str,
            "facility_type": "interconnection_facility",
            "confidence": confidence,
            "source_url": f"https://www.peeringdb.com/fac/{fid}",
            "license_note": LICENSE_NOTE,
        })

    return rows


def write_raw_json(raw: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    print(f"Raw JSON written: {path} ({len(raw)} records)")


def write_processed_csv(rows: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Processed CSV written: {path} ({len(rows)} rows)")
    return len(rows)


def write_frontend_csv(rows: list[dict], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontend_cols = [
        "source", "source_id", "name", "operator", "city", "country",
        "latitude", "longitude", "net_count", "ix_count", "confidence",
        "source_url", "license_note",
    ]
    mapped = [r for r in rows if r["confidence"] in ("high", "medium")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=frontend_cols, extrasaction="ignore")
        writer.writeheader()
        for r in mapped:
            writer.writerow({
                "source": r["source"],
                "source_id": r["source_id"],
                "name": r["name"],
                "operator": r["operator"],
                "city": r["city"],
                "country": r["country"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "net_count": r["net_count"],
                "ix_count": r["ix_count"],
                "confidence": r["confidence"],
                "source_url": r["source_url"],
                "license_note": r["license_note"],
            })
    print(f"Frontend CSV written: {path} ({len(mapped)} rows, {len(rows) - len(mapped)} unmapped excluded)")
    return len(mapped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PeeringDB facilities and produce structured CSV",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip API fetch, use existing raw JSON",
    )
    parser.add_argument(
        "--raw-json",
        type=str,
        default=str(RAW_DIR / "facilities_raw.json"),
        help="Path for raw JSON (default: data/raw/peeringdb/facilities_raw.json)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("PEERINGDB_API_KEY")

    raw_path = Path(args.raw_json)

    if args.skip_fetch and raw_path.exists():
        print(f"Loading raw JSON from: {raw_path}")
        with open(raw_path, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        print("Fetching PeeringDB facilities...")
        raw = fetch_facilities(api_key)
        if not raw:
            print("ERROR: No facilities fetched.", file=sys.stderr)
            sys.exit(1)
        write_raw_json(raw, raw_path)

    print(f"Total raw facilities: {len(raw)}")

    rows = process_facilities(raw)
    print(f"Processed rows: {len(rows)}")

    processed_path = PROCESSED_DIR / "global_datacenters_public_peeringdb.csv"
    write_processed_csv(rows, processed_path)

    frontend_path = FRONTEND_DATA_DIR / "datacenters_public.csv"
    mapped_count = write_frontend_csv(rows, frontend_path)

    total_mapped = sum(1 for r in rows if r["confidence"] in ("high", "medium"))
    total_unmapped = sum(1 for r in rows if r["confidence"] == "unmapped")
    print(f"\nSummary:")
    print(f"  Total facilities: {len(rows)}")
    print(f"  Mapped (with coords): {total_mapped}")
    print(f"  Unmapped (no coords): {total_unmapped}")
    print(f"  Frontend CSV: {frontend_path}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
