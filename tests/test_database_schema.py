from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_SQL = PROJECT_ROOT / "database" / "migrations" / "001_initial_schema.sql"
DATASET_MIGRATION_SQL = PROJECT_ROOT / "database" / "migrations" / "002_dataset_registry.sql"
DATASET_SEED_SQL = PROJECT_ROOT / "database" / "seeds" / "002_seed_datasets.sql"


def _sql() -> str:
    return MIGRATION_SQL.read_text(encoding="utf-8").lower()


def _dataset_sql() -> str:
    return DATASET_MIGRATION_SQL.read_text(encoding="utf-8").lower()


def _dataset_seed_sql() -> str:
    return DATASET_SEED_SQL.read_text(encoding="utf-8").lower()


def test_migration_sql_file_exists():
    assert MIGRATION_SQL.is_file()


def test_required_table_names_are_present():
    sql = _sql()

    for table_name in [
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
    ]:
        assert f"create table if not exists {table_name}" in sql


def test_required_indexes_are_present():
    sql = _sql()

    for index_name in [
        "idx_infra_asset_geom",
        "idx_infra_asset_type_subtype",
        "idx_infra_asset_country_iso2",
        "idx_infra_asset_source_id",
        "idx_infra_asset_confidence",
        "idx_region_score_geom",
        "idx_region_score_final_score_desc",
        "idx_region_score_region_id",
        "idx_region_score_model_version",
        "idx_asset_relationship_from_asset_id",
        "idx_asset_relationship_to_asset_id",
        "idx_asset_relationship_type",
    ]:
        assert index_name in sql


def test_postgis_extension_is_enabled():
    sql = _sql()

    assert "create extension if not exists postgis" in sql
    assert "create extension if not exists pgcrypto" in sql


def test_infra_asset_required_columns_are_present():
    sql = _sql()
    infra_asset_sql = sql.split("create table if not exists infra_asset", maxsplit=1)[1]
    infra_asset_sql = infra_asset_sql.split("create index", maxsplit=1)[0]

    for column_name in ["confidence", "sensitivity_level", "geometry_precision", "source_id", "geom"]:
        assert column_name in infra_asset_sql


def test_region_score_required_columns_are_present():
    sql = _sql()
    region_score_sql = sql.split("create table if not exists region_score", maxsplit=1)[1]
    region_score_sql = region_score_sql.split("create index", maxsplit=1)[0]

    assert "final_score" in region_score_sql
    assert "geom" in region_score_sql


def test_ingestion_log_required_columns_are_present():
    sql = _sql()
    ingestion_log_sql = sql.split("create table if not exists ingestion_log", maxsplit=1)[1]
    ingestion_log_sql = ingestion_log_sql.split("create table if not exists asset_relationship", maxsplit=1)[0]

    assert "file_sha256" in ingestion_log_sql
    assert "status" in ingestion_log_sql


def test_dataset_registry_migration_sql_file_exists():
    assert DATASET_MIGRATION_SQL.is_file()


def test_dataset_registry_tables_are_present():
    sql = _dataset_sql()

    assert "create table if not exists dim_dataset" in sql
    assert "create table if not exists dataset_manifest" in sql


def test_dataset_registry_constraints_are_present():
    sql = _dataset_sql()

    assert "dim_dataset_ingestion_status_check" in sql
    assert "dataset_manifest_manifest_type_check" in sql
    assert "'raw', 'ingestion', 'processed'" in sql
    assert "'not_started'" in sql
    assert "'deprecated'" in sql


def test_dataset_seed_sql_exists_and_uses_on_conflict():
    assert DATASET_SEED_SQL.is_file()
    sql = _dataset_seed_sql()

    assert "insert into dim_dataset" in sql
    assert "on conflict (dataset_key) do update" in sql
