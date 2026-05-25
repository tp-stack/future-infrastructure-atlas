"""Repository layer for the commercial API."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from atlas import db
from atlas.api.models import AuthContext, CheckoutSessionRequest, ExportCreateRequest
from atlas.api.rights import sql_commercial_rights_predicate
from atlas.payments import price_env_var


class CommercialRepositoryProtocol(Protocol):
    def authenticate_key(self, key_hash: str) -> AuthContext | None: ...
    def count_monthly_requests(self, customer_id: str) -> int: ...
    def record_usage(
        self,
        auth: AuthContext | None,
        *,
        endpoint: str,
        status_code: int,
        layer: str | None = None,
        records_returned: int = 0,
        bytes_served: int = 0,
    ) -> None: ...
    def list_assets(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]: ...
    def get_asset(self, auth: AuthContext, asset_id: str) -> dict[str, Any] | None: ...
    def search_assets(self, auth: AuthContext, query: str, limit: int) -> list[dict[str, Any]]: ...
    def list_region_scores(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]: ...
    def list_attribution(self, auth: AuthContext) -> list[dict[str, Any]]: ...
    def list_tile_layers(self, auth: AuthContext) -> list[dict[str, Any]]: ...
    def get_tile_layer(self, auth: AuthContext, layer_id: str) -> dict[str, Any] | None: ...
    def create_export_job(self, auth: AuthContext, request: ExportCreateRequest) -> dict[str, Any]: ...
    def get_export_job(self, auth: AuthContext, job_id: str) -> dict[str, Any] | None: ...
    def list_billing_plans(self) -> list[dict[str, Any]]: ...
    def get_billing_plan(self, plan_key: str) -> dict[str, Any] | None: ...
    def fulfill_checkout_session(self, session: dict[str, Any]) -> None: ...
    def update_billing_subscription(self, subscription: dict[str, Any]) -> None: ...


def _scopes(raw: Any) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, list):
        return frozenset(str(item) for item in raw)
    return frozenset(str(raw).strip("{}").split(","))


def _asset_select_sql() -> str:
    return """
        SELECT
            a.asset_id::text,
            a.asset_type,
            a.asset_subtype,
            a.canonical_name,
            a.raw_name,
            a.country_iso2,
            a.confidence::float,
            a.sensitivity_level,
            a.geometry_precision,
            CASE WHEN a.geom IS NULL THEN NULL ELSE ST_AsGeoJSON(a.geom)::json END AS geometry,
            COALESCE(a.properties, '{}'::jsonb) AS properties,
            s.source_key,
            s.source_name,
            s.license,
            s.url,
            g.attribution_required,
            g.terms_url
        FROM infra_asset a
        JOIN dim_source s ON s.source_id = a.source_id
        JOIN data_rights_grant g ON g.source_id = a.source_id
    """


def _attribution_from_assets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    attribution: list[dict[str, Any]] = []
    for row in rows:
        source_key = row.get("source_key")
        if not source_key or source_key in seen:
            continue
        seen.add(source_key)
        attribution.append(
            {
                "source_key": source_key,
                "source_name": row.get("source_name") or source_key,
                "license": row.get("license") or "",
                "url": row.get("url"),
                "attribution_required": bool(row.get("attribution_required", True)),
                "terms_url": row.get("terms_url"),
            }
        )
    return attribution


def _scopes_list(raw: Any) -> list[str]:
    return sorted(_scopes(raw))


def _stripe_price_id_for_plan(row: dict[str, Any]) -> str | None:
    env_value = os.environ.get(price_env_var(row["plan_key"]))
    return env_value or row.get("stripe_price_id")


def _customer_key(value: str | None, fallback: str) -> str:
    raw = value or fallback
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw.lower()).strip("-")
    return (cleaned or "stripe-customer")[:80]


class CommercialRepository:
    """Postgres-backed repository for commercial API routes."""

    def authenticate_key(self, key_hash: str) -> AuthContext | None:
        row = db.fetch_one(
            """
            SELECT
                k.api_key_id::text,
                k.scopes,
                c.customer_id::text,
                c.customer_key,
                p.plan_key,
                p.max_page_size,
                p.monthly_request_quota,
                p.monthly_export_quota_mb,
                p.max_export_rows
            FROM api_key k
            JOIN api_customer c ON c.customer_id = k.customer_id
            LEFT JOIN api_plan p ON p.plan_id = c.plan_id
            WHERE k.key_hash = %(key_hash)s
              AND k.status = 'active'
              AND c.status = 'active'
              AND (k.expires_at IS NULL OR k.expires_at > now())
            """,
            {"key_hash": key_hash},
        )
        if not row:
            return None
        db.run_sql("UPDATE api_key SET last_used_at = now() WHERE api_key_id = %(api_key_id)s", {"api_key_id": row["api_key_id"]})
        return AuthContext(
            customer_id=row["customer_id"],
            customer_key=row["customer_key"],
            api_key_id=row["api_key_id"],
            scopes=_scopes(row.get("scopes")),
            plan_key=row.get("plan_key") or "unplanned",
            max_page_size=int(row.get("max_page_size") or 100),
            monthly_request_quota=int(row.get("monthly_request_quota") or 1),
            monthly_export_quota_mb=int(row.get("monthly_export_quota_mb") or 0),
            max_export_rows=int(row.get("max_export_rows") or 0),
        )

    def count_monthly_requests(self, customer_id: str) -> int:
        row = db.fetch_one(
            """
            SELECT count(*)::int AS count
            FROM api_usage_event
            WHERE customer_id = %(customer_id)s
              AND created_at >= date_trunc('month', now())
            """,
            {"customer_id": customer_id},
        )
        return int(row["count"] if row else 0)

    def record_usage(
        self,
        auth: AuthContext | None,
        *,
        endpoint: str,
        status_code: int,
        layer: str | None = None,
        records_returned: int = 0,
        bytes_served: int = 0,
    ) -> None:
        db.run_sql(
            """
            INSERT INTO api_usage_event (
                customer_id,
                api_key_id,
                endpoint,
                layer,
                records_returned,
                bytes_served,
                status_code
            ) VALUES (
                %(customer_id)s,
                %(api_key_id)s,
                %(endpoint)s,
                %(layer)s,
                %(records_returned)s,
                %(bytes_served)s,
                %(status_code)s
            )
            """,
            {
                "customer_id": auth.customer_id if auth else None,
                "api_key_id": auth.api_key_id if auth else None,
                "endpoint": endpoint,
                "layer": layer,
                "records_returned": records_returned,
                "bytes_served": bytes_served,
                "status_code": status_code,
            },
        )

    def list_assets(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(int(filters.get("limit") or 50), auth.max_page_size)
        params: dict[str, Any] = {"limit": limit + 1}
        where = [sql_commercial_rights_predicate("s", "g")]

        if filters.get("asset_type"):
            where.append("a.asset_type = %(asset_type)s")
            params["asset_type"] = filters["asset_type"]
        if filters.get("country"):
            where.append("a.country_iso2 = %(country)s")
            params["country"] = str(filters["country"]).upper()
        if filters.get("min_confidence") is not None:
            where.append("a.confidence >= %(min_confidence)s")
            params["min_confidence"] = filters["min_confidence"]
        if filters.get("cursor"):
            where.append("a.asset_id::text > %(cursor)s")
            params["cursor"] = filters["cursor"]
        if filters.get("bbox"):
            min_lon, min_lat, max_lon, max_lat = filters["bbox"]
            where.append("a.geom && ST_MakeEnvelope(%(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326)")
            params.update({"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat})
        if filters.get("operator"):
            where.append(
                """
                EXISTS (
                    SELECT 1 FROM dim_operator o
                    WHERE o.operator_id = a.operator_id
                      AND o.canonical_name ILIKE %(operator)s
                )
                """
            )
            params["operator"] = f"%{filters['operator']}%"

        rows = db.fetch_all(
            f"{_asset_select_sql()} WHERE {' AND '.join(where)} ORDER BY a.asset_id LIMIT %(limit)s",
            params,
        )
        next_cursor = rows[limit]["asset_id"] if len(rows) > limit else None
        return rows[:limit], next_cursor

    def get_asset(self, auth: AuthContext, asset_id: str) -> dict[str, Any] | None:
        rows = db.fetch_all(
            f"{_asset_select_sql()} WHERE {sql_commercial_rights_predicate('s', 'g')} AND a.asset_id = %(asset_id)s LIMIT 1",
            {"asset_id": asset_id},
        )
        return rows[0] if rows else None

    def search_assets(self, auth: AuthContext, query: str, limit: int) -> list[dict[str, Any]]:
        capped_limit = min(limit, auth.max_page_size)
        return db.fetch_all(
            f"""
            {_asset_select_sql()}
            WHERE {sql_commercial_rights_predicate('s', 'g')}
              AND (
                a.canonical_name ILIKE %(query)s
                OR a.raw_name ILIKE %(query)s
                OR a.properties::text ILIKE %(query)s
              )
            ORDER BY a.confidence DESC NULLS LAST, a.asset_id
            LIMIT %(limit)s
            """,
            {"query": f"%{query}%", "limit": capped_limit},
        )

    def list_region_scores(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        limit = min(int(filters.get("limit") or 50), auth.max_page_size)
        params: dict[str, Any] = {"limit": limit + 1}
        where: list[str] = []
        if filters.get("region_type"):
            where.append("region_type = %(region_type)s")
            params["region_type"] = filters["region_type"]
        if filters.get("cursor"):
            where.append("score_id::text > %(cursor)s")
            params["cursor"] = filters["cursor"]
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = db.fetch_all(
            f"""
            SELECT
                score_id::text,
                region_id,
                region_type,
                score_model_version,
                final_score::float,
                confidence::float,
                CASE WHEN geom IS NULL THEN NULL ELSE ST_AsGeoJSON(geom)::json END AS geometry
            FROM region_score
            {where_sql}
            ORDER BY score_id
            LIMIT %(limit)s
            """,
            params,
        )
        next_cursor = rows[limit]["score_id"] if len(rows) > limit else None
        return rows[:limit], next_cursor

    def list_attribution(self, auth: AuthContext) -> list[dict[str, Any]]:
        return db.fetch_all(
            f"""
            SELECT DISTINCT
                s.source_key,
                s.source_name,
                s.license,
                s.url,
                g.attribution_required,
                g.terms_url
            FROM dim_source s
            JOIN data_rights_grant g ON g.source_id = s.source_id
            WHERE {sql_commercial_rights_predicate('s', 'g')}
            ORDER BY s.source_key
            """
        )

    def list_tile_layers(self, auth: AuthContext) -> list[dict[str, Any]]:
        return db.fetch_all(
            f"""
            SELECT
                g.layer_id,
                g.tile_format,
                g.tile_url,
                s.source_key,
                s.source_name,
                s.license,
                s.url,
                g.attribution_required,
                g.terms_url
            FROM data_rights_grant g
            JOIN dim_source s ON s.source_id = g.source_id
            WHERE {sql_commercial_rights_predicate('s', 'g')}
              AND g.layer_id IS NOT NULL
              AND g.tile_url IS NOT NULL
            ORDER BY g.layer_id
            """
        )

    def get_tile_layer(self, auth: AuthContext, layer_id: str) -> dict[str, Any] | None:
        rows = db.fetch_all(
            f"""
            SELECT
                g.layer_id,
                g.tile_format,
                g.tile_url,
                s.source_key,
                s.source_name,
                s.license,
                s.url,
                g.attribution_required,
                g.terms_url
            FROM data_rights_grant g
            JOIN dim_source s ON s.source_id = g.source_id
            WHERE {sql_commercial_rights_predicate('s', 'g')}
              AND g.layer_id = %(layer_id)s
              AND g.tile_url IS NOT NULL
            LIMIT 1
            """,
            {"layer_id": layer_id},
        )
        return rows[0] if rows else None

    def create_export_job(self, auth: AuthContext, request: ExportCreateRequest) -> dict[str, Any]:
        allowed_layers = {
            row["layer_id"]
            for row in db.fetch_all(
                f"""
                SELECT DISTINCT g.layer_id
                FROM data_rights_grant g
                JOIN dim_source s ON s.source_id = g.source_id
                WHERE {sql_commercial_rights_predicate('s', 'g', require_redistribution=True)}
                  AND g.layer_id IS NOT NULL
                """
            )
        }
        requested = set(request.layers)
        if not requested <= allowed_layers:
            blocked = sorted(requested - allowed_layers)
            row = db.fetch_one(
                """
                INSERT INTO api_export_job (customer_id, status, format, requested_layers, filters, error_message)
                VALUES (%(customer_id)s, 'rejected', %(format)s, %(layers)s, %(filters)s::jsonb, %(error)s)
                RETURNING export_job_id::text, status, format, requested_layers, filters, row_count, size_bytes, signed_url, error_message
                """,
                {
                    "customer_id": auth.customer_id,
                    "format": request.format,
                    "layers": request.layers,
                    "filters": json.dumps(request.filters),
                    "error": f"Layers are not commercially redistributable: {', '.join(blocked)}",
                },
            )
            return row or {}
        row = db.fetch_one(
            """
            INSERT INTO api_export_job (customer_id, status, format, requested_layers, filters)
            VALUES (%(customer_id)s, 'queued', %(format)s, %(layers)s, %(filters)s::jsonb)
            RETURNING export_job_id::text, status, format, requested_layers, filters, row_count, size_bytes, signed_url, error_message
            """,
            {
                "customer_id": auth.customer_id,
                "format": request.format,
                "layers": request.layers,
                "filters": json.dumps(request.filters),
            },
        )
        return row or {}

    def get_export_job(self, auth: AuthContext, job_id: str) -> dict[str, Any] | None:
        return db.fetch_one(
            """
            SELECT export_job_id::text, status, format, requested_layers, row_count, size_bytes, signed_url, error_message
            FROM api_export_job
            WHERE export_job_id = %(job_id)s
              AND customer_id = %(customer_id)s
            """,
            {"job_id": job_id, "customer_id": auth.customer_id},
        )

    def list_billing_plans(self) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT
                plan_key,
                display_name,
                monthly_request_quota,
                monthly_export_quota_mb,
                max_export_rows,
                allowed_scopes,
                stripe_price_id,
                price_monthly_cents,
                included_export_jobs,
                extra_extraction_cents
            FROM api_plan
            WHERE plan_key IN ('launch', 'scale', 'enterprise')
            ORDER BY CASE plan_key WHEN 'launch' THEN 1 WHEN 'scale' THEN 2 ELSE 3 END
            """
        )
        plans = []
        for row in rows:
            price_id = _stripe_price_id_for_plan(row)
            plans.append(
                {
                    "plan_key": row["plan_key"],
                    "display_name": row["display_name"],
                    "price_monthly_cents": int(row.get("price_monthly_cents") or 0),
                    "monthly_request_quota": int(row["monthly_request_quota"]),
                    "monthly_export_quota_mb": int(row["monthly_export_quota_mb"]),
                    "max_export_rows": int(row["max_export_rows"]),
                    "included_export_jobs": int(row.get("included_export_jobs") or 0),
                    "extra_extraction_cents": int(row.get("extra_extraction_cents") or 0),
                    "allowed_scopes": _scopes_list(row.get("allowed_scopes")),
                    "stripe_price_id": price_id,
                    "stripe_price_configured": bool(price_id),
                }
            )
        return plans

    def get_billing_plan(self, plan_key: str) -> dict[str, Any] | None:
        for plan in self.list_billing_plans():
            if plan["plan_key"] == plan_key:
                return plan
        return None

    def fulfill_checkout_session(self, session: dict[str, Any]) -> None:
        metadata = dict(session.get("metadata") or {})
        plan_key = metadata.get("plan_key")
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")
        customer_details = session.get("customer_details") or {}
        email = customer_details.get("email") or session.get("customer_email")
        if not plan_key or not stripe_customer_id:
            return

        plan = db.fetch_one("SELECT plan_id FROM api_plan WHERE plan_key = %(plan_key)s", {"plan_key": plan_key})
        if not plan:
            return

        existing = db.fetch_one(
            "SELECT customer_id FROM api_customer WHERE stripe_customer_id = %(stripe_customer_id)s",
            {"stripe_customer_id": stripe_customer_id},
        )
        values = {
            "plan_id": plan["plan_id"],
            "customer_key": _customer_key(metadata.get("customer_key"), email or stripe_customer_id),
            "display_name": email or stripe_customer_id,
            "billing_email": email,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "checkout_session_id": session.get("id"),
            "billing_status": "active",
        }
        if existing:
            values["customer_id"] = existing["customer_id"]
            db.run_sql(
                """
                UPDATE api_customer
                SET plan_id = %(plan_id)s,
                    display_name = COALESCE(%(display_name)s, display_name),
                    billing_email = %(billing_email)s,
                    stripe_subscription_id = %(stripe_subscription_id)s,
                    checkout_session_id = %(checkout_session_id)s,
                    billing_status = %(billing_status)s,
                    status = 'active'
                WHERE customer_id = %(customer_id)s
                """,
                values,
            )
            return

        db.run_sql(
            """
            INSERT INTO api_customer (
                customer_key,
                display_name,
                plan_id,
                status,
                billing_email,
                stripe_customer_id,
                stripe_subscription_id,
                billing_status,
                checkout_session_id
            ) VALUES (
                %(customer_key)s,
                %(display_name)s,
                %(plan_id)s,
                'active',
                %(billing_email)s,
                %(stripe_customer_id)s,
                %(stripe_subscription_id)s,
                %(billing_status)s,
                %(checkout_session_id)s
            )
            ON CONFLICT (customer_key) DO UPDATE SET
                plan_id = EXCLUDED.plan_id,
                display_name = EXCLUDED.display_name,
                billing_email = EXCLUDED.billing_email,
                stripe_customer_id = EXCLUDED.stripe_customer_id,
                stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                billing_status = EXCLUDED.billing_status,
                checkout_session_id = EXCLUDED.checkout_session_id,
                status = 'active'
            """,
            values,
        )

    def update_billing_subscription(self, subscription: dict[str, Any]) -> None:
        stripe_subscription_id = subscription.get("id")
        stripe_customer_id = subscription.get("customer")
        status = subscription.get("status") or "unknown"
        if not stripe_subscription_id and not stripe_customer_id:
            return
        customer_status = "active" if status in {"active", "trialing"} else "suspended"
        db.run_sql(
            """
            UPDATE api_customer
            SET stripe_subscription_id = COALESCE(%(stripe_subscription_id)s, stripe_subscription_id),
                billing_status = %(billing_status)s,
                status = %(customer_status)s
            WHERE (%(stripe_subscription_id)s IS NOT NULL AND stripe_subscription_id = %(stripe_subscription_id)s)
               OR (%(stripe_customer_id)s IS NOT NULL AND stripe_customer_id = %(stripe_customer_id)s)
            """,
            {
                "stripe_subscription_id": stripe_subscription_id,
                "stripe_customer_id": stripe_customer_id,
                "billing_status": status,
                "customer_status": customer_status,
            },
        )


def rows_to_asset_response(rows: list[dict[str, Any]], next_cursor: str | None) -> dict[str, Any]:
    data = []
    for row in rows:
        data.append(
            {
                "asset_id": row["asset_id"],
                "asset_type": row["asset_type"],
                "asset_subtype": row.get("asset_subtype"),
                "canonical_name": row.get("canonical_name"),
                "raw_name": row.get("raw_name"),
                "country_iso2": row.get("country_iso2"),
                "confidence": row.get("confidence"),
                "sensitivity_level": row["sensitivity_level"],
                "geometry_precision": row["geometry_precision"],
                "geometry": row.get("geometry"),
                "properties": row.get("properties") or {},
                "source": {
                    "source_key": row["source_key"],
                    "source_name": row["source_name"],
                    "license": row["license"],
                    "url": row.get("url"),
                    "attribution_required": bool(row.get("attribution_required", True)),
                    "terms_url": row.get("terms_url"),
                },
            }
        )
    return {"data": data, "next_cursor": next_cursor, "attribution": _attribution_from_assets(rows)}
