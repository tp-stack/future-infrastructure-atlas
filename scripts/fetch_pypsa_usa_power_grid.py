"""Fetch/convert PyPSA-USA transmission data for atlas layers.

PyPSA-USA does not publish line/bus CSVs as GitHub release assets. This script
therefore supports two operational modes:

1. Download explicit buses/lines/links CSV URLs provided by the caller.
2. Convert an existing PyPSA-USA CSV export directory.

Expected CSV shape follows PyPSA-style exports:
- buses.csv: bus_id or name, x, y, voltage, country/state
- lines.csv: line_id or name, voltage, circuits, length, geometry WKT
- links.csv: link_id or name, voltage, p_nom, length, geometry WKT
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = PROJECT_ROOT / "data" / "cache" / "pypsa_usa"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"

PYPSA_USA_REPO = "https://github.com/PyPSA/pypsa-usa"
PYPSA_USA_DOCS = "https://pypsa-usa.readthedocs.io/en/latest/data-transmission.html"
GITHUB_RELEASES_API = "https://api.github.com/repos/PyPSA/pypsa-usa/releases"
EXPECTED_RELEASE_FILES = {
    "buses.csv": ("buses.csv", "bus.csv"),
    "lines.csv": ("lines.csv", "line.csv"),
    "links.csv": ("links.csv", "link.csv"),
}


def download(url: str, dest: Path, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"using cached: {dest}")
        return dest
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"saved: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def load_json_url(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "future-infrastructure-atlas"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def release_api_url(tag: str) -> str:
    if tag == "latest":
        return f"{GITHUB_RELEASES_API}/latest"
    return f"{GITHUB_RELEASES_API}/tags/{tag}"


def maybe_extract_expected_csvs(archive_path: Path, output_dir: Path) -> list[Path]:
    if archive_path.suffix.lower() != ".zip":
        return []

    extracted: list[Path] = []
    with ZipFile(archive_path) as zf:
        names = zf.namelist()
        for target, candidates in EXPECTED_RELEASE_FILES.items():
            matches = [
                name for name in names
                if Path(name).name.lower() in candidates
            ]
            if not matches:
                continue
            member = matches[0]
            out = output_dir / target
            out.write_bytes(zf.read(member))
            extracted.append(out)
            print(f"extracted {member} -> {out}")
    return extracted


def download_release_assets(tag: str, output_dir: Path, force: bool = False) -> list[Path]:
    """Download matching PyPSA-USA release assets when the release publishes CSVs or a CSV zip."""
    try:
        release = load_json_url(release_api_url(tag))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Could not load PyPSA-USA release '{tag}' from GitHub API: HTTP {exc.code}") from exc

    assets = release.get("assets", [])
    if not assets:
        raise RuntimeError(
            f"PyPSA-USA release {release.get('tag_name', tag)} has no downloadable CSV assets. "
            "Run the PyPSA-USA workflow and export buses.csv/lines.csv/links.csv locally, "
            "or provide --buses-url/--lines-url."
        )

    downloaded: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset in assets:
        name = asset.get("name", "")
        lower = name.lower()
        direct_target = next(
            (target for target, candidates in EXPECTED_RELEASE_FILES.items() if lower in candidates),
            None,
        )
        if direct_target:
            downloaded.append(download(asset["browser_download_url"], output_dir / direct_target, force))
            continue

        if lower.endswith(".zip") and any(token in lower for token in ("network", "transmission", "pypsa", "grid")):
            archive = download(asset["browser_download_url"], output_dir / name, force)
            downloaded.extend(maybe_extract_expected_csvs(archive, output_dir))

    if not downloaded:
        asset_names = ", ".join(asset.get("name", "") for asset in assets) or "(none)"
        raise RuntimeError(
            "No release assets matched buses.csv, lines.csv, links.csv, or a likely network zip. "
            f"Release assets: {asset_names}"
        )

    return downloaded


def parse_wkt_linestring(wkt: str) -> list[list[float]] | None:
    wkt = wkt.strip().strip("'")
    if not wkt.startswith("LINESTRING (") or not wkt.endswith(")"):
        return None
    coords: list[list[float]] = []
    for pair in wkt[12:-1].split(","):
        parts = pair.strip().split()
        if len(parts) < 2:
            return None
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            return None
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return None
        coords.append([lon, lat])
    return coords if len(coords) >= 2 else None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    if not text.strip():
        return []

    sample = text[:4096]
    if "geometry" not in sample:
        return list(csv.DictReader(text.splitlines()))

    # Prefer real CSV parsing. Some PyPSA exports quote WKT geometry correctly.
    rows = list(csv.DictReader(text.splitlines()))
    if rows and all(None not in row and (row.get("geometry") or "").strip().strip("'").endswith(")") for row in rows):
        return rows

    # Fallback for PyPSA-style files where the final geometry field contains
    # unquoted commas. This is intentionally limited to last-column geometry.
    lines = text.splitlines()
    headers = [h.strip() for h in lines[0].split(",")]
    if not headers or headers[-1] != "geometry":
        return rows
    n = len(headers)
    repaired: list[dict[str, str]] = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        parts = raw.split(",")
        row = {headers[i]: parts[i] if i < len(parts) else "" for i in range(n - 1)}
        row[headers[-1]] = ",".join(parts[n - 1:])
        repaired.append(row)
    return repaired


def float_value(row: dict[str, str], *keys: str, default: float = 0) -> float:
    for key in keys:
        raw = row.get(key)
        if raw not in (None, ""):
            try:
                return float(raw)
            except ValueError:
                pass
    return default


def text_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        raw = row.get(key)
        if raw:
            return raw
    return ""


def convert_lines(path: Path, link: bool = False) -> list[dict]:
    features: list[dict] = []
    for idx, row in enumerate(read_csv_rows(path), start=1):
        coords = parse_wkt_linestring(row.get("geometry", ""))
        if not coords:
            continue
        voltage = int(float_value(row, "voltage", "v_nom"))
        length_m = float_value(row, "length", default=0)
        capacity = float_value(row, "s_nom", "p_nom", default=0)
        feature_id = text_value(row, "link_id" if link else "line_id", "name", "id") or f"{'link' if link else 'line'}-{idx}"
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "kind": "power_line",
                "id": f"pypsa-usa/{feature_id}",
                "voltage": voltage,
                "circuits": 0 if link else int(float_value(row, "circuits", default=1)),
                "length_km": round(length_m / 1000, 3) if length_m > 1000 else round(length_m, 3),
                "underground": row.get("underground") == "t",
                "country": "US",
                "type": "HVDC" if link else text_value(row, "type"),
                "s_nom_mva": round(capacity),
                "source": "PyPSA-USA",
            },
        })
    return features


def convert_buses(path: Path) -> list[dict]:
    features: list[dict] = []
    for idx, row in enumerate(read_csv_rows(path), start=1):
        lon = float_value(row, "x", "lon", "longitude", default=float("nan"))
        lat = float_value(row, "y", "lat", "latitude", default=float("nan"))
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            continue
        voltage = int(float_value(row, "voltage", "v_nom"))
        bus_id = text_value(row, "bus_id", "name", "id") or f"bus-{idx}"
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "kind": "substation",
                "id": f"pypsa-usa/{bus_id}",
                "n": bus_id,
                "voltage": voltage,
                "dc": row.get("dc") == "t",
                "symbol": text_value(row, "symbol") or "Substation",
                "under_construction": row.get("under_construction") == "t",
                "country": "US",
                "lat": lat,
                "lon": lon,
                "source": "PyPSA-USA",
            },
        })
    return features


def feature_collection(features: list[dict], source_label: str, source_url: str) -> dict:
    voltage_groups = defaultdict(int)
    total_km = 0.0
    for feature in features:
        props = feature["properties"]
        voltage_groups[props.get("voltage") or 0] += 1
        total_km += float(props.get("length_km") or 0)
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_features": len(features),
            "total_route_km": round(total_km),
            "voltage_distribution": dict(sorted(voltage_groups.items())),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source_label,
            "source_url": source_url,
            "reference": "PyPSA-USA transmission docs describe ReEDS/NARIS and TAMU synthetic network options.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch/convert PyPSA-USA power grid CSV exports")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_CACHE, help="Directory containing buses.csv, lines.csv, and optional links.csv")
    parser.add_argument("--github-release", help="Download matching CSV assets from a PyPSA-USA GitHub release tag, or 'latest'")
    parser.add_argument("--buses-url", help="URL for buses.csv")
    parser.add_argument("--lines-url", help="URL for lines.csv")
    parser.add_argument("--links-url", help="URL for links.csv")
    parser.add_argument("--force", action="store_true", help="Re-download URL inputs")
    parser.add_argument("--merge-output", action="store_true", help="Append PyPSA-USA features to existing power_lines.json/substations.json")
    args = parser.parse_args()

    args.input_dir.mkdir(parents=True, exist_ok=True)
    if args.github_release:
        try:
            download_release_assets(args.github_release, args.input_dir, args.force)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            print(f"Source docs: {PYPSA_USA_DOCS}", file=sys.stderr)
            sys.exit(1)
    if args.buses_url:
        download(args.buses_url, args.input_dir / "buses.csv", args.force)
    if args.lines_url:
        download(args.lines_url, args.input_dir / "lines.csv", args.force)
    if args.links_url:
        download(args.links_url, args.input_dir / "links.csv", args.force)

    buses_csv = args.input_dir / "buses.csv"
    lines_csv = args.input_dir / "lines.csv"
    links_csv = args.input_dir / "links.csv"
    missing = [str(path) for path in (buses_csv, lines_csv) if not path.exists()]
    if missing:
        print("Missing required PyPSA-USA CSV exports:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        print(f"Provide --buses-url/--lines-url or export PyPSA-USA network CSVs into {args.input_dir}.", file=sys.stderr)
        print(f"Source docs: {PYPSA_USA_DOCS}", file=sys.stderr)
        sys.exit(1)

    line_features = convert_lines(lines_csv, link=False)
    if links_csv.exists():
        line_features.extend(convert_lines(links_csv, link=True))
    substation_features = convert_buses(buses_csv)

    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)
    power_lines_path = FRONTEND_DATA / "power_lines.json"
    substations_path = FRONTEND_DATA / "substations.json"

    if args.merge_output and power_lines_path.exists():
        with open(power_lines_path, encoding="utf-8") as f:
            existing = json.load(f)
        line_features = existing.get("features", []) + line_features
    if args.merge_output and substations_path.exists():
        with open(substations_path, encoding="utf-8") as f:
            existing = json.load(f)
        substation_features = existing.get("features", []) + substation_features

    power_lines = feature_collection(line_features, "PyPSA-USA", PYPSA_USA_REPO)
    substations = feature_collection(substation_features, "PyPSA-USA", PYPSA_USA_REPO)

    power_lines_path.write_text(json.dumps(power_lines, ensure_ascii=False), encoding="utf-8")
    substations_path.write_text(json.dumps(substations, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(line_features)} power lines -> {power_lines_path}")
    print(f"wrote {len(substation_features)} substations -> {substations_path}")


if __name__ == "__main__":
    main()
