from __future__ import annotations

import pytest

from atlas.db import fetch_one, get_connection
from atlas.loaders.postgis import insert_infra_asset_minimal, postgis_available, table_exists


REQUIRED_TABLES = [
    "dim_source",
    "dim_country",
    "dim_operator",
    "infra_asset",
    "energy_asset",
    "telecom_asset",
    "resource_asset",
    "region_score",
    "ingestion_log",
    "asset_relationship",
    "dim_dataset",
    "dataset_manifest",
]


def _database_available() -> bool:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _database_available(), reason="PostGIS database is unavailable")


def test_postgis_available_when_database_is_running():
    assert postgis_available() is True


def test_required_tables_exist_when_database_is_initialized():
    missing = [table for table in REQUIRED_TABLES if not table_exists(table)]

    assert missing == []


def test_source_seed_rows_exist():
    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM dim_source
        WHERE source_key IN (
            'wri_global_power_plant_database',
            'peeringdb',
            'pch_ixp_directory',
            'osm_openinframap',
            'global_energy_monitor',
            'usgs_mineral_commodity_summaries',
            'wri_aqueduct',
            'hydrosheds',
            'world_bank_wgi',
            'cloud_provider_official_regions'
        )
        """
    )

    assert row["count"] == 10


def test_insert_infra_asset_minimal_creates_point_with_srid_4326():
    asset_id = insert_infra_asset_minimal(
        asset_type="test_asset",
        asset_subtype="test_point",
        canonical_name="Step 2 integration test asset",
        source_key="peeringdb",
        sensitivity_level="low",
        geometry_precision="exact_public",
        confidence=0.9,
        longitude=12.4924,
        latitude=41.8902,
        properties={"test_run": True},
    )

    row = fetch_one(
        """
        SELECT ST_SRID(geom) AS srid
        FROM infra_asset
        WHERE asset_id = %s
        """,
        (asset_id,),
    )

    assert row["srid"] == 4326
