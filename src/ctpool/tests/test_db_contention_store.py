"""Tests for shared DB contention state persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.db_contention_store import (
    load_db_contention_directive,
    merge_db_contention_observation,
)
from ctpool.db_contention_types import DbContentionObservation
from ctpool.models.db_contention_state import CtDbContentionState


def _settings(base: Settings, **overrides: object) -> Settings:
    return base.model_copy(update=overrides)


async def test_load_returns_baseline_when_state_row_is_missing(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    directive = await load_db_contention_directive(
        db_session,
        test_settings,
        requested_batch_size=64,
    )

    assert directive.base_sleep_seconds == 0.0
    assert directive.batch_size_cap is None


async def test_merge_creates_and_updates_shared_state_row(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    settings = _settings(
        test_settings,
        ct_db_contention_ema_alpha=0.5,
        ct_db_contention_high_retry_ratio=0.1,
        ct_db_contention_sleep_step_seconds=0.5,
        ct_db_contention_min_batch_size=8,
    )
    directive = await merge_db_contention_observation(
        db_session,
        settings,
        DbContentionObservation(entries_attempted=10, retryable_errors=2),
        requested_batch_size=64,
    )
    count = await db_session.scalar(
        select(func.count()).select_from(CtDbContentionState)
    )
    row = await db_session.scalar(select(CtDbContentionState))

    assert directive.base_sleep_seconds == 0.5
    assert directive.batch_size_cap == 32
    assert count == 1
    assert row is not None
    assert float(row.pressure_ema) == 0.2
    assert float(row.extra_sleep_seconds) == 0.5
    assert row.batch_size_cap == 32


async def test_merge_returns_baseline_when_control_is_disabled(
    db_session: AsyncSession,
    test_settings: Settings,
) -> None:
    settings = _settings(test_settings, ct_db_contention_enabled=False)
    directive = await merge_db_contention_observation(
        db_session,
        settings,
        DbContentionObservation(entries_attempted=10, retryable_errors=2),
        requested_batch_size=64,
    )

    assert directive.base_sleep_seconds == 0.0
    assert directive.batch_size_cap is None
