"""Pure coverage math for the adaptive backfill window.

All functions are side-effect-free and independently unit-testable.
They answer three questions a backfill worker needs to self-correct:

1. What is the coverage target date for a given lookback window?
2. Has the worker already seen a cert that reaches that target?
3. If not, how many extra entries should we go back, and what is
   the new ``backfill_start_index``?
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

_FALLBACK_ENTRIES_PER_DAY: int = 50_000
"""Conservative fallback density when a batch spans < 1 second."""


def coverage_target_date(backfill_days: int) -> datetime:
    """Return ``utcnow − backfill_days`` as a timezone-aware datetime."""
    return datetime.now(tz=UTC) - timedelta(days=backfill_days)


def coverage_reached(
    oldest_not_before: datetime | None,
    target: datetime,
) -> bool:
    """Return True when *oldest_not_before* is on or before *target*.

    ``None`` means no cert has been observed yet → coverage not reached.
    """
    if oldest_not_before is None:
        return False
    return oldest_not_before <= target


def estimate_extension_entries(
    batch_entries: int,
    batch_oldest: datetime,
    batch_newest: datetime,
    missing_days: float,
) -> int:
    """Estimate how many additional index entries cover *missing_days*.

    Uses the observed entry density from the current batch.  When the
    batch time span is less than one second (degenerate input), falls
    back to ``_FALLBACK_ENTRIES_PER_DAY``.

    Args:
        batch_entries: Number of successfully written entries in the batch.
        batch_oldest:  Oldest ``not_before`` seen in the batch.
        batch_newest:  Newest ``not_before`` seen in the batch.
        missing_days:  How many additional days of coverage are needed.

    Returns:
        A positive integer — the estimated number of entries to go back.
        Always at least 1.
    """
    if missing_days <= 0:
        return 1

    span_seconds = (batch_newest - batch_oldest).total_seconds()
    if span_seconds < 1.0 or batch_entries < 1:
        entries_per_day: float = _FALLBACK_ENTRIES_PER_DAY
    else:
        entries_per_day = batch_entries / (span_seconds / 86_400.0)

    return max(1, int(entries_per_day * missing_days))


def compute_extended_start(current_start: int, extension_entries: int) -> int:
    """Return the new ``backfill_start_index``, floored at 0.

    The window only ever grows backward; the result is always ≤ *current_start*.
    """
    return max(0, current_start - extension_entries)
