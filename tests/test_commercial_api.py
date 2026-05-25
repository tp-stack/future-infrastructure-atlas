from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.api.models import AuthContext, CheckoutSessionRequest, ExportCreateRequest
from atlas.api.rights import is_commercial_source_allowed
from atlas.api.security import hash_api_key


VALID_KEY = "fia_test_key"
ASSETS_ONLY_KEY = "fia_assets_only"


class FakeCommercialRepository:
    def __init__(self) -> None:
        self.usage_events: list[dict[str, Any]] = []
        self.quota_used = 0
        self.fulfilled_sessions: list[dict[str, Any]] = []
        self.updated_subscriptions: list[dict[str, Any]] = []

    def authenticate_key(self, key_hash: str) -> AuthContext | None:
        if key_hash == hash_api_key(VALID_KEY):
            return AuthContext(
                customer_id="customer-1",
                customer_key="acme",
                api_key_id="key-1",
                scopes=frozenset({"assets:read", "tiles:read", "exports:create"}),
                plan_key="developer",
                max_page_size=100,
                monthly_request_quota=1000,
                monthly_export_quota_mb=100,
                max_export_rows=10000,
            )
        if key_hash == hash_api_key(ASSETS_ONLY_KEY):
            return AuthContext(
                customer_id="customer-2",
                customer_key="assets-only",
                api_key_id="key-2",
                scopes=frozenset({"assets:read"}),
                plan_key="developer",
                max_page_size=100,
                monthly_request_quota=1000,
                monthly_export_quota_mb=100,
                max_export_rows=10000,
            )
        return None

    def count_monthly_requests(self, customer_id: str) -> int:
        return self.quota_used

    def record_usage(self, auth: AuthContext | None, **kwargs: Any) -> None:
        self.usage_events.append({"auth": auth, **kwargs})

    def _asset_row(self) -> dict[str, Any]:
        return {
            "asset_id": "asset-1",
            "asset_type": "power_plant",
            "asset_subtype": "solar",
            "canonical_name": "Clean Solar One",
            "raw_name": "Clean Solar One",
            "country_iso2": "US",
            "confidence": 0.95,
            "sensitivity_level": "low",
            "geometry_precision": "generalized",
            "geometry": {"type": "Point", "coordinates": [-100, 40]},
            "properties": {"capacity_mw": 100},
            "source_key": "owned_research",
            "source_name": "Owned Research",
            "license": "owned",
            "url": "https://example.com",
            "attribution_required": False,
            "terms_url": "https://example.com/terms",
        }

    def list_assets(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        return [self._asset_row()], None

    def get_asset(self, auth: AuthContext, asset_id: str) -> dict[str, Any] | None:
        return self._asset_row() if asset_id == "asset-1" else None

    def search_assets(self, auth: AuthContext, query: str, limit: int) -> list[dict[str, Any]]:
        return [self._asset_row()]

    def list_region_scores(self, auth: AuthContext, filters: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
        return [
            {
                "score_id": "score-1",
                "region_id": "US",
                "region_type": "country",
                "score_model_version": "v1",
                "final_score": 88.0,
                "confidence": 0.8,
                "geometry": None,
            }
        ], None

    def list_attribution(self, auth: AuthContext) -> list[dict[str, Any]]:
        return [
            {
                "source_key": "owned_research",
                "source_name": "Owned Research",
                "license": "owned",
                "url": "https://example.com",
                "attribution_required": False,
                "terms_url": "https://example.com/terms",
            }
        ]

    def list_tile_layers(self, auth: AuthContext) -> list[dict[str, Any]]:
        return [
            {
                "layer_id": "commercial_power",
                "tile_format": "pmtiles",
                "tile_url": "https://tiles.example.com/commercial_power.pmtiles",
                "source_key": "owned_research",
                "source_name": "Owned Research",
                "license": "owned",
                "url": "https://example.com",
                "attribution_required": False,
                "terms_url": "https://example.com/terms",
            }
        ]

    def get_tile_layer(self, auth: AuthContext, layer_id: str) -> dict[str, Any] | None:
        return self.list_tile_layers(auth)[0] if layer_id == "commercial_power" else None

    def create_export_job(self, auth: AuthContext, request: ExportCreateRequest) -> dict[str, Any]:
        if "blocked_layer" in request.layers:
            return {
                "export_job_id": "export-1",
                "status": "rejected",
                "format": request.format,
                "requested_layers": request.layers,
                "row_count": None,
                "size_bytes": None,
                "signed_url": None,
                "error_message": "Layers are not commercially redistributable: blocked_layer",
            }
        return {
            "export_job_id": "export-2",
            "status": "queued",
            "format": request.format,
            "requested_layers": request.layers,
            "row_count": None,
            "size_bytes": None,
            "signed_url": None,
            "error_message": None,
        }

    def get_export_job(self, auth: AuthContext, job_id: str) -> dict[str, Any] | None:
        if job_id != "export-2":
            return None
        return {
            "export_job_id": "export-2",
            "status": "succeeded",
            "format": "csv",
            "requested_layers": ["commercial_power"],
            "row_count": 10,
            "size_bytes": 2048,
            "signed_url": "https://exports.example.com/export-2.csv",
            "error_message": None,
        }

    def list_billing_plans(self) -> list[dict[str, Any]]:
        return [
            {
                "plan_key": "scale",
                "display_name": "Scale",
                "price_monthly_cents": 125000,
                "monthly_request_quota": 250000,
                "monthly_export_quota_mb": 5000,
                "max_export_rows": 500000,
                "included_export_jobs": 50,
                "extra_extraction_cents": 14900,
                "allowed_scopes": ["assets:read", "tiles:read", "exports:create"],
                "stripe_price_id": "price_scale_test",
                "stripe_price_configured": True,
            }
        ]

    def get_billing_plan(self, plan_key: str) -> dict[str, Any] | None:
        return self.list_billing_plans()[0] if plan_key == "scale" else None

    def fulfill_checkout_session(self, session: dict[str, Any]) -> None:
        self.fulfilled_sessions.append(session)

    def update_billing_subscription(self, subscription: dict[str, Any]) -> None:
        self.updated_subscriptions.append(subscription)


class FakeBillingService:
    def create_checkout_session(self, request: CheckoutSessionRequest, price_id: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": "cs_test_123",
            "url": f"https://checkout.stripe.test/session/{request.plan}/{price_id}",
        }

    def verify_webhook_signature(self, payload: bytes, signature: str, endpoint_secret: str) -> dict[str, Any]:
        assert signature == "valid"
        assert endpoint_secret == "whsec_test"
        return {
            "id": "evt_test",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "customer": "cus_test",
                    "subscription": "sub_test",
                    "metadata": {"plan_key": "scale"},
                    "customer_details": {"email": "buyer@example.com"},
                }
            },
        }


