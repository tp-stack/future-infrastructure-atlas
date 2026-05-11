from __future__ import annotations

from pathlib import Path

from atlas.ingestion.cable_loader import (
    _get_cable_name,
    has_license_restriction,
    load_cables_from_geojson,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


class TestGetCableName:
    def test_from_name_field(self):
        assert _get_cable_name({"name": "Cable A"}) == "Cable A"

    def test_from_cable_name_field(self):
        assert _get_cable_name({"cable_name": "Cable B"}) == "Cable B"

    def test_from_cable_system_name_field(self):
        assert _get_cable_name({"cable_system_name": "Cable C"}) == "Cable C"

    def test_from_title_field(self):
        assert _get_cable_name({"title": "Cable D"}) == "Cable D"

    def test_returns_empty_when_none(self):
        assert _get_cable_name({}) == ""
        assert _get_cable_name({"name": ""}) == ""
        assert _get_cable_name({"name": "  "}) == ""


class TestHasLicenseRestriction:
    def test_restricted_default(self):
        assert has_license_restriction("telegeography_licensed_submarine_cables") is True
        assert has_license_restriction("emodnet_schematic_cables") is True

    def test_not_restricted_default(self):
        assert has_license_restriction("copernicus_telegeography_submarine_cables") is False

    def test_from_config(self):
        config = {
            "sources": [
                {"source_key": "my_source", "requires_license_review": True},
                {"source_key": "free_source", "requires_license_review": False},
            ],
        }
        assert has_license_restriction("my_source", config) is True
        assert has_license_restriction("free_source", config) is False

    def test_default_false_when_not_in_config(self):
        config = {"sources": [{"source_key": "other", "requires_license_review": True}]}
        assert has_license_restriction("unknown", config) is False


class TestLoadCablesFromGeojson:
    def test_loads_valid_cables(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        assert len(cables) == 2

    def test_cable_fields(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        alpha = next(c for c in cables if c["n"] == "Cable Alpha")
        assert alpha["source"] == "scn_data"
        assert len(alpha["geometry"]) == 3
        assert alpha["geometry_precision"] == "generalized_public_geometry"
        assert alpha["mapped_status"] == "mapped"

    def test_multilinestring_merged(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        beta = next(c for c in cables if c["n"] == "Cable Beta")
        assert len(beta["geometry"]) == 6

    def test_deduplicates_by_name(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        alpha_count = sum(1 for c in cables if c["n"] == "Cable Alpha")
        assert alpha_count == 1

    def test_skips_empty_name(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        names = [c["n"] for c in cables]
        assert "" not in names

    def test_skips_single_point_linestring(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        names = [c["n"] for c in cables]
        assert "Single Point Cable" not in names

    def test_skips_bad_coords(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        names = [c["n"] for c in cables]
        assert "Bad Coord Cable" not in names

    def test_returns_empty_on_missing_file(self, tmp_path):
        cables = load_cables_from_geojson(tmp_path / "nonexistent.geojson")
        assert cables == []

    def test_sets_source_from_props_fallback(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path)
        cables_no_explicit = [c for c in cables if not c.get("source")]
        assert len(cables_no_explicit) == 0

    def test_override_source_name(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path, source_name="custom_source")
        for c in cables:
            assert c["source"] == "custom_source"

    def test_override_geometry_precision(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path, geometry_precision="schematic")
        assert cables[0]["geometry_precision"] == "schematic"

    def test_override_source_license(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path, source_license="CC BY 4.0")
        assert cables[0]["source_license"] == "CC BY 4.0"

    def test_override_confidence(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        cables = load_cables_from_geojson(path, confidence=0.9)
        assert cables[0]["confidence"] == 0.9
