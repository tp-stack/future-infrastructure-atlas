"""
Download European power transmission lines from the PyPSA-Eur dataset (Zenodo v0.7)
and convert to GeoJSON for the frontend.

Sources:
- lines.csv: AC lines and cables (220-750 kV)
- links.csv: DC links (HVDC)
- buses.csv: Substations (used for line metadata)

License: ODbL 1.0 (Open Data Commons Open Database License)
Reference: Xiong et al. (2025) Nature Scientific Data. https://doi.org/10.1038/s41597-025-04550-7
"""
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from io import StringIO
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_CACHE_DIR = Path(__file__).resolve().parent / "data" / "cache"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "pypsa_eur"
OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "data"


def get_cache_dir() -> Path:
    env_dir = os.environ.get("PYPSA_EUR_CACHE_DIR")
    if env_dir:
        return Path(env_dir)
    if all((LEGACY_CACHE_DIR / name).exists() for name in ("lines.csv", "links.csv", "buses.csv")):
        return LEGACY_CACHE_DIR
    return DEFAULT_CACHE_DIR

ZENODO_BASE = "https://zenodo.org/records/18619025/files"
FILES = {
    "lines.csv": f"{ZENODO_BASE}/lines.csv",
    "links.csv": f"{ZENODO_BASE}/links.csv",
    "buses.csv": f"{ZENODO_BASE}/buses.csv",
}
CACHE_DIR = get_cache_dir()

VOLTAGE_COLORS = {
    750: "#8b0000",
    500: "#d00000",
    420: "#e04000",
    400: "#e06000",
    380: "#e08000",
    330: "#e0a000",
    300: "#c0a000",
    275: "#80a000",
    220: "#40a000",
}

VOLTAGE_LABELS = {
    750: "750 kV",
    500: "500 kV",
    420: "420 kV",
    400: "400 kV",
    380: "380 kV",
    330: "330 kV",
    300: "300 kV",
    275: "275 kV",
    220: "220 kV",
}

DC_COLOR = "#800080"


