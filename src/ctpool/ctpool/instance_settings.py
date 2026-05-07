"""CRUD helpers for the ct_instance_settings table.

Exports:
    get_active_settings — Return the active settings row or None.
    bootstrap_settings_from_env — Seed settings on first boot from env vars.
    update_settings — Validate and write a new settings payload to the DB.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.bootstrap_config import BootstrapConfig
from ctpool.models.instance_settings import CtInstanceSettings
from ctpool.profile_defaults import defaults_for_profile
from ctpool.storage_modes import CertStorageMode, StorageProfile
from ctpool.storage_settings_history import (
    compute_settings_hash_from_dict,
    record_profile_from_dict,
)

_VALID_PROFILES = {p.value for p in StorageProfile}
_VALID_MODES = {m.value for m in CertStorageMode}


async def get_active_settings(
    session: AsyncSession,
) -> CtInstanceSettings | None:
    """Return the most-recently-updated instance settings row, or None.

    Args:
        session: Active async database session.

    Returns:
        The active settings row, or None if the table is empty.
    """
    result = await session.execute(
        select(CtInstanceSettings)
        .order_by(CtInstanceSettings.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _apply_overrides(
    defaults: dict[str, Any],
    bootstrap: BootstrapConfig,
) -> dict[str, Any]:
    """Return defaults merged with non-None bootstrap overrides."""
    merged = dict(defaults)
    if bootstrap.backfill_days is not None:
        merged["backfill_days"] = bootstrap.backfill_days
    if bootstrap.cert_storage_mode is not None:
        merged["cert_storage_mode"] = bootstrap.cert_storage_mode
    if bootstrap.hostname_retention_mode is not None:
        merged["hostname_retention_mode"] = bootstrap.hostname_retention_mode
    if bootstrap.cert_retention_days is not None:
        merged["cert_retention_days"] = bootstrap.cert_retention_days
    if bootstrap.observation_retention_days is not None:
        merged["observation_retention_days"] = bootstrap.observation_retention_days
    if bootstrap.entry_outcome_retention_days is not None:
        merged["entry_outcome_retention_days"] = bootstrap.entry_outcome_retention_days
    if bootstrap.metrics_retention_days is not None:
        merged["metrics_retention_days"] = bootstrap.metrics_retention_days
    return merged


async def bootstrap_settings_from_env(
    session: AsyncSession,
    bootstrap: BootstrapConfig,
) -> CtInstanceSettings:
    """Seed instance settings on first boot if no row exists.

    Does nothing if a settings row already exists; always returns the
    currently active row after the call.

    Args:
        session: Active async database session.
        bootstrap: Bootstrap configuration from env vars.

    Returns:
        The active settings row (newly created or pre-existing).
    """
    existing = await get_active_settings(session)
    if existing is not None:
        return existing

    profile = StorageProfile(bootstrap.profile)
    payload = _apply_overrides(defaults_for_profile(profile), bootstrap)
    settings_hash = compute_settings_hash_from_dict(payload)
    now = datetime.now(UTC)

    row = CtInstanceSettings(
        id=uuid.uuid4(),
        storage_profile=payload["storage_profile"],
        cert_storage_mode=payload["cert_storage_mode"],
        hostname_retention_mode=payload["hostname_retention_mode"],
        backfill_days=payload["backfill_days"],
        cert_retention_days=payload["cert_retention_days"],
        observation_retention_days=payload["observation_retention_days"],
        entry_outcome_retention_days=payload["entry_outcome_retention_days"],
        metrics_retention_days=payload["metrics_retention_days"],
        created_at=now,
        updated_at=now,
        updated_by="bootstrap",
        settings_hash=settings_hash,
        settings_json=payload,
    )
    session.add(row)
    await record_profile_from_dict(session, payload)
    return row


def _validate_payload(payload: dict[str, Any]) -> None:
    """Raise ValueError for invalid profile or mode values."""
    profile = payload.get("storage_profile", "")
    mode = payload.get("cert_storage_mode", "")
    if profile not in _VALID_PROFILES:
        raise ValueError(
            f"Invalid storage_profile '{profile}'. "
            f"Must be one of: {sorted(_VALID_PROFILES)}"
        )
    if mode not in _VALID_MODES:
        raise ValueError(
            f"Invalid cert_storage_mode '{mode}'. "
            f"Must be one of: {sorted(_VALID_MODES)}"
        )


async def update_settings(
    session: AsyncSession,
    payload: dict[str, Any],
    updated_by: str | None = None,
) -> CtInstanceSettings:
    """Validate and write a new settings payload to the database.

    Replaces the current active row; this is an upsert-style replace pattern
    (one row per instance, replaced in full on each update).

    Args:
        session: Active async database session.
        payload: Dict with all required settings fields.
        updated_by: Optional identifier of the caller (user/API key/CLI).

    Returns:
        The newly created settings row.

    Raises:
        ValueError: If profile or cert_storage_mode values are invalid.
    """
    _validate_payload(payload)

    settings_hash = compute_settings_hash_from_dict(payload)
    now = datetime.now(UTC)

    row = CtInstanceSettings(
        id=uuid.uuid4(),
        storage_profile=payload["storage_profile"],
        cert_storage_mode=payload["cert_storage_mode"],
        hostname_retention_mode=payload["hostname_retention_mode"],
        backfill_days=payload["backfill_days"],
        cert_retention_days=payload["cert_retention_days"],
        observation_retention_days=payload["observation_retention_days"],
        entry_outcome_retention_days=payload["entry_outcome_retention_days"],
        metrics_retention_days=payload["metrics_retention_days"],
        created_at=now,
        updated_at=now,
        updated_by=updated_by,
        settings_hash=settings_hash,
        settings_json=payload,
    )
    session.add(row)
    await record_profile_from_dict(session, payload)
    return row
