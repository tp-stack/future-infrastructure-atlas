"""Stripe billing helpers for the commercial API."""

from __future__ import annotations

import os
from typing import Any

import stripe

from atlas.api.models import CheckoutSessionRequest


PLAN_PRICE_ENV = {
    "launch": "STRIPE_PRICE_LAUNCH",
    "scale": "STRIPE_PRICE_SCALE",
    "enterprise": "STRIPE_PRICE_ENTERPRISE",
}


def get_stripe_api_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not key:
        raise ValueError("STRIPE_SECRET_KEY is required for Stripe billing.")
    return key


def get_stripe_webhook_secret() -> str:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is required to verify Stripe webhooks.")
    return secret


def get_public_app_url() -> str:
    return os.environ.get("PUBLIC_APP_URL") or os.environ.get("APP_URL") or "http://127.0.0.1:5174"


def price_env_var(plan_key: str) -> str:
    try:
        return PLAN_PRICE_ENV[plan_key]
    except KeyError as exc:
        raise ValueError(f"Unsupported billing plan: {plan_key}") from exc


class StripeService:
    """Thin wrapper around Stripe Checkout and webhooks."""

    def _configure(self) -> None:
        stripe.api_key = get_stripe_api_key()

    def create_checkout_session(
        self,
        request: CheckoutSessionRequest,
        price_id: str,
        *,
        success_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._configure()
        app_url = get_public_app_url().rstrip("/")
        session_metadata = {
            "plan_key": request.plan,
            "customer_key": request.customer_key or "",
        }
        if metadata:
            session_metadata.update({key: str(value) for key, value in metadata.items()})

        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url or f"{app_url}/?commercialPanel=1&checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": cancel_url or f"{app_url}/?commercialPanel=1&checkout=cancelled",
            "allow_promotion_codes": True,
            "metadata": session_metadata,
            "subscription_data": {"metadata": session_metadata},
        }
        if request.email:
            params["customer_email"] = request.email
        return dict(stripe.checkout.Session.create(**params))

    def verify_webhook_signature(self, payload: bytes, signature: str, endpoint_secret: str) -> dict[str, Any]:
        self._configure()
        try:
            event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
            return dict(event)
        except ValueError as e:
            raise ValueError(f"Invalid webhook signature: {e}")
        except stripe.error.SignatureVerificationError as e:
            raise ValueError(f"Signature verification failed: {e}")


# Global Stripe service instance
_stripe_service: StripeService | None = None


def get_stripe_service() -> StripeService:
    global _stripe_service
    if _stripe_service is None:
        _stripe_service = StripeService()
    return _stripe_service
