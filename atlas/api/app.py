"""FastAPI application for the commercial Atlas API."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from atlas import settings
from atlas.api.errors import api_error
from atlas.api.models import (
    AssetDetailResponse,
    AssetListResponse,
    AuthContext,
    BillingPlanCatalogResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    ExportCreateRequest,
    ExportJobResponse,
    RegionScoreResponse,
    TileCatalogResponse,
    TileJSONResponse,
)
from atlas.api.repository import CommercialRepository, CommercialRepositoryProtocol, rows_to_asset_response
from atlas.api.security import API_KEY_HEADER, hash_api_key, sign_path
from atlas.payments import StripeService, get_stripe_service, get_stripe_webhook_secret
from atlas.registry import load_commercial_api_policy


def _max_response_bytes() -> int:
    storage = settings.get_storage_config()
    return int(storage.get("max_api_response_size_mb", 5)) * 1024 * 1024


def _commercial_api_policy() -> dict[str, Any]:
    try:
        return load_commercial_api_policy()
    except FileNotFoundError:
        return {}


def _max_request_body_bytes() -> int:
    policy = _commercial_api_policy()
    return int(policy.get("max_request_body_bytes", 1024 * 1024))


def get_repository(request: Request) -> CommercialRepositoryProtocol:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        repository = CommercialRepository()
        request.app.state.repository = repository
    return repository


def get_billing_service(request: Request) -> StripeService:
    service = getattr(request.app.state, "billing_service", None)
    if service is None:
        service = get_stripe_service()
        request.app.state.billing_service = service
    return service


def require_auth(required_scope: str) -> Callable[..., AuthContext]:
    def dependency(
        request: Request,
        x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
        authorization: Annotated[str | None, Header()] = None,
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> AuthContext:
        raw_key = x_api_key
        if not raw_key and authorization and authorization.lower().startswith("bearer "):
            raw_key = authorization[7:].strip()
        if not raw_key:
            raise api_error(401, "missing_api_key", f"Provide {API_KEY_HEADER} or Authorization: Bearer.")

        auth = repository.authenticate_key(hash_api_key(raw_key))
        if not auth:
            raise api_error(401, "invalid_api_key", "API key is invalid, inactive, or expired.")
        if required_scope not in auth.scopes and "admin:read" not in auth.scopes:
            raise api_error(403, "missing_scope", f"API key requires scope: {required_scope}.")
        if repository.count_monthly_requests(auth.customer_id) >= auth.monthly_request_quota:
            raise api_error(429, "quota_exceeded", "Monthly request quota exceeded.")
        request.state.auth = auth
        return auth

    return dependency


async def response_size_limit_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    response = await call_next(request)
    max_bytes = _max_response_bytes()
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
        if len(body) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": {"code": "response_too_large", "message": "API response exceeded configured size limit."}},
            )
    headers = dict(response.headers)
    headers["content-length"] = str(len(body))
    return Response(content=body, status_code=response.status_code, headers=headers, media_type=response.media_type)


async def request_size_limit_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            request_bytes = int(content_length)
        except ValueError:
            raise api_error(400, "invalid_content_length", "Content-Length must be an integer.") from None
        if request_bytes > _max_request_body_bytes():
            return JSONResponse(
                status_code=413,
                content={"detail": {"code": "request_too_large", "message": "API request exceeded configured size limit."}},
            )
    return await call_next(request)


async def usage_logging_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    repository = get_repository(request)
    auth = getattr(request.state, "auth", None)
    endpoint = request.url.path
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        auth = getattr(request.state, "auth", auth)
        if endpoint.startswith("/v1/"):
            try:
                repository.record_usage(auth, endpoint=endpoint, status_code=locals().get("status_code", 500))
            except Exception:
                # Usage logging must never expose internals or break customer responses.
                pass


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    try:
        values = tuple(float(part) for part in bbox.split(","))
    except ValueError as exc:
        raise api_error(422, "invalid_bbox", "bbox must be minLon,minLat,maxLon,maxLat.") from exc
    if len(values) != 4:
        raise api_error(422, "invalid_bbox", "bbox must contain four comma-separated numbers.")
    min_lon, min_lat, max_lon, max_lat = values
    if min_lon >= max_lon or min_lat >= max_lat:
        raise api_error(422, "invalid_bbox", "bbox minimums must be less than maximums.")
    return values


def _export_response(row: dict[str, Any]) -> ExportJobResponse:
    return ExportJobResponse(
        export_job_id=row["export_job_id"],
        status=row["status"],
        format=row["format"],
        requested_layers=list(row.get("requested_layers") or []),
        row_count=row.get("row_count"),
        size_bytes=row.get("size_bytes"),
        signed_url=row.get("signed_url"),
        error_message=row.get("error_message"),
    )


def create_app(repository: CommercialRepositoryProtocol | None = None, billing_service: StripeService | None = None) -> FastAPI:
    app = FastAPI(
        title="FUTURE Infrastructure Atlas Commercial API",
        version="0.1.0",
        description="Authenticated commercial API for clean-room infrastructure intelligence.",
    )
    if repository is not None:
        app.state.repository = repository
    if billing_service is not None:
        app.state.billing_service = billing_service

    policy = _commercial_api_policy()
    allowed_origins = policy.get("cors_allowed_origins") or []
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[API_KEY_HEADER, "Authorization", "Content-Type"],
        )

    app.middleware("http")(usage_logging_middleware)
    app.middleware("http")(request_size_limit_middleware)
    app.middleware("http")(response_size_limit_middleware)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/assets", response_model=AssetListResponse)
    def list_assets(
        auth: AuthContext = Depends(require_auth("assets:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
        asset_type: str | None = None,
        country: str | None = None,
        bbox: str | None = None,
        operator: str | None = None,
        min_confidence: float | None = Query(default=None, ge=0, le=1),
        limit: int = Query(default=50, ge=1, le=1000),
        cursor: str | None = None,
    ) -> dict[str, Any]:
        rows, next_cursor = repository.list_assets(
            auth,
            {
                "asset_type": asset_type,
                "country": country,
                "bbox": parse_bbox(bbox),
                "operator": operator,
                "min_confidence": min_confidence,
                "limit": limit,
                "cursor": cursor,
            },
        )
        return rows_to_asset_response(rows, next_cursor)

    @app.get("/v1/assets/{asset_id}", response_model=AssetDetailResponse)
    def get_asset(
        asset_id: str,
        auth: AuthContext = Depends(require_auth("assets:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> dict[str, Any]:
        row = repository.get_asset(auth, asset_id)
        if not row:
            raise api_error(404, "asset_not_found", "Asset does not exist or is not commercially available.")
        response = rows_to_asset_response([row], None)
        return {"data": response["data"][0], "attribution": response["attribution"]}

    @app.get("/v1/search", response_model=AssetListResponse)
    def search(
        q: str = Query(min_length=2),
        limit: int = Query(default=25, ge=1, le=100),
        auth: AuthContext = Depends(require_auth("assets:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> dict[str, Any]:
        rows = repository.search_assets(auth, q, limit)
        return rows_to_asset_response(rows, None)

    @app.get("/v1/regions/scores", response_model=RegionScoreResponse)
    def region_scores(
        auth: AuthContext = Depends(require_auth("assets:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
        region_type: str | None = None,
        limit: int = Query(default=50, ge=1, le=1000),
        cursor: str | None = None,
    ) -> dict[str, Any]:
        rows, next_cursor = repository.list_region_scores(auth, {"region_type": region_type, "limit": limit, "cursor": cursor})
        return {"data": rows, "next_cursor": next_cursor}

    @app.get("/v1/sources/attribution")
    def attribution(
        auth: AuthContext = Depends(require_auth("assets:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> dict[str, Any]:
        return {"sources": repository.list_attribution(auth)}

    @app.get("/v1/billing/plans", response_model=BillingPlanCatalogResponse)
    def billing_plans(repository: CommercialRepositoryProtocol = Depends(get_repository)) -> dict[str, Any]:
        return {"plans": repository.list_billing_plans()}

    @app.post("/v1/billing/checkout", response_model=CheckoutSessionResponse)
    def create_checkout_session(
        request: CheckoutSessionRequest,
        repository: CommercialRepositoryProtocol = Depends(get_repository),
        billing_service: StripeService = Depends(get_billing_service),
    ) -> dict[str, Any]:
        plan = repository.get_billing_plan(request.plan)
        if not plan:
            raise api_error(404, "billing_plan_not_found", "Billing plan is not available.")
        price_id = plan.get("stripe_price_id")
        if not price_id:
            raise api_error(503, "stripe_price_not_configured", f"Stripe price is not configured for plan: {request.plan}.")
        try:
            session = billing_service.create_checkout_session(
                request,
                price_id,
                metadata={
                    "plan_key": request.plan,
                    "price_monthly_cents": plan.get("price_monthly_cents", 0),
                },
            )
        except ValueError as exc:
            raise api_error(503, "stripe_not_configured", str(exc)) from exc
        return {"checkout_url": session["url"], "session_id": session["id"], "plan": request.plan}

    @app.get("/v1/tiles/catalog", response_model=TileCatalogResponse)
    def tile_catalog(
        auth: AuthContext = Depends(require_auth("tiles:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> dict[str, Any]:
        layers = []
        for row in repository.list_tile_layers(auth):
            layers.append(
                {
                    "layer_id": row["layer_id"],
                    "tile_format": row["tile_format"],
                    "tilejson_url": f"/v1/tiles/{row['layer_id']}/tilejson",
                    "attribution": [
                        {
                            "source_key": row["source_key"],
                            "source_name": row["source_name"],
                            "license": row["license"],
                            "url": row.get("url"),
                            "attribution_required": bool(row.get("attribution_required", True)),
                            "terms_url": row.get("terms_url"),
                        }
                    ],
                }
            )
        return {"layers": layers}

    @app.get("/v1/tiles/{layer}/tilejson", response_model=TileJSONResponse)
    def tilejson(
        layer: str,
        auth: AuthContext = Depends(require_auth("tiles:read")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> dict[str, Any]:
        row = repository.get_tile_layer(auth, layer)
        if not row:
            raise api_error(404, "tile_layer_not_found", "Tile layer does not exist or is not commercially available.")
        attribution = f"{row['source_name']} ({row['license']})"
        return {
            "name": row["layer_id"],
            "format": row["tile_format"],
            "tiles": [sign_path(row["tile_url"])],
            "attribution": attribution,
            "vector_layers": [{"id": row["layer_id"], "fields": {}}],
        }

    @app.post("/v1/exports", response_model=ExportJobResponse, status_code=202)
    def create_export(
        request: ExportCreateRequest,
        auth: AuthContext = Depends(require_auth("exports:create")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> ExportJobResponse:
        row = repository.create_export_job(auth, request)
        return _export_response(row)

    @app.get("/v1/exports/{job_id}", response_model=ExportJobResponse)
    def get_export(
        job_id: str,
        auth: AuthContext = Depends(require_auth("exports:create")),
        repository: CommercialRepositoryProtocol = Depends(get_repository),
    ) -> ExportJobResponse:
        row = repository.get_export_job(auth, job_id)
        if not row:
            raise api_error(404, "export_not_found", "Export job does not exist for this customer.")
        if row.get("signed_url"):
            row = dict(row)
            row["signed_url"] = sign_path(row["signed_url"])
        return _export_response(row)

    @app.get("/openapi-commercial.json", include_in_schema=False)
    def openapi_json() -> dict[str, Any]:
        return json.loads(json.dumps(app.openapi()))

    async def _stripe_webhook_handler(
        request: Request,
        repository: CommercialRepositoryProtocol,
        billing_service: StripeService,
    ) -> dict[str, str]:
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        if not signature:
            raise api_error(400, "missing_signature", "stripe-signature header required")

        try:
            event = billing_service.verify_webhook_signature(payload, signature, get_stripe_webhook_secret())
        except ValueError as exc:
            raise api_error(401, "invalid_signature", str(exc)) from exc

        event_type = event.get("type")
        obj = (event.get("data") or {}).get("object") or {}
        if event_type == "checkout.session.completed":
            repository.fulfill_checkout_session(obj)
        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
            repository.update_billing_subscription(obj)
        elif event_type == "invoice.payment_succeeded":
            repository.update_billing_subscription({"id": obj.get("subscription"), "customer": obj.get("customer"), "status": "active"})
        elif event_type == "invoice.payment_failed":
            repository.update_billing_subscription({"id": obj.get("subscription"), "customer": obj.get("customer"), "status": "past_due"})
        return {"status": "success"}

    @app.post("/v1/billing/webhook", include_in_schema=False)
    async def stripe_billing_webhook(
        request: Request,
        repository: CommercialRepositoryProtocol = Depends(get_repository),
        billing_service: StripeService = Depends(get_billing_service),
    ) -> dict[str, str]:
        return await _stripe_webhook_handler(request, repository, billing_service)

    @app.post("/v1/webhooks/stripe", include_in_schema=False)
    async def stripe_webhook_compat(
        request: Request,
        repository: CommercialRepositoryProtocol = Depends(get_repository),
        billing_service: StripeService = Depends(get_billing_service),
    ) -> dict[str, str]:
        return await _stripe_webhook_handler(request, repository, billing_service)

    return app


app = create_app()
