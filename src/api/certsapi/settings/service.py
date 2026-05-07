"""Business logic for the storage settings API endpoints.

Orchestrates SettingsRepository, validation, archive opt-in guard,
and response assembly.
"""

from __future__ import annotations

from typing import Literal

from ctpool.models.instance_settings import CtInstanceSettings
from ctpool.models.storage_profile_history import CtStorageProfileHistory
from ctpool.profile_defaults import defaults_for_profile
from ctpool.storage_modes import StorageProfile
from ctpool.storage_settings_history import (
    compute_settings_hash_from_dict,
    record_profile_from_dict,
)

from certsapi.settings.models import (
    StorageSettingsHistoryItem,
    StorageSettingsResponse,
    UpdateStorageSettingsRequest,
    UpdateStorageSettingsResult,
)
from certsapi.settings.repository import SettingsRepository

import uuid
from datetime import UTC, datetime


class SettingsService:
    """Orchestrates storage settings read/write with guards and audit."""

    def __init__(self, repository: SettingsRepository) -> None:
        self._repo = repository

    async def get_settings(self) -> StorageSettingsResponse | None:
        """Return active settings as a response model, or None if not seeded.

        Returns:
            StorageSettingsResponse when a row exists, None otherwise.
        """
        row = await self._repo.get_active_settings()
        if row is None:
            return None
        return _row_to_response(row)

    async def update_settings(
        self,
        request: UpdateStorageSettingsRequest,
    ) -> UpdateStorageSettingsResult:
        """Validate, guard, and persist new storage settings.

        Args:
            request: Validated request from the API layer.

        Returns:
            UpdateStorageSettingsResult with status and recommended actions.

        Raises:
            ValueError: When archive profile is requested without opt-in.
        """
        _guard_archive_optin(request)
        payload = request.model_dump(exclude={"archive_explicit_optin"})
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
            updated_by=payload.get("updated_by"),
            settings_hash=settings_hash,
            settings_json=payload,
        )
        await self._repo.save_settings(row)
        await record_profile_from_dict(self._repo._session, payload)
        actions = _recommended_actions(request.storage_profile)
        return UpdateStorageSettingsResult(
            status="updated",
            storage_profile=request.storage_profile,
            settings_hash=settings_hash,
            message=(
                f"Storage profile updated to '{request.storage_profile}'. "
                "Changes take effect on the next worker refresh cycle."
            ),
            recommended_actions=actions,
        )

    async def get_history(self, limit: int = 50) -> list[StorageSettingsHistoryItem]:
        """Return profile-change history newest first.

        Args:
            limit: Maximum rows to return.

        Returns:
            List of StorageSettingsHistoryItem models.
        """
        rows = await self._repo.get_settings_history(limit=limit)
        return [_history_row_to_item(r) for r in rows]


def _guard_archive_optin(request: UpdateStorageSettingsRequest) -> None:
    """Raise ValueError if archive profile requested without explicit opt-in."""
    if (
        request.storage_profile == StorageProfile.ARCHIVE
        and not request.archive_explicit_optin
    ):
        raise ValueError(
            "archive profile requires archive_explicit_optin=true. "
            "This profile can require terabytes of storage."
        )


def _row_to_response(row: CtInstanceSettings) -> StorageSettingsResponse:
    """Convert an ORM row to a StorageSettingsResponse."""
    return StorageSettingsResponse(
        storage_profile=row.storage_profile,
        cert_storage_mode=row.cert_storage_mode,
        hostname_retention_mode=row.hostname_retention_mode,
        backfill_days=row.backfill_days,
        cert_retention_days=row.cert_retention_days,
        observation_retention_days=row.observation_retention_days,
        entry_outcome_retention_days=row.entry_outcome_retention_days,
        metrics_retention_days=row.metrics_retention_days,
        settings_hash=row.settings_hash,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
        source="database",
    )


def _history_row_to_item(
    row: CtStorageProfileHistory,
) -> StorageSettingsHistoryItem:
    """Convert a history ORM row to a StorageSettingsHistoryItem."""
    return StorageSettingsHistoryItem(
        settings_hash=row.settings_hash,
        storage_profile=row.storage_profile,
        cert_storage_mode=row.cert_storage_mode,
        hostname_retention_mode=row.hostname_retention_mode,
        backfill_days=row.backfill_days,
        cert_retention_days=row.cert_retention_days,
        observation_retention_days=row.observation_retention_days,
        entry_outcome_retention_days=row.entry_outcome_retention_days,
        metrics_retention_days=row.metrics_retention_days,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        is_current=row.is_current,
    )


def _recommended_actions(profile: str) -> list[str]:
    """Return a list of operator action suggestions for the new profile."""
    actions: list[str] = []
    if profile == StorageProfile.ARCHIVE:
        actions.append(
            "Archive mode retains data indefinitely. "
            "Monitor disk usage and run 'ctpool storage metrics' regularly."
        )
    elif profile == StorageProfile.LITE:
        actions.append(
            "Run 'ctpool prune' to reclaim disk space from any previously "
            "retained certificates under a more aggressive profile."
        )
    actions.append(
        "Restart worker processes or wait for the next refresh cycle "
        f"({get_worker_refresh_config_hint()} seconds) for changes to take effect."
    )
    return actions


def get_worker_refresh_config_hint() -> int:
    """Return the configured worker refresh interval."""
    from ctpool.bootstrap_config import get_worker_refresh_config

    return get_worker_refresh_config().settings_refresh_seconds
