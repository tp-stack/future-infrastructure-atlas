"""Test atlas_core.json generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def atlas_core_path() -> Path:
    """Path to atlas_core.json."""
    return Path(__file__).parent.parent / "frontend" / "public" / "data" / "atlas_core.json"


@pytest.fixture
def atlas_core_data(atlas_core_path: Path) -> dict:
    """Load atlas_core.json if it exists."""
    if not atlas_core_path.exists():
        pytest.skip(f"atlas_core.json not found at {atlas_core_path}")
    with open(atlas_core_path, encoding="utf-8") as f:
        return json.load(f)


class TestAtlasCoreStructure:
    def test_atlas_core_exists(self, atlas_core_path: Path) -> None:
        """atlas_core.json file exists."""
        assert atlas_core_path.exists(), f"atlas_core.json not found at {atlas_core_path}"

    def test_atlas_core_valid_json(self, atlas_core_data: dict) -> None:
        """atlas_core.json is valid JSON and parses successfully."""
        assert isinstance(atlas_core_data, dict)

    def test_atlas_core_file_size(self, atlas_core_path: Path) -> None:
        """atlas_core.json file size is reasonable (< 500 KB)."""
        size_kb = atlas_core_path.stat().st_size / 1024
        assert size_kb < 500, f"File size {size_kb:.1f} KB exceeds 500 KB limit"

    def test_atlas_core_required_keys(self, atlas_core_data: dict) -> None:
        """atlas_core.json contains required top-level keys."""
        required = ["generated_at", "counts", "sources", "disclaimer", "tile_registry"]
        for key in required:
            assert key in atlas_core_data, f"Missing required key: {key}"

    def test_atlas_core_counts_structure(self, atlas_core_data: dict) -> None:
        """Counts section has expected fields."""
        counts = atlas_core_data.get("counts", {})
        expected_count_keys = [
            "power_plants_total",
            "power_plants_mapped",
            "submarine_cables_total",
            "submarine_cables_mapped",
            "data_centers_total",
            "data_centers_mapped",
        ]
        for key in expected_count_keys:
            assert key in counts, f"Counts missing {key}"

    def test_atlas_core_tile_registry(self, atlas_core_data: dict) -> None:
        """tile_registry has entries for all three tile types."""
        registry = atlas_core_data.get("tile_registry", {})
        expected_tiles = ["power_plants", "submarine_cables", "data_centers"]
        for tile_key in expected_tiles:
            assert tile_key in registry, f"tile_registry missing {tile_key}"
            entry = registry[tile_key]
            assert "url" in entry, f"tile_registry[{tile_key}] missing 'url'"
            assert "status" in entry, f"tile_registry[{tile_key}] missing 'status'"
            assert "layer_name" in entry, f"tile_registry[{tile_key}] missing 'layer_name'"

    def test_atlas_core_tile_urls_format(self, atlas_core_data: dict) -> None:
        """Tile URLs have correct format."""
        registry = atlas_core_data.get("tile_registry", {})
        for tile_key, entry in registry.items():
            url = entry.get("url", "")
            deployment_mode = entry.get("deployment_mode")
            if deployment_mode in {"remote_required", "invalid_remote", "missing"}:
                assert url == "", f"{tile_key} should not advertise an unavailable tile URL: {url}"
                continue
            if url.startswith("pmtiles://"):
                assert url.endswith(".pmtiles"), f"PMTiles URL should end with .pmtiles: {url}"
                continue
            assert url.startswith("/tiles/"), f"URL should start with /tiles/: {url}"
            assert url.endswith(".pmtiles"), f"URL should end with .pmtiles: {url}"

    def test_atlas_core_no_heavy_arrays(self, atlas_core_data: dict) -> None:
        """atlas_core.json does not contain heavy coordinate arrays."""
        heavy_keys = ["power_plants", "cables", "data_centers", "geometry"]
        for key in heavy_keys:
            assert key not in atlas_core_data, (
                f"atlas_core.json should not contain heavy key '{key}' "
                "(coordinates should be in PMTiles only)"
            )

    def test_atlas_core_license_warnings(self, atlas_core_data: dict) -> None:
        """License warnings section exists and is properly structured."""
        warnings = atlas_core_data.get("license_warnings", [])
        assert isinstance(warnings, list)
        for warning in warnings:
            assert "layer" in warning
            assert "message" in warning
            assert "active" in warning

    def test_atlas_core_data_gaps(self, atlas_core_data: dict) -> None:
        """Data gaps section exists with explanation."""
        gaps = atlas_core_data.get("data_gaps", {})
        assert "cables_unmapped" in gaps
        assert "data_centers_unmapped" in gaps
        assert "note" in gaps

    def test_atlas_core_generated_at_format(self, atlas_core_data: dict) -> None:
        """generated_at is in ISO format."""
        generated_at = atlas_core_data.get("generated_at", "")
        # Should be ISO 8601 format with Z suffix
        assert generated_at.endswith("Z"), "generated_at should end with 'Z'"
        assert "T" in generated_at, "generated_at should contain 'T' (ISO format)"

    def test_atlas_core_architecture_field(self, atlas_core_data: dict) -> None:
        """Architecture field correctly identifies PMTiles approach."""
        architecture = atlas_core_data.get("architecture", "")
        assert "PMTiles" in architecture, "Should mention PMTiles in architecture"


class TestTileRegistry:
    def test_tile_registry_power_plants(self, atlas_core_data: dict) -> None:
        """Power plants tile registry entry is correct."""
        registry = atlas_core_data.get("tile_registry", {})
        pp = registry.get("power_plants", {})
        assert pp.get("url") == "/tiles/power_plants.pmtiles"
        assert pp.get("layer_name") == "power_plants"

    def test_tile_registry_submarine_cables(self, atlas_core_data: dict) -> None:
        """Submarine cables tile registry entry is correct."""
        registry = atlas_core_data.get("tile_registry", {})
        cables = registry.get("submarine_cables", {})
        assert cables.get("url") == "/tiles/submarine_cables.pmtiles"
        assert cables.get("layer_name") == "submarine_cables"

    def test_tile_registry_data_centers(self, atlas_core_data: dict) -> None:
        """Data centers tile registry entry is correct."""
        registry = atlas_core_data.get("tile_registry", {})
        dcs = registry.get("data_centers", {})
        assert dcs.get("url") == "/tiles/data_centers.pmtiles"
        assert dcs.get("layer_name") == "data_centers"


class TestCountsValidation:
    def test_counts_are_non_negative(self, atlas_core_data: dict) -> None:
        """All counts are non-negative integers."""
        counts = atlas_core_data.get("counts", {})
        for key, value in counts.items():
            if isinstance(value, (int, float)):
                assert value >= 0, f"Count {key} is negative: {value}"

    def test_counts_mapped_less_than_total(self, atlas_core_data: dict) -> None:
        """Mapped counts should not exceed total counts."""
        counts = atlas_core_data.get("counts", {})
        
        pp_mapped = counts.get("power_plants_mapped", 0)
        pp_total = counts.get("power_plants_total", 0)
        if pp_total > 0:
            assert pp_mapped <= pp_total, (
                f"Power plants mapped ({pp_mapped}) > total ({pp_total})"
            )
        
        cables_mapped = counts.get("submarine_cables_mapped", 0)
        cables_total = counts.get("submarine_cables_total", 0)
        if cables_total > 0:
            assert cables_mapped <= cables_total, (
                f"Cables mapped ({cables_mapped}) > total ({cables_total})"
            )
        
        dcs_mapped = counts.get("data_centers_mapped", 0)
        dcs_total = counts.get("data_centers_total", 0)
        if dcs_total > 0:
            assert dcs_mapped <= dcs_total, (
                f"Data centers mapped ({dcs_mapped}) > total ({dcs_total})"
            )
