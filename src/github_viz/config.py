"""Centralized runtime configuration for Agentic Cure Graph."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from the environment."""

    app_name: str = "Agentic Cure Graph API"
    app_version: str = "0.4.0"
    host: str = "127.0.0.1"
    port: int = 8000
    max_sessions: int = 50
    analysis_workers: int = 4
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings loaded from environment variables."""
    return Settings(
        host=os.getenv("CUREGRAPH_HOST", os.getenv("CODEGRAPH_HOST", "127.0.0.1")),
        port=int(os.getenv("CUREGRAPH_PORT", os.getenv("CODEGRAPH_PORT", "8000"))),
        max_sessions=int(os.getenv("CUREGRAPH_MAX_SESSIONS", os.getenv("CODEGRAPH_MAX_SESSIONS", "50"))),
        analysis_workers=int(os.getenv("CUREGRAPH_ANALYSIS_WORKERS", os.getenv("CODEGRAPH_ANALYSIS_WORKERS", "4"))),
        log_level=os.getenv("CUREGRAPH_LOG_LEVEL", os.getenv("CODEGRAPH_LOG_LEVEL", "INFO")).upper(),
    )
