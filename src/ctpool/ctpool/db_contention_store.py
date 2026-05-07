"""Persistence helpers for the shared DB contention control state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings
from ctpool.db_contention_controller import (
    DbContentionController,
    DbContentionControllerConfig,
)
from ctpool.db_contention_types import (
    DbContentionDirective,
    DbContentionObservation,
    DbContentionStateView,
)
from ctpool.models.db_contention_state import CtDbContentionState

_GLOBAL_SCOPE = "global"


def baseline_db_contention_directive() -> DbContentionDirective:
    """Return the default no-throttle directive."""
    return DbContentionDirective(
        pressure_ema=0.0,
        base_sleep_seconds=0.0,
        batch_size_cap=None,
    )


def degraded_db_contention_directive(
    settings: Settings,
    requested_batch_size: int,
) -> DbContentionDirective:
    """Return a conservative fallback directive when control-state I/O fails."""
    safe_cap = max(
        1,
        min(requested_batch_size, settings.ct_db_contention_min_batch_size),
    )
    return DbContentionDirective(
        pressure_ema=1.0,
        base_sleep_seconds=settings.ct_db_contention_max_sleep_seconds,
        batch_size_cap=safe_cap,
    )


def build_db_contention_controller(settings: Settings) -> DbContentionController:
    """Create a controller instance from validated settings."""
    return DbContentionController(
        DbContentionControllerConfig(
            ema_alpha=settings.ct_db_contention_ema_alpha,
            high_retry_ratio=settings.ct_db_contention_high_retry_ratio,
            low_retry_ratio=settings.ct_db_contention_low_retry_ratio,
            recovery_windows=settings.ct_db_contention_recovery_windows,
            sleep_step_seconds=settings.ct_db_contention_sleep_step_seconds,
            max_sleep_seconds=settings.ct_db_contention_max_sleep_seconds,
            min_batch_size=settings.ct_db_contention_min_batch_size,
            batch_growth_step=settings.ct_db_contention_batch_growth_step,
            stale_after_seconds=settings.ct_db_contention_stale_after_seconds,
            enable_batch_cap=settings.ct_db_contention_enable_batch_cap,
        )
    )


async def load_db_contention_directive(
    session: AsyncSession,
    settings: Settings,
    requested_batch_size: int,
) -> DbContentionDirective:
    """Read the current shared pacing hint without mutating controller state."""
    if not settings.ct_db_contention_enabled:
        return baseline_db_contention_directive()
    row = await _load_state_row(session)
    if row is None:
        return baseline_db_contention_directive()
    controller = build_db_contention_controller(settings)
    state = _state_view_from_row(row)
    return controller.directive(state, requested_batch_size, now=datetime.now(UTC))


async def merge_db_contention_observation(
    session: AsyncSession,
    settings: Settings,
    observation: DbContentionObservation,
    requested_batch_size: int,
) -> DbContentionDirective:
    """Merge one boundary observation into shared state and return a directive."""
    if not settings.ct_db_contention_enabled:
        return baseline_db_contention_directive()
    row = await _lock_state_row(session)
    controller = build_db_contention_controller(settings)
    now = datetime.now(UTC)
    state = _state_view_from_row(row)
    next_state, directive = controller.merge(
        state,
        observation,
        requested_batch_size,
        now=now,
    )
    _apply_state_view(row, next_state)
    _accumulate_retry_counts(row, observation.retryable_errors, now)
    return directive


async def _load_state_row(session: AsyncSession) -> CtDbContentionState | None:
    result = await session.execute(
        select(CtDbContentionState).where(CtDbContentionState.scope == _GLOBAL_SCOPE)
    )
    return result.scalar_one_or_none()


async def _lock_state_row(session: AsyncSession) -> CtDbContentionState:
    await session.execute(
        pg_insert(CtDbContentionState)
        .values(scope=_GLOBAL_SCOPE)
        .on_conflict_do_nothing(index_elements=["scope"])
    )
    result = await session.execute(
        select(CtDbContentionState)
        .where(CtDbContentionState.scope == _GLOBAL_SCOPE)
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    assert row is not None  # noqa: S101
    return row


def _state_view_from_row(row: CtDbContentionState) -> DbContentionStateView:
    updated_at = None if _is_pristine_state_row(row) else row.updated_at
    return DbContentionStateView(
        pressure_ema=float(row.pressure_ema),
        extra_sleep_seconds=float(row.extra_sleep_seconds),
        batch_size_cap=row.batch_size_cap,
        healthy_streak=row.healthy_streak,
        updated_at=updated_at,
    )


def _is_pristine_state_row(row: CtDbContentionState) -> bool:
    return (
        float(row.pressure_ema) == 0.0
        and float(row.extra_sleep_seconds) == 0.0
        and row.batch_size_cap is None
        and row.healthy_streak == 0
    )


def _apply_state_view(
    row: CtDbContentionState,
    state: DbContentionStateView,
) -> None:
    row.pressure_ema = state.pressure_ema
    row.extra_sleep_seconds = state.extra_sleep_seconds
    row.batch_size_cap = state.batch_size_cap
    row.healthy_streak = state.healthy_streak
    row.updated_at = state.updated_at or datetime.now(UTC)


_RETRY_WINDOW_SECONDS = 300


def _accumulate_retry_counts(
    row: CtDbContentionState,
    retryable_errors: int,
    now: datetime,
) -> None:
    """Accumulate *retryable_errors* into the row's cumulative and rolling counters.

    The rolling window resets when more than ``_RETRY_WINDOW_SECONDS`` have
    elapsed since ``retry_window_start_at``.
    """
    if retryable_errors <= 0:
        return
    row.total_retryable_errors = (row.total_retryable_errors or 0) + retryable_errors
    start = row.retry_window_start_at
    elapsed = (now - start).total_seconds() if start is not None else None
    if start is None or elapsed is None or elapsed > _RETRY_WINDOW_SECONDS:
        row.retry_window_start_at = now
        row.retry_window_count = retryable_errors
    else:
        row.retry_window_count = (row.retry_window_count or 0) + retryable_errors
