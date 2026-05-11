"""Logging setup for Atlas utilities."""

from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    """Configure process-wide logging with a simple production-readable format."""

    log_level = level or os.getenv("ATLAS_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
