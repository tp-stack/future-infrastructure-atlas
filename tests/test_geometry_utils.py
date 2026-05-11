from __future__ import annotations

from atlas.ingestion.geometry_utils import (
    geometry_bounds,
    normalize_linestring_geometry,
    normalize_multilinestring_geometry,
    parse_lat,
    parse_lon,
    safe_slug_key,
    valid_line_geometry,
    valid_lon_lat,
)


class TestParseLon:
    def test_accepts_valid(self):
        assert parse_lon(0) == 0.0
        assert parse_lon(180) == 180.0
        assert parse_lon(-180) == -180.0
        assert parse_lon("45.5") == 45.5

    def test_rejects_out_of_range(self):
        assert parse_lon(181) is None
        assert parse_lon(-181) is None

    def test_rejects_none(self):
        assert parse_lon(None) is None

    def test_rejects_non_numeric(self):
        assert parse_lon("abc") is None


class TestParseLat:
    def test_accepts_valid(self):
        assert parse_lat(0) == 0.0
        assert parse_lat(90) == 90.0
        assert parse_lat(-90) == -90.0
        assert parse_lat("33.86") == 33.86

    def test_rejects_out_of_range(self):
        assert parse_lat(91) is None
        assert parse_lat(-91) is None

    def test_rejects_none(self):
        assert parse_lat(None) is None

    def test_rejects_non_numeric(self):
        assert parse_lat("xyz") is None


class TestValidLonLat:
    def test_accepts_valid(self):
        assert valid_lon_lat(0, 0) is True
        assert valid_lon_lat(180, 90) is True
        assert valid_lon_lat(-180, -90) is True

    def test_rejects_out_of_range(self):
        assert valid_lon_lat(181, 0) is False
        assert valid_lon_lat(0, 91) is False

    def test_rejects_none(self):
        assert valid_lon_lat(None, 0) is False

    def test_rejects_non_numeric(self):
        assert valid_lon_lat("a", 0) is False


class TestValidLineGeometry:
    def test_accepts_valid(self):
        coords = [[0, 0], [1, 1], [2, 2]]
        assert valid_line_geometry(coords) is True

    def test_rejects_empty(self):
        assert valid_line_geometry([]) is False

    def test_rejects_single_point(self):
        assert valid_line_geometry([[0, 0]]) is False

    def test_rejects_bad_coords(self):
        assert valid_line_geometry([[200, 0], [1, 1]]) is False

    def test_rejects_malformed(self):
        assert valid_line_geometry([[0], [1, 1]]) is False


class TestNormalizeLinestringGeometry:
    def test_accepts_valid(self):
        geom = {"type": "LineString", "coordinates": [[0.1234567, 1.2345678], [2.0, 3.0]]}
        result = normalize_linestring_geometry(geom)
        assert result is not None
        assert result[0] == [0.123457, 1.234568]
        assert result[1] == [2.0, 3.0]

    def test_rejects_wrong_type(self):
        assert normalize_linestring_geometry({"type": "Point", "coordinates": [0, 0]}) is None

    def test_rejects_invalid_coords(self):
        geom = {"type": "LineString", "coordinates": [[200, 0], [1, 1]]}
        assert normalize_linestring_geometry(geom) is None


class TestNormalizeMultilinestringGeometry:
    def test_accepts_valid(self):
        geom = {
            "type": "MultiLineString",
            "coordinates": [
                [[0, 0], [1, 1]],
                [[2, 2], [3, 3]],
            ],
        }
        result = normalize_multilinestring_geometry(geom)
        assert result is not None
        assert len(result) == 4

    def test_rejects_wrong_type(self):
        assert normalize_multilinestring_geometry({"type": "LineString", "coordinates": [[0, 0], [1, 1]]}) is None

    def test_rejects_all_invalid_lines(self):
        geom = {
            "type": "MultiLineString",
            "coordinates": [
                [[200, 0], [201, 1]],
            ],
        }
        assert normalize_multilinestring_geometry(geom) is None

    def test_filters_invalid_lines_in_mixed(self):
        geom = {
            "type": "MultiLineString",
            "coordinates": [
                [[200, 0], [201, 1]],
                [[0, 0], [1, 1]],
            ],
        }
        result = normalize_multilinestring_geometry(geom)
        assert result is not None
        assert len(result) == 2
        assert result[0] == [0.0, 0.0]


class TestGeometryBounds:
    def test_returns_bounds(self):
        geom = [[-10, -5], [0, 0], [10, 5]]
        result = geometry_bounds(geom)
        assert result == (-10.0, -5.0, 10.0, 5.0)

    def test_rejects_too_short(self):
        assert geometry_bounds([[0, 0]]) is None

    def test_rejects_empty(self):
        assert geometry_bounds([]) is None


class TestSafeSlugKey:
    def test_normalizes(self):
        assert safe_slug_key("Cable Alpha") == "cable_alpha"
        assert safe_slug_key("2Africa/South") == "2africa_south"
        assert safe_slug_key(" name-with-dashes ") == "name_with_dashes"
