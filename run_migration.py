"""Run the Stripe payment migration."""

import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg is not installed. Run: pip install psycopg")
    sys.exit(1)

# Read the migration file
migration_file = Path(__file__).parent / "database" / "migrations" / "001_add_stripe_payments.sql"
if not migration_file.exists():
    print(f"ERROR: Migration file not found at {migration_file}")
    sys.exit(1)

sql_content = migration_file.read_text()

# Connect to database
try:
    conn = psycopg.connect(
        "postgresql://future_atlas:future_atlas_dev_password@localhost:5432/future_atlas"
    )
except psycopg.OperationalError as e:
    print(f"ERROR: Could not connect to database: {e}")
    print("Make sure PostgreSQL is running and credentials are correct")
    sys.exit(1)

# Execute migration
try:
    with conn.cursor() as cur:
        cur.execute(sql_content)
    conn.commit()
    print("✅ Migration completed successfully!")
    print("Created tables: api_key_payments, payments, subscriptions, invoices")
except Exception as e:
    print(f"ERROR: Migration failed: {e}")
    conn.rollback()
    sys.exit(1)
finally:
    conn.close()
