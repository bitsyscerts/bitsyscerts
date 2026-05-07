"""Bootstrap configuration loaded from BITSYSCERTS_BOOTSTRAP_* env vars.

This is a completely separate settings class from ctpool.config.Settings.
Bootstrap env vars seed the database on first startup only; they do NOT
override database-backed instance settings after the first boot.

Exports:
    BootstrapConfig — Pydantic-settings class for bootstrap env vars.
    get_bootstrap_config — Return a cached BootstrapConfig instance.
"""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class BootstrapConfig(BaseSettings):
    """Bootstrap defaults, used only when no ct_instance_settings row exists.

    All fields are optional; unset fields use the Lite profile defaults.
    The prefix ``BITSYSCERTS_BOOTSTRAP_`` distinguishes these from the
    existing ``CT_*`` worker settings.
    """

    model_config = SettingsConfigDict(
        env_prefix="BITSYSCERTS_BOOTSTRAP_",
        case_sensitive=False,
    )

    profile: str = "lite"
    """Profile to seed when no database settings exist.

    Allowed values: lite, standard, research, archive, custom.
    """
    backfill_days: int | None = None
    cert_storage_mode: str | None = None
    hostname_retention_mode: str | None = None
    cert_retention_days: int | None = None
    observation_retention_days: int | None = None
    entry_outcome_retention_days: int | None = None
    metrics_retention_days: int | None = None


class WorkerRefreshConfig(BaseSettings):
    """Deployment-level worker settings refresh interval.

    Kept separate from BootstrapConfig because it controls runtime behavior
    rather than initial DB seeding.
    """

    model_config = SettingsConfigDict(
        env_prefix="BITSYSCERTS_",
        case_sensitive=False,
    )

    settings_refresh_seconds: int = 60
    """How often workers refresh the active instance settings from the DB."""


@functools.lru_cache(maxsize=1)
def get_bootstrap_config() -> BootstrapConfig:
    """Return a cached BootstrapConfig instance."""
    return BootstrapConfig()


@functools.lru_cache(maxsize=1)
def get_worker_refresh_config() -> WorkerRefreshConfig:
    """Return a cached WorkerRefreshConfig instance."""
    return WorkerRefreshConfig()
