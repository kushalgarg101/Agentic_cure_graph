"""Centralized runtime configuration for Agentic Cure Graph."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings loaded from the environment."""

    app_name: str = "Agentic Cure Graph API"
    app_version: str = "0.5.0"
    host: str = "127.0.0.1"
    port: int = 8000
    max_sessions: int = 50
    analysis_workers: int = 4
    log_level: str = "INFO"
    db_path: Path = Path("var/agentic_cure_graph.db")
    allow_origins: tuple[str, ...] = ("*",)
    extra_provider_paths: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings loaded from environment variables."""
    origins = tuple(
        item.strip()
        for item in os.getenv("CUREGRAPH_ALLOW_ORIGINS", "*").split(",")
        if item.strip()
    ) or ("*",)
    provider_paths = tuple(
        item.strip()
        for item in os.getenv("CUREGRAPH_EVIDENCE_PROVIDER_PATHS", "").split(os.pathsep)
        if item.strip()
    )
    return Settings(
        host=os.getenv("CUREGRAPH_HOST", "127.0.0.1"),
        port=int(os.getenv("CUREGRAPH_PORT", "8000")),
        max_sessions=int(os.getenv("CUREGRAPH_MAX_SESSIONS", "50")),
        analysis_workers=int(os.getenv("CUREGRAPH_ANALYSIS_WORKERS", "4")),
        log_level=os.getenv("CUREGRAPH_LOG_LEVEL", "INFO").upper(),
        db_path=Path(os.getenv("CUREGRAPH_DB_PATH", "var/agentic_cure_graph.db")),
        allow_origins=origins,
        extra_provider_paths=provider_paths,
    )
