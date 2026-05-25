"""Tests for startup isolation (Stripe-free import) and storage cleanup."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from atlas.site_selection.persistence import cleanup_old_queries, STORAGE_DIR, _is_storage_writable


def test_import_payments_without_stripe():
    """atlas.payments module must import without stripe package installed."""
    import importlib
    import sys

    if "stripe" in sys.modules:
        del sys.modules["stripe"]

    from atlas.payments import is_stripe_available, StripeService
    assert is_stripe_available() is False

    svc = StripeService()
    assert svc is not None


def test_app_factory_can_import_without_stripe():
    """create_app must not crash when stripe is unavailable."""
    from atlas.api.app import create_app

    app = create_app()
    assert app is not None
    assert app.title == "FUTURE Infrastructure Atlas Commercial API"


def test_site_selection_router_importable():
    """site_selection router must remain importable regardless of Stripe status."""
    import importlib
    import sys

    if "stripe" in sys.modules:
        del sys.modules["stripe"]

    from atlas.site_selection.api import router
    assert len(router.routes) >= 6


def test_cleanup_removes_old_files():
    """cleanup_old_queries removes files older than max_age_days."""
    import atlas.site_selection.persistence as p

    old_dir = p.STORAGE_DIR
    p._storage_writable = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        p.STORAGE_DIR = tmp_path
        p._storage_writable = None

        old_file = tmp_path / "old_query.jsonl"
        old_file.write_text('{"test": true}\n')
        old_mtime = 1000000000  # 2001-09-09
        os.utime(str(old_file), (old_mtime, old_mtime))

        new_file = tmp_path / "new_query.jsonl"
        new_file.write_text('{"test": true}\n')

        removed = cleanup_old_queries(max_age_days=1)
        assert removed == 1
        assert not old_file.exists()
        assert new_file.exists()

    p.STORAGE_DIR = old_dir
    p._storage_writable = None


def test_cleanup_returns_zero_when_not_writable():
    """cleanup_old_queries returns 0 in read-only/serverless environments."""
    import atlas.site_selection.persistence as p

    old_writable = p._storage_writable
    old_dir = p.STORAGE_DIR
    try:
        p._storage_writable = False
        result = cleanup_old_queries(max_age_days=1)
        assert result == 0
    finally:
        p._storage_writable = old_writable
        p.STORAGE_DIR = old_dir


def test_cleanup_uses_env_var_default():
    """cleanup_old_queries reads SITE_SELECTION_RETENTION_DAYS from env."""
    import atlas.site_selection.persistence as p

    old_dir = p.STORAGE_DIR
    p._storage_writable = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        p.STORAGE_DIR = tmp_path
        p._storage_writable = None

        old_file = tmp_path / "very_old.jsonl"
        old_file.write_text('{"test": true}\n')
        old_mtime = 1000000000
        os.utime(str(old_file), (old_mtime, old_mtime))

        with patch.dict(os.environ, {"SITE_SELECTION_RETENTION_DAYS": "365"}):
            removed = cleanup_old_queries()
            assert removed == 1

    p.STORAGE_DIR = old_dir
    p._storage_writable = None
