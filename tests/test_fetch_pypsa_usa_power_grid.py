from __future__ import annotations

import pytest

from scripts import fetch_pypsa_usa_power_grid as pypsa_usa


def test_parse_wkt_linestring_valid() -> None:
    coords = pypsa_usa.parse_wkt_linestring("'LINESTRING (-75 40, -74.5 40.5)'")
    assert coords == [[-75.0, 40.0], [-74.5, 40.5]]


def test_parse_wkt_linestring_rejects_invalid_coordinate() -> None:
    assert pypsa_usa.parse_wkt_linestring("LINESTRING (-190 40, -74.5 40.5)") is None


def test_read_csv_rows_handles_quoted_geometry(tmp_path) -> None:
    path = tmp_path / "lines.csv"
    path.write_text(
        'line_id,voltage,circuits,length,geometry\n'
        'L1,345,2,100,"LINESTRING (-75 40, -74 41)"\n',
        encoding="utf-8",
    )

    rows = pypsa_usa.read_csv_rows(path)

    assert len(rows) == 1
    assert rows[0]["line_id"] == "L1"
    assert rows[0]["geometry"] == "LINESTRING (-75 40, -74 41)"


def test_read_csv_rows_repairs_unquoted_last_geometry(tmp_path) -> None:
    path = tmp_path / "lines.csv"
    path.write_text(
        "line_id,voltage,circuits,length,geometry\n"
        "L1,345,2,100,LINESTRING (-75 40, -74 41)\n",
        encoding="utf-8",
    )

    rows = pypsa_usa.read_csv_rows(path)

    assert len(rows) == 1
    assert rows[0]["geometry"] == "LINESTRING (-75 40, -74 41)"


def test_convert_lines_builds_power_line_features(tmp_path) -> None:
    path = tmp_path / "lines.csv"
    path.write_text(
        "line_id,voltage,circuits,s_nom,length,type,geometry\n"
        "L1,345,2,900,100000,ACSR,LINESTRING (-75 40, -74 41)\n",
        encoding="utf-8",
    )

    features = pypsa_usa.convert_lines(path)

    assert len(features) == 1
    feature = features[0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["properties"]["kind"] == "power_line"
    assert feature["properties"]["id"] == "pypsa-usa/L1"
    assert feature["properties"]["voltage"] == 345
    assert feature["properties"]["circuits"] == 2
    assert feature["properties"]["length_km"] == 100
    assert feature["properties"]["s_nom_mva"] == 900


def test_convert_buses_builds_substation_features(tmp_path) -> None:
    path = tmp_path / "buses.csv"
    path.write_text(
        "bus_id,x,y,voltage,dc,symbol,under_construction\n"
        "B1,-75,40,345,f,Substation,f\n",
        encoding="utf-8",
    )

    features = pypsa_usa.convert_buses(path)

    assert len(features) == 1
    feature = features[0]
    assert feature["geometry"]["type"] == "Point"
    assert feature["properties"]["kind"] == "substation"
    assert feature["properties"]["id"] == "pypsa-usa/B1"
    assert feature["properties"]["voltage"] == 345
    assert feature["properties"]["country"] == "US"


def test_download_release_assets_reports_missing_assets(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        pypsa_usa,
        "load_json_url",
        lambda _url: {"tag_name": "v-test", "assets": []},
    )

    with pytest.raises(RuntimeError, match="has no downloadable CSV assets"):
        pypsa_usa.download_release_assets("latest", tmp_path)
