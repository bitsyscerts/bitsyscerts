"""Dispatcher shim: re-exports from dispatcher_tail and dispatcher_backfill.

All implementation now lives in:
  - ``dispatcher_tail``     — tail log eligibility, cursors, and lease functions
  - ``dispatcher_backfill`` — backfill range creation, claiming, and lifecycle

This shim preserves all existing import paths.
"""

from ctpool.dispatcher_backfill import (
    claim_backfill_range,
    create_backfill_ranges,
    get_eligible_backfill_logs,
    has_backfill_ranges,
    mark_range_complete,
    mark_range_failed,
    mark_range_pending,
    reap_stale_backfill_claims,
    update_range_heartbeat,
)
from ctpool.dispatcher_tail import (
    advance_tail_cursor,
    claim_tail_log,
    ensure_tail_cursor,
    get_eligible_tail_logs,
    heartbeat_tail_lease,
    reap_stale_tail_leases,
    release_tail_log,
    reset_tail_cursor,
    try_claim_tail_log,
)

__all__ = [
    "advance_tail_cursor",
    "claim_backfill_range",
    "claim_tail_log",
    "create_backfill_ranges",
    "ensure_tail_cursor",
    "get_eligible_backfill_logs",
    "get_eligible_tail_logs",
    "has_backfill_ranges",
    "heartbeat_tail_lease",
    "mark_range_complete",
    "mark_range_failed",
    "mark_range_pending",
    "reap_stale_backfill_claims",
    "reap_stale_tail_leases",
    "release_tail_log",
    "reset_tail_cursor",
    "try_claim_tail_log",
    "update_range_heartbeat",
]
