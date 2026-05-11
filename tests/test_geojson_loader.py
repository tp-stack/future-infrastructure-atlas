from __future__ import annotations

from pathlib import Path

from atlas.ingestion.geojson_loader import (
    load_geojson_features,
    normalize_features,
    normalize_line_feature,
    normalize_point_feature,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"


class TestLoadGeojsonFeatures:
    def test_loads_feature_collection(self):
        path = FIXTURES / "sample_submarine_cables.geojson"
        features = load_geojson_features(path)
        assert len(features) == 6

    def test_loads_single_feature(self, tmp_path):
        p = tmp_path / "single.geojson"
        p.write_text('{"type": "Feature", "properties": {"name": "test"}, "geometry": {"type": "Point", "coordinates": [0, 0]}}', encoding="utf-8")
        features = load_geojson_features(p)
        assert len(features) == 1

    def test_returns_empty_on_invalid_type(self, tmp_path):
        p = tmp_path / "invalid.geojson"
        p.write_text('{"type": "GeometryCollection", "geometries": []}', encoding="utf-8")
        features = load_geojson_features(p)
        assert features == []

    def test_returns_empty_on_missing_file(self, tmp_path):
        features = load_geojson_features(tmp_path / "nonexistent.geojson")
        assert features == []


class TestNormalizePointFeature:
    def test_accepts_valid(self):
        feature = {
            "type": "Feature",
            "properties": {"name": "Test DC", "operator": "OpCo"},
            "geometry": {"type": "Point", "coordinates": [-77.5, 39.0]},
        }
        result = normalize_point_feature(feature)
        assert result is not None
        assert result["type"] == "Point"
        assert result["coordinates"] == [-77.5, 39.0]
        assert result["properties"]["name"] == "Test DC"

    def test_rejects_missing_geometry(self):
        feature = {"type": "Feature", "properties": {}}
        assert normalize_point_feature(feature) is None

    def test_rejects_wrong_geometry_type(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        }
        assert normalize_point_feature(feature) is None

    def test_rejects_bad_coords(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": [200, 45]},
        }
        assert normalize_point_feature(feature) is None


class TestNormalizeLineFeature:
    def test_accepts_linestring(self):
        feature = {
            "type": "Feature",
            "properties": {"name": "Cable A"},
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        }
        result = normalize_line_feature(feature)
        assert result is not None
        assert result["type"] == "LineString"
        assert len(result["coordinates"]) == 2
        assert result["coordinates"][0] == [0.0, 0.0]

    def test_accepts_multilinestring(self):
        feature = {
            "type": "Feature",
            "properties": {"name": "Cable B"},
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [[0, 0], [1, 1]],
                    [[2, 2], [3, 3]],
                ],
            },
        }
        result = normalize_line_feature(feature)
        assert result is not None
        assert result["type"] == "LineString"
        assert len(result["coordinates"]) == 4

    def test_rejects_missing_geometry(self):
        feature = {"type": "Feature", "properties": {}}
        assert normalize_line_feature(feature) is None

    def test_rejects_invalid_geom_type(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": [0, 0]},
        }
        assert normalize_line_feature(feature) is None

    def test_rejects_bad_coords(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[200, 0], [1, 1]]},
        }
        assert normalize_line_feature(feature) is None


class TestNormalizeFeatures:
    def test_normalize_point_features(self):
        features = [
            {"type": "Feature", "properties": {"name": "A"}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
            {"type": "Feature", "properties": {"name": "B"}, "geometry": {"type": "Point", "coordinates": [200, 0]}},
        ]
        result = normalize_features(features, expected_geom="Point")
        assert len(result) == 1

    def test_normalize_line_features(self):
        features = [
            {"type": "Feature", "properties": {"name": "A"}, "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
            {"type": "Feature", "properties": {"name": "B"}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
        ]
        result = normalize_features(features, expected_geom="LineString")
        assert len(result) == 1

    def test_auto_detect(self):
        features = [
            {"type": "Feature", "properties": {"name": "P"}, "geometry": {"type": "Point", "coordinates": [0, 0]}},
            {"type": "Feature", "properties": {"name": "L"}, "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
        ]
        result = normalize_features(features, expected_geom="auto")
        assert len(result) == 2