def download_file(url: str, dest: str) -> None:
    """Download a file with progress indication."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        age = time.time() - os.path.getmtime(dest)
        if age < 86400:
            print(f"  using cached: {dest}")
            return
    print(f"  downloading {url}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  saved: {dest} ({os.path.getsize(dest) / 1e6:.1f} MB)")
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code} for {url}")
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  using existing cached file as fallback")
        else:
            raise


def download_all() -> dict[str, str]:
    """Download all source files and return paths."""
    paths = {}
    os.makedirs(CACHE_DIR, exist_ok=True)
    for name, url in FILES.items():
        dest = os.path.join(CACHE_DIR, name)
        download_file(url, dest)
        paths[name] = dest
    return paths


def parse_wkt_point(wkt: str) -> tuple[float, float] | None:
    """Parse POINT (x y) WKT string."""
    wkt = wkt.strip()
    if wkt.startswith("POINT ("):
        coords = wkt[7:-1].strip()
        parts = coords.split()
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                return None
    return None


def parse_wkt_linestring(wkt: str) -> list[list[float]] | None:
    """Parse LINESTRING (x y, x y, ...) WKT string into [[lon, lat], ...]."""
    wkt = wkt.strip().strip("'")
    if wkt.startswith("LINESTRING ("):
        coords_str = wkt[12:-1].strip()
        pairs = coords_str.split(",")
        coords = []
        for pair in pairs:
            parts = pair.strip().split()
            if len(parts) >= 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    return None
        return coords if coords else None
    return None


def read_buses(path: str) -> dict[str, dict]:
    """Read buses.csv into a lookup dict."""
    buses = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bus_id = row["bus_id"]
            buses[bus_id] = {
                "voltage": int(row["voltage"]) if row["voltage"] else 0,
                "country": row.get("country", ""),
                "lat": float(row["y"]) if row.get("y") else None,
                "lon": float(row["x"]) if row.get("x") else None,
            }
    print(f"  read {len(buses)} buses")
    return buses


def read_substations(path: str) -> list[dict]:
    """Read buses.csv into point GeoJSON features."""
    features = []
    skipped = 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lon = float(row["x"])
                lat = float(row["y"])
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                skipped += 1
                continue
            try:
                voltage = int(float(row.get("voltage") or 0))
            except (TypeError, ValueError):
                voltage = 0
            bus_id = row.get("bus_id", "")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "kind": "substation",
                    "id": bus_id,
                    "n": bus_id,
                    "voltage": voltage,
                    "dc": row.get("dc", "") == "t",
                    "symbol": row.get("symbol", ""),
                    "under_construction": row.get("under_construction", "") == "t",
                    "country": row.get("country", ""),
                    "lat": lat,
                    "lon": lon,
                },
            })

    print(f"  substation features: {len(features)}, skipped: {skipped}")
    return features


def read_csv_rows(path: str) -> list[dict]:
    """Read a CSV whose last field (geometry) contains unquoted commas."""
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    lines = text.splitlines()
    if not lines:
        return rows
    headers = [h.strip() for h in lines[0].split(",")]
    n = len(headers)
    for raw in lines[1:]:
        if not raw.strip():
            continue
        parts = raw.split(",")
        row = {}
        for i in range(n - 1):
            row[headers[i]] = parts[i]
        geometry = ",".join(parts[n - 1:])
        row[headers[n - 1]] = geometry
        rows.append(row)
    return rows


def read_lines(path: str, buses: dict) -> list[dict]:
    """Read lines.csv into GeoJSON features."""
    features = []
    line_count = 0
    skipped = 0

    csv_rows = read_csv_rows(path)
    for row in csv_rows:
        line_count += 1
        if line_count % 2000 == 0:
            print(f"  processed {line_count} lines...")

        geometry_wkt = row.get("geometry", "")
        if not geometry_wkt:
            skipped += 1
            continue

        coords = parse_wkt_linestring(geometry_wkt)
        if not coords or len(coords) < 2:
            skipped += 1
            continue

        voltage_raw = row.get("voltage", "0")
        try:
            voltage = int(float(voltage_raw))
        except (ValueError, TypeError):
            voltage = 0

        circuits_raw = row.get("circuits", "1")
        try:
            circuits = int(float(circuits_raw))
        except (ValueError, TypeError):
            circuits = 1

        length_raw = row.get("length", "0")
        try:
            length_km = round(float(length_raw) / 1000, 3)
        except (ValueError, TypeError):
            length_km = 0

        underground = row.get("underground", "f") == "t"

        bus0_id = row.get("bus0", "")
        bus1_id = row.get("bus1", "")
        bus0 = buses.get(bus0_id, {})
        bus1 = buses.get(bus1_id, {})

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "kind": "power_line",
                "id": row.get("line_id", f"line-{line_count}"),
                "voltage": voltage,
                "circuits": circuits,
                "length_km": length_km,
                "underground": underground,
                "country": bus0.get("country", bus1.get("country", "")),
                "type": row.get("type", ""),
                "s_nom_mva": round(float(row["s_nom"])) if row.get("s_nom") else 0,
            },
        }
        features.append(feature)

    print(f"  total lines: {line_count}, features: {len(features)}, skipped: {skipped}")
    return features


def read_links(path: str, buses: dict) -> list[dict]:
    """Read links.csv (DC links) into GeoJSON features."""
    features = []
    csv_rows = read_csv_rows(path)
    for row in csv_rows:
        geometry_wkt = row.get("geometry", "")
        if not geometry_wkt:
            continue

        coords = parse_wkt_linestring(geometry_wkt)
        if not coords or len(coords) < 2:
            continue

        voltage_raw = row.get("voltage", "0")
        try:
            voltage = int(float(voltage_raw))
        except (ValueError, TypeError):
            voltage = 0

        p_nom_raw = row.get("p_nom", "0")
        try:
            p_nom = int(float(p_nom_raw))
        except (ValueError, TypeError):
            p_nom = 0

        length_raw = row.get("length", "0")
        try:
            length_km = round(float(length_raw) / 1000, 3)
        except (ValueError, TypeError):
            length_km = 0

        bus0_id = row.get("bus0", "")
        bus1_id = row.get("bus1", "")
        bus0 = buses.get(bus0_id, {})
        bus1 = buses.get(bus1_id, {})

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "kind": "power_line",
                "id": row.get("link_id", ""),
                "voltage": voltage,
                "circuits": 0,
                "length_km": length_km,
                "underground": row.get("underground", "f") == "t",
                "country": bus0.get("country", bus1.get("country", "")),
                "type": "HVDC",
                "s_nom_mva": p_nom,
            },
        }
        features.append(feature)

    print(f"  DC link features: {len(features)}")
    return features


def format_power_lines_json(features: list[dict]) -> dict:
    """Build the final power lines GeoJSON + metadata structure."""
    all_features = features
    voltage_groups = defaultdict(int)
    countries = set()
    total_km = 0

    for f in all_features:
        v = f["properties"]["voltage"]
        v_rounded = round(v / 10) * 10 if v > 0 else 0
        voltage_groups[v_rounded] += 1
        if f["properties"]["country"]:
            countries.add(f["properties"]["country"])
        total_km += f["properties"]["length_km"]

    return {
        "type": "FeatureCollection",
        "features": all_features,
        "metadata": {
            "total_features": len(all_features),
            "total_route_km": round(total_km),
            "countries": sorted(countries),
            "voltage_distribution": dict(sorted(voltage_groups.items())),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "PyPSA-Eur v0.7 (Zenodo 10.5281/zenodo.18619025)",
            "source_url": "https://zenodo.org/records/18619025",
            "license": "ODbL 1.0",
            "reference": "Xiong et al. (2025) Modelling the high-voltage grid using open data for Europe and beyond. Nature Scientific Data.",
        },
    }


def format_substations_json(features: list[dict]) -> dict:
    """Build the final substation GeoJSON + metadata structure."""
    voltage_groups = defaultdict(int)
    countries = set()
    for feature in features:
        props = feature["properties"]
        voltage_groups[props.get("voltage") or 0] += 1
        if props.get("country"):
            countries.add(props["country"])

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_features": len(features),
            "countries": sorted(countries),
            "voltage_distribution": dict(sorted(voltage_groups.items())),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "PyPSA-Eur v0.7 buses.csv (Zenodo 10.5281/zenodo.18619025)",
            "source_url": "https://zenodo.org/records/18619025",
            "license": "ODbL 1.0",
            "precision_note": "Source-native public OSM-derived substation coordinates from PyPSA-Eur.",
        },
    }


def main():
    print("=== Fetching PyPSA-Eur European transmission grid data ===\n")

    paths = download_all()

    print("\nReading buses...")
    buses = read_buses(paths["buses.csv"])

    print("\nReading AC lines...")
    line_features = read_lines(paths["lines.csv"], buses)

    print("\nReading DC links...")
    link_features = read_links(paths["links.csv"], buses)

    all_features = line_features + link_features
    print(f"\nTotal features: {len(all_features)}")

    output = format_power_lines_json(all_features)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "power_lines.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    file_size = os.path.getsize(out_path) / 1e6
    print(f"\nSaved: {out_path} ({file_size:.1f} MB)")
    print(f"Features: {len(all_features)}")
    print(f"Total route length: {output['metadata']['total_route_km']:,} km")
    print(f"Countries: {len(output['metadata']['countries'])}")

    print("\nReading substations...")
    substation_features = read_substations(paths["buses.csv"])
    substations = format_substations_json(substation_features)
    substations_path = os.path.join(OUTPUT_DIR, "substations.json")
    with open(substations_path, "w", encoding="utf-8") as f:
        json.dump(substations, f, ensure_ascii=False)
    substation_size = os.path.getsize(substations_path) / 1e6
    print(f"Saved: {substations_path} ({substation_size:.1f} MB)")
    print(f"Substations: {len(substation_features)}")
    print("Done.")


if __name__ == "__main__":
    main()
