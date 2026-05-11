"""Lightweight PostGIS loader helpers."""

from __future__ import annotations

import json
from typing import Any

from atlas.db import fetch_all, fetch_one


def table_exists(table_name: str) -> bool:
    """Return true when a public table exists."""

    row = fetch_one(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        ) AS exists
        """,
        (table_name,),
    )
    return bool(row and row["exists"])


def postgis_available() -> bool:
    """Return true when the PostGIS extension is installed."""

    row = fetch_one("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') AS available")
    return bool(row and row["available"])


def get_table_columns(table_name: str) -> list[str]:
    """Return ordered column names for a public table."""

    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [row["column_name"] for row in rows]


def count_rows(table_name: str) -> int:
    """Return row count for a known-safe table name."""

    if not table_exists(table_name):
        raise ValueError(f"Table does not exist: {table_name}")
    row = fetch_one(f'SELECT COUNT(*) AS count FROM "{table_name}"')
    return int(row["count"]) if row else 0


def insert_infra_asset_minimal(
    *,
    asset_type: str,
    asset_subtype: str | None,
    canonical_name: str,
    source_key: str,
    sensitivity_level: str,
    geometry_precision: str,
    confidence: float | None,
    longitude: float,
    latitude: float,
    properties: dict[str, Any] | None = None,
) -> str:
    """Insert a minimal point asset and return its UUID."""

    row = fetch_one(
        """
        INSERT INTO infra_asset (
            asset_type,
            asset_subtype,
            canonical_name,
            source_id,
            sensitivity_level,
            geometry_precision,
            confidence,
            geom,
            properties
        )
        SELECT
            %s,
            %s,
            %s,
            source_id,
            %s,
            %s,
            %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326),
            %s::jsonb
        FROM dim_source
        WHERE source_key = %s
        RETURNING asset_id::text
        """,
        (
            asset_type,
            asset_subtype,
            canonical_name,
            sensitivity_level,
            geometry_precision,
            confidence,
            longitude,
            latitude,
            json.dumps(properties or {}),
            source_key,
        ),
    )
    if row is None:
        raise ValueError(f"Source key not found: {source_key}")
    return str(row["asset_id"])
