"""Preflight checks for Vercel deploys.

The deploy target should not upload raw data or large PMTiles as source/static
assets. Europe power lines are intentionally remote-only unless the local public
PMTiles file is below the selected threshold.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_core.json"
PUBLIC_POWER_LINES = PROJECT_ROOT / "frontend" / "public" / "tiles" / "power_lines.pmtiles"
ARTIFACT_POWER_LINES = PROJECT_ROOT / "data" / "tiles" / "power_lines.pmtiles"

FORBIDDEN_STAGED_PREFIXES = (
    "data/raw/",
    "data/cache/",
    "data/processed/",
    "data/tiles/",
    "data/logs/",
    "data/reports/",
    "scripts/data/",
)

POWER_LINES_HOBBY_MESSAGE = (
    "power_lines.pmtiles is 190.37 MB. Use object storage or Vercel Pro. "
    "Do not deploy this file inside the Hobby source upload."
)


def _posix(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def _staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [_posix(item) for item in result.stdout.decode("utf-8", errors="replace").split("\0") if item]


def _load_core() -> dict:
    with open(CORE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("atlas_core.json must contain a JSON object")
    return data


def _manual_steps() -> str:
    return """
Manual object-storage steps:
1. Create a public Cloudflare R2 bucket or another object store with HTTP Range Request support.
2. Upload data/tiles/power_lines.pmtiles.
3. Configure CORS for GET, HEAD, and OPTIONS.
4. Copy the public HTTPS URL.
5. Set the environment variable:
   $env:POWER_LINES_PMTILES_URL="https://<domain>/power_lines.pmtiles"
6. Rebuild atlas_core:
   python scripts/build_atlas_core.py
7. Run:
   python scripts/preflight_deploy.py --max-local-pmtiles-mb 100
""".strip()


def _check_staged_files(max_local_pmtiles_mb: float) -> list[str]:
    errors: list[str] = []
    for path_str in _staged_files():
        if path_str == "frontend/tsconfig.tsbuildinfo":
            errors.append("frontend/tsconfig.tsbuildinfo is staged; remove it before deploy.")
        if path_str.endswith(".pmtiles"):
            path = PROJECT_ROOT / path_str
            if path.exists() and _size_mb(path) > max_local_pmtiles_mb:
                errors.append(f"{path_str} is {_size_mb(path):.2f} MB, above the {max_local_pmtiles_mb:.0f} MB deploy threshold.")
        if any(path_str.startswith(prefix) for prefix in FORBIDDEN_STAGED_PREFIXES):
            errors.append(f"{path_str} is staged from a forbidden generated/raw data path.")
    return errors


def _check_core(max_local_pmtiles_mb: float) -> list[str]:
    errors: list[str] = []
    if not CORE_PATH.exists():
        return [f"atlas_core.json is missing at {CORE_PATH}."]

    try:
        core = _load_core()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"atlas_core.json is invalid: {exc}"]

    power_lines = (core.get("tile_registry") or {}).get("power_lines") or {}
    power_url = str(power_lines.get("url") or "")
    status = str(power_lines.get("status") or "")

    source_rows = core.get("sources") or []
    source_text = json.dumps(source_rows, ensure_ascii=False)
    warning_text = json.dumps(core.get("license_warnings") or [], ensure_ascii=False)
    if "OpenStreetMap" not in source_text or "ODbL" not in source_text:
        errors.append("OpenStreetMap Europe power-line ODbL source is missing from atlas_core.sources.")
    if "ODbL" not in warning_text or "share-alike" not in warning_text:
        errors.append("ODbL share-alike warning is missing from atlas_core.license_warnings.")

    if power_url.startswith("pmtiles://https://"):
        remote_url = power_url.removeprefix("pmtiles://")
        if not remote_url.startswith("https://"):
            errors.append("Remote power_lines PMTiles URL must start with https://.")
        return errors

    local_url = power_url in {"pmtiles:///tiles/power_lines.pmtiles", "/tiles/power_lines.pmtiles"}
    local_path = PUBLIC_POWER_LINES if PUBLIC_POWER_LINES.exists() else ARTIFACT_POWER_LINES
    local_size = _size_mb(local_path) if local_path.exists() else 0

    if local_url:
        if not PUBLIC_POWER_LINES.exists():
            errors.append("atlas_core.json points to local power_lines.pmtiles, but frontend/public/tiles/power_lines.pmtiles is missing.")
        elif local_size > max_local_pmtiles_mb:
            errors.append(POWER_LINES_HOBBY_MESSAGE)
        return errors

    remote_env = os.environ.get("POWER_LINES_PMTILES_URL", "").strip()
    if not remote_env and local_path.exists() and local_size > max_local_pmtiles_mb:
        if "remote_required" in status:
            errors.append(POWER_LINES_HOBBY_MESSAGE)
        else:
            errors.append(POWER_LINES_HOBBY_MESSAGE)
    elif not power_url:
        errors.append("atlas_core.json has no power_lines tile URL. Set POWER_LINES_PMTILES_URL or provide a small local PMTiles file.")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Vercel deploy safety checks.")
    parser.add_argument("--max-local-pmtiles-mb", type=float, default=100.0)
    args = parser.parse_args()

    errors = []
    errors.extend(_check_staged_files(args.max_local_pmtiles_mb))
    errors.extend(_check_core(args.max_local_pmtiles_mb))

    dist_index = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        print("OK: frontend build artifact exists.")
    else:
        print("NOTE: frontend/dist/index.html is not present yet; run npm run build before deploy.")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        if any("power_lines.pmtiles is 190.37 MB" in error for error in errors):
            print()
            print(_manual_steps())
        sys.exit(1)

    print("preflight_deploy: PASSED")


if __name__ == "__main__":
    main()
