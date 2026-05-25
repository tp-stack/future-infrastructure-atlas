"""Repository for payment data persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from atlas import db


class PaymentRepository:
    """Repository for managing payment and subscription data."""

    @staticmethod
    def create_payment(
        stripe_payment_intent_id: str,
        api_key_id: str,
        amount_cents: int,
        currency: str,
        status: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a payment record."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payments 
                    (stripe_payment_intent_id, api_key_id, amount_cents, currency, status, description, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, stripe_payment_intent_id, api_key_id, amount_cents, currency, status, created_at, updated_at
                    """,
                    (
                        stripe_payment_intent_id,
                        api_key_id,
                        amount_cents,
                        currency,
                        status,
                        description,
                        metadata or {},
                    ),
                )
                result = cur.fetchone()
            conn.commit()
        return result

    @staticmethod
    def update_payment_status(stripe_payment_intent_id: str, status: str) -> dict[str, Any]:
        """Update payment status."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE payments 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE stripe_payment_intent_id = %s
                    RETURNING id, stripe_payment_intent_id, api_key_id, amount_cents, currency, status, created_at, updated_at
                    """,
                    (status, stripe_payment_intent_id),
                )
                result = cur.fetchone()
            conn.commit()
        return result

    @staticmethod
    def get_payment(stripe_payment_intent_id: str) -> dict[str, Any] | None:
        """Get a payment by Stripe ID."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM payments WHERE stripe_payment_intent_id = %s",
                    (stripe_payment_intent_id,),
                )
                return cur.fetchone()

    @staticmethod
    def create_subscription(
        stripe_subscription_id: str,
        api_key_id: str,
        plan_type: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a subscription record."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subscriptions 
                    (stripe_subscription_id, api_key_id, plan_type, status, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, stripe_subscription_id, api_key_id, plan_type, status, 
                              current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at
                    """,
                    (
                        stripe_subscription_id,
                        api_key_id,
                        plan_type,
                        status,
                        metadata or {},
                    ),
                )
                result = cur.fetchone()
            conn.commit()
        return result

    @staticmethod
    def update_subscription(
        stripe_subscription_id: str,
        status: str | None = None,
        plan_type: str | None = None,
        current_period_start: datetime | None = None,
        current_period_end: datetime | None = None,
        cancel_at_period_end: bool | None = None,
    ) -> dict[str, Any]:
        """Update a subscription record."""
        updates = []
        params = []

        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if plan_type is not None:
            updates.append("plan_type = %s")
            params.append(plan_type)
        if current_period_start is not None:
            updates.append("current_period_start = %s")
            params.append(current_period_start)
        if current_period_end is not None:
            updates.append("current_period_end = %s")
            params.append(current_period_end)
        if cancel_at_period_end is not None:
            updates.append("cancel_at_period_end = %s")
            params.append(cancel_at_period_end)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(stripe_subscription_id)

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                query = f"""
                    UPDATE subscriptions 
                    SET {", ".join(updates)}
                    WHERE stripe_subscription_id = %s
                    RETURNING id, stripe_subscription_id, api_key_id, plan_type, status, 
                              current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at
                    """
                cur.execute(query, params)
                result = cur.fetchone()
            conn.commit()
        return result

    @staticmethod
    def get_subscription(stripe_subscription_id: str) -> dict[str, Any] | None:
        """Get a subscription by Stripe ID."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM subscriptions WHERE stripe_subscription_id = %s",
                    (stripe_subscription_id,),
                )
                return cur.fetchone()

    @staticmethod
    def get_subscription_by_api_key(api_key_id: str) -> dict[str, Any] | None:
        """Get active subscription for an API key."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM subscriptions 
                    WHERE api_key_id = %s AND status IN ('active', 'past_due')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (api_key_id,),
                )
                return cur.fetchone()

    @staticmethod
    def create_invoice(
        stripe_invoice_id: str,
        api_key_id: str,
        amount_cents: int,
        currency: str,
        status: str,
        subscription_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an invoice record."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoices 
                    (stripe_invoice_id, subscription_id, api_key_id, amount_cents, currency, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, stripe_invoice_id, subscription_id, api_key_id, amount_cents, 
                              currency, status, paid, paid_at, created_at, updated_at
                    """,
                    (
                        stripe_invoice_id,
                        subscription_id,
                        api_key_id,
                        amount_cents,
                        currency,
                        status,
                        metadata or {},
                    ),
                )
                result = cur.fetchone()
            conn.commit()
        return result

    @staticmethod
    def update_invoice_status(
        stripe_invoice_id: str,
        status: str,
        paid: bool | None = None,
    ) -> dict[str, Any]:
        """Update invoice status."""
        updates = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
        params = [status]

        if paid is not None:
            updates.insert(1, "paid = %s")
            params.insert(1, paid)
            if paid:
                updates.insert(2, "paid_at = CURRENT_TIMESTAMP")

        params.append(stripe_invoice_id)

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                query = f"""
                    UPDATE invoices 
                    SET {", ".join(updates)}
                    WHERE stripe_invoice_id = %s
                    RETURNING id, stripe_invoice_id, subscription_id, api_key_id, amount_cents, 
                              currency, status, paid, paid_at, created_at, updated_at
                    """
                cur.execute(query, params)
                result = cur.fetchone()
            conn.commit()
        return result
