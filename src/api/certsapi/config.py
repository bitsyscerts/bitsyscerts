"""Application configuration loaded from environment variables via pydantic-settings."""

from __future__ import annotations

import functools

from pydantic import AliasChoices, Field, PostgresDsn
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

    # Application metadata
    app_name: str = "BitsyCerts API"
    app_version: str = "0.1.0"

    # Pagination defaults
    default_page_limit: int = 50
    max_page_limit: int = 200

    # Operator stats power the bundled dashboard and are enabled by default
    # for self-hosted workstation, lab, and local Docker Compose deployments.
    # Unusual deployments can explicitly disable them behind a gateway.
    expose_stats_api: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "expose_stats_api",
            "BITSYSCERTS_EXPOSE_STATS_API",
            "EXPOSE_STATS_API",
        ),
    )

    # Sprint 5: how old a stats snapshot may be before the API marks it stale.
    # The dashboard surfaces ``is_stale=true`` so the operator never reads
    # stale numbers as current.  Must be greater than the snapshotter cadence
    # (``ct_stats_heavy_refresh_seconds``, default 300 s).  The default of
    # 360 s tolerates a full refresh cycle plus a one-cycle margin.
    stats_stale_seconds: int = 360


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()  # type: ignore[call-arg]
