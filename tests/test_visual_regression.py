from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_core_map_routes_are_not_visually_empty() -> None:
    subprocess.run(
        [sys.executable, "scripts/check_visual_regression.py"],
        cwd=PROJECT_ROOT,
        check=True,
        timeout=180,
    )
