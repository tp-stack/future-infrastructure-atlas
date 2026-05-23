"""Fetch fresh OSM power-grid data from Geofabrik PBF extracts.

This script is intentionally region-oriented: continent extracts can be very
large, so inputs are downloaded, processed, and deleted one at a time unless
--keep-raw is set.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import osmium
except ImportError as exc:  # pragma: no cover - exercised by CLI users
    raise SystemExit("Missing dependency: install with `python -m pip install osmium`.") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "osm_power_grid"
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "osm_global_power_grid"
EUROPE_CACHE = PROJECT_ROOT / "data" / "cache" / "osm_europe_power_lines"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
SOURCE_URL = "https://download.geofabrik.de/"
POWER_LINE_VALUES = {"line", "minor_line", "cable"}

BASE_GEOFABRIK = "https://download.geofabrik.de/"

REGIONS: dict[str, list[tuple[str, str]]] = {
    "north-america": [
        ("us", f"{BASE_GEOFABRIK}north-america/us-latest.osm.pbf"),
        ("canada", f"{BASE_GEOFABRIK}north-america/canada-latest.osm.pbf"),
        ("mexico", f"{BASE_GEOFABRIK}north-america/mexico-latest.osm.pbf"),
        ("greenland", f"{BASE_GEOFABRIK}north-america/greenland-latest.osm.pbf"),
    ],
    "south-america": [
        ("south-america", f"{BASE_GEOFABRIK}south-america-latest.osm.pbf"),
    ],
    "africa": [
        ("africa", f"{BASE_GEOFABRIK}africa-latest.osm.pbf"),
    ],
    "asia": [
        ("afghanistan", f"{BASE_GEOFABRIK}asia/afghanistan-latest.osm.pbf"),
        ("armenia", f"{BASE_GEOFABRIK}asia/armenia-latest.osm.pbf"),
        ("azerbaijan", f"{BASE_GEOFABRIK}asia/azerbaijan-latest.osm.pbf"),
        ("bangladesh", f"{BASE_GEOFABRIK}asia/bangladesh-latest.osm.pbf"),
        ("bhutan", f"{BASE_GEOFABRIK}asia/bhutan-latest.osm.pbf"),
        ("cambodia", f"{BASE_GEOFABRIK}asia/cambodia-latest.osm.pbf"),
        ("china", f"{BASE_GEOFABRIK}asia/china-latest.osm.pbf"),
        ("gcc-states", f"{BASE_GEOFABRIK}asia/gcc-states-latest.osm.pbf"),
        ("india", f"{BASE_GEOFABRIK}asia/india-latest.osm.pbf"),
        ("indonesia", f"{BASE_GEOFABRIK}asia/indonesia-latest.osm.pbf"),
        ("iran", f"{BASE_GEOFABRIK}asia/iran-latest.osm.pbf"),
        ("iraq", f"{BASE_GEOFABRIK}asia/iraq-latest.osm.pbf"),
        ("israel-and-palestine", f"{BASE_GEOFABRIK}asia/israel-and-palestine-latest.osm.pbf"),
        ("japan", f"{BASE_GEOFABRIK}asia/japan-latest.osm.pbf"),
        ("jordan", f"{BASE_GEOFABRIK}asia/jordan-latest.osm.pbf"),
        ("kazakhstan", f"{BASE_GEOFABRIK}asia/kazakhstan-latest.osm.pbf"),
        ("kyrgyzstan", f"{BASE_GEOFABRIK}asia/kyrgyzstan-latest.osm.pbf"),
        ("laos", f"{BASE_GEOFABRIK}asia/laos-latest.osm.pbf"),
        ("lebanon", f"{BASE_GEOFABRIK}asia/lebanon-latest.osm.pbf"),
        ("malaysia-singapore-brunei", f"{BASE_GEOFABRIK}asia/malaysia-singapore-brunei-latest.osm.pbf"),
        ("maldives", f"{BASE_GEOFABRIK}asia/maldives-latest.osm.pbf"),
        ("mongolia", f"{BASE_GEOFABRIK}asia/mongolia-latest.osm.pbf"),
        ("myanmar", f"{BASE_GEOFABRIK}asia/myanmar-latest.osm.pbf"),
        ("nepal", f"{BASE_GEOFABRIK}asia/nepal-latest.osm.pbf"),
        ("north-korea", f"{BASE_GEOFABRIK}asia/north-korea-latest.osm.pbf"),
        ("pakistan", f"{BASE_GEOFABRIK}asia/pakistan-latest.osm.pbf"),
        ("philippines", f"{BASE_GEOFABRIK}asia/philippines-latest.osm.pbf"),
        ("russian-federation", f"{BASE_GEOFABRIK}russia-latest.osm.pbf"),
        ("south-korea", f"{BASE_GEOFABRIK}asia/south-korea-latest.osm.pbf"),
        ("sri-lanka", f"{BASE_GEOFABRIK}asia/sri-lanka-latest.osm.pbf"),
        ("syria", f"{BASE_GEOFABRIK}asia/syria-latest.osm.pbf"),
        ("taiwan", f"{BASE_GEOFABRIK}asia/taiwan-latest.osm.pbf"),
        ("tajikistan", f"{BASE_GEOFABRIK}asia/tajikistan-latest.osm.pbf"),
        ("thailand", f"{BASE_GEOFABRIK}asia/thailand-latest.osm.pbf"),
        ("turkmenistan", f"{BASE_GEOFABRIK}asia/turkmenistan-latest.osm.pbf"),
        ("uzbekistan", f"{BASE_GEOFABRIK}asia/uzbekistan-latest.osm.pbf"),
        ("vietnam", f"{BASE_GEOFABRIK}asia/vietnam-latest.osm.pbf"),
        ("yemen", f"{BASE_GEOFABRIK}asia/yemen-latest.osm.pbf"),
    ],
    "australia-oceania": [
        ("australia-oceania", f"{BASE_GEOFABRIK}australia-oceania-latest.osm.pbf"),
    ],
}


class StopProcessing(Exception):
    """Internal signal used for --limit smoke runs."""


FILTER_TAGS = "w/power=line w/power=cable w/power=minor_line w/power=substation n/power=substation"
_FILTER_CACHE: dict[Path, Path] = {}


def _ensure_filtered(pbf: Path) -> Path:
    """If PBF is large, pre-filter to power features using osmium-tool via Docker."""
    if pbf.stat().st_size < 200 * 1024 * 1024:
        return pbf
    filtered = pbf.with_name(pbf.stem + "-power-filtered.osm.pbf")
    if filtered.exists():
        _FILTER_CACHE[pbf] = filtered
        return filtered
    print(f"  pre-filtering large PBF ({pbf.stat().st_size / 1024 / 1024:.0f} MB) with osmium-tool...")
    import shlex, subprocess
    mount_src = str(pbf.parent.resolve())
    mount_dst = "/data"
    inner = (
        f"apt-get update -qq && apt-get install -y -qq osmium-tool >/dev/null 2>&1 && "
        f"osmium tags-filter /data/{pbf.name} {FILTER_TAGS} "
        f"-o /data/{filtered.name} -f pbf --overwrite"
    )
    cmd = [
        shutil.which("docker") or "docker",
        "run", "--rm",
        "-v", f"{mount_src}:{mount_dst}",
        "ubuntu:24.04",
        "bash", "-lc", inner,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        print(f"  osmium-tool pre-filter failed: {result.stderr[:500]}", file=sys.stderr)
        return pbf
    if filtered.exists():
        print(f"  filtered PBF: {filtered.stat().st_size / 1024 / 1024:.1f} MB")
        _FILTER_CACHE[pbf] = filtered
        return filtered
    return pbf


def parse_voltage_kv(raw: Any) -> int:
    if raw is None:
        return 0
    values: list[float] = []
    for match in re.findall(r"\d+(?:[.,]\d+)?", str(raw)):
        try:
            value = float(match.replace(",", "."))
        except ValueError:
            continue
        if value <= 0:
            continue
        values.append(value / 1000 if value >= 1000 else value)
    return int(round(max(values))) if values else 0


def parse_int(raw: Any) -> int:
    if raw is None:
        return 0
    match = re.search(r"\d+", str(raw))
    return int(match.group(0)) if match else 0


def bool_tag(raw: Any) -> bool:
    return str(raw or "").strip().lower() in {"yes", "true", "1", "t"}


def valid_coord(lon: float, lat: float) -> bool:
    return -180 <= lon <= 180 and -90 <= lat <= 90


def haversine_km(a: list[float], b: list[float]) -> float:
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(h)))


def line_length_km(coords: list[list[float]]) -> float:
    return sum(haversine_km(coords[idx - 1], coords[idx]) for idx in range(1, len(coords)))


def update_bounds(bounds: dict[str, float] | None, coords: list[list[float]]) -> dict[str, float]:
    if bounds is None:
        bounds = {"minLon": 180.0, "minLat": 90.0, "maxLon": -180.0, "maxLat": -90.0}
    for lon, lat in coords:
        bounds["minLon"] = min(bounds["minLon"], lon)
        bounds["minLat"] = min(bounds["minLat"], lat)
        bounds["maxLon"] = max(bounds["maxLon"], lon)
        bounds["maxLat"] = max(bounds["maxLat"], lat)
    return bounds


def _tag(tags: Any, key: str) -> str:
    try:
        return tags.get(key) or ""
    except AttributeError:
        return ""


def _normalize_paths(coords_or_paths: Any) -> list[list[list[float]]]:
    if not isinstance(coords_or_paths, list) or not coords_or_paths:
        return []
    if isinstance(coords_or_paths[0], list) and coords_or_paths[0] and isinstance(coords_or_paths[0][0], list):
        raw_paths = coords_or_paths
    else:
        raw_paths = [coords_or_paths]
    paths: list[list[list[float]]] = []
    for raw_path in raw_paths:
        path: list[list[float]] = []
        for pair in raw_path:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            lon = float(pair[0])
            lat = float(pair[1])
            if valid_coord(lon, lat):
                path.append([round(lon, 7), round(lat, 7)])
        if len(path) >= 2:
            paths.append(path)
    return paths


def normalize_line_feature(osm_id: int | str, tags: Any, coords: Any, region: str) -> dict[str, Any] | None:
    paths = _normalize_paths(coords)
    if not paths:
        return None
    power = _tag(tags, "power")
    voltage = parse_voltage_kv(_tag(tags, "voltage"))
    frequency = _tag(tags, "frequency").strip()
    line_type = "HVDC" if frequency in {"0", "0.0"} else (power or "power_line")
    location = _tag(tags, "location").lower()
    underground = power == "cable" or location in {"underground", "underwater"} or bool_tag(_tag(tags, "tunnel"))
    name = _tag(tags, "name") or _tag(tags, "ref") or f"OSM way {osm_id}"
    geometry: dict[str, Any]
    if len(paths) == 1:
        geometry = {"type": "LineString", "coordinates": paths[0]}
    else:
        geometry = {"type": "MultiLineString", "coordinates": paths}
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "kind": "power_line",
            "id": f"osm-{osm_id}",
            "n": name,
            "voltage": voltage,
            "voltage_raw": _tag(tags, "voltage"),
            "circuits": parse_int(_tag(tags, "circuits")),
            "cables": parse_int(_tag(tags, "cables")),
            "length_km": round(sum(line_length_km(path) for path in paths), 3),
            "underground": underground,
            "country": "",
            "region": region,
            "type": line_type,
            "power": power,
            "frequency": frequency,
            "osm_id": str(osm_id),
            "source": "OpenStreetMap",
        },
    }


def normalize_substation_feature(osm_id: int | str, tags: Any, lon: float, lat: float, region: str, osm_type: str) -> dict[str, Any] | None:
    if not valid_coord(lon, lat):
        return None
    name = _tag(tags, "name") or _tag(tags, "ref") or f"OSM {osm_type} {osm_id}"
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]},
        "properties": {
            "kind": "substation",
            "id": f"osm-{osm_type}-{osm_id}",
            "n": name,
            "voltage": parse_voltage_kv(_tag(tags, "voltage")),
            "dc": bool_tag(_tag(tags, "dc")),
            "symbol": _tag(tags, "substation") or "Substation",
            "under_construction": bool_tag(_tag(tags, "construction")) or _tag(tags, "power") == "construction",
            "country": "",
            "region": region,
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "source": "OpenStreetMap",
            "osm_id": str(osm_id),
            "osm_type": osm_type,
        },
    }


def centroid(coords: list[list[float]]) -> tuple[float, float] | None:
    valid = [(lon, lat) for lon, lat in coords if valid_coord(lon, lat)]
    if not valid:
        return None
    return (sum(lon for lon, _lat in valid) / len(valid), sum(lat for _lon, lat in valid) / len(valid))


class PowerGridHandler(osmium.SimpleHandler):
    def __init__(
        self,
        region: str,
        line_out,
        substation_out,
        seen_lines: set[str],
        seen_substations: set[str],
        limit: int | None,
        stats: dict[str, Any],
    ) -> None:
        super().__init__()
        self.region = region
        self.line_out = line_out
        self.substation_out = substation_out
        self.seen_lines = seen_lines
        self.seen_substations = seen_substations
        self.limit = limit
        self.stats = stats

    def _check_limit(self) -> None:
        if self.limit is not None and self.stats["features_written"] >= self.limit:
            raise StopProcessing()

    def node(self, node: Any) -> None:
        if _tag(node.tags, "power") != "substation" or not node.location.valid():
            return
        sid = f"osm-node-{node.id}"
        if sid in self.seen_substations:
            return
        feature = normalize_substation_feature(node.id, node.tags, node.location.lon, node.location.lat, self.region, "node")
        if not feature:
            return
        self.substation_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.seen_substations.add(sid)
        self.stats["substations"] += 1
        self.stats["features_written"] += 1
        self.stats["substation_voltage_distribution"][feature["properties"]["voltage"]] += 1
        self.stats["substation_bounds"] = update_bounds(self.stats["substation_bounds"], [feature["geometry"]["coordinates"]])
        self._check_limit()

    def way(self, way: Any) -> None:
        power = _tag(way.tags, "power")
        try:
            coords = [[node.lon, node.lat] for node in way.nodes if node.location.valid()]
        except osmium.InvalidLocationError:
            coords = []

        if power in POWER_LINE_VALUES:
            lid = f"osm-{way.id}"
            if lid not in self.seen_lines:
                feature = normalize_line_feature(way.id, way.tags, coords, self.region)
                if feature:
                    self.line_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
                    self.seen_lines.add(lid)
                    self.stats["power_lines"] += 1
                    self.stats["features_written"] += 1
                    props = feature["properties"]
                    self.stats["total_route_km"] += float(props["length_km"] or 0)
                    self.stats["line_voltage_distribution"][props["voltage"]] += 1
                    self.stats["power_distribution"][props["power"] or "unknown"] += 1
                    self.stats["line_bounds"] = update_bounds(self.stats["line_bounds"], coords)
                    self._check_limit()

        if power == "substation":
            sid = f"osm-way-{way.id}"
            if sid in self.seen_substations:
                return
            center = centroid(coords)
            if not center:
                return
            feature = normalize_substation_feature(way.id, way.tags, center[0], center[1], self.region, "way")
            if not feature:
                return
            self.substation_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
            self.seen_substations.add(sid)
            self.stats["substations"] += 1
            self.stats["features_written"] += 1
            self.stats["substation_voltage_distribution"][feature["properties"]["voltage"]] += 1
            self.stats["substation_bounds"] = update_bounds(self.stats["substation_bounds"], [feature["geometry"]["coordinates"]])
            self._check_limit()


def make_stats() -> dict[str, Any]:
    return {
        "features_written": 0,
        "power_lines": 0,
        "substations": 0,
        "total_route_km": 0.0,
        "line_bounds": None,
        "substation_bounds": None,
        "line_voltage_distribution": Counter(),
        "substation_voltage_distribution": Counter(),
        "power_distribution": Counter(),
        "regions": [],
    }


def download(url: str, dest: Path, force: bool = False, retries: int = 3) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"using cached: {dest}")
        return dest
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        if dest.exists():
            dest.unlink()
        print(f"downloading {url}" + (f" (attempt {attempt}/{retries})" if retries > 1 else ""))
        try:
            with urllib.request.urlopen(url, timeout=300) as response, dest.open("wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"  {done / total * 100:5.1f}% ({done / 1024 / 1024:.1f} MB)", end="\r")
            if total and dest.stat().st_size != total:
                raise RuntimeError(
                    f"incomplete download for {url}: got {dest.stat().st_size:,} bytes, expected {total:,}"
                )
            print(f"\nsaved: {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
            return dest
        except Exception as exc:
            last_error = exc
            if dest.exists():
                dest.unlink()
            print(f"\ndownload failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(min(30, attempt * 5))
    raise RuntimeError(f"failed to download {url} after {retries} attempts") from last_error


def process_pbf(
    region: str,
    path: Path,
    line_out,
    substation_out,
    seen_lines: set[str],
    seen_substations: set[str],
    limit: int | None,
    stats: dict[str, Any],
) -> None:
    print(f"processing {region}: {path}")
    handler = PowerGridHandler(region, line_out, substation_out, seen_lines, seen_substations, limit, stats)
    try:
        handler.apply_file(str(path), locations=True)
    except StopProcessing:
        print(f"  stopped after --limit {limit}")
    stats["regions"].append(region)


def _line_paths(feature: dict[str, Any]) -> list[list[list[float]]]:
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") == "LineString":
        return [coords]
    if geom.get("type") == "MultiLineString":
        return coords
    return []


def _record_line_stats(feature: dict[str, Any], stats: dict[str, Any]) -> None:
    stats["power_lines"] += 1
    stats["features_written"] += 1
    props = feature.get("properties") or {}
    stats["total_route_km"] += float(props.get("length_km") or 0)
    stats["line_voltage_distribution"][int(props.get("voltage") or 0)] += 1
    stats["power_distribution"][str(props.get("power") or "unknown")] += 1
    for path in _line_paths(feature):
        stats["line_bounds"] = update_bounds(stats["line_bounds"], path)


def _record_substation_stats(feature: dict[str, Any], stats: dict[str, Any]) -> None:
    stats["substations"] += 1
    stats["features_written"] += 1
    props = feature.get("properties") or {}
    stats["substation_voltage_distribution"][int(props.get("voltage") or 0)] += 1
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) >= 2:
        stats["substation_bounds"] = update_bounds(stats["substation_bounds"], [[coords[0], coords[1]]])


def append_existing_europe(
    line_out,
    substation_out,
    seen_lines: set[str],
    seen_substations: set[str],
    stats: dict[str, Any],
    frontend_data: Path = FRONTEND_DATA,
) -> None:
    europe_lines = EUROPE_CACHE / "power_lines.ndjson"
    if europe_lines.exists():
        with europe_lines.open(encoding="utf-8") as f:
            for raw in f:
                if not raw.strip():
                    continue
                feature = json.loads(raw)
                fid = str((feature.get("properties") or {}).get("id") or "")
                if fid in seen_lines:
                    continue
                line_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
                seen_lines.add(fid)
                _record_line_stats(feature, stats)

    europe_substations = frontend_data / "substations.json"
    if europe_substations.exists():
        data = json.loads(europe_substations.read_text(encoding="utf-8"))
        for feature in data.get("features", []):
            fid = str((feature.get("properties") or {}).get("id") or "")
            sid = fid or json.dumps(feature.get("geometry"), sort_keys=True)
            if sid in seen_substations:
                continue
            substation_out.write(json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n")
            seen_substations.add(sid)
            _record_substation_stats(feature, stats)

    if europe_lines.exists() or europe_substations.exists():
        stats["regions"].append("europe-existing")


def write_frontend_metadata(
    stats: dict[str, Any],
    line_ndjson: Path,
    substation_ndjson: Path,
    frontend_data: Path = FRONTEND_DATA,
) -> None:
    frontend_data.mkdir(parents=True, exist_ok=True)
    line_rel = line_ndjson.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    substation_rel = substation_ndjson.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    power_lines = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "total_features": stats["power_lines"],
            "total_route_km": round(stats["total_route_km"]),
            "bounds": stats["line_bounds"],
            "voltage_distribution": dict(sorted(stats["line_voltage_distribution"].items())),
            "power_distribution": dict(sorted(stats["power_distribution"].items())),
            "regions": stats["regions"],
            "pmtiles_input": line_rel,
            "generated_at": generated_at,
            "source": "OpenStreetMap power grid via Geofabrik extracts",
            "source_url": SOURCE_URL,
            "license": "ODbL 1.0",
            "attribution": "(c) OpenStreetMap contributors",
            "scope": "Global power=line, power=minor_line, and power=cable from fresh OSM PBF extracts.",
            "precision_note": "Frontend GeoJSON intentionally stores metadata only. Full line geometry is served from PMTiles.",
        },
    }
    substations = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "total_features": stats["substations"],
            "bounds": stats["substation_bounds"],
            "voltage_distribution": dict(sorted(stats["substation_voltage_distribution"].items())),
            "regions": stats["regions"],
            "pmtiles_input": substation_rel,
            "generated_at": generated_at,
            "source": "OpenStreetMap power grid via Geofabrik extracts",
            "source_url": SOURCE_URL,
            "license": "ODbL 1.0",
            "attribution": "(c) OpenStreetMap contributors",
            "scope": "Global power=substation from fresh OSM PBF extracts.",
            "precision_note": "Frontend GeoJSON intentionally stores metadata only. Full substation geometry is served from PMTiles.",
        },
    }
    (frontend_data / "power_lines.json").write_text(json.dumps(power_lines, ensure_ascii=False, indent=2), encoding="utf-8")
    (frontend_data / "substations.json").write_text(json.dumps(substations, ensure_ascii=False, indent=2), encoding="utf-8")


def selected_inputs(region_args: list[str]) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    for region in region_args:
        if region in REGIONS:
            selected.extend(REGIONS[region])
            continue
        matches = [(name, url) for entries in REGIONS.values() for name, url in entries if name == region]
        if not matches:
            raise SystemExit(f"Unknown region '{region}'. Options: {', '.join(sorted(REGIONS))} or individual subregion names.")
        selected.extend(matches)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch fresh OSM power-grid features from Geofabrik PBF extracts")
    parser.add_argument("--regions", nargs="+", default=["north-america"], help="Region groups or individual subregions to process")
    parser.add_argument("--limit", type=int, default=None, help="Stop after writing N total features; for smoke tests")
    parser.add_argument("--force", action="store_true", help="Re-download existing raw PBF files")
    parser.add_argument("--keep-raw", action="store_true", help="Keep downloaded raw PBF files after processing")
    parser.add_argument("--skip-download", action="store_true", help="Use existing raw PBF files only")
    parser.add_argument("--no-europe-existing", action="store_true", help="Do not prepend existing Europe cache/features")
    parser.add_argument("--append", action="store_true", help="Append to existing NDJSON instead of overwriting")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=CACHE_DIR,
        help="Where merged NDJSON is written; use a scratch directory for smoke runs",
    )
    parser.add_argument(
        "--frontend-data-dir",
        type=Path,
        default=FRONTEND_DATA,
        help="Where metadata-only power_lines.json and substations.json are written; use data/cache/... for smoke runs",
    )
    args = parser.parse_args()

    inputs = selected_inputs(args.regions)
    cache_dir = args.cache_dir if args.cache_dir.is_absolute() else PROJECT_ROOT / args.cache_dir
    frontend_data_dir = args.frontend_data_dir if args.frontend_data_dir.is_absolute() else PROJECT_ROOT / args.frontend_data_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    line_ndjson = cache_dir / "power_lines.ndjson"
    substation_ndjson = cache_dir / "substations.ndjson"
    seen_lines: set[str] = set()
    seen_substations: set[str] = set()
    stats = make_stats()

    if args.append:
        if line_ndjson.exists():
            with line_ndjson.open(encoding="utf-8") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    feat = json.loads(raw)
                    fid = str((feat.get("properties") or {}).get("id") or "")
                    if fid:
                        seen_lines.add(fid)
        if substation_ndjson.exists():
            with substation_ndjson.open(encoding="utf-8") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    feat = json.loads(raw)
                    fid = str((feat.get("properties") or {}).get("id") or "")
                    if fid:
                        seen_substations.add(fid)
        print(f"append mode: loaded {len(seen_lines)} seen lines, {len(seen_substations)} seen substations from existing NDJSON")
        if line_ndjson.exists():
            with line_ndjson.open(encoding="utf-8") as f:
                for raw in f:
                    if raw.strip():
                        feature = json.loads(raw)
                        _record_line_stats(feature, stats)
                        region = str((feature.get("properties") or {}).get("region") or "")
                        if region and region not in stats["regions"]:
                            stats["regions"].append(region)
        if substation_ndjson.exists():
            with substation_ndjson.open(encoding="utf-8") as f:
                for raw in f:
                    if raw.strip():
                        feature = json.loads(raw)
                        _record_substation_stats(feature, stats)
                        region = str((feature.get("properties") or {}).get("region") or "")
                        if region and region not in stats["regions"]:
                            stats["regions"].append(region)
    mode = "a" if args.append else "w"
    with line_ndjson.open(mode, encoding="utf-8") as line_out, substation_ndjson.open(mode, encoding="utf-8") as substation_out:
        if not args.no_europe_existing:
            append_existing_europe(line_out, substation_out, seen_lines, seen_substations, stats, frontend_data_dir)
        for name, url in inputs:
            if args.limit is not None and stats["features_written"] >= args.limit:
                break
            pbf = RAW_DIR / name / Path(url).name
            if args.skip_download and not pbf.exists():
                raise SystemExit(f"Missing raw PBF for --skip-download: {pbf}")
            if not args.skip_download:
                download(url, pbf, force=args.force)
            filtered = _ensure_filtered(pbf)
            process_pbf(name, filtered, line_out, substation_out, seen_lines, seen_substations, args.limit, stats)
            if not args.keep_raw:
                pbf.unlink(missing_ok=True)
                print(f"deleted raw PBF: {pbf}")
                cached_filtered = _FILTER_CACHE.get(pbf)
                if cached_filtered and cached_filtered.exists():
                    cached_filtered.unlink(missing_ok=True)
                    print(f"deleted filtered PBF: {cached_filtered}")

    write_frontend_metadata(stats, line_ndjson, substation_ndjson, frontend_data_dir)
    print(f"power lines: {stats['power_lines']:,} -> {line_ndjson}")
    print(f"substations: {stats['substations']:,} -> {substation_ndjson}")
    print(f"regions: {', '.join(stats['regions'])}")


if __name__ == "__main__":
    main()
