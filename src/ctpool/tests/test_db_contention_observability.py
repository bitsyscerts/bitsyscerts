"""Tests for shared DB contention operator snapshots."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.db_contention_observability import read_db_contention_operator_snapshot
from ctpool.models.db_contention_state import CtDbContentionState


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 64,
        "ct_db_contention_enabled": True,
        "ct_db_contention_stale_after_seconds": 30,
    }
    base.update(overrides)
    return Settings.model_validate(base)


async def test_snapshot_initializing_when_no_row_exists(
    db_session: AsyncSession,
) -> None:
    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(),
    )

    assert snapshot.status == "initializing"
    assert snapshot.effective_batch_size_cap is None


async def test_snapshot_throttling_when_shared_sleep_is_active(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        CtDbContentionState(
            scope="global",
            pressure_ema=0.2,
            extra_sleep_seconds=0.5,
            batch_size_cap=16,
            updated_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(),
        requested_batch_size=64,
    )

    assert snapshot.status == "throttling"
    assert snapshot.effective_batch_size_cap == 16
    assert snapshot.base_sleep_seconds == 0.5


async def test_snapshot_stale_marks_degraded_mode_active(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        CtDbContentionState(
            scope="global",
            pressure_ema=0.3,
            extra_sleep_seconds=1.0,
            batch_size_cap=8,
            updated_at=datetime.now(UTC) - timedelta(seconds=60),
        )
    )
    await db_session.flush()

    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(ct_db_contention_stale_after_seconds=30),
        requested_batch_size=64,
        now=datetime.now(UTC),
    )

    assert snapshot.status == "stale"
    assert snapshot.degraded_mode_active is True
    assert snapshot.base_sleep_seconds == 0.0
    assert snapshot.effective_batch_size_cap is None


async def test_snapshot_degrades_when_shared_state_is_unavailable(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def raise_sqlalchemy_error(_: AsyncSession) -> CtDbContentionState | None:
        raise SQLAlchemyError("missing table")

    monkeypatch.setattr(
        "ctpool.db_contention_observability._load_state_row",
        raise_sqlalchemy_error,
    )

    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(),
    )

    assert snapshot.status == "initializing"
    assert snapshot.degraded_mode_active is True
    assert "Apply migrations" in snapshot.notes[0]


async def test_snapshot_includes_retry_totals_from_row(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        CtDbContentionState(
            scope="global",
            pressure_ema=0.0,
            extra_sleep_seconds=0.0,
            batch_size_cap=None,
            updated_at=datetime.now(UTC),
            total_retryable_errors=42,
            retry_window_count=7,
            retry_window_start_at=datetime.now(UTC) - timedelta(seconds=120),
        )
    )
    await db_session.flush()

    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(),
        now=datetime.now(UTC),
    )

    assert snapshot.total_retryable_errors == 42
    assert snapshot.retryable_errors_per_min_5min is not None
    assert snapshot.retryable_errors_per_min_5min == pytest.approx(7 / 2.0, rel=0.05)


async def test_snapshot_retry_rate_is_none_when_no_window_started(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        CtDbContentionState(
            scope="global",
            pressure_ema=0.0,
            extra_sleep_seconds=0.0,
            batch_size_cap=None,
            updated_at=datetime.now(UTC),
            total_retryable_errors=0,
            retry_window_count=0,
            retry_window_start_at=None,
        )
    )
    await db_session.flush()

    snapshot = await read_db_contention_operator_snapshot(
        db_session,
        _settings(),
        now=datetime.now(UTC),
    )

    assert snapshot.total_retryable_errors == 0
    assert snapshot.retryable_errors_per_min_5min is None
