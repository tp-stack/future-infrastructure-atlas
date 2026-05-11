"""Local storage and repository safety utilities."""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import yaml


DEFAULT_STORAGE_CONFIG: dict[str, Any] = {
    "local_storage_root": "data/",
    "raw_dir": "data/raw",
    "staging_dir": "data/staging",
    "processed_dir": "data/processed",
    "tiles_dir": "data/tiles",
    "cache_dir": "data/cache",
    "reports_dir": "data/reports",
    "logs_dir": "data/logs",
    "max_git_file_size_mb": 5,
    "max_test_fixture_size_mb": 1,
    "max_api_response_size_mb": 5,
    "allowed_large_file_locations": [
        "data/raw/",
        "data/staging/",
        "data/processed/",
        "data/tiles/",
        "data/cache/",
        "data/reports/",
        "data/logs/",
    ],
    "blocked_file_extensions": [
        ".geojson",
        ".gpkg",
        ".shp",
        ".dbf",
        ".shx",
        ".prj",
        ".pbf",
        ".mbtiles",
        ".pmtiles",
        ".tif",
        ".tiff",
        ".nc",
        ".grib",
        ".parquet",
        ".duckdb",
        ".sqlite",
    ],
    "atomic_write_required": True,
    "checksum_algorithm": "sha256",
}

STORAGE_DIR_KEYS = (
    "raw_dir",
    "staging_dir",
    "processed_dir",
    "tiles_dir",
    "cache_dir",
    "reports_dir",
    "logs_dir",
)

SKIPPED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "node_modules",
    "dist",
    "build",
}


@dataclass(frozen=True)
class FileSafetyIssue:
    """A repository file safety problem."""

    path: str
    reason: str
    size_mb: float | None = None
    detail: str | None = None


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()


def _load_storage_config(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = _repo_root(repo_root)
    config_path = root / "config" / "storage.yaml"
    if not config_path.exists():
        return DEFAULT_STORAGE_CONFIG.copy()

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in {config_path}")

    config = DEFAULT_STORAGE_CONFIG.copy()
    config.update(loaded)
    return config


def _resolve_repo_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_test_fixture(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return len(relative.parts) >= 2 and relative.parts[0] == "tests" and relative.parts[1] == "fixtures"


def _iter_repo_files(root: Path) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIPPED_DIRECTORIES]
        current_path = Path(current_root)
        for filename in filenames:
            yield current_path / filename


def get_storage_paths(repo_root: str | Path | None = None) -> dict[str, Path]:
    """Return absolute paths for the configured local storage directories."""

    root = _repo_root(repo_root)
    config = _load_storage_config(root)
    return {key: _resolve_repo_path(root, config[key]) for key in STORAGE_DIR_KEYS}


def ensure_storage_dirs(repo_root: str | Path | None = None, create_gitkeep: bool = True) -> dict[str, Path]:
    """Create required local storage directories and optional `.gitkeep` files."""

    paths = get_storage_paths(repo_root)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
        if create_gitkeep:
            gitkeep = path / ".gitkeep"
            gitkeep.touch(exist_ok=True)
    return paths


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 checksum for a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: str | Path, content: str) -> None:
    """Write text atomically by replacing the target from a temporary sibling."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def get_file_size_mb(path: str | Path) -> float:
    """Return file size in MiB."""

    return Path(path).stat().st_size / (1024 * 1024)


def is_blocked_large_file(path: str | Path, max_mb: float) -> bool:
    """Return true when a file exceeds the configured Git-safe size limit."""

    file_path = Path(path)
    return file_path.is_file() and get_file_size_mb(file_path) > max_mb


def validate_repo_file_safety(repo_root: str | Path) -> list[FileSafetyIssue]:
    """Find files that should not be committed to the repository."""

    root = _repo_root(repo_root)
    config = _load_storage_config(root)
    max_git_file_size_mb = float(config["max_git_file_size_mb"])
    max_test_fixture_size_mb = float(config["max_test_fixture_size_mb"])
    blocked_extensions = {str(ext).lower() for ext in config["blocked_file_extensions"]}
    allowed_large_locations = [
        _resolve_repo_path(root, location) for location in config["allowed_large_file_locations"]
    ]

    issues: list[FileSafetyIssue] = []

    for file_path in _iter_repo_files(root):
        resolved_path = file_path.resolve()
        relative_path = resolved_path.relative_to(root).as_posix()
        size_mb = get_file_size_mb(resolved_path)
        suffix = resolved_path.suffix.lower()
        in_allowed_large_location = any(
            _is_relative_to(resolved_path, allowed_location)
            for allowed_location in allowed_large_locations
        )
        is_fixture = _is_test_fixture(resolved_path, root)

        if is_fixture and size_mb > max_test_fixture_size_mb:
            issues.append(
                FileSafetyIssue(
                    path=relative_path,
                    reason="test_fixture_too_large",
                    size_mb=size_mb,
                    detail=f"Test fixtures must be <= {max_test_fixture_size_mb:g} MiB.",
                )
            )
            continue

        if not in_allowed_large_location and size_mb > max_git_file_size_mb:
            issues.append(
                FileSafetyIssue(
                    path=relative_path,
                    reason="file_too_large",
                    size_mb=size_mb,
                    detail=f"Repository files must be <= {max_git_file_size_mb:g} MiB.",
                )
            )

        if not in_allowed_large_location and not is_fixture and suffix in blocked_extensions:
            issues.append(
                FileSafetyIssue(
                    path=relative_path,
                    reason="blocked_extension",
                    size_mb=size_mb,
                    detail=f"Files with extension {suffix} belong in ignored data directories.",
                )
            )

    return issues


def _format_issue(issue: FileSafetyIssue) -> str:
    size = "" if issue.size_mb is None else f" ({issue.size_mb:.2f} MiB)"
    detail = "" if issue.detail is None else f" - {issue.detail}"
    return f"{issue.reason}: {issue.path}{size}{detail}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate repository storage safety.")
    parser.add_argument("repo_root", nargs="?", default=".", help="Repository root to validate.")
    args = parser.parse_args()

    issues = validate_repo_file_safety(args.repo_root)
    if issues:
        for issue in issues:
            print(_format_issue(issue))
        return 1

    print("Storage safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
