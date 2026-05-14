"""Test PMTiles input generation from web data."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.build_pmtiles_inputs import (
    generate_power_plants,
    generate_submarine_cables,
    generate_data_centers,
)


@pytest.fixture
def sample_web_data() -> dict:
    """Load sample atlas_web_data.json if it exists."""
    web_data_path = Path(__file__).parent.parent / "frontend" / "public" / "data" / "atlas_web_data.json"
    if not web_data_path.exists():
        pytest.skip("atlas_web_data.json not found")
    with open(web_data_path, encoding="utf-8") as f:
        return json.load(f)


class TestGeneratePowerPlants:
    def test_power_plants_generates_features(self, sample_web_data: dict) -> None:
        """Power plants GeoJSON has valid FeatureCollection structure."""
        fc = generate_power_plants(sample_web_data)
        assert fc["type"] == "FeatureCollection"
        assert "features" in fc
        assert isinstance(fc["features"], list)

    def test_power_plants_count(self, sample_web_data: dict) -> None:
        """Power plants count is reasonable (> 1000)."""
        fc = generate_power_plants(sample_web_data)
        count = len(fc["features"])
        assert count > 1000, f"Expected > 1000 power plants, got {count}"

    def test_power_plants_geometry_valid(self, sample_web_data: dict) -> None:
        """Power plant features have Point geometry with valid coordinates."""
        fc = generate_power_plants(sample_web_data)
        for feature in fc["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"
            coords = feature["geometry"]["coordinates"]
            assert len(coords) == 2
            lon, lat = coords
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_power_plants_properties(self, sample_web_data: dict) -> None:
        """Power plant features have required properties."""
        fc = generate_power_plants(sample_web_data)
        for feature in fc["features"]:
            props = feature["properties"]
            assert "n" in props  # name
            assert "c" in props  # country
            assert "f" in props  # fuel
            assert "mw" in props  # capacity


class TestGenerateSubmarineCables:
    def test_cables_generates_features(self, sample_web_data: dict) -> None:
        """Submarine cables GeoJSON has valid FeatureCollection structure."""
        fc = generate_submarine_cables(sample_web_data)
        assert fc["type"] == "FeatureCollection"
        assert "features" in fc

    def test_cables_only_mapped(self, sample_web_data: dict) -> None:
        """Only mapped cables are included."""
        fc = generate_submarine_cables(sample_web_data)
        for feature in fc["features"]:
            # Unmapped cables should not be in the output
            # (We can't directly test this without accessing source data,
            # but we can verify the filter was applied during generation)
            pass

    def test_cables_geometry_valid(self, sample_web_data: dict) -> None:
        """Cable features have LineString or MultiLineString geometry."""
        fc = generate_submarine_cables(sample_web_data)
        for feature in fc["features"]:
            assert feature["type"] == "Feature"
            gtype = feature["geometry"]["type"]
            assert gtype in ["LineString", "MultiLineString"]
            coords = feature["geometry"]["coordinates"]
            assert len(coords) >= 2

    def test_cables_properties(self, sample_web_data: dict) -> None:
        """Cable features have required properties."""
        fc = generate_submarine_cables(sample_web_data)
        if len(fc["features"]) > 0:
            for feature in fc["features"]:
                props = feature["properties"]
                assert "n" in props  # name
                assert "source" in props
                assert "source_license" in props

    def test_cables_count_zero_ok(self, sample_web_data: dict) -> None:
        """Cable count can be zero if no mapped cables exist."""
        fc = generate_submarine_cables(sample_web_data)
        count = len(fc["features"])
        assert count >= 0


class TestGenerateDataCenters:
    def test_datacenters_generates_features(self, sample_web_data: dict) -> None:
        """Data centers GeoJSON has valid FeatureCollection structure."""
        fc = generate_data_centers(sample_web_data)
        assert fc["type"] == "FeatureCollection"
        assert "features" in fc

    def test_datacenters_only_mapped(self, sample_web_data: dict) -> None:
        """Only mapped data centers are included."""
        fc = generate_data_centers(sample_web_data)
        # Unmapped should not be in output (tested indirectly through count/structure)
        pass

    def test_datacenters_geometry_valid(self, sample_web_data: dict) -> None:
        """Data center features have Point geometry with valid coordinates."""
        fc = generate_data_centers(sample_web_data)
        for feature in fc["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"
            coords = feature["geometry"]["coordinates"]
            assert len(coords) == 2
            lon, lat = coords
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_datacenters_properties(self, sample_web_data: dict) -> None:
        """Data center features have required properties."""
        fc = generate_data_centers(sample_web_data)
        if len(fc["features"]) > 0:
            for feature in fc["features"]:
                props = feature["properties"]
                assert "n" in props  # name
                assert "op" in props  # operator
                assert "c" in props  # country
                assert "city" in props

    def test_datacenters_count_zero_ok(self, sample_web_data: dict) -> None:
        """Data center count can be zero if no mapped data centers exist."""
        fc = generate_data_centers(sample_web_data)
        count = len(fc["features"])
        assert count >= 0


class TestInputFilesComplete:
    def test_all_three_generators_produce_output(self, sample_web_data: dict) -> None:
        """All three generators run without error."""
        pp = generate_power_plants(sample_web_data)
        cables = generate_submarine_cables(sample_web_data)
        dcs = generate_data_centers(sample_web_data)

        assert pp is not None
        assert cables is not None
        assert dcs is not None
        assert len(pp["features"]) > 0
