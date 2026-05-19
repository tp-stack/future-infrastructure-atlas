"""Generate a static build observatory page for Atlas QA."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PUBLIC = PROJECT_ROOT / "frontend" / "public"
DATA_DIR = FRONTEND_PUBLIC / "data"
TILES_DIR = FRONTEND_PUBLIC / "tiles"
ARTIFACT_TILES_DIR = PROJECT_ROOT / "data" / "tiles"
OUTPUT_PATH = FRONTEND_PUBLIC / "debug" / "build_observatory.html"

ROUTES = [
    ("/", "Normal app"),
    ("/?reliableMap=1", "Reliable canvas route"),
    ("/?reliableMap=1&proof=1", "Reliable proof route"),
    ("/?zoomMap=1", "Clean zoomable route"),
    ("/?maplibreMap=1", "Protected map route"),
    ("/?debugMap=1", "Debug route"),
    ("/?debugMap=1&proof=1", "Proof route"),
    ("/?pmtilesMap=1", "PMTiles route"),
]

PMTILES = [
    "power_plants.pmtiles",
    "submarine_cables.pmtiles",
    "data_centers.pmtiles",
]


def run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def size_label(path: Path) -> str:
    if not path.exists():
        return "missing"
    size = path.stat().st_size
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / 1024:.1f} KB"


def status_class(ok: bool | None) -> str:
    if ok is True:
        return "ok"
    if ok is False:
        return "warn"
    return "muted"


def route_links(live_url: str) -> str:
    links = []
    base = live_url.rstrip("/")
    for route, label in ROUTES:
        href = f"{base}{route}" if base else route
        links.append(f'<a href="{html.escape(href)}">{html.escape(label)}<span>{html.escape(route)}</span></a>')
    return "\n".join(links)


def render_sources(web_data: dict[str, Any] | None, core: dict[str, Any] | None) -> str:
    metadata = (web_data or {}).get("metadata", {})
    sources = metadata.get("sources") or (core or {}).get("sources") or []
    rows = []
    for source in sources:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(source.get('key', '')))}</td>"
            f"<td>{html.escape(str(source.get('name', '')))}</td>"
            f"<td>{html.escape(str(source.get('license', '')))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="3">No source metadata found.</td></tr>'


def render_license_warnings(web_data: dict[str, Any] | None, core: dict[str, Any] | None) -> str:
    counts = ((web_data or {}).get("metadata") or {}).get("counts", {})
    warnings = list((core or {}).get("license_warnings", []))
    if counts.get("cable_geometry_license_status") == "to_verify" or counts.get("cable_geometry_review_required"):
        warnings.append({
            "layer": "submarine_cables",
            "message": "KMCD cable data remains source_license: to_verify and license_review_required: true.",
            "active": True,
        })
    warnings.append({
        "layer": "data_centers",
        "message": "PeeringDB public facilities / interconnection data, not all data centers in the world.",
        "active": True,
    })
    return "\n".join(
        f"<li class=\"{status_class(not bool(w.get('active')))}\"><strong>{html.escape(str(w.get('layer', 'warning')))}</strong>: {html.escape(str(w.get('message', '')))}</li>"
        for w in warnings
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frontend/public/debug/build_observatory.html")
    parser.add_argument("--live-url", default="", help="Production deployment URL")
    args = parser.parse_args()

    web_path = DATA_DIR / "atlas_web_data.json"
    core_path = DATA_DIR / "atlas_core.json"
    web_data = load_json(web_path)
    core = load_json(core_path)
    counts = ((web_data or {}).get("metadata") or {}).get("counts", {}) or (core or {}).get("counts", {})

    branch = run_git(["branch", "--show-current"])
    commit = run_git(["rev-parse", "--short", "HEAD"])
    generated_at = datetime.now(timezone.utc).isoformat()

    atlas_web_ok = web_path.exists() and web_path.stat().st_size <= 5 * 1024 * 1024
    atlas_core_ok = core_path.exists() and core_path.stat().st_size <= 500 * 1024

    tile_rows = []
    tile_registry = (core or {}).get("tile_registry", {})
    for name in PMTILES:
        layer_key = name.replace(".pmtiles", "")
        status = (tile_registry.get(layer_key) or {}).get("status", "unknown")
        tile_path = TILES_DIR / name
        artifact_path = ARTIFACT_TILES_DIR / name
        present = tile_path.exists()
        artifact_present = artifact_path.exists()
        tile_rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f"<td class=\"{status_class(present)}\">{html.escape('present' if present else 'missing')}</td>"
            f"<td>{html.escape(size_label(tile_path))}</td>"
            f"<td class=\"{status_class(artifact_present)}\">{html.escape('present' if artifact_present else 'missing')}</td>"
            f"<td>{html.escape(size_label(artifact_path))}</td>"
            f"<td>{html.escape(str(status))}</td>"
            "</tr>"
        )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FUTURE Infrastructure Atlas Build Observatory</title>
  <style>
    body {{ margin: 0; background: #05070a; color: #eef2f7; font-family: Inter, system-ui, sans-serif; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    h2 {{ font-size: 14px; margin: 24px 0 10px; color: #9ca3af; text-transform: uppercase; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .panel {{ border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); border-radius: 8px; padding: 14px; }}
    .metric {{ font-size: 26px; font-weight: 700; }}
    .label {{ color: #9ca3af; font-size: 12px; margin-top: 4px; }}
    a {{ color: #67e8f9; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .routes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }}
    .routes a {{ display: flex; flex-direction: column; gap: 4px; border: 1px solid rgba(103,232,249,0.18); border-radius: 6px; padding: 10px; background: rgba(8,145,178,0.08); }}
    .routes span {{ color: #9ca3af; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid rgba(255,255,255,0.08); padding: 8px; text-align: left; vertical-align: top; }}
    th {{ color: #9ca3af; font-size: 12px; }}
    ul {{ margin: 0; padding-left: 18px; line-height: 1.7; }}
    .ok {{ color: #86efac; }}
    .warn {{ color: #fbbf24; }}
    .muted {{ color: #9ca3af; }}
    .small {{ color: #9ca3af; font-size: 12px; line-height: 1.6; }}
  </style>
</head>
<body>
<main>
  <h1>FUTURE Infrastructure Atlas Build Observatory</h1>
  <div class="small">Generated {html.escape(generated_at)} on branch {html.escape(branch)} at commit {html.escape(commit)}.</div>
  <div class="small">Live URL: <a href="{html.escape(args.live_url)}">{html.escape(args.live_url or "not configured")}</a></div>

  <h2>Routes</h2>
  <section class="routes">{route_links(args.live_url)}</section>

  <h2>Data Status</h2>
  <section class="grid">
    <div class="panel"><div class="metric {status_class(atlas_web_ok)}">{html.escape(size_label(web_path))}</div><div class="label">atlas_web_data.json, 5 MB cap</div></div>
    <div class="panel"><div class="metric {status_class(atlas_core_ok)}">{html.escape(size_label(core_path))}</div><div class="label">atlas_core.json, metadata only</div></div>
    <div class="panel"><div class="metric">{int(counts.get("power_plants_mapped") or 0):,}</div><div class="label">mapped power plants</div></div>
    <div class="panel"><div class="metric">{int(counts.get("submarine_cables_mapped") or counts.get("cables_mapped") or 0):,} / {int(counts.get("submarine_cables_total") or counts.get("cables_total") or 0):,}</div><div class="label">mapped submarine cables</div></div>
    <div class="panel"><div class="metric">{int(counts.get("data_centers_mapped") or 0):,} / {int(counts.get("data_centers_total") or 0):,}</div><div class="label">mapped data centers</div></div>
  </section>

  <h2>PMTiles</h2>
  <table><thead><tr><th>File</th><th>Public file</th><th>Public size</th><th>Artifact file</th><th>Artifact size</th><th>atlas_core status</th></tr></thead><tbody>{''.join(tile_rows)}</tbody></table>

  <h2>Source And License Warnings</h2>
  <ul>{render_license_warnings(web_data, core)}</ul>
  <table><thead><tr><th>Key</th><th>Name</th><th>License</th></tr></thead><tbody>{render_sources(web_data, core)}</tbody></table>

  <h2>Visual QA Checklist</h2>
  <ul>
    <li>Normal app and <code>?reliableMap=1</code> show a non-empty zoomable global map without relying on MapLibre.</li>
    <li><code>?maplibreMap=1</code> is protected by the reliable renderer; <code>?zoomMap=1</code> remains available for raw MapLibre diagnostics.</li>
    <li>Power plants, data centers, cable lines, and graticule are visible.</li>
    <li><code>?debugMap=1&amp;proof=1</code> shows five large proof points.</li>
    <li>Zoom controls, cluster expansion, reset global view, and fit filtered results work.</li>
    <li>Clicking a power plant, data center, or cable opens a popup or details panel.</li>
    <li><code>?pmtilesMap=1</code> shows setup warnings instead of a black screen when PMTiles are missing.</li>
  </ul>

  <h2>Build And Test Status</h2>
  <div class="panel small">
    This observatory captures file and route metadata. Validation commands are run separately:
    <code>pytest -q</code>, <code>python -m atlas.storage .</code>, <code>npm.cmd run build</code>,
    <code>python scripts/check_frontend_data.py</code>, and PMTiles/core checks where available.
  </div>
</main>
</body>
</html>
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html_doc, encoding="utf-8")
    print(f"Build observatory written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
