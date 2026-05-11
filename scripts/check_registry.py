"""Validate source, dataset, and layer registries."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.registry import validate_all_registries  # noqa: E402


def main() -> int:
    result = validate_all_registries()

    print(f"registry: {'ok' if result.ok else 'failed'}")
    print(f"errors: {len(result.errors)}")
    print(f"warnings: {len(result.warnings)}")

    for warning in result.warnings:
        print(f"warning: {warning}")
    for error in result.errors:
        print(f"error: {error}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
