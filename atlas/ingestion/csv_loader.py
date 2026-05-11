from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def read_csv_records(file_path: str | Path) -> list[dict[str, Any]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise ValueError(f"CSV path is not a file: {path}")

    with path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        records = list(reader)

    if not records:
        raise ValueError(f"CSV file is empty or missing header row: {path}")

    return records


def read_csv_stream(file_path: str | Path) -> Iterator[dict[str, Any]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise ValueError(f"CSV path is not a file: {path}")

    with path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        yielded = False
        for row in reader:
            yielded = True
            yield row

    if not yielded:
        raise ValueError(f"CSV file is empty or missing header row: {path}")
