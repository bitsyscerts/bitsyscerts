"""Per-log exponential backoff and batch-size management.

Exports:
    BackoffState   — Immutable snapshot of a log's current rate-limit state.
    RateLimiter    — Stateless calculator that produces updated BackoffState
                     values from 429, 5xx, and success events.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BackoffState:
    """Immutable snapshot of a single CT log's backoff state.

    All fields mirror the corresponding columns in ``ct_log_runtime_state``.
    """

    log_source_id: uuid.UUID
    consecutive_failures: int
    backoff_until: datetime | None
    last_429_at: datetime | None
    current_batch_size: int
    learned_max_batch_size: int


class RateLimiter:
    """Stateless backoff calculator for CT log fetch operations.

    Produces new :class:`BackoffState` values given an event type and the
    current state.  No I/O is performed here — callers persist the result.

    Args:
        base_backoff_seconds: Starting backoff delay for the first failure.
        max_backoff_seconds:  Upper cap on exponential backoff (seconds).
        jitter_fraction:      Random jitter applied as a fraction of the
                              computed delay (0.0 – 1.0).
        min_batch_size:       Floor for batch-size reduction on errors.
    """

    def __init__(
        self,
        base_backoff_seconds: int = 10,
        max_backoff_seconds: int = 300,
        jitter_fraction: float = 0.25,
        min_batch_size: int = 1,
    ) -> None:
        self._base = base_backoff_seconds
        self._max = max_backoff_seconds
        self._jitter = jitter_fraction
        self._min_batch = min_batch_size

    # ------------------------------------------------------------------
    # Public event handlers
    # ------------------------------------------------------------------

    def handle_429(
        self,
        state: BackoffState,
        retry_after: int | None = None,
    ) -> BackoffState:
        """Return an updated state after receiving a 429 response.

        If *retry_after* is supplied the backoff window uses that value
        directly (plus jitter) rather than the exponential schedule.
        """
        now = datetime.now(UTC)
        failures = state.consecutive_failures + 1

        if retry_after is not None:
            delay = retry_after + self._jitter_seconds(retry_after)
        else:
            delay = self._exponential_delay(failures)

        new_batch = max(self._min_batch, state.current_batch_size // 2)
        return BackoffState(
            log_source_id=state.log_source_id,
            consecutive_failures=failures,
            backoff_until=_future(delay),
            last_429_at=now,
            current_batch_size=new_batch,
            learned_max_batch_size=state.learned_max_batch_size,
        )

    def handle_5xx(self, state: BackoffState, status_code: int) -> BackoffState:
        """Return an updated state after receiving a 5xx response.

        Args:
            state:       Current backoff state.
            status_code: The HTTP status code received (500–599).
        """
        _ = status_code  # retained for future per-code behaviour
        failures = state.consecutive_failures + 1
        delay = self._exponential_delay(failures)
        new_batch = max(self._min_batch, state.current_batch_size // 2)
        return BackoffState(
            log_source_id=state.log_source_id,
            consecutive_failures=failures,
            backoff_until=_future(delay),
            last_429_at=state.last_429_at,
            current_batch_size=new_batch,
            learned_max_batch_size=state.learned_max_batch_size,
        )

    def handle_success(self, state: BackoffState) -> BackoffState:
        """Return an updated state after a successful fetch.

        Resets the failure counter and backoff window, and increments the
        batch size up to the learned maximum.
        """
        # Grow batch size by 25 %, capped by the learned maximum
        new_batch = min(
            state.learned_max_batch_size,
            math.ceil(state.current_batch_size * 1.25),
        )
        # Update the learned maximum if current batch succeeded
        new_learned = max(state.learned_max_batch_size, state.current_batch_size)
        return BackoffState(
            log_source_id=state.log_source_id,
            consecutive_failures=0,
            backoff_until=None,
            last_429_at=state.last_429_at,
            current_batch_size=new_batch,
            learned_max_batch_size=new_learned,
        )

    # ------------------------------------------------------------------
    # Eligibility helpers
    # ------------------------------------------------------------------

    def seconds_until_eligible(self, state: BackoffState) -> float:
        """Return seconds until this log is eligible for a fetch attempt.

        Returns 0.0 if the log is already eligible.
        """
        if state.backoff_until is None:
            return 0.0
        remaining = (state.backoff_until - datetime.now(UTC)).total_seconds()
        return max(0.0, remaining)

    def is_eligible(self, state: BackoffState) -> bool:
        """Return True if the log can be fetched right now."""
        return self.seconds_until_eligible(state) == 0.0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _exponential_delay(self, failures: int) -> float:
        """Compute exponential backoff delay with jitter for *failures*."""
        # Caps at max before adding jitter so total stays bounded
        raw: float = min(self._base * (2 ** (failures - 1)), self._max)
        return raw + self._jitter_seconds(raw)

    def _jitter_seconds(self, base: float) -> float:
        """Return a random jitter value up to *jitter_fraction* × *base*."""
        return float(random.uniform(0, base * self._jitter))  # noqa: S311


def _future(seconds: float) -> datetime:
    """Return a UTC datetime *seconds* from now."""
    from datetime import timedelta

    return datetime.now(UTC) + timedelta(seconds=seconds)
