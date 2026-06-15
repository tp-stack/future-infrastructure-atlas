"""Load materialized Future Dataset Engine tables from the active app schema."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import sql

from atlas import settings
from atlas.db import fetch_all, fetch_one, get_connection

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_RESERVED_TABLES = {
    "api_customer",
    "api_export_job",
    "api_key",
    "api_plan",
    "api_usage_event",
    "asset_relationship",
    "data_rights_grant",
    "dataset_manifest",
    "dim_country",
    "dim_dataset",
    "dim_operator",
    "dim_source",
    "energy_asset",
    "infra_asset",
    "ingestion_log",
    "region_score",
    "resource_asset",
    "telecom_asset",
}


def validate_table_name(table_name: str) -> str:
    """Validate and return a safe table identifier."""

    if not _IDENTIFIER_RE.fullmatch(table_name):
        raise ValueError(f"Unsafe table name: {table_name}")
    return table_name


def _schema() -> str:
    return settings.database_schema


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in row.items()}


def list_fde_tables(include_atlas_system_tables: bool = False) -> list[dict[str, Any]]:
    """List materialized tables in the active FDE app schema."""

    rows = fetch_all(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (_schema(),),
    )
    tables: list[dict[str, Any]] = []
    for row in rows:
        table_name = row["table_name"]
        if not include_atlas_system_tables and table_name in _RESERVED_TABLES:
            continue
        tables.append(
            {
                "table_name": table_name,
                "row_count": count_fde_table_rows(table_name),
            }
        )
    return tables


def count_fde_table_rows(table_name: str) -> int:
    """Return the row count for a validated FDE table."""

    table_name = validate_table_name(table_name)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT COUNT(*) AS count FROM {}").format(sql.Identifier(table_name))
            )
            row = cursor.fetchone()
            return int(row["count"]) if row else 0


def inspect_fde_table(table_name: str) -> list[dict[str, Any]]:
    """Return ordered column metadata for a table in the active schema."""

    table_name = validate_table_name(table_name)
    return fetch_all(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (_schema(), table_name),
    )


def preview_fde_table(table_name: str, limit: int = 25) -> dict[str, Any]:
    """Return table metadata plus sample rows."""

    table_name = validate_table_name(table_name)
    safe_limit = max(1, min(int(limit), 100))
    columns = inspect_fde_table(table_name)
    if not columns:
        raise ValueError(f"FDE table not found in schema {_schema()}: {table_name}")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(table_name)),
                (safe_limit,),
            )
            rows = [_jsonable_row(dict(row)) for row in cursor.fetchall()]

    return {
        "table_name": table_name,
        "schema": _schema(),
        "row_count": count_fde_table_rows(table_name),
        "columns": columns,
        "sample_rows": rows,
    }


def load_fde_table(table_name: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Load rows from a validated FDE table."""

    table_name = validate_table_name(table_name)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if limit is None:
                cursor.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name)))
            else:
                safe_limit = max(1, int(limit))
                cursor.execute(
                    sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(table_name)),
                    (safe_limit,),
                )
            return [_jsonable_row(dict(row)) for row in cursor.fetchall()]


def configured_table_status() -> dict[str, dict[str, Any]]:
    """Return status for configured FDE table names."""

    configured = {
        "primary": settings.atlas_fde_primary_table,
        "data_centers": settings.atlas_fde_data_centers_table,
        "power_plants": settings.atlas_fde_power_plants_table,
        "cable_landing_points": settings.atlas_fde_cable_landing_points_table,
        "energy_sites": settings.atlas_fde_energy_sites_table,
        "cables": settings.atlas_fde_cables_table,
    }
    status: dict[str, dict[str, Any]] = {}
    available = {entry["table_name"]: entry for entry in list_fde_tables(include_atlas_system_tables=True)}
    for key, table_name in configured.items():
        if not table_name:
            status[key] = {"configured": False, "table_name": None, "exists": False}
            continue
        validate_table_name(table_name)
        status[key] = {
            "configured": True,
            "table_name": table_name,
            "exists": table_name in available,
            "row_count": available.get(table_name, {}).get("row_count", 0),
        }
    return status
