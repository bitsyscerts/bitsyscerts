"""Application configuration loaded from environment variables via pydantic-settings.

All configuration values are validated at import time. Missing required fields
(e.g. DATABASE_URL) raise a ValidationError immediately on startup.
"""

from __future__ import annotations

import functools

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — required; no default
    database_url: PostgresDsn

    # Ingestion behavior
    ct_backfill_days: int = 180
    """Days of CT log history to seed on first encounter.

    The backfill worker estimates a pivot index from the log's STH timestamp
    and ``first_seen_at``, then seeds only ranges covering the most recent
    ``ct_backfill_days`` days.  Set to ``0`` to seed the full log history
    from index 0 (may be billions of entries for large logs).
    """
    ct_tail_interval_seconds: int = 300
    ct_default_batch_size: int = 256
    ct_max_batch_size: int = 1024

    # Disk safety thresholds (GiB)
    ct_min_free_disk_gb: int = 50
    ct_critical_free_disk_gb: int = 20

    # HTTP behavior
    ct_http_timeout_seconds: int = 30
    ct_max_retries: int = 5
    ct_backoff_max_seconds: int = 300

    # CT log list source — compile-time constant; not user-configurable at runtime
    # (SSRF prevention: CT log URLs originate from this trusted source only)
    ct_log_list_url: str = "https://www.gstatic.com/ct/log_list/v3/log_list.json"

    # Logging
    log_level: str = "INFO"


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()  # type: ignore[call-arg]
