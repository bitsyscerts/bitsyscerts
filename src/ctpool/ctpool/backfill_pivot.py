"""Pure pivot-estimation helpers for the CT backfill worker.

Exports:
    estimate_log_age_days — Estimate a CT log's age in days from STH timestamp.
    compute_pivot_index   — Calculate the start index for a days-bounded backfill.
"""

from __future__ import annotations

from datetime import datetime

# Milliseconds-per-day constant used by the pivot estimation.
_MS_PER_DAY: float = 86_400_000.0


def estimate_log_age_days(
    sth_timestamp_ms: int,
    first_seen_at: datetime | None,
) -> float:
    """Return a CT log's approximate age in days.

    Uses the STH millisecond timestamp as *now* and ``first_seen_at`` as the
    log creation proxy.  Returns ``0.0`` if the result would be negative or
    ``first_seen_at`` is ``None``.

    Args:
        sth_timestamp_ms: Milliseconds since epoch from the log's signed tree head.
        first_seen_at:    When this log was first observed (from ``CtLogSource``).
                          ``None`` is treated as unknown → returns ``0.0``.

    Returns:
        Age in days as a float, minimum ``0.0``.
    """
    if first_seen_at is None:
        return 0.0
    first_seen_ms = first_seen_at.timestamp() * 1000.0
    age_ms = sth_timestamp_ms - first_seen_ms
    return max(0.0, age_ms / _MS_PER_DAY)


def compute_pivot_index(
    tree_size: int,
    days: int,
    log_age_days: float,
) -> int:
    """Return the start index for a days-bounded backfill window.

    Estimates the index corresponding to ``days`` ago by assuming uniform
    certificate issuance over the log's lifetime.  Returns ``0`` when the
    window covers the full history or the age estimate is not usable.

    Args:
        tree_size:    Current tree size (number of entries in the log).
        days:         How far back to backfill (0 means full history).
        log_age_days: Estimated total age of the log in days.

    Returns:
        First index to include; always in ``[0, tree_size)``.
    """
    if tree_size == 0 or days <= 0 or log_age_days <= 0 or days >= log_age_days:
        return 0
    fraction_to_skip = 1.0 - (days / log_age_days)
    return max(0, min(int(tree_size * fraction_to_skip), tree_size - 1))
