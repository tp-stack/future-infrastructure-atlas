from pathlib import Path

from atlas.storage import ensure_storage_dirs, validate_repo_file_safety


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_storage_directories_can_be_created(tmp_path):
    paths = ensure_storage_dirs(tmp_path)

    assert set(paths) == {
        "raw_dir",
        "staging_dir",
        "processed_dir",
        "tiles_dir",
        "cache_dir",
        "reports_dir",
        "logs_dir",
    }
    for path in paths.values():
        assert path.is_dir()
        assert (path / ".gitkeep").is_file()


def test_gitignore_contains_blocked_geospatial_patterns():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in [
        "data/raw/**",
        "data/staging/**",
        "data/processed/**",
        "data/tiles/**",
        "*.geojson",
        "*.gpkg",
        "*.shp",
        "*.mbtiles",
        "*.pmtiles",
        "*.tif",
        "*.parquet",
        "*.duckdb",
        "*.sqlite",
        "!data/README.md",
        "!data/**/.gitkeep",
        "!tests/fixtures/**",
    ]:
        assert pattern in gitignore


def test_validate_repo_file_safety_catches_large_file_outside_data(tmp_path):
    large_file = tmp_path / "large-output.txt"
    with large_file.open("wb") as handle:
        handle.seek((6 * 1024 * 1024) - 1)
        handle.write(b"0")

    issues = validate_repo_file_safety(tmp_path)

    assert any(issue.path == "large-output.txt" and issue.reason == "file_too_large" for issue in issues)


def test_validate_repo_file_safety_catches_blocked_extension_outside_data(tmp_path):
    blocked_file = tmp_path / "unsafe.gpkg"
    blocked_file.write_text("tiny but unsafe location", encoding="utf-8")

    issues = validate_repo_file_safety(tmp_path)

    assert any(issue.path == "unsafe.gpkg" and issue.reason == "blocked_extension" for issue in issues)


def test_validate_repo_file_safety_allows_tiny_test_fixtures(tmp_path):
    fixture_dir = tmp_path / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture = fixture_dir / "sample.geojson"
    fixture.write_text("{}", encoding="utf-8")

    issues = validate_repo_file_safety(tmp_path)

    assert issues == []


def test_validate_repo_file_safety_allows_gitkeep_files_in_data(tmp_path):
    ensure_storage_dirs(tmp_path)

    issues = validate_repo_file_safety(tmp_path)

    assert issues == []
