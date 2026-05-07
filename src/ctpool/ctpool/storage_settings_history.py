"""Settings hash computation and profile-history recording.

Exports:
    compute_settings_hash   — Return a 16-char hex hash of the storage settings.
    compute_settings_hash_from_dict — Dict-based variant for API update path.
    record_profile_on_startup — Upsert the current settings into the history table.
    record_profile_from_dict — Dict-based variant for API update path.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.models.storage_profile_history import CtStorageProfileHistory


def compute_settings_hash(settings: Settings) -> str:
    """Return a stable 16-character hex hash of the storage-relevant settings.

    The hash covers only the fields that affect how data is written and retained.
    Changes to other settings (e.g. HTTP timeouts) do not affect the hash.

    Args:
        settings: Application settings instance.

    Returns:
        A 16-character lowercase hex string.
    """
    payload = {
        "storage_profile": settings.ct_storage_profile,
        "cert_storage_mode": settings.ct_cert_storage_mode,
        "hostname_retention_mode": settings.ct_hostname_retention_mode,
        "backfill_days": settings.ct_backfill_days,
        "cert_retention_days": settings.ct_cert_retention_days,
        "observation_retention_days": settings.ct_observation_retention_days,
        "entry_outcome_retention_days": settings.ct_entry_outcome_retention_days,
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _build_raw_json(settings: Settings) -> str:
    """Return a full JSON snapshot of all storage-relevant settings."""
    payload = {
        "storage_profile": settings.ct_storage_profile,
        "cert_storage_mode": settings.ct_cert_storage_mode,
        "hostname_retention_mode": settings.ct_hostname_retention_mode,
        "backfill_days": settings.ct_backfill_days,
        "cert_retention_days": settings.ct_cert_retention_days,
        "observation_retention_days": settings.ct_observation_retention_days,
        "entry_outcome_retention_days": settings.ct_entry_outcome_retention_days,
        "metrics_retention_days": settings.ct_metrics_retention_days,
    }
    return json.dumps(payload, sort_keys=True)


async def record_profile_on_startup(
    session: AsyncSession,
    settings: Settings,
) -> str:
    """Upsert the current storage settings into the profile history table.

    On each startup:
    1. Clear the ``is_current`` flag from any previous active row.
    2. Insert the new settings row, or update ``last_seen_at`` if the hash
       already exists.
    3. Set ``is_current = true`` on the row matching the current hash.

    Args:
        session:  Active async database session (caller manages transaction).
        settings: Application settings.

    Returns:
        The 16-character settings hash for the current configuration.
    """
    settings_hash = compute_settings_hash(settings)
    now = datetime.now(UTC)

    # Step 1: clear the is_current flag on all rows.
    await session.execute(update(CtStorageProfileHistory).values(is_current=False))

    # Step 2: insert or update last_seen_at.
    stmt = (
        pg_insert(CtStorageProfileHistory)
        .values(
            id=uuid.uuid4(),
            settings_hash=settings_hash,
            storage_profile=settings.ct_storage_profile,
            cert_storage_mode=settings.ct_cert_storage_mode,
            hostname_retention_mode=settings.ct_hostname_retention_mode,
            backfill_days=settings.ct_backfill_days,
            cert_retention_days=settings.ct_cert_retention_days,
            observation_retention_days=settings.ct_observation_retention_days,
            entry_outcome_retention_days=settings.ct_entry_outcome_retention_days,
            metrics_retention_days=settings.ct_metrics_retention_days,
            raw_settings_json=_build_raw_json(settings),
            first_seen_at=now,
            last_seen_at=now,
            is_current=True,
        )
        .on_conflict_do_update(
            index_elements=["settings_hash"],
            set_={"last_seen_at": now, "is_current": True},
        )
    )
    await session.execute(stmt)
    return settings_hash


_HASH_KEYS = (
    "storage_profile",
    "cert_storage_mode",
    "hostname_retention_mode",
    "backfill_days",
    "cert_retention_days",
    "observation_retention_days",
    "entry_outcome_retention_days",
)


def compute_settings_hash_from_dict(payload: dict[str, object]) -> str:
    """Return a stable 16-character hex hash for a settings dict.

    Only the fields listed in ``_HASH_KEYS`` are included, matching the
    subset used by ``compute_settings_hash``.

    Args:
        payload: Dict containing at minimum the storage-relevant keys.

    Returns:
        A 16-character lowercase hex string.
    """
    subset = {k: payload[k] for k in _HASH_KEYS if k in payload}
    raw = json.dumps(subset, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


async def record_profile_from_dict(
    session: AsyncSession,
    payload: dict[str, object],
) -> str:
    """Upsert a settings dict into the profile history table.

    Variant of ``record_profile_on_startup`` for the API update code path.
    Caller is responsible for managing the transaction.

    Args:
        session: Active async database session.
        payload: Dict with all storage-relevant fields.

    Returns:
        The 16-character settings hash.
    """
    settings_hash = compute_settings_hash_from_dict(payload)
    now = datetime.now(UTC)

    await session.execute(update(CtStorageProfileHistory).values(is_current=False))

    stmt = (
        pg_insert(CtStorageProfileHistory)
        .values(
            id=uuid.uuid4(),
            settings_hash=settings_hash,
            storage_profile=payload.get("storage_profile", ""),
            cert_storage_mode=payload.get("cert_storage_mode", ""),
            hostname_retention_mode=payload.get("hostname_retention_mode", ""),
            backfill_days=payload.get("backfill_days", 0),
            cert_retention_days=payload.get("cert_retention_days", 0),
            observation_retention_days=payload.get("observation_retention_days", 0),
            entry_outcome_retention_days=payload.get("entry_outcome_retention_days", 0),
            metrics_retention_days=payload.get("metrics_retention_days", 1),
            raw_settings_json=json.dumps(payload, sort_keys=True),
            first_seen_at=now,
            last_seen_at=now,
            is_current=True,
        )
        .on_conflict_do_update(
            index_elements=["settings_hash"],
            set_={"last_seen_at": now, "is_current": True},
        )
    )
    await session.execute(stmt)
    return settings_hash
