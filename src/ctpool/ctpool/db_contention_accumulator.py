"""Accumulate retryable DB retry signals across one worker boundary."""

from __future__ import annotations

from collections.abc import Callable

from ctpool.db_contention_types import DbContentionObservation


class DbRetryPressureAccumulator:
    """Track attempted entries and retryable DB retries until drained."""

    def __init__(self) -> None:
        self._entries_attempted = 0
        self._retryable_errors = 0

    def record_entry_attempt(self) -> None:
        """Increment the attempted-entry counter by one."""
        self._entries_attempted += 1

    def record_retryable_error(self) -> None:
        """Increment the retryable-error counter by one."""
        self._retryable_errors += 1

    def wrap_retry_callback(
        self,
        callback: Callable[[int, BaseException, float], None] | None,
    ) -> Callable[[int, BaseException, float], None]:
        """Return a callback that records retryable errors before delegating."""

        def _wrapped(attempt: int, exc: BaseException, delay: float) -> None:
            self.record_retryable_error()
            if callback is not None:
                callback(attempt, exc, delay)

        return _wrapped

    def drain(self) -> DbContentionObservation:
        """Return the current observation and reset the accumulator."""
        observation = DbContentionObservation(
            entries_attempted=self._entries_attempted,
            retryable_errors=self._retryable_errors,
        )
        self._entries_attempted = 0
        self._retryable_errors = 0
        return observation
