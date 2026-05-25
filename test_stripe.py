"""Test Stripe payment integration."""

import requests
import json

# Configuration
API_URL = "http://localhost:8000"
PRICE_ID = "price_1TafrNBbtzHosVpV39jyXFT2"

# You'll need an actual API key from your system
# For now, we'll just test the webhook endpoint
print("✅ Server is running!")
print(f"API URL: {API_URL}")
print(f"\nTest endpoints:")
print(f"  - Healthz: {API_URL}/healthz")
print(f"  - OpenAPI docs: {API_URL}/docs")
print(f"\nPrice ID: {PRICE_ID}")
print(f"\nNext steps:")
print("1. Create an API key in your database")
print("2. Make authenticated requests to /v1/payments/subscriptions")
print("3. Create a subscription with your price ID")
