"""Tests for the pure DB contention control loop."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from ctpool.db_contention_controller import (
    DbContentionController,
    DbContentionControllerConfig,
)
from ctpool.db_contention_types import DbContentionObservation, DbContentionStateView


def _controller(**overrides: object) -> DbContentionController:
    config_kwargs: dict[str, object] = {
        "ema_alpha": 0.5,
        "high_retry_ratio": 0.10,
        "low_retry_ratio": 0.02,
        "recovery_windows": 2,
        "sleep_step_seconds": 0.5,
        "max_sleep_seconds": 2.0,
        "min_batch_size": 8,
        "batch_growth_step": 8,
        "stale_after_seconds": 30,
        "enable_batch_cap": True,
    }
    config_kwargs.update(overrides)
    # The test helper allows heterogeneous scalar overrides for controller knobs.
    config = DbContentionControllerConfig(**cast(dict[str, Any], config_kwargs))
    return DbContentionController(config)


def test_merge_raises_sleep_and_reduces_batch_cap_on_high_retry_ratio() -> None:
    controller = _controller()
    state, directive = controller.merge(
        DbContentionStateView(),
        DbContentionObservation(entries_attempted=10, retryable_errors=2),
        requested_batch_size=64,
    )

    assert state.extra_sleep_seconds == 0.5
    assert state.batch_size_cap == 32
    assert directive.batch_size_cap == 32
    assert directive.base_sleep_seconds == 0.5


def test_merge_recovers_after_required_healthy_windows() -> None:
    controller = _controller()
    now = datetime.now(UTC)
    state = DbContentionStateView(
        pressure_ema=0.2,
        extra_sleep_seconds=1.0,
        batch_size_cap=16,
        healthy_streak=0,
        updated_at=now,
    )
    first, _ = controller.merge(
        state,
        DbContentionObservation(entries_attempted=20, retryable_errors=0),
        requested_batch_size=32,
        now=now + timedelta(seconds=1),
    )
    second, directive = controller.merge(
        first,
        DbContentionObservation(entries_attempted=20, retryable_errors=0),
        requested_batch_size=32,
        now=now + timedelta(seconds=2),
    )

    assert first.extra_sleep_seconds == 1.0
    assert first.batch_size_cap == 16
    assert first.healthy_streak == 1
    assert second.extra_sleep_seconds == 0.5
    assert second.batch_size_cap == 24
    assert directive.batch_size_cap == 24


def test_directive_drops_batch_cap_when_request_is_already_smaller() -> None:
    controller = _controller()
    directive = controller.directive(
        DbContentionStateView(batch_size_cap=64),
        requested_batch_size=32,
    )

    assert directive.batch_size_cap is None


def test_merge_ignores_empty_observations() -> None:
    controller = _controller()
    state = DbContentionStateView(extra_sleep_seconds=1.0, batch_size_cap=16)
    updated, directive = controller.merge(
        state,
        DbContentionObservation(entries_attempted=0, retryable_errors=3),
        requested_batch_size=32,
    )

    assert updated == state
    assert directive.base_sleep_seconds == 1.0
    assert directive.batch_size_cap == 16


def test_directive_resets_stale_state_to_baseline() -> None:
    controller = _controller(stale_after_seconds=10)
    state = DbContentionStateView(
        pressure_ema=0.3,
        extra_sleep_seconds=1.0,
        batch_size_cap=16,
        updated_at=datetime.now(UTC) - timedelta(seconds=20),
    )
    directive = controller.directive(
        state,
        requested_batch_size=32,
        now=datetime.now(UTC),
    )

    assert directive.pressure_ema == 0.0
    assert directive.base_sleep_seconds == 0.0
    assert directive.batch_size_cap is None
