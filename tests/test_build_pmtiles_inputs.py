"""Tests for PMTiles input generation (no tippecanoe required)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_pmtiles import (
    _generate_power_plants_ndjson,
    _generate_cables_ndjson,
    _generate_datacenters_ndjson,
    _generate_power_lines_ndjson,
    _generate_substations_ndjson,
    LAYERS,
)


def test_generate_power_plants_ndjson(tmp_path):
    data = {
        "power_plants": [
            {"n": "Plant A", "c": "US", "f": "Gas", "mw": 500, "lat": 40.0, "lon": -75.0},
            {"n": "Plant B", "c": "DE", "f": "Solar", "mw": 100, "lat": 51.0, "lon": 10.0},
        ],
    }
    out = tmp_path / "pp.ndjson"
    count = _generate_power_plants_ndjson(data, out)
    assert count == 2
    lines = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        feat = json.loads(line)
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert "n" in feat["properties"]
        assert "c" in feat["properties"]
        assert "f" in feat["properties"]
        assert "mw" in feat["properties"]


def test_generate_power_plants_skips_none_coords(tmp_path):
    data = {
        "power_plants": [
            {"n": "Plant A", "lat": None, "lon": None},
            {"n": "Plant B", "lat": 51.0, "lon": 10.0},
        ],
    }
    out = tmp_path / "pp.ndjson"
    count = _generate_power_plants_ndjson(data, out)
    assert count == 1


def test_generate_cables_ndjson(tmp_path):
    data = {
        "cables": [
            {"n": "Cable A", "mapped_status": "mapped", "geometry": [[0, 0], [1, 1], [2, 2]], "source": "test", "source_license": "", "geometry_precision": "", "confidence": 0.8},
            {"n": "Cable B", "mapped_status": "unmapped", "geometry": [[0, 0], [1, 1]]},
        ],
    }
    out = tmp_path / "cables.ndjson"
    count = _generate_cables_ndjson(data, out)
    assert count == 1  # only mapped
    feat = json.loads(out.read_text(encoding="utf-8").strip())
    assert feat["geometry"]["type"] == "LineString"


def test_generate_cables_multi_line(tmp_path):
    data = {
        "cables": [
            {
                "n": "Multi Cable",
                "mapped_status": "mapped",
                "geometry": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]],
                "source": "test", "source_license": "", "geometry_precision": "", "confidence": 0.5,
            },
        ],
    }
    out = tmp_path / "cables.ndjson"
    count = _generate_cables_ndjson(data, out)
    assert count == 1
    feat = json.loads(out.read_text(encoding="utf-8").strip())
    assert feat["geometry"]["type"] == "MultiLineString"


def test_generate_datacenters_ndjson(tmp_path):
    data = {
        "data_centers": [
            {"n": "DC A", "mapped_status": "mapped", "lat": 40.0, "lon": -75.0, "op": "OpCo", "c": "US", "city": "NYC", "coordinate_precision": "", "source_license": "", "confidence": 0.75},
            {"n": "DC B", "mapped_status": "unmapped", "lat": None, "lon": None},
        ],
    }
    out = tmp_path / "dcs.ndjson"
    count = _generate_datacenters_ndjson(data, out)
    assert count == 1
    feat = json.loads(out.read_text(encoding="utf-8").strip())
    assert feat["geometry"]["type"] == "Point"
    assert feat["properties"]["n"] == "DC A"


def test_generate_power_lines_ndjson(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    power_lines = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                "properties": {"id": "L1", "voltage": 400, "circuits": 2, "length_km": 10, "type": "AC"},
            },
        ],
    }
    (data_dir / "power_lines.json").write_text(json.dumps(power_lines), encoding="utf-8")
    monkeypatch.setattr("scripts.build_pmtiles.FRONTEND_DATA", data_dir)

    out = tmp_path / "power_lines.ndjson"
    count = _generate_power_lines_ndjson({}, out)
    assert count == 1
    feat = json.loads(out.read_text(encoding="utf-8").strip())
    assert feat["geometry"]["type"] == "LineString"
    assert feat["properties"]["voltage"] == 400
    assert feat["properties"]["circuits"] == 2


def test_generate_substations_ndjson(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    substations = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [10, 45]},
                "properties": {"id": "S1", "n": "S1", "voltage": 220, "country": "IT", "lat": 45, "lon": 10},
            },
        ],
    }
    (data_dir / "substations.json").write_text(json.dumps(substations), encoding="utf-8")
    monkeypatch.setattr("scripts.build_pmtiles.FRONTEND_DATA", data_dir)

    out = tmp_path / "substations.ndjson"
    count = _generate_substations_ndjson({}, out)
    assert count == 1
    feat = json.loads(out.read_text(encoding="utf-8").strip())
    assert feat["geometry"]["type"] == "Point"
    assert feat["properties"]["voltage"] == 220


def test_generate_substations_ndjson_uses_pmtiles_input(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    project_root = tmp_path / "project"
    cache_dir = project_root / "data" / "cache" / "osm_global_power_grid"
    data_dir.mkdir()
    cache_dir.mkdir(parents=True)
    source = cache_dir / "substations.ndjson"
    source.write_text(
        json.dumps({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [10, 45]},
            "properties": {"id": "osm-node-1", "voltage": 220},
        }) + "\n",
        encoding="utf-8",
    )
    substations = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {"pmtiles_input": "data/cache/osm_global_power_grid/substations.ndjson"},
    }
    (data_dir / "substations.json").write_text(json.dumps(substations), encoding="utf-8")
    monkeypatch.setattr("scripts.build_pmtiles.FRONTEND_DATA", data_dir)
    monkeypatch.setattr("scripts.build_pmtiles.PROJECT_ROOT", project_root)

    out = tmp_path / "substations.ndjson"
    count = _generate_substations_ndjson({}, out)

    assert count == 1
    assert out.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_layer_configs_have_required_keys():
    assert "power_lines" in LAYERS
    assert "substations" in LAYERS
    for key, cfg in LAYERS.items():
        assert "input_ndjson" in cfg
        assert "output_pmtiles" in cfg
        assert "layer_name" in cfg
        assert "description" in cfg
