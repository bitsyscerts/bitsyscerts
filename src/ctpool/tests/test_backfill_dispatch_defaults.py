"""Tests for default backfill dispatch settings."""

from __future__ import annotations

from ctpool.config import Settings


def test_default_dispatch_mode_is_per_log() -> None:
    """Sprint 1B: default mode is per-log, not legacy-ranges."""
    settings = Settings.model_validate(
        {"database_url": "postgresql+psycopg://x:y@h/db"}
    )

    assert settings.ct_backfill_dispatch_mode == "per-log"
