"""Remove local cache contents while preserving cache directory placeholders."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.storage import get_storage_paths  # noqa: E402


def main() -> int:
    cache_dir = get_storage_paths(PROJECT_ROOT)["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)

    for child in cache_dir.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    (cache_dir / ".gitkeep").touch(exist_ok=True)
    print(f"Cleaned cache directory: {cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
