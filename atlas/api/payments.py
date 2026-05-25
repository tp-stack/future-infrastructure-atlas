"""Payment service for Stripe integration."""

from __future__ import annotations

from atlas.api.payment_models import PaymentIntentResponse, SubscriptionResponse
from atlas.api.payment_repository import PaymentRepository
from atlas.payments import get_stripe_service


async def create_payment_intent_service(
    api_key_id: str,
    customer_id: str,
    amount_cents: int,
    currency: str = "usd",
    description: str | None = None,
    metadata: dict | None = None,
) -> PaymentIntentResponse:
    """Create a payment intent."""
    stripe_service = get_stripe_service()

    # Get or create customer
    customer = stripe_service.get_or_create_customer(
        api_key_id=api_key_id,
        metadata={"customer_id": customer_id},
    )

    # Create payment intent
    payment_intent = stripe_service.create_payment_intent(
        customer_id=customer.id,
        amount_cents=amount_cents,
        currency=currency,
        description=description,
        metadata=metadata or {},
    )

    # Store in database
    PaymentRepository.create_payment(
        stripe_payment_intent_id=payment_intent.id,
        api_key_id=api_key_id,
        amount_cents=amount_cents,
        currency=currency,
        status=payment_intent.status,
        description=description,
        metadata=metadata or {},
    )

    return PaymentIntentResponse(
        client_secret=payment_intent.client_secret,
        payment_intent_id=payment_intent.id,
        amount_cents=amount_cents,
        currency=currency,
        status=payment_intent.status,
        created_at=payment_intent.created,
    )


async def create_subscription_service(
    api_key_id: str,
    customer_id: str,
    price_id: str,
    plan_type: str | None = None,
    metadata: dict | None = None,
) -> SubscriptionResponse:
    """Create a subscription."""
    stripe_service = get_stripe_service()

    # Get or create customer
    customer = stripe_service.get_or_create_customer(
        api_key_id=api_key_id,
        metadata={"customer_id": customer_id},
    )

    # Create subscription
    subscription = stripe_service.create_subscription(
        customer_id=customer.id,
        price_id=price_id,
        metadata=metadata or {"plan_type": plan_type},
    )

    # Store in database
    PaymentRepository.create_subscription(
        stripe_subscription_id=subscription.id,
        api_key_id=api_key_id,
        plan_type=plan_type or "custom",
        status=subscription.status,
        metadata=metadata or {},
    )

    # Update the subscription metadata in DB with period info
    if hasattr(subscription, "current_period_start") and hasattr(subscription, "current_period_end"):
        PaymentRepository.update_subscription(
            stripe_subscription_id=subscription.id,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
        )

    return SubscriptionResponse(
        subscription_id=subscription.id,
        customer_id=customer.id,
        plan_type=plan_type or "custom",
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        created_at=subscription.created,
    )
    """Cancel a subscription."""
    stripe_service = get_stripe_service()

    # Verify subscription belongs to this customer
    subscription_record = PaymentRepository.get_subscription(subscription_id)
    if not subscription_record or subscription_record["api_key_id"] != auth_context.api_key_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    # Cancel in Stripe
    subscription = stripe_service.cancel_subscription(
        subscription_id=subscription_id,
        immediately=request.immediately,
    )

    # Update in database
    PaymentRepository.update_subscription(
        stripe_subscription_id=subscription_id,
        status=subscription.status,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )

    return SubscriptionResponse(
        subscription_id=subscription.id,
        customer_id=subscription.customer,
        plan_type=subscription_record["plan_type"],
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        created_at=subscription.created,
    )
