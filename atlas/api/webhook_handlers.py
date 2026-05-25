"""Webhook handlers for Stripe events."""

from __future__ import annotations

import logging
import os
from typing import Any

from atlas.api.payment_repository import PaymentRepository
from atlas.payments import get_stripe_service


logger = logging.getLogger(__name__)


def get_webhook_secret() -> str:
    """Get Stripe webhook secret from environment."""
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise ValueError(
            "STRIPE_WEBHOOK_SECRET environment variable not set. "
            "Set it with your webhook endpoint secret from the Stripe dashboard"
        )
    return secret


class StripeWebhookHandler:
    """Handler for Stripe webhook events."""

    @staticmethod
    def handle_payment_intent_succeeded(event: dict[str, Any]) -> None:
        """Handle payment_intent.succeeded event."""
        payment_intent = event["data"]["object"]
        logger.info(f"Payment intent succeeded: {payment_intent['id']}")

        PaymentRepository.update_payment_status(
            stripe_payment_intent_id=payment_intent["id"],
            status="succeeded",
        )

    @staticmethod
    def handle_payment_intent_payment_failed(event: dict[str, Any]) -> None:
        """Handle payment_intent.payment_failed event."""
        payment_intent = event["data"]["object"]
        logger.error(f"Payment intent failed: {payment_intent['id']}")

        PaymentRepository.update_payment_status(
            stripe_payment_intent_id=payment_intent["id"],
            status="failed",
        )

    @staticmethod
    def handle_customer_subscription_created(event: dict[str, Any]) -> None:
        """Handle customer.subscription.created event."""
        subscription = event["data"]["object"]
        logger.info(f"Subscription created: {subscription['id']}")

        # Subscription is already created via API, but we can update any extra info here
        PaymentRepository.update_subscription(
            stripe_subscription_id=subscription["id"],
            status=subscription["status"],
            current_period_start=subscription.get("current_period_start"),
            current_period_end=subscription.get("current_period_end"),
        )

    @staticmethod
    def handle_customer_subscription_updated(event: dict[str, Any]) -> None:
        """Handle customer.subscription.updated event."""
        subscription = event["data"]["object"]
        logger.info(f"Subscription updated: {subscription['id']}")

        PaymentRepository.update_subscription(
            stripe_subscription_id=subscription["id"],
            status=subscription["status"],
            current_period_start=subscription.get("current_period_start"),
            current_period_end=subscription.get("current_period_end"),
            cancel_at_period_end=subscription.get("cancel_at_period_end"),
        )

    @staticmethod
    def handle_customer_subscription_deleted(event: dict[str, Any]) -> None:
        """Handle customer.subscription.deleted event."""
        subscription = event["data"]["object"]
        logger.info(f"Subscription deleted: {subscription['id']}")

        PaymentRepository.update_subscription(
            stripe_subscription_id=subscription["id"],
            status="canceled",
        )

    @staticmethod
    def handle_invoice_created(event: dict[str, Any]) -> None:
        """Handle invoice.created event."""
        invoice = event["data"]["object"]
        logger.info(f"Invoice created: {invoice['id']}")

        # Try to find the subscription
        subscription_id = None
        if invoice.get("subscription"):
            subscription_record = PaymentRepository.get_subscription(invoice["subscription"])
            if subscription_record:
                subscription_id = subscription_record["id"]

        # Get API key from subscription or customer metadata
        api_key_id = invoice.get("metadata", {}).get("api_key_id")
        if not api_key_id and subscription_record:
            api_key_id = subscription_record["api_key_id"]

        if api_key_id:
            PaymentRepository.create_invoice(
                stripe_invoice_id=invoice["id"],
                api_key_id=api_key_id,
                subscription_id=subscription_id,
                amount_cents=invoice.get("amount_due", 0),
                currency=invoice.get("currency", "usd"),
                status=invoice["status"],
            )

    @staticmethod
    def handle_invoice_paid(event: dict[str, Any]) -> None:
        """Handle invoice.paid event."""
        invoice = event["data"]["object"]
        logger.info(f"Invoice paid: {invoice['id']}")

        PaymentRepository.update_invoice_status(
            stripe_invoice_id=invoice["id"],
            status=invoice["status"],
            paid=True,
        )

    @staticmethod
    def handle_invoice_payment_failed(event: dict[str, Any]) -> None:
        """Handle invoice.payment_failed event."""
        invoice = event["data"]["object"]
        logger.warning(f"Invoice payment failed: {invoice['id']}")

        PaymentRepository.update_invoice_status(
            stripe_invoice_id=invoice["id"],
            status=invoice["status"],
            paid=False,
        )

    @staticmethod
    def handle_charge_refunded(event: dict[str, Any]) -> None:
        """Handle charge.refunded event."""
        charge = event["data"]["object"]
        logger.info(f"Charge refunded: {charge['id']}")

        if charge.get("payment_intent"):
            PaymentRepository.update_payment_status(
                stripe_payment_intent_id=charge["payment_intent"],
                status="refunded",
            )


# Map event types to handlers
EVENT_HANDLERS = {
    "payment_intent.succeeded": StripeWebhookHandler.handle_payment_intent_succeeded,
    "payment_intent.payment_failed": StripeWebhookHandler.handle_payment_intent_payment_failed,
    "customer.subscription.created": StripeWebhookHandler.handle_customer_subscription_created,
    "customer.subscription.updated": StripeWebhookHandler.handle_customer_subscription_updated,
    "customer.subscription.deleted": StripeWebhookHandler.handle_customer_subscription_deleted,
    "invoice.created": StripeWebhookHandler.handle_invoice_created,
    "invoice.paid": StripeWebhookHandler.handle_invoice_paid,
    "invoice.payment_failed": StripeWebhookHandler.handle_invoice_payment_failed,
    "charge.refunded": StripeWebhookHandler.handle_charge_refunded,
}


def process_webhook_event(event: dict[str, Any]) -> None:
    """Process a Stripe webhook event."""
    event_type = event["type"]
    handler = EVENT_HANDLERS.get(event_type)

    if handler:
        try:
            handler(event)
            logger.info(f"Successfully handled event {event['id']} (type: {event_type})")
        except Exception as e:
            logger.error(f"Error handling webhook event {event['id']}: {e}", exc_info=True)
    else:
        logger.debug(f"No handler for event type: {event_type}")
