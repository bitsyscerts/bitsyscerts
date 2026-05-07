"""Read and normalize shared DB contention state for operator surfaces."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import Settings, get_settings
from ctpool.db_contention_store import build_db_contention_controller
from ctpool.db_contention_types import (
    DbContentionOperatorSnapshot,
    DbContentionOperatorStatus,
    DbContentionStateView,
)
from ctpool.models.db_contention_state import CtDbContentionState

_GLOBAL_SCOPE = "global"


async def read_db_contention_operator_snapshot(
    session: AsyncSession,
    settings: Settings | None = None,
    *,
    requested_batch_size: int | None = None,
    now: datetime | None = None,
) -> DbContentionOperatorSnapshot:
    """Return the shared DB contention state normalized for operator surfaces."""
    active_settings = settings or get_settings()
    batch_size = requested_batch_size or active_settings.ct_default_batch_size
    timestamp = now or datetime.now(UTC)
    if not active_settings.ct_db_contention_enabled:
        return DbContentionOperatorSnapshot(
            status="disabled",
            degraded_mode_active=False,
            pressure_ema=0.0,
            base_sleep_seconds=0.0,
            shared_batch_size_cap=None,
            effective_batch_size_cap=None,
            updated_at=None,
            notes=["Shared DB contention control is disabled."],
        )

    try:
        row = await _load_state_row(session)
    except SQLAlchemyError:
        return DbContentionOperatorSnapshot(
            status="initializing",
            degraded_mode_active=True,
            pressure_ema=0.0,
            base_sleep_seconds=0.0,
            shared_batch_size_cap=None,
            effective_batch_size_cap=None,
            updated_at=None,
            notes=[
                "Shared DB contention state is unavailable. Apply migrations "
                "to enable shared coordination and operator telemetry.",
            ],
        )

    if row is None:
        return DbContentionOperatorSnapshot(
            status="initializing",
            degraded_mode_active=False,
            pressure_ema=0.0,
            base_sleep_seconds=0.0,
            shared_batch_size_cap=None,
            effective_batch_size_cap=None,
            updated_at=None,
            notes=[
                "No shared DB contention state has been recorded yet.",
            ],
        )

    controller = build_db_contention_controller(active_settings)
    state = DbContentionStateView(
        pressure_ema=float(row.pressure_ema),
        extra_sleep_seconds=float(row.extra_sleep_seconds),
        batch_size_cap=row.batch_size_cap,
        healthy_streak=row.healthy_streak,
        updated_at=row.updated_at,
    )
    directive = controller.directive(state, batch_size, now=timestamp)
    stale = _is_stale(
        row.updated_at,
        active_settings.ct_db_contention_stale_after_seconds,
        timestamp,
    )
    status = _snapshot_status(
        stale,
        directive.base_sleep_seconds,
        directive.batch_size_cap,
    )
    return DbContentionOperatorSnapshot(
        status=status,
        degraded_mode_active=stale,
        pressure_ema=directive.pressure_ema,
        base_sleep_seconds=directive.base_sleep_seconds,
        shared_batch_size_cap=row.batch_size_cap,
        effective_batch_size_cap=directive.batch_size_cap,
        updated_at=row.updated_at,
        notes=_snapshot_notes(status),
        total_retryable_errors=int(row.total_retryable_errors),
        retryable_errors_per_min_5min=_compute_retry_rate(
            int(row.retry_window_count),
            row.retry_window_start_at,
            timestamp,
        ),
    )


async def _load_state_row(session: AsyncSession) -> CtDbContentionState | None:
    result = await session.execute(
        select(CtDbContentionState).where(CtDbContentionState.scope == _GLOBAL_SCOPE)
    )
    return result.scalar_one_or_none()


def _is_stale(updated_at: datetime, stale_after_seconds: int, now: datetime) -> bool:
    return now - updated_at > timedelta(seconds=stale_after_seconds)


def _snapshot_status(
    stale: bool,
    base_sleep_seconds: float,
    effective_batch_size_cap: int | None,
) -> DbContentionOperatorStatus:
    if stale:
        return "stale"
    if base_sleep_seconds > 0.0 or effective_batch_size_cap is not None:
        return "throttling"
    return "healthy"


def _snapshot_notes(status: str) -> list[str]:
    if status == "stale":
        return [
            "Shared contention state is stale; workers fall back to local "
            "conservative pacing when coordination is unavailable.",
        ]
    if status == "throttling":
        return ["Shared DB contention throttling is currently active."]
    if status == "healthy":
        return ["Shared DB contention control is active and not throttling."]
    return []


_RETRY_RATE_WINDOW_SECONDS = 300


def _compute_retry_rate(
    window_count: int,
    window_start_at: datetime | None,
    now: datetime,
) -> float | None:
    """Return retryable errors per minute for the rolling 5-min window.

    Returns None when no window has started (no retries have ever occurred).
    Returns 0.0 when the window has started but the count is zero.
    Clamps the elapsed denominator to at least 1 second to avoid division
    by zero on the first observation.
    """
    if window_start_at is None:
        return None
    elapsed_seconds = max((now - window_start_at).total_seconds(), 1.0)
    elapsed_minutes = elapsed_seconds / 60.0
    return window_count / elapsed_minutes
