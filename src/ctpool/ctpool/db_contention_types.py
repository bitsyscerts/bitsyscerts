"""Typed payloads used by the shared DB contention controller.

Exports:
    DbContentionObservation — One worker-boundary sample of DB retry pressure.
    DbContentionDirective   — Shared pacing hint consumed by workers.
    DbContentionStateView   — Serializable controller state snapshot.
    DbContentionOperatorSnapshot — Normalized operator-facing contention status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class DbContentionObservation:
    """One worker-boundary sample of retryable database pressure."""

    entries_attempted: int
    retryable_errors: int

    @property
    def has_activity(self) -> bool:
        """Return True when the boundary attempted at least one entry write."""
        return self.entries_attempted > 0

    @property
    def retry_ratio(self) -> float:
        """Return retries per attempted entry for this boundary."""
        if self.entries_attempted <= 0:
            return 0.0
        return self.retryable_errors / self.entries_attempted


@dataclass(frozen=True)
class DbContentionDirective:
    """Shared pacing hint that workers apply at loop or batch boundaries."""

    pressure_ema: float
    base_sleep_seconds: float
    batch_size_cap: int | None


@dataclass(frozen=True)
class DbContentionStateView:
    """Serializable snapshot of shared DB contention controller state."""

    pressure_ema: float = 0.0
    extra_sleep_seconds: float = 0.0
    batch_size_cap: int | None = None
    healthy_streak: int = 0
    updated_at: datetime | None = None


DbContentionOperatorStatus = Literal[
    "disabled",
    "initializing",
    "healthy",
    "throttling",
    "stale",
]


@dataclass(frozen=True)
class DbContentionOperatorSnapshot:
    """Normalized shared contention state shown in operator-facing stats."""

    status: DbContentionOperatorStatus
    degraded_mode_active: bool
    pressure_ema: float
    base_sleep_seconds: float
    shared_batch_size_cap: int | None
    effective_batch_size_cap: int | None
    updated_at: datetime | None
    notes: list[str]