def client(repo: FakeCommercialRepository | None = None) -> TestClient:
    return TestClient(create_app(repository=repo or FakeCommercialRepository(), billing_service=FakeBillingService()))


def test_rights_gate_is_fail_closed_without_grant() -> None:
    source = {"license": "owned", "allowed_usage": "owned"}

    assert not is_commercial_source_allowed(source, None)


def test_rights_gate_blocks_unreviewed_and_share_alike_sources() -> None:
    source = {"license": "ODbL", "allowed_usage": "redistribution_safe"}

    assert not is_commercial_source_allowed(
        source,
        {
            "license_review_status": "pending",
            "commercial_api_allowed": True,
            "redistribution_allowed": True,
            "share_alike_risk": False,
        },
    )
    assert not is_commercial_source_allowed(
        source,
        {
            "license_review_status": "approved",
            "commercial_api_allowed": True,
            "redistribution_allowed": True,
            "share_alike_risk": True,
        },
    )


def test_rights_gate_allows_approved_clean_commercial_source() -> None:
    source = {"license": "owned", "allowed_usage": "owned"}
    grant = {
        "license_review_status": "approved",
        "commercial_api_allowed": True,
        "redistribution_allowed": True,
        "share_alike_risk": False,
    }

    assert is_commercial_source_allowed(source, grant, require_redistribution=True)


def test_assets_endpoint_requires_api_key() -> None:
    response = client().get("/v1/assets")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_api_key"


def test_assets_endpoint_returns_attribution() -> None:
    response = client().get("/v1/assets", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["asset_id"] == "asset-1"
    assert body["data"][0]["source"]["source_key"] == "owned_research"
    assert body["attribution"][0]["license"] == "owned"


def test_asset_detail_endpoint_returns_single_asset_with_attribution() -> None:
    response = client().get("/v1/assets/asset-1", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["asset_id"] == "asset-1"
    assert body["attribution"][0]["source_key"] == "owned_research"


def test_request_size_limit_is_enforced() -> None:
    response = client().post(
        "/v1/exports",
        headers={"X-API-Key": VALID_KEY, "Content-Length": "1048577"},
        json={"format": "csv", "layers": ["commercial_power"], "filters": {}},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_too_large"


def test_tile_scope_is_enforced() -> None:
    response = client().get("/v1/tiles/catalog", headers={"X-API-Key": ASSETS_ONLY_KEY})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "missing_scope"


def test_tilejson_returns_signed_tile_url() -> None:
    response = client().get("/v1/tiles/commercial_power/tilejson", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 200
    tile_url = response.json()["tiles"][0]
    assert "signature=" in tile_url
    assert "expires=" in tile_url


def test_export_create_rejects_blocked_layer() -> None:
    response = client().post(
        "/v1/exports",
        headers={"X-API-Key": VALID_KEY},
        json={"format": "csv", "layers": ["blocked_layer"], "filters": {}},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "rejected"
    assert "blocked_layer" in body["error_message"]


def test_quota_is_enforced() -> None:
    repo = FakeCommercialRepository()
    repo.quota_used = 1000

    response = client(repo).get("/v1/assets", headers={"X-API-Key": VALID_KEY})

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "quota_exceeded"


def test_billing_plans_are_public() -> None:
    response = client().get("/v1/billing/plans")

    assert response.status_code == 200
    body = response.json()
    assert body["plans"][0]["plan_key"] == "scale"
    assert body["plans"][0]["stripe_price_configured"] is True


def test_checkout_session_is_created_server_side() -> None:
    response = client().post("/v1/billing/checkout", json={"plan": "scale", "email": "buyer@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "cs_test_123"
    assert body["checkout_url"].startswith("https://checkout.stripe.test/session/scale/")


def test_stripe_webhook_fulfills_checkout(monkeypatch) -> None:
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    repo = FakeCommercialRepository()

    response = client(repo).post("/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "valid"})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert repo.fulfilled_sessions[0]["customer"] == "cus_test"
