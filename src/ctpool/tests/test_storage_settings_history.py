"""Unit tests for ctpool.storage_settings_history.

Covers:
    - compute_settings_hash: determinism, golden value, field sensitivity
    - record_profile_on_startup: calls correct DB operations
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ctpool.config import Settings
from ctpool.storage_settings_history import (
    compute_settings_hash,
    record_profile_on_startup,
)


def _settings(**overrides) -> Settings:
    defaults = {"database_url": "postgresql+psycopg://x:x@localhost/x"}
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# compute_settings_hash
# ---------------------------------------------------------------------------


def test_compute_settings_hash_returns_16_chars():
    h = compute_settings_hash(_settings())
    assert isinstance(h, str)
    assert len(h) == 16


def test_compute_settings_hash_is_deterministic():
    s = _settings()
    assert compute_settings_hash(s) == compute_settings_hash(s)


def test_compute_settings_hash_golden_value():
    """Golden-value test: hash must not change for known inputs.

    This test will fail if the hash algorithm or included fields change.
    Update this golden value intentionally if the hash computation is
    deliberately changed.
    """
    s = _settings(
        ct_storage_profile="lite",
        ct_cert_storage_mode="none",
        ct_hostname_retention_mode="forever",
        ct_backfill_days=30,
        ct_cert_retention_days=7,
        ct_observation_retention_days=7,
        ct_entry_outcome_retention_days=7,
    )
    expected = "0f9463053ea83202"
    assert compute_settings_hash(s) == expected


def test_compute_settings_hash_changes_with_profile():
    s1 = _settings(ct_storage_profile="lite")
    s2 = _settings(ct_storage_profile="standard")
    assert compute_settings_hash(s1) != compute_settings_hash(s2)


def test_compute_settings_hash_changes_with_cert_mode():
    s1 = _settings(ct_cert_storage_mode="none")
    s2 = _settings(ct_cert_storage_mode="metadata")
    assert compute_settings_hash(s1) != compute_settings_hash(s2)


def test_compute_settings_hash_changes_with_retention_days():
    s1 = _settings(ct_cert_retention_days=7)
    s2 = _settings(ct_cert_retention_days=30)
    assert compute_settings_hash(s1) != compute_settings_hash(s2)


def test_compute_settings_hash_ignores_log_level():
    """Fields outside the storage scope must not affect the hash."""
    s1 = _settings(log_level="INFO")
    s2 = _settings(log_level="DEBUG")
    assert compute_settings_hash(s1) == compute_settings_hash(s2)


# ---------------------------------------------------------------------------
# record_profile_on_startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_profile_on_startup_returns_hash():
    session = AsyncMock()
    s = _settings()
    result = await record_profile_on_startup(session, s)
    assert isinstance(result, str)
    assert len(result) == 16
    assert result == compute_settings_hash(s)


@pytest.mark.asyncio
async def test_record_profile_on_startup_calls_two_executes():
    """record_profile_on_startup must call session.execute at least twice."""
    session = AsyncMock()
    await record_profile_on_startup(session, _settings())
    # Step 1: update is_current=False; Step 2: insert/upsert
    assert session.execute.await_count >= 2
