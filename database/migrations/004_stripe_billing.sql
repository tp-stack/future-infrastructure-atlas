ALTER TABLE api_plan
    ADD COLUMN IF NOT EXISTS stripe_price_id TEXT,
    ADD COLUMN IF NOT EXISTS price_monthly_cents INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS included_export_jobs INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS extra_extraction_cents INTEGER NOT NULL DEFAULT 0;

ALTER TABLE api_customer
    ADD COLUMN IF NOT EXISTS billing_email TEXT,
    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
    ADD COLUMN IF NOT EXISTS billing_status TEXT NOT NULL DEFAULT 'not_started',
    ADD COLUMN IF NOT EXISTS checkout_session_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_customer_stripe_customer_id
    ON api_customer (stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_api_customer_stripe_subscription_id
    ON api_customer (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_api_customer_billing_status
    ON api_customer (billing_status);

INSERT INTO api_plan (
    plan_key,
    display_name,
    monthly_request_quota,
    monthly_export_quota_mb,
    max_page_size,
    max_export_rows,
    allowed_scopes,
    price_monthly_cents,
    included_export_jobs,
    extra_extraction_cents
) VALUES
(
    'launch',
    'Launch',
    25000,
    500,
    250,
    50000,
    ARRAY['assets:read', 'tiles:read', 'exports:create'],
    29900,
    5,
    4900
),
(
    'scale',
    'Scale',
    250000,
    5000,
    1000,
    500000,
    ARRAY['assets:read', 'tiles:read', 'exports:create'],
    125000,
    50,
    14900
),
(
    'enterprise',
    'Enterprise',
    2000000,
    50000,
    5000,
    5000000,
    ARRAY['assets:read', 'tiles:read', 'exports:create', 'admin:read'],
    490000,
    500,
    0
)
ON CONFLICT (plan_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    monthly_request_quota = EXCLUDED.monthly_request_quota,
    monthly_export_quota_mb = EXCLUDED.monthly_export_quota_mb,
    max_page_size = EXCLUDED.max_page_size,
    max_export_rows = EXCLUDED.max_export_rows,
    allowed_scopes = EXCLUDED.allowed_scopes,
    price_monthly_cents = EXCLUDED.price_monthly_cents,
    included_export_jobs = EXCLUDED.included_export_jobs,
    extra_extraction_cents = EXCLUDED.extra_extraction_cents;
