"""Tests for ctpool.maintenance_queries pure helpers.

The DB-backed ``query_latest_maintenance_run`` is exercised indirectly via
the orchestrator integration; here we cover the pure projection helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ctpool.maintenance_queries import compute_next_due, is_lite_enforced


class TestComputeNextDue:
    def test_returns_none_for_missing_started_at(self) -> None:
        assert compute_next_due(None, 3600) is None

    def test_returns_none_for_zero_interval(self) -> None:
        assert compute_next_due(datetime.now(UTC), 0) is None

    def test_adds_interval_to_started_at(self) -> None:
        now = datetime.now(UTC)
        nxt = compute_next_due(now, 60)
        assert nxt is not None
        assert (nxt - now).total_seconds() == 60


class TestIsLiteEnforced:
    def _make_run(self, **overrides: object) -> dict[str, object]:
        run: dict[str, object] = {
            "status": "complete",
            "mode": "execute",
            "completed_at": datetime.now(UTC),
        }
        run.update(overrides)
        return run

    def test_none_run_is_not_enforced(self) -> None:
        assert is_lite_enforced(None, interval_seconds=3600) is False

    def test_failed_status_is_not_enforced(self) -> None:
        run = self._make_run(status="failed")
        assert is_lite_enforced(run, interval_seconds=3600) is False

    def test_dry_run_mode_is_not_enforced(self) -> None:
        run = self._make_run(mode="dry_run")
        assert is_lite_enforced(run, interval_seconds=3600) is False

    def test_recent_execute_run_is_enforced(self) -> None:
        run = self._make_run()
        assert is_lite_enforced(run, interval_seconds=3600) is True

    def test_stale_run_is_not_enforced(self) -> None:
        # Older than 2× interval (default grace factor) → not enforced.
        run = self._make_run(completed_at=datetime.now(UTC) - timedelta(hours=10))
        assert is_lite_enforced(run, interval_seconds=3600) is False

    def test_missing_completed_at_is_not_enforced(self) -> None:
        run = self._make_run(completed_at=None)
        assert is_lite_enforced(run, interval_seconds=3600) is False
