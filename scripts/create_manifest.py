"""Create a raw provenance manifest for a registered local file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.provenance import build_raw_manifest, validate_raw_manifest, write_manifest  # noqa: E402
from atlas.registry import get_dataset_by_key  # noqa: E402
from atlas.storage import get_storage_paths, validate_repo_file_safety  # noqa: E402


def _default_output_path(file_path: Path) -> Path:
    return PROJECT_ROOT / "data" / "cache" / f"{file_path.name}.raw_manifest.json"


def _matching_safety_issues(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        relative_path = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return []

    storage_paths = list(get_storage_paths(PROJECT_ROOT).values())
    tests_fixtures = (PROJECT_ROOT / "tests" / "fixtures").resolve()
    resolved_path = path.resolve()
    in_storage = any(resolved_path.is_relative_to(storage_path) for storage_path in storage_paths)
    in_test_fixtures = resolved_path.is_relative_to(tests_fixtures)
    if not in_storage and not in_test_fixtures:
        issues.append("git_tracked_unsafe_location")

    issues.extend(
        issue.reason
        for issue in validate_repo_file_safety(PROJECT_ROOT)
        if issue.path == relative_path
    )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a raw dataset provenance manifest.")
    parser.add_argument("--dataset-key", required=True)
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--original-url")
    parser.add_argument("--output")
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
    if not file_path.is_file():
        print(f"error: path is not a file: {file_path}")
        return 1

    safety_issues = _matching_safety_issues(file_path)
    if safety_issues:
        print(f"error: file is not safe for repository manifest creation: {file_path}")
        for issue in safety_issues:
            print(f"issue: {issue}")
        return 1

    manifest = build_raw_manifest(args.dataset_key, file_path, original_url=args.original_url)
    validation = validate_raw_manifest(manifest)
    if not validation["ok"]:
        for error in validation["errors"]:
            print(f"error: {error}")
        return 1

    output_path = Path(args.output) if args.output else _default_output_path(file_path)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    write_manifest(output_path, manifest)
    print(f"raw manifest written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
