"""Logging setup helpers.

This project uses standard-library logging with a compact structured format
that is suitable for local development and hosted logs.
"""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Initialize root logging configuration once.

    The function is idempotent and safe to call from both CLI and API startup.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
