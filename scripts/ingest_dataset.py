"""Ingest a registered dataset: validate, normalize, and write processed output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.ingestion.run import run_ingestion  # noqa: E402
from atlas.registry import get_dataset_by_key  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a registered dataset.")
    parser.add_argument("--dataset-key", required=True)
    parser.add_argument("--file-path", required=True)
    args = parser.parse_args()

    if get_dataset_by_key(args.dataset_key) is None:
        print(f"error: unknown dataset_key: {args.dataset_key}")
        return 1

    file_path = Path(args.file_path)
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    if not file_path.exists():
        print(f"error: file does not exist: {file_path}")
        return 1

    try:
        manifest = run_ingestion(args.dataset_key, file_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 1

    print(f"dataset_key: {manifest['dataset_key']}")
    print(f"run_id: {manifest['run_id']}")
    print(f"status: {manifest['status']}")
    print(f"records_raw: {manifest['records_raw']}")
    print(f"records_loaded: {manifest['records_loaded']}")
    print(f"records_rejected: {manifest['records_rejected']}")
    print(f"output_path: {manifest['output_path']}")

    if manifest.get("rejected_details"):
        for detail in manifest["rejected_details"]:
            for error in detail.get("errors", []):
                print(f"rejected: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
