"""Pure state machine for shared DB contention pacing.

Exports:
    DbContentionController       — Stateless transition calculator.
    DbContentionControllerConfig — Tunables for retry-pressure control.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ctpool.db_contention_types import (
    DbContentionDirective,
    DbContentionObservation,
    DbContentionStateView,
)


@dataclass(frozen=True)
class DbContentionControllerConfig:
    """Tunables for the shared DB contention control loop."""

    ema_alpha: float = 0.25
    high_retry_ratio: float = 0.05
    low_retry_ratio: float = 0.01
    recovery_windows: int = 3
    sleep_step_seconds: float = 0.25
    max_sleep_seconds: float = 5.0
    min_batch_size: int = 16
    batch_growth_step: int = 32
    stale_after_seconds: int = 120
    enable_batch_cap: bool = True


class DbContentionController:
    """Compute shared pacing hints from aggregated retry-pressure samples."""

    def __init__(self, config: DbContentionControllerConfig) -> None:
        self._config = config

    def directive(
        self,
        state: DbContentionStateView,
        requested_batch_size: int,
        *,
        now: datetime | None = None,
    ) -> DbContentionDirective:
        """Return the current worker-facing pacing directive."""
        active = self._normalize_stale(state, now=now)
        return DbContentionDirective(
            pressure_ema=active.pressure_ema,
            base_sleep_seconds=active.extra_sleep_seconds,
            batch_size_cap=self._cap_for_request(
                active.batch_size_cap,
                requested_batch_size,
            ),
        )

    def merge(
        self,
        state: DbContentionStateView,
        observation: DbContentionObservation,
        requested_batch_size: int,
        *,
        now: datetime | None = None,
    ) -> tuple[DbContentionStateView, DbContentionDirective]:
        """Apply one boundary observation and return state plus directive."""
        timestamp = now or datetime.now(UTC)
        active = self._normalize_stale(state, now=timestamp)
        if not observation.has_activity:
            directive = self.directive(active, requested_batch_size, now=timestamp)
            return active, directive

        next_state = self._next_state(
            active,
            observation,
            requested_batch_size,
            timestamp,
        )
        directive = self.directive(next_state, requested_batch_size, now=timestamp)
        return next_state, directive

    def _next_state(
        self,
        state: DbContentionStateView,
        observation: DbContentionObservation,
        requested_batch_size: int,
        now: datetime,
    ) -> DbContentionStateView:
        ratio = observation.retry_ratio
        pressure_ema = self._blend_pressure(state, ratio)
        if (
            ratio > self._config.high_retry_ratio
            or pressure_ema > self._config.high_retry_ratio
        ):
            return DbContentionStateView(
                pressure_ema=pressure_ema,
                extra_sleep_seconds=self._increase_sleep(state.extra_sleep_seconds),
                batch_size_cap=self._reduce_batch_cap(
                    state.batch_size_cap,
                    requested_batch_size,
                ),
                healthy_streak=0,
                updated_at=now,
            )
        if ratio <= self._config.low_retry_ratio:
            return self._recover_state(
                state,
                pressure_ema,
                requested_batch_size,
                now,
            )
        return DbContentionStateView(
            pressure_ema=pressure_ema,
            extra_sleep_seconds=state.extra_sleep_seconds,
            batch_size_cap=state.batch_size_cap,
            healthy_streak=0,
            updated_at=now,
        )

    def _recover_state(
        self,
        state: DbContentionStateView,
        pressure_ema: float,
        requested_batch_size: int,
        now: datetime,
    ) -> DbContentionStateView:
        streak = state.healthy_streak + 1
        if streak < self._config.recovery_windows:
            return DbContentionStateView(
                pressure_ema=pressure_ema,
                extra_sleep_seconds=state.extra_sleep_seconds,
                batch_size_cap=state.batch_size_cap,
                healthy_streak=streak,
                updated_at=now,
            )
        return DbContentionStateView(
            pressure_ema=pressure_ema,
            extra_sleep_seconds=max(
                0.0,
                state.extra_sleep_seconds - self._config.sleep_step_seconds,
            ),
            batch_size_cap=self._relax_batch_cap(
                state.batch_size_cap,
                requested_batch_size,
            ),
            healthy_streak=0,
            updated_at=now,
        )

    def _blend_pressure(
        self,
        state: DbContentionStateView,
        retry_ratio: float,
    ) -> float:
        if state.updated_at is None:
            return retry_ratio
        alpha = self._config.ema_alpha
        return (state.pressure_ema * (1.0 - alpha)) + (retry_ratio * alpha)

    def _normalize_stale(
        self,
        state: DbContentionStateView,
        *,
        now: datetime | None,
    ) -> DbContentionStateView:
        if state.updated_at is None or now is None:
            return state
        stale_after = timedelta(seconds=self._config.stale_after_seconds)
        if now - state.updated_at <= stale_after:
            return state
        return DbContentionStateView()

    def _increase_sleep(self, current_sleep: float) -> float:
        next_sleep = current_sleep + self._config.sleep_step_seconds
        return min(self._config.max_sleep_seconds, next_sleep)

    def _reduce_batch_cap(
        self,
        current_cap: int | None,
        requested_batch_size: int,
    ) -> int | None:
        if not self._config.enable_batch_cap:
            return None
        starting_cap = current_cap or requested_batch_size
        reduced = max(self._config.min_batch_size, starting_cap // 2)
        return min(reduced, requested_batch_size)

    def _relax_batch_cap(
        self,
        current_cap: int | None,
        requested_batch_size: int,
    ) -> int | None:
        if not self._config.enable_batch_cap or current_cap is None:
            return None
        relaxed = min(
            requested_batch_size,
            current_cap + self._config.batch_growth_step,
        )
        if relaxed >= requested_batch_size:
            return None
        return relaxed

    def _cap_for_request(
        self,
        current_cap: int | None,
        requested_batch_size: int,
    ) -> int | None:
        if current_cap is None:
            return None
        if current_cap >= requested_batch_size:
            return None
        return current_cap
