"""Unit tests for ctpool.prune_reporter.

Covers:
    - PruneSummary: default values and status tracking
    - PruneReporter: announce, batch_progress, print_summary (smoke tests)
"""

from __future__ import annotations

from datetime import UTC, datetime

from ctpool.prune_reporter import PruneReporter, PruneSummary


def _make_summary(**kwargs) -> PruneSummary:
    defaults = {
        "mode": "dry_run",
        "retention_days": 30,
        "cutoff": datetime(2025, 1, 1, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return PruneSummary(**defaults)


# ---------------------------------------------------------------------------
# PruneSummary
# ---------------------------------------------------------------------------


def test_prune_summary_default_values():
    s = _make_summary()
    assert s.candidate_certificates == 0
    assert s.blocked_latest_certificates == 0
    assert s.blocked_missing_summary == 0
    assert s.deleted_certificates == 0
    assert s.status == "running"
    assert s.error_message is None


def test_prune_summary_status_transitions():
    s = _make_summary()
    s.status = "complete"
    assert s.status == "complete"
    s.status = "failed"
    s.error_message = "oops"
    assert s.status == "failed"
    assert s.error_message == "oops"


# ---------------------------------------------------------------------------
# PruneReporter
# ---------------------------------------------------------------------------


def test_prune_reporter_announce_does_not_raise():
    from rich.console import Console

    console = Console(quiet=True)
    reporter = PruneReporter(console)
    s = _make_summary(mode="execute")
    reporter.announce(s)  # must not raise


def test_prune_reporter_batch_progress_does_not_raise():
    from rich.console import Console

    console = Console(quiet=True)
    reporter = PruneReporter(console)
    s = _make_summary()
    s.deleted_certificates = 150
    s.batches_processed = 1
    reporter.batch_progress(s)  # must not raise


def test_prune_reporter_print_summary_dry_run():
    from rich.console import Console

    console = Console(quiet=True)
    reporter = PruneReporter(console)
    s = _make_summary(mode="dry_run")
    s.status = "dry_run"
    reporter.print_summary(s)  # must not raise


def test_prune_reporter_print_summary_with_error():
    from rich.console import Console

    console = Console(quiet=True)
    reporter = PruneReporter(console)
    s = _make_summary(mode="execute")
    s.status = "failed"
    s.error_message = "DB connection lost"
    reporter.print_summary(s)  # must not raise
