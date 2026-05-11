"""Release validation script.

Checks:
- All config registries pass validation
- Build pipeline produces valid output under 5 MB
- Storage safety passes
- No large/blocked files in the repo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from atlas.registry import validate_all_registries  # noqa: E402
from atlas.storage import validate_repo_file_safety  # noqa: E402


def check_registry() -> list[str]:
    result = validate_all_registries()
    if result.ok:
        return []
    return result.errors


def check_storage_safety() -> list[str]:
    issues = validate_repo_file_safety(PROJECT_ROOT)
    return [f"{i.path}: {i.reason}" for i in issues]


def check_build_output() -> list[str]:
    errors = []
    paths_to_check = [
        PROJECT_ROOT / "frontend" / "public" / "data" / "atlas_web_data.json",
    ]
    for path in paths_to_check:
        if not path.exists():
            errors.append(f"Missing build output: {path.relative_to(PROJECT_ROOT)}")
            continue
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 5:
            errors.append(f"Build output too large: {path.relative_to(PROJECT_ROOT)} is {size_mb:.2f} MB (max 5 MB)")
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if "metadata" not in data:
                errors.append(f"Build output missing 'metadata' key in {path.relative_to(PROJECT_ROOT)}")
            if "power_plants" not in data:
                errors.append(f"Build output missing 'power_plants' key in {path.relative_to(PROJECT_ROOT)}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors.append(f"Build output is not valid JSON: {e}")
    return errors


def main() -> int:
    errors: list[str] = []

    registry_errors = check_registry()
    if registry_errors:
        errors.append(f"Registry errors ({len(registry_errors)}):")
        errors.extend(f"  {e}" for e in registry_errors)

    storage_errors = check_storage_safety()
    if storage_errors:
        errors.append(f"Storage safety issues ({len(storage_errors)}):")
        errors.extend(f"  {e}" for e in storage_errors)

    build_errors = check_build_output()
    if build_errors:
        errors.append(f"Build output issues ({len(build_errors)}):")
        errors.extend(f"  {e}" for e in build_errors)

    if errors:
        print("RELEASE CHECK FAILED")
        print("\n".join(errors))
        return 1
    else:
        print("RELEASE CHECK PASSED")
        print(f"  Registry: OK")
        print(f"  Storage safety: OK")
        print(f"  Build output: OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
