"""Unit tests for certsapi.settings.models."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from certsapi.settings.models import (
    StorageSettingsHistoryItem,
    StorageSettingsResponse,
    UpdateStorageSettingsRequest,
    UpdateStorageSettingsResult,
)

_NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)


def test_storage_settings_response_round_trips() -> None:
    """StorageSettingsResponse serialises and deserialises cleanly."""
    obj = StorageSettingsResponse(
        storage_profile="lite",
        cert_storage_mode="none",
        hostname_retention_mode="forever",
        backfill_days=30,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
        metrics_retention_days=14,
        settings_hash="abc123",
        updated_at=_NOW,
    )
    raw = json.loads(obj.model_dump_json())
    assert raw["storage_profile"] == "lite"
    assert raw["source"] == "database"
    assert raw["updated_by"] is None


def test_update_request_accepts_zero_retention() -> None:
    """cert_retention_days=0 (retain indefinitely) is valid."""
    req = UpdateStorageSettingsRequest(
        storage_profile="archive",
        cert_storage_mode="full_der",
        hostname_retention_mode="forever",
        backfill_days=0,
        cert_retention_days=0,
        observation_retention_days=0,
        entry_outcome_retention_days=0,
        metrics_retention_days=90,
    )
    assert req.cert_retention_days == 0


def test_update_request_rejects_negative_retention() -> None:
    """cert_retention_days=-1 must be rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        UpdateStorageSettingsRequest(
            storage_profile="custom",
            cert_storage_mode="metadata",
            hostname_retention_mode="forever",
            backfill_days=30,
            cert_retention_days=-1,
            observation_retention_days=30,
            entry_outcome_retention_days=30,
            metrics_retention_days=30,
        )


def test_update_request_rejects_zero_metrics_retention() -> None:
    """metrics_retention_days must be >= 1."""
    with pytest.raises(ValidationError):
        UpdateStorageSettingsRequest(
            storage_profile="custom",
            cert_storage_mode="none",
            hostname_retention_mode="forever",
            backfill_days=30,
            cert_retention_days=7,
            observation_retention_days=7,
            entry_outcome_retention_days=7,
            metrics_retention_days=0,
        )


def test_update_result_model() -> None:
    """UpdateStorageSettingsResult includes expected fields."""
    result = UpdateStorageSettingsResult(
        status="updated",
        storage_profile="standard",
        settings_hash="abc123",
        message="Storage profile updated.",
        recommended_actions=["Run prune to reclaim space."],
    )
    assert result.status == "updated"
    assert len(result.recommended_actions) == 1


def test_history_item_model() -> None:
    """StorageSettingsHistoryItem deserialises correctly."""
    item = StorageSettingsHistoryItem(
        settings_hash="abc",
        storage_profile="lite",
        cert_storage_mode="none",
        hostname_retention_mode="forever",
        backfill_days=30,
        cert_retention_days=1,
        observation_retention_days=7,
        entry_outcome_retention_days=7,
        metrics_retention_days=14,
        first_seen_at=_NOW,
        last_seen_at=_NOW,
        is_current=True,
    )
    assert item.is_current is True
