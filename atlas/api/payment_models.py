"""Pydantic models for payment and subscription endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PaymentIntentRequest(BaseModel):
    """Request to create a payment intent."""

    amount_cents: int = Field(..., gt=0, description="Amount in cents")
    currency: str = Field(default="usd", description="Currency code (ISO 4217)")
    description: str | None = Field(None, description="Payment description")
    metadata: dict[str, str] | None = Field(None, description="Additional metadata")


class PaymentIntentResponse(BaseModel):
    """Response containing payment intent details."""

    client_secret: str
    payment_intent_id: str
    amount_cents: int
    currency: str
    status: str
    created_at: datetime


class SubscriptionRequest(BaseModel):
    """Request to create or update a subscription."""

    price_id: str = Field(..., description="Stripe price ID")
    plan_type: str | None = Field(None, description="Internal plan type")
    metadata: dict[str, str] | None = Field(None, description="Additional metadata")


class SubscriptionResponse(BaseModel):
    """Response containing subscription details."""

    subscription_id: str
    customer_id: str
    plan_type: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime


class SubscriptionCancelRequest(BaseModel):
    """Request to cancel a subscription."""

    immediately: bool = Field(default=False, description="Cancel immediately or at period end")


class CustomerResponse(BaseModel):
    """Response containing customer details."""

    customer_id: str
    email: str | None
    name: str | None
    created_at: datetime


class PaymentStatusResponse(BaseModel):
    """Response with payment status."""

    payment_id: str
    api_key_id: str
    amount_cents: int
    currency: str
    status: str
    created_at: datetime


class SubscriptionStatusResponse(BaseModel):
    """Response with subscription status."""

    subscription_id: str
    api_key_id: str
    plan_type: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    created_at: datetime


class WebhookEvent(BaseModel):
    """Stripe webhook event model."""

    event_type: str
    event_id: str
    data: dict[str, Any]
    timestamp: datetime
