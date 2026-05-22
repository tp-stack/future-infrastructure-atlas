from __future__ import annotations

import json

from scripts import fetch_openinframap_power_extract as oim


def test_parse_openinframap_url() -> None:
    zoom, lat, lon = oim.parse_openinframap_url("https://openinframap.org/#5.83/46.28/17.082")
    assert zoom == 5.83
    assert lat == 46.28
    assert lon == 17.082


def test_bbox_from_view_contains_center() -> None:
    min_lat, min_lon, max_lat, max_lon = oim.bbox_from_view(5.83, 46.28, 17.082)
    assert min_lat < 46.28 < max_lat
    assert min_lon < 17.082 < max_lon


def test_process_elements_writes_power_lines_and_substations(tmp_path) -> None:
    data = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "tags": {"power": "cable", "voltage": "110000", "cables": "3", "name": "Cable A"},
                "geometry": [{"lon": 10, "lat": 45}, {"lon": 11, "lat": 46}],
            },
            {
                "type": "node",
                "id": 2,
                "lat": 45.5,
                "lon": 10.5,
                "tags": {"power": "substation", "voltage": "110000", "name": "Sub A"},
            },
            {
                "type": "relation",
                "id": 3,
                "center": {"lat": 45.8, "lon": 10.8},
                "tags": {"power": "substation", "voltage": "220000"},
            },
        ]
    }
    line_out = tmp_path / "lines.ndjson"
    sub_out = tmp_path / "subs.ndjson"

    stats = oim.process_elements(data, line_out, sub_out, "test")

    lines = [json.loads(line) for line in line_out.read_text(encoding="utf-8").splitlines()]
    subs = [json.loads(line) for line in sub_out.read_text(encoding="utf-8").splitlines()]
    assert stats["power_lines"] == 1
    assert stats["substations"] == 2
    assert lines[0]["properties"]["power"] == "cable"
    assert lines[0]["properties"]["underground"] is True
    assert subs[0]["properties"]["voltage"] == 110
