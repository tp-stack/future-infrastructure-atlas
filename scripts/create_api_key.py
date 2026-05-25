"""Create a hashed commercial API key for a customer.

This script prints the raw key exactly once. Store the hash in the database and
give the raw key to the customer through a secure channel.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atlas.api.security import hash_api_key, key_prefix  # noqa: E402
from atlas.db import run_sql  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a commercial API key")
    parser.add_argument("--customer-key", required=True)
    parser.add_argument("--scopes", default="assets:read,tiles:read,exports:create")
    args = parser.parse_args()

    raw_key = f"fia_{secrets.token_urlsafe(32)}"
    scopes = [scope.strip() for scope in args.scopes.split(",") if scope.strip()]
    run_sql(
        """
        INSERT INTO api_key (customer_id, key_prefix, key_hash, scopes)
        SELECT customer_id, %(key_prefix)s, %(key_hash)s, %(scopes)s
        FROM api_customer
        WHERE customer_key = %(customer_key)s
        """,
        {
            "customer_key": args.customer_key,
            "key_prefix": key_prefix(raw_key),
            "key_hash": hash_api_key(raw_key),
            "scopes": scopes,
        },
    )
    print(raw_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
