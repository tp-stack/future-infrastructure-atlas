"""Pydantic models for the commercial API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ApiScope = Literal["assets:read", "tiles:read", "exports:create", "admin:read"]
ExportFormat = Literal["geojson", "csv", "parquet"]


@dataclass(frozen=True)
class AuthContext:
    customer_id: str
    customer_key: str
    api_key_id: str
    scopes: frozenset[str]
    plan_key: str
    max_page_size: int
    monthly_request_quota: int
    monthly_export_quota_mb: int
    max_export_rows: int


class SourceAttribution(BaseModel):
    source_key: str
    source_name: str
    license: str
    url: str | None = None
    attribution_required: bool = True
    terms_url: str | None = None


class AssetRecord(BaseModel):
    asset_id: str
    asset_type: str
    asset_subtype: str | None = None
    canonical_name: str | None = None
    raw_name: str | None = None
    country_iso2: str | None = None
    confidence: float | None = None
    sensitivity_level: str
    geometry_precision: str
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source: SourceAttribution


class AssetListResponse(BaseModel):
    data: list[AssetRecord]
    next_cursor: str | None = None
    attribution: list[SourceAttribution]


class AssetDetailResponse(BaseModel):
    data: AssetRecord
    attribution: list[SourceAttribution]


class RegionScoreRecord(BaseModel):
    score_id: str
    region_id: str
    region_type: str
    score_model_version: str
    final_score: float | None = None
    confidence: float | None = None
    geometry: dict[str, Any] | None = None


class RegionScoreResponse(BaseModel):
    data: list[RegionScoreRecord]
    next_cursor: str | None = None


class TileCatalogLayer(BaseModel):
    layer_id: str
    tile_format: str
    tilejson_url: str
    attribution: list[SourceAttribution]


class TileCatalogResponse(BaseModel):
    layers: list[TileCatalogLayer]


class TileJSONResponse(BaseModel):
    tilejson: str = "3.0.0"
    name: str
    format: str
    tiles: list[str]
    attribution: str
    vector_layers: list[dict[str, Any]] = Field(default_factory=list)


class ExportCreateRequest(BaseModel):
    format: ExportFormat
    layers: list[str] = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportJobResponse(BaseModel):
    export_job_id: str
    status: str
    format: str
    requested_layers: list[str]
    row_count: int | None = None
    size_bytes: int | None = None
    signed_url: str | None = None
    error_message: str | None = None


class BillingPlanRecord(BaseModel):
    plan_key: str
    display_name: str
    price_monthly_cents: int
    monthly_request_quota: int
    monthly_export_quota_mb: int
    max_export_rows: int
    included_export_jobs: int
    extra_extraction_cents: int
    allowed_scopes: list[str]
    stripe_price_configured: bool


class BillingPlanCatalogResponse(BaseModel):
    plans: list[BillingPlanRecord]


class CheckoutSessionRequest(BaseModel):
    plan: Literal["launch", "scale", "enterprise"]
    email: str | None = None
    customer_key: str | None = None

    @field_validator("email", "customer_key")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    plan: str
