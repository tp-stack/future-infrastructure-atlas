"""Authentication and signing helpers for commercial API access."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlencode


API_KEY_HEADER = "X-API-Key"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def key_prefix(api_key: str) -> str:
    return api_key[:12]


def signing_secret() -> bytes:
    return os.environ.get("ATLAS_SIGNING_SECRET", "atlas-dev-signing-secret").encode("utf-8")


def sign_path(path_or_url: str, *, expires_in_seconds: int = 900) -> str:
    expires = int(time.time()) + expires_in_seconds
    payload = f"{path_or_url}:{expires}".encode("utf-8")
    signature = hmac.new(signing_secret(), payload, hashlib.sha256).hexdigest()
    separator = "&" if "?" in path_or_url else "?"
    return f"{path_or_url}{separator}{urlencode({'expires': expires, 'signature': signature})}"
