from __future__ import annotations

import io
import json

from scripts import fetch_osm_global_power_grid as osm_grid


def test_parse_voltage_kv_handles_osm_voltage_forms() -> None:
    assert osm_grid.parse_voltage_kv("110000") == 110
    assert osm_grid.parse_voltage_kv("220000;400000") == 400
    assert osm_grid.parse_voltage_kv("33/66") == 66
    assert osm_grid.parse_voltage_kv("10 kV") == 10
    assert osm_grid.parse_voltage_kv("") == 0
    assert osm_grid.parse_voltage_kv("unknown") == 0


def test_normalize_line_feature_handles_linestring() -> None:
    feature = osm_grid.normalize_line_feature(
        123,
        {"power": "line", "voltage": "345000", "circuits": "2", "cables": "6", "name": "Test line"},
        [[-75, 40], [-74, 41]],
        "test-region",
    )

    assert feature is not None
    assert feature["geometry"]["type"] == "LineString"
    assert feature["properties"]["id"] == "osm-123"
    assert feature["properties"]["voltage"] == 345
    assert feature["properties"]["circuits"] == 2
    assert feature["properties"]["cables"] == 6
    assert feature["properties"]["region"] == "test-region"
    assert feature["properties"]["length_km"] > 0


def test_normalize_line_feature_handles_multisegment_paths() -> None:
    feature = osm_grid.normalize_line_feature(
        456,
        {"power": "cable", "voltage": "500000", "frequency": "0"},
        [[[-75, 40], [-74, 41]], [[-73, 42], [-72, 43]]],
        "test-region",
    )

    assert feature is not None
    assert feature["geometry"]["type"] == "MultiLineString"
    assert feature["properties"]["type"] == "HVDC"
    assert feature["properties"]["underground"] is True
    assert feature["properties"]["voltage"] == 500


def test_normalize_substation_feature_validates_coordinates() -> None:
    assert osm_grid.normalize_substation_feature(1, {"power": "substation"}, -200, 40, "test", "node") is None

    feature = osm_grid.normalize_substation_feature(
        2,
        {"power": "substation", "voltage": "138000", "substation": "transmission"},
        -75,
        40,
        "test",
        "node",
    )
    assert feature is not None
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["id"] == "osm-node-2"
    assert feature["properties"]["voltage"] == 138
    assert feature["properties"]["symbol"] == "transmission"


def test_append_existing_europe_dedupes_ids(tmp_path, monkeypatch) -> None:
    europe_cache = tmp_path / "europe"
    frontend_data = tmp_path / "frontend"
    europe_cache.mkdir()
    frontend_data.mkdir()

    line = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        "properties": {"id": "osm-1", "voltage": 110, "length_km": 10, "power": "line"},
    }
    (europe_cache / "power_lines.ndjson").write_text(
        json.dumps(line) + "\n" + json.dumps(line) + "\n",
        encoding="utf-8",
    )

    substation = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10, 45]},
        "properties": {"id": "s1", "voltage": 220},
    }
    (frontend_data / "substations.json").write_text(
        json.dumps({"type": "FeatureCollection", "features": [substation, substation]}),
        encoding="utf-8",
    )

    monkeypatch.setattr(osm_grid, "EUROPE_CACHE", europe_cache)
    monkeypatch.setattr(osm_grid, "FRONTEND_DATA", frontend_data)

    line_out = io.StringIO()
    substation_out = io.StringIO()
    stats = osm_grid.make_stats()
    osm_grid.append_existing_europe(line_out, substation_out, set(), set(), stats, frontend_data)

    assert len([line for line in line_out.getvalue().splitlines() if line]) == 1
    assert len([line for line in substation_out.getvalue().splitlines() if line]) == 1
    assert stats["power_lines"] == 1
    assert stats["substations"] == 1
