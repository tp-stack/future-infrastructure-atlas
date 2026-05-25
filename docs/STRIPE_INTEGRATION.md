# Stripe Payment Integration Guide

This document explains how to integrate and use Stripe payments in the FUTURE Infrastructure Atlas API.

## Setup

### 1. Install Dependencies

Dependencies have been added to `pyproject.toml`. Install them with:

```bash
pip install -e .
```

Or to update an existing environment:

```bash
pip install stripe python-dotenv
```

### 2. Set Up Database

Apply the payment schema migration to your PostgreSQL database:

```bash
psql -U future_atlas -d future_atlas < database/migrations/001_add_stripe_payments.sql
```

This creates the following tables:
- `api_key_payments` - Maps API keys to Stripe customers
- `payments` - Individual payment transaction records  
- `subscriptions` - Subscription records
- `invoices` - Invoice records for accounting

### 3. Configure Environment Variables

Create a `.env` file in the project root with your Stripe credentials:

```bash
# Stripe API Keys (from https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_live_your_secret_key_here  # Production: sk_live_***, Testing: sk_test_***
STRIPE_PUBLIC_KEY=pk_live_your_public_key_here  # For frontend (optional for server integration)

# Stripe Webhook Secret (from https://dashboard.stripe.com/webhooks)
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

**Production vs Testing:**
- For testing: Use test mode keys from the Stripe dashboard (`sk_test_*`, `pk_test_*`)
- For production: Use live mode keys (`sk_live_*`, `pk_live_*`)

### 4. Configure Stripe Products and Prices

In the Stripe dashboard, create products and prices for your subscription plans:

1. Go to [Products](https://dashboard.stripe.com/products)
2. Create products (e.g., "Atlas Starter", "Atlas Professional")
3. Add prices to each product with your pricing
4. Note the Price IDs (format: `price_XXXXX`) for use in API calls

### 5. Set Up Webhooks

To receive real-time payment events:

1. Go to [Webhooks](https://dashboard.stripe.com/webhooks)
2. Click "Add endpoint"
3. Enter your webhook URL: `https://your-domain.com/v1/webhooks/stripe`
4. Select events to receive:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.created`
   - `invoice.paid`
   - `invoice.payment_failed`
   - `charge.refunded`
5. Copy the signing secret and set as `STRIPE_WEBHOOK_SECRET`

## API Endpoints

All payment endpoints require authentication via `X-API-Key` header.

### Payment Intents (One-Time Payments)

#### Create a payment intent

```bash
curl -X POST https://your-api.com/v1/payments/payment-intents \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_cents": 10000,
    "currency": "usd",
    "description": "Data export fee"
  }'
```

**Response:**
```json
{
  "client_secret": "pi_XXXXX_secret_XXXXX",
  "payment_intent_id": "pi_XXXXX",
  "amount_cents": 10000,
  "currency": "usd",
  "status": "requires_payment_method",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Get payment intent status

```bash
curl https://your-api.com/v1/payments/payment-intents/pi_XXXXX \
  -H "X-API-Key: your_api_key"
```

### Subscriptions

#### Create a subscription

```bash
curl -X POST https://your-api.com/v1/payments/subscriptions \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "price_id": "price_XXXXX",
    "plan_type": "professional",
    "metadata": {
      "custom_field": "value"
    }
  }'
```

**Response:**
```json
{
  "subscription_id": "sub_XXXXX",
  "customer_id": "cus_XXXXX",
  "plan_type": "professional",
  "status": "active",
  "current_period_start": "2024-01-15T10:30:00Z",
  "current_period_end": "2024-02-15T10:30:00Z",
  "cancel_at_period_end": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Get subscription status

```bash
curl https://your-api.com/v1/payments/subscriptions/sub_XXXXX \
  -H "X-API-Key: your_api_key"
```

#### Update subscription (change plan)

```bash
curl -X PATCH https://your-api.com/v1/payments/subscriptions/sub_XXXXX \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "price_id": "price_XXXXX_new",
    "plan_type": "enterprise"
  }'
```

#### Cancel subscription

```bash
curl -X POST https://your-api.com/v1/payments/subscriptions/sub_XXXXX/cancel \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "immediately": false
  }'
```

- `"immediately": true` - Cancel subscription immediately
- `"immediately": false` - Cancel at the end of the current billing period

## Frontend Integration

For client-side payment processing with Stripe.js:

1. Get the client secret from the payment intent endpoint
2. Use Stripe.js library on the frontend:

```javascript
const stripe = Stripe('pk_test_...');  // Use STRIPE_PUBLIC_KEY from .env
const elements = stripe.elements();
const cardElement = elements.create('card');
cardElement.mount('#card-element');

// Confirm payment
stripe.confirmCardPayment(clientSecret, {
  payment_method: {
    card: cardElement,
  },
});
```

## Database Operations

### Query current subscriptions

```sql
SELECT * FROM subscriptions 
WHERE api_key_id = 'your_api_key_id' 
  AND status IN ('active', 'past_due');
```

### Query payment history

```sql
SELECT * FROM payments 
WHERE api_key_id = 'your_api_key_id'
ORDER BY created_at DESC;
```

### Query invoices

```sql
SELECT * FROM invoices 
WHERE api_key_id = 'your_api_key_id'
ORDER BY created_at DESC;
```

## Error Handling

The API returns standard HTTP status codes:

- `400 Bad Request` - Invalid request format
- `401 Unauthorized` - Missing/invalid API key or invalid Stripe signature
- `403 Forbidden` - API key lacks required permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists
- `500 Internal Server Error` - Server error

## Testing

### Using Stripe Test Mode

Use these test card numbers in test mode:

| Card Number | Expiry | CVC | Result |
|---|---|---|---|
| 4242 4242 4242 4242 | Any future date | Any 3 digits | Successful payment |
| 4000 0000 0000 0002 | Any future date | Any 3 digits | Payment declined |
| 3782 822463 10005 | Any future date | Any 4 digits | Amex test card |

### Test Webhook Locally

Use Stripe CLI to forward webhooks to your local development environment:

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to localhost:8000/v1/webhooks/stripe
```

This will output a webhook signing secret for testing.

## Production Checklist

- [ ] Verify `STRIPE_SECRET_KEY` uses `sk_live_` prefix
- [ ] Verify `STRIPE_PUBLIC_KEY` uses `pk_live_` prefix  
- [ ] Configure webhook signing secret in `.env`
- [ ] Set up all required webhook events in Stripe dashboard
- [ ] Test end-to-end payment flow with live test card
- [ ] Enable webhooks in production Stripe account
- [ ] Monitor webhook delivery in Stripe dashboard
- [ ] Set up payment reconciliation process
- [ ] Implement backup payment failure notifications
- [ ] Document payment refund policy in terms of service

## Troubleshooting

### Webhook signature verification fails

- Verify `STRIPE_WEBHOOK_SECRET` is correct
- Check that webhook endpoint is accessible from the internet
- Ensure request body is not being modified/parsed before webhook handler

### Payment intent not found

- Verify the payment intent ID exists and belongs to the current customer
- Check that payments are being created in the database

### Subscription not active

- Verify customer has a valid payment method on file
- Check Stripe dashboard for payment failures
- Review webhook logs for subscription events

### Database connection errors

- Verify PostgreSQL is running and accessible
- Check `DATABASE_URL` environment variable
- Verify database user has permission to create tables

## Additional Resources

- [Stripe Documentation](https://stripe.com/docs)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Stripe Python SDK](https://github.com/stripe/stripe-python)
- [Stripe CLI](https://stripe.com/docs/stripe-cli)
