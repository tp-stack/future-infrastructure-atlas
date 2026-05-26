#!/usr/bin/env python3
"""Fetch protected-area features from Geofabrik OSM PBF extracts.

Extracts boundary=protected_area, boundary=national_park, and
leisure=nature_reserve features from the same Geofabrik PBFs used by
the power grid pipeline. Reuses the same download infrastructure.

Output: compact NDJSON with centroid points and key tags (name,
protect_class, boundary, leisure, designation, operator).

Pattern matches fetch_osm_global_power_grid.py.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import osmium
except ImportError as exc:
    raise SystemExit("Missing dependency: install with `python -m pip install osmium`.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "osm_protected_areas"
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "osm_protected_areas"
SOURCE_URL = "https://download.geofabrik.de/"

BASE_GEOFABRIK = "https://download.geofabrik.de/"

PROTECTED_BOUNDARY_VALUES = {"protected_area", "national_park"}
PROTECTED_LEISURE_VALUES = {"nature_reserve", "park"}
PROTECTED_LANDUSE_VALUES = {"conservation", "national_park"}


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
    "europe": [
        ("netherlands", f"{BASE_GEOFABRIK}europe/netherlands-latest.osm.pbf"),
        ("germany", f"{BASE_GEOFABRIK}europe/germany-latest.osm.pbf"),
        ("belgium", f"{BASE_GEOFABRIK}europe/belgium-latest.osm.pbf"),
        ("france", f"{BASE_GEOFABRIK}europe/france-latest.osm.pbf"),
        ("uk", f"{BASE_GEOFABRIK}europe/great-britain-latest.osm.pbf"),
        ("italy", f"{BASE_GEOFABRIK}europe/italy-latest.osm.pbf"),
        ("spain", f"{BASE_GEOFABRIK}europe/spain-latest.osm.pbf"),
        ("switzerland", f"{BASE_GEOFABRIK}europe/switzerland-latest.osm.pbf"),
        ("austria", f"{BASE_GEOFABRIK}europe/austria-latest.osm.pbf"),
        ("poland", f"{BASE_GEOFABRIK}europe/poland-latest.osm.pbf"),
        ("sweden", f"{BASE_GEOFABRIK}europe/sweden-latest.osm.pbf"),
        ("norway", f"{BASE_GEOFABRIK}europe/norway-latest.osm.pbf"),
        ("denmark", f"{BASE_GEOFABRIK}europe/denmark-latest.osm.pbf"),
        ("finland", f"{BASE_GEOFABRIK}europe/finland-latest.osm.pbf"),
        ("portugal", f"{BASE_GEOFABRIK}europe/portugal-latest.osm.pbf"),
        ("ireland", f"{BASE_GEOFABRIK}europe/ireland-latest.osm.pbf"),
        ("czech-republic", f"{BASE_GEOFABRIK}europe/czech-republic-latest.osm.pbf"),
        ("hungary", f"{BASE_GEOFABRIK}europe/hungary-latest.osm.pbf"),
        ("romania", f"{BASE_GEOFABRIK}europe/romania-latest.osm.pbf"),
        ("netherlands-antilles", f"{BASE_GEOFABRIK}europe/netherlands-antilles-latest.osm.pbf"),
    ],
    "micro": [
        ("liechtenstein", f"{BASE_GEOFABRIK}europe/liechtenstein-latest.osm.pbf"),
        ("andorra", f"{BASE_GEOFABRIK}europe/andorra-latest.osm.pbf"),
        ("monaco", f"{BASE_GEOFABRIK}europe/monaco-latest.osm.pbf"),
        ("san-marino", f"{BASE_GEOFABRIK}europe/san-marino-latest.osm.pbf"),
        ("malta", f"{BASE_GEOFABRIK}europe/malta-latest.osm.pbf"),
        ("luxembourg", f"{BASE_GEOFABRIK}europe/luxembourg-latest.osm.pbf"),
    ],
}


class StopProcessing(Exception):
    """Internal signal used for --limit smoke runs."""


def _tag(tags: Any, key: str) -> str:
    val = tags.get(key)
    return str(val) if val is not None else ""


def _centroid(coords: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _is_protected(tags: Any) -> bool:
    boundary = _tag(tags, "boundary")
    leisure = _tag(tags, "leisure")
    landuse = _tag(tags, "landuse")
    protect_class = _tag(tags, "protect_class")

    if boundary in PROTECTED_BOUNDARY_VALUES:
        return True
    if leisure in PROTECTED_LEISURE_VALUES:
        return True
    if landuse in PROTECTED_LANDUSE_VALUES:
        return True
    if protect_class and protect_class.isdigit():
        cls = int(protect_class)
        if 1 <= cls <= 6:
            return True
    return False


def _protect_class_label(tags: Any) -> str:
    pc = _tag(tags, "protect_class")
    if pc and pc.isdigit():
        return f"class-{pc}"
    boundary = _tag(tags, "boundary")
    leisure = _tag(tags, "leisure")
    if boundary == "national_park":
        return "national_park"
    if boundary == "protected_area":
        return "protected_area"
    if leisure == "nature_reserve":
        return "nature_reserve"
    if leisure == "park":
        return "park"
    return "unknown"


def make_feature(
    osm_id: int,
    tags: Any,
    lon: float,
    lat: float,
    region: str,
    geom_type: str,
) -> dict[str, Any] | None:
    if not _is_protected(tags):
        return None
    return {
        "id": f"pa-{region}-{geom_type}-{osm_id}",
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "t": "pa",
        "q": "obs",
        "n": _tag(tags, "name") or "",
        "c": _tag(tags, "protect_class") or "",
        "b": _tag(tags, "boundary") or "",
        "l": _tag(tags, "leisure") or "",
        "d": _tag(tags, "designation") or "",
        "pcl": _protect_class_label(tags),
        "region": region,
    }


def normalize_feature(
    osm_id: int,
    tags: Any,
    lon: float,
    lat: float,
    region: str,
    geom_type: str,
) -> dict[str, Any] | None:
    feat = make_feature(osm_id, tags, lon, lat, region, geom_type)
    if feat is None:
        return None
    return feat


class ProtectedAreaHandler(osmium.SimpleHandler):
    def __init__(
        self,
        region: str,
        out,
        seen: set[str],
        limit: int | None,
        stats: dict[str, Any],
    ) -> None:
        super().__init__()
        self.region = region
        self.out = out
        self.seen = seen
        self.limit = limit
        self.stats = stats

    def _check_limit(self) -> None:
        if self.limit is not None and self.stats["features_written"] >= self.limit:
            raise StopProcessing()

    def node(self, node: Any) -> None:
        if not node.location.valid():
            return
        if not _is_protected(node.tags):
            return
        sid = f"node-{node.id}"
        if sid in self.seen:
            return
        feat = normalize_feature(node.id, node.tags, node.location.lon, node.location.lat, self.region, "node")
        if not feat:
            return
        self.out.write(json.dumps(feat, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.seen.add(sid)
        self.stats["features"] += 1
        self.stats["features_written"] += 1
        self._check_limit()

    def way(self, way: Any) -> None:
        if not _is_protected(way.tags):
            return
        try:
            coords = [(node.lon, node.lat) for node in way.nodes if node.location.valid()]
        except osmium.InvalidLocationError:
            coords = []
        if len(coords) < 3:
            return
        center = _centroid(coords)
        if not center:
            return
        sid = f"way-{way.id}"
        if sid in self.seen:
            return
        feat = normalize_feature(way.id, way.tags, center[0], center[1], self.region, "way")
        if not feat:
            return
        self.out.write(json.dumps(feat, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.seen.add(sid)
        self.stats["features"] += 1
        self.stats["features_written"] += 1
        self._check_limit()


def make_stats() -> dict[str, Any]:
    return {
        "features": 0,
        "features_written": 0,
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
    out,
    seen: set[str],
    limit: int | None,
    stats: dict[str, Any],
) -> None:
    print(f"processing {region}: {path}")
    handler = ProtectedAreaHandler(region, out, seen, limit, stats)
    try:
        handler.apply_file(str(path), locations=True)
    except StopProcessing:
        print(f"  stopped after --limit {limit}")
    except Exception:
        print(f"  invalid PBF, skipping: {path}")
        return
    stats["regions"].append(region)


def selected_inputs(region_args: list[str]) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    for region in region_args:
        if region in REGIONS:
            selected.extend(REGIONS[region])
            continue
        matches = [(name, url) for entries in REGIONS.values() for name, url in entries if name == region]
        if not matches:
            known = sorted(REGIONS)
            raise SystemExit(f"Unknown region '{region}'. Options: {', '.join(known)} or individual subregion names.")
        selected.extend(matches)
    return selected


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch protected-area features from Geofabrik PBF extracts")
    parser.add_argument("--regions", nargs="+", default=["europe"], help="Region groups or individual subregions to process")
    parser.add_argument("--limit", type=int, default=None, help="Stop after writing N total features; for smoke tests")
    parser.add_argument("--force", action="store_true", help="Re-download existing raw PBF files")
    parser.add_argument("--keep-raw", action="store_true", help="Keep downloaded raw PBF files after processing")
    parser.add_argument("--skip-download", action="store_true", help="Use existing raw PBF files only")
    parser.add_argument("--append", action="store_true", help="Append to existing NDJSON instead of overwriting")
    args = parser.parse_args()

    inputs = selected_inputs(args.regions)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ndjson = CACHE_DIR / "protected_areas.ndjson"
    seen: set[str] = set()
    stats = make_stats()

    if args.append and ndjson.exists():
        with ndjson.open(encoding="utf-8") as f:
            for raw in f:
                if not raw.strip():
                    continue
                feat = json.loads(raw)
                fid = str(feat.get("id", ""))
                if fid:
                    seen.add(fid)
        print(f"append mode: loaded {len(seen)} seen features from existing NDJSON")

    mode = "a" if args.append else "w"
    with ndjson.open(mode, encoding="utf-8") as out:
        for name, url in inputs:
            if args.limit is not None and stats["features_written"] >= args.limit:
                break
            pbf = RAW_DIR / name / Path(url).name
            if args.skip_download and not pbf.exists():
                raise SystemExit(f"Missing raw PBF for --skip-download: {pbf}")
            if not args.skip_download:
                download(url, pbf, force=args.force)
            if pbf.stat().st_size == 0:
                print(f"skipping {name}: PBF is empty (0 bytes)")
                pbf.unlink(missing_ok=True)
                continue
            process_pbf(name, pbf, out, seen, args.limit, stats)
            if not args.keep_raw:
                try:
                    pbf.unlink(missing_ok=True)
                    print(f"deleted raw PBF: {pbf}")
                except PermissionError:
                    print(f"could not delete (locked): {pbf}")

    print(f"protected areas: {stats['features']:,} -> {ndjson}")
    print(f"regions: {', '.join(stats['regions'])}")


if __name__ == "__main__":
    main()
