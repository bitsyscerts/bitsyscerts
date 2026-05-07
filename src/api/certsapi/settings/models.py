"""Pydantic models for the storage settings API endpoints.

Mirrors ctpool ORM fields; no direct database imports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StorageSettingsResponse(BaseModel):
    """Active instance storage settings returned by GET /v1/settings/storage."""

    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    backfill_days: int
    cert_retention_days: int
    observation_retention_days: int
    entry_outcome_retention_days: int
    metrics_retention_days: int
    settings_hash: str
    updated_at: datetime
    updated_by: str | None = None
    source: Literal["database"] = "database"


class UpdateStorageSettingsRequest(BaseModel):
    """Request body for PUT /v1/settings/storage."""

    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    backfill_days: int = Field(ge=0)
    cert_retention_days: int = Field(ge=0)
    observation_retention_days: int = Field(ge=0)
    entry_outcome_retention_days: int = Field(ge=0)
    metrics_retention_days: int = Field(ge=1)
    updated_by: str | None = None
    archive_explicit_optin: bool = False
    """Must be True when storage_profile is 'archive'."""


class UpdateStorageSettingsResult(BaseModel):
    """Response body for PUT /v1/settings/storage."""

    status: Literal["updated"]
    storage_profile: str
    settings_hash: str
    message: str
    recommended_actions: list[str] = Field(default_factory=list)


class StorageSettingsHistoryItem(BaseModel):
    """One entry from the settings history table."""

    settings_hash: str
    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    backfill_days: int
    cert_retention_days: int
    observation_retention_days: int
    entry_outcome_retention_days: int
    metrics_retention_days: int
    first_seen_at: datetime
    last_seen_at: datetime
    is_current: bool
