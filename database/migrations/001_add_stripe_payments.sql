"""
Stripe payment integration migration.

This migration creates tables for storing payment and subscription information
linked to API keys.
"""

-- api_key_payments: Maps API keys to Stripe customers
CREATE TABLE IF NOT EXISTS api_key_payments (
    id SERIAL PRIMARY KEY,
    api_key_id VARCHAR(255) NOT NULL UNIQUE,
    stripe_customer_id VARCHAR(255) NOT NULL UNIQUE,
    plan_type VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- payments: Individual payment transaction records
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    stripe_payment_intent_id VARCHAR(255) NOT NULL UNIQUE,
    api_key_id VARCHAR(255) NOT NULL REFERENCES api_key_payments(api_key_id),
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    status VARCHAR(50) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- subscriptions: Subscription records
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    stripe_subscription_id VARCHAR(255) NOT NULL UNIQUE,
    api_key_id VARCHAR(255) NOT NULL REFERENCES api_key_payments(api_key_id),
    plan_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- invoices: Invoice records for accounting
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    stripe_invoice_id VARCHAR(255) NOT NULL UNIQUE,
    subscription_id INTEGER REFERENCES subscriptions(id),
    api_key_id VARCHAR(255) NOT NULL REFERENCES api_key_payments(api_key_id),
    amount_cents INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'usd',
    status VARCHAR(50) NOT NULL,
    paid BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMP,
    due_date TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_api_key_payments_api_key_id ON api_key_payments(api_key_id);
CREATE INDEX idx_api_key_payments_stripe_customer_id ON api_key_payments(stripe_customer_id);
CREATE INDEX idx_payments_api_key_id ON payments(api_key_id);
CREATE INDEX idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);
CREATE INDEX idx_subscriptions_api_key_id ON subscriptions(api_key_id);
CREATE INDEX idx_subscriptions_stripe_subscription_id ON subscriptions(stripe_subscription_id);
CREATE INDEX idx_invoices_api_key_id ON invoices(api_key_id);
CREATE INDEX idx_invoices_stripe_invoice_id ON invoices(stripe_invoice_id);
