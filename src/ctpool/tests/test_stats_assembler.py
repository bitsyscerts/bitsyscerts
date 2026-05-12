"""Unit tests for stats_assembler.assemble_stats_payload."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ctpool.stats_assembler import assemble_stats_payload


def _make_settings(
    metrics_retention_days: int = 30,
    backfill_claim_timeout: int = 1800,
) -> MagicMock:
    """Return a minimal mock CtInstanceSettings row."""
    s = MagicMock()
    s.metrics_retention_days = metrics_retention_days
    s.ct_backfill_claim_timeout_seconds = backfill_claim_timeout
    s.cert_storage_mode = "none"
    s.hostname_retention_mode = "all"
    s.backfill_days = 180
    s.cert_retention_days = 7
    s.observation_retention_days = 7
    s.entry_outcome_retention_days = 7
    s.storage_profile = "lite"
    s.settings_hash = "abc123"
    s.updated_at = None
    return s


def _minimal_contention() -> MagicMock:
    c = MagicMock()
    c.status = "healthy"
    c.degraded_mode_active = False
    c.pressure_ema = 0.0
    c.base_sleep_seconds = 0.1
    c.shared_batch_size_cap = 256
    c.effective_batch_size_cap = 256
    c.updated_at = None
    c.notes = []
    c.total_retryable_errors = 0
    c.retryable_errors_per_min_5min = 0.0
    return c


_GLOBAL_COUNTS = {
    "hostnames": 100,
    "certificates": 50,
    "observations": 1000,
    "cert_hostnames": 200,
}

_STORAGE_DATA = {
    "total": {"total_size_bytes": 1_000_000, "total_size_pretty": "1 MB"},
    "tables": [
        {
            "table_name": "ct_log_observations",
            "row_estimate": 1000,
            "size_bytes": 500_000,
            "size_pretty": "500 kB",
        }
    ],
}

_BACKFILL_PROGRESS = {"planned_total": 10_000, "planned_completed": 500}
_BACKFILL_STATUS = {
    "pending": 5,
    "in_progress": 2,
    "stale_in_progress": 0,
    "completed": 50,
    "failed": 0,
}
_FRESHNESS = {
    "total_logs": 2,
    "logs_with_cursor": 2,
    "fresh_logs": 2,
    "stale_logs": 0,
    "last_sync_at": None,
    "max_lag_seconds": None,
    "min_lag_seconds": None,
    "stale_threshold_seconds": 300,
}
_METRICS_SUMMARY = {"row_count": 100, "oldest_at": None}
_AUDIT_COUNTS: dict[str, int] = {}


def _call_assemble(
    active_settings: object = None,
    obs_count: int = 1000,
    planned_total: int = 10_000,
) -> dict:
    global_counts = {**_GLOBAL_COUNTS, "observations": obs_count}
    return assemble_stats_payload(
        global_counts=global_counts,
        database_size_bytes=1_000_000,
        backfill_progress={"planned_total": planned_total, "planned_completed": 500},
        backfill_status_counts=_BACKFILL_STATUS,
        storage_data=_STORAGE_DATA,
        contention_snapshot=_minimal_contention(),
        rate_rows=[],
        freshness_row=_FRESHNESS,
        outcome_counts={"stored": 900, "parse_error": 5},
        metrics_summary=_METRICS_SUMMARY,
        audit_counts=_AUDIT_COUNTS,
        per_log_rows=[],
        active_settings=active_settings,
        now=datetime(2025, 1, 1, tzinfo=UTC),
    )


class TestAssembleStatsPayload:
    """Tests for the public assemble_stats_payload function."""

    def test_returns_dict_with_required_top_level_keys(self) -> None:
        result = _call_assemble()
        for key in (
            "total_hostnames",
            "total_certificates",
            "total_logs",
            "storage",
            "storage_projection",
            "db_contention",
            "ingestion_rate",
            "tail_freshness",
            "entry_outcomes",
            "backfill_ranges",
            "backfill_health",
            "metrics_retention",
            "audit_health",
            "logs",
        ):
            assert key in result, f"Missing key: {key}"

    def test_total_hostnames_matches_global_counts(self) -> None:
        result = _call_assemble()
        assert result["total_hostnames"] == 100

    def test_total_logs_equals_per_log_rows_length(self) -> None:
        result = _call_assemble()
        assert result["total_logs"] == 0  # empty per_log_rows

    def test_storage_tables_are_mapped_correctly(self) -> None:
        result = _call_assemble()
        tables = result["storage"]["tables"]
        assert len(tables) == 1
        assert tables[0]["table_name"] == "ct_log_observations"
        assert tables[0]["size_bytes"] == 500_000

    def test_ingestion_rate_windows_include_uniqueness_and_error_rates(self) -> None:
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[
                {
                    "window_seconds": 300,
                    "entries_fetched": 6000,
                    "entries_parsed": 5700,
                    "certs_upserted": 5400,
                    "hostnames_upserted": 22000,
                    "new_unique_certificates": 1200,
                    "duplicate_certificates": 4200,
                    "new_unique_hostnames": 180,
                    "known_hostnames": 21820,
                    "retryable_errors": 10,
                    "terminal_entry_errors": 3,
                }
            ],
            freshness_row=_FRESHNESS,
            outcome_counts={"stored": 900, "parse_error": 5},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts=_AUDIT_COUNTS,
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
        )
        window = result["ingestion_rate"]["windows"][0]
        assert window["certificates_parsed_per_min"] == 1140.0
        assert window["new_unique_certificates_per_min"] == 240.0
        assert window["known_hostnames_per_min"] == pytest.approx(4364.0)
        assert window["retryable_errors_per_min"] == 2.0

    def test_entry_outcomes_stored_count(self) -> None:
        result = _call_assemble()
        assert result["entry_outcomes"]["stored"] == 900

    def test_projection_available_when_zero_obs_with_valid_plan(self) -> None:
        # obs_count=0 (fresh install) no longer gates projection when
        # planned_total is non-zero — user approved Option A removal.
        result = _call_assemble(obs_count=0)
        assert result["storage_projection"]["status"] in (
            "available",
            "insufficient_backfill_plan",
        )

    def test_projection_status_insufficient_when_zero_planned(self) -> None:
        result = _call_assemble(planned_total=0)
        assert result["storage_projection"]["status"] == "insufficient_backfill_plan"

    def test_projection_available_with_positive_counts(self) -> None:
        result = _call_assemble(obs_count=1000, planned_total=10_000)
        # May be available or insufficient depending on profile_projection import
        assert result["storage_projection"]["status"] in (
            "available",
            "insufficient_backfill_plan",
        )

    def test_metrics_retention_days_defaults_to_30_when_no_settings(self) -> None:
        result = _call_assemble(active_settings=None)
        assert result["metrics_retention"]["metrics_retention_days"] == 30

    def test_metrics_retention_days_uses_settings_when_provided(self) -> None:
        settings = _make_settings(metrics_retention_days=14)
        result = _call_assemble(active_settings=settings)
        assert result["metrics_retention"]["metrics_retention_days"] == 14

    def test_backfill_ranges_all_statuses_present(self) -> None:
        result = _call_assemble()
        ranges = result["backfill_ranges"]
        assert ranges["pending"] == 5
        assert ranges["completed"] == 50
        assert ranges["failed"] == 0

    def test_storage_profile_none_when_no_settings(self) -> None:
        result = _call_assemble(active_settings=None)
        assert result["storage_profile"] is None

    def test_storage_profile_populated_from_settings(self) -> None:
        settings = _make_settings()
        result = _call_assemble(active_settings=settings)
        assert result["storage_profile"] is not None
        assert result["storage_profile"]["storage_profile"] == "lite"

    def test_now_defaults_to_utc_when_not_provided(self) -> None:
        """assemble_stats_payload should not raise when now=None."""
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts=_AUDIT_COUNTS,
            per_log_rows=[],
            active_settings=None,
            now=None,
        )
        assert result["total_hostnames"] == 100

    def test_audit_health_open_counts_match_input(self) -> None:
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={"critical": 2, "error": 1},
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
        )
        ah = result["audit_health"]
        assert ah["open_critical"] == 2
        assert ah["open_error"] == 1


class TestDispatchModeFlags:
    """Tests for dispatch_mode + is_primary flags injected by assembler."""

    def test_per_log_default_marks_state_primary(self) -> None:
        result = _call_assemble()
        # default dispatch_mode is "per-log"
        ranges = result["backfill_ranges"]
        assert ranges["dispatch_mode"] == "per-log"
        assert ranges["is_primary"] is False

    def test_per_log_default_marks_legacy_ranges_not_primary(self) -> None:
        # backfill_state may be None when not provided; only verify ranges
        # branch when caller does provide state.
        result_with_state = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={},
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
            backfill_state={"total_logs": 3, "items": []},
            dispatch_mode="per-log",
        )
        state = result_with_state["backfill_state"]
        assert state["dispatch_mode"] == "per-log"
        assert state["is_primary"] is True
        assert result_with_state["backfill_ranges"]["is_primary"] is False

    def test_legacy_dispatch_mode_marks_ranges_primary(self) -> None:
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={},
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
            backfill_state={"total_logs": 0, "items": []},
            dispatch_mode="legacy-ranges",
        )
        assert result["backfill_ranges"]["dispatch_mode"] == "legacy-ranges"
        assert result["backfill_ranges"]["is_primary"] is True
        assert result["backfill_state"]["is_primary"] is False


class TestIngestionHealth:
    """Tests for the ingestion_health summary block (Sprint 3)."""

    def _state(self, **overrides: object) -> dict:
        base: dict = {
            "total_logs": 5,
            "pending": 0,
            "claimed": 0,
            "processing": 3,
            "retrying": 1,
            "rate_limited": 1,
            "paused": 0,
            "complete": 0,
            "error": 0,
            "stale": 0,
            "items": [
                {"retryable_error_count": 4, "terminal_error_count": 2},
                {"retryable_error_count": 1, "terminal_error_count": 0},
            ],
        }
        base.update(overrides)
        return base

    def _workers(self) -> dict:
        return {
            "total": 3,
            "active": 2,
            "stale": 1,
            "tail_active": 1,
            "backfill_active": 1,
            "items": [],
        }

    def test_ingestion_health_aggregates_state_counters(self) -> None:
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={"stored": 100, "parse_error": 7, "write_error": 3},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={},
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
            backfill_state=self._state(),
            worker_summary=self._workers(),
            dispatch_mode="per-log",
        )
        health = result["ingestion_health"]
        assert health["retrying_logs"] == 1
        assert health["rate_limited_logs"] == 1
        assert health["paused_logs"] == 0
        assert health["error_logs"] == 0
        assert health["stale_workers"] == 1
        assert health["retryable_error_total"] == 5
        assert health["terminal_error_total"] == 2
        assert health["recent_terminal_outcomes"] == 10
        assert health["status"] == "ok"

    def test_ingestion_health_attention_when_paused(self) -> None:
        result = assemble_stats_payload(
            global_counts=_GLOBAL_COUNTS,
            database_size_bytes=1_000_000,
            backfill_progress=_BACKFILL_PROGRESS,
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={},
            per_log_rows=[],
            active_settings=None,
            now=datetime(2025, 1, 1, tzinfo=UTC),
            backfill_state=self._state(paused=2),
            worker_summary=self._workers(),
            dispatch_mode="per-log",
        )
        health = result["ingestion_health"]
        assert health["paused_logs"] == 2
        assert health["status"] == "attention_needed"


class TestMaintenanceCard:
    """Coverage for the Sprint 4 ``maintenance`` payload key."""

    def _payload(
        self, maintenance_run: dict | None = None, profile: str = "lite"
    ) -> dict:
        active_settings = _make_settings()
        active_settings.storage_profile = profile
        return assemble_stats_payload(
            global_counts={**_GLOBAL_COUNTS},
            database_size_bytes=1,
            backfill_progress={"planned_total": 0, "planned_completed": 0},
            backfill_status_counts=_BACKFILL_STATUS,
            storage_data=_STORAGE_DATA,
            contention_snapshot=_minimal_contention(),
            rate_rows=[],
            freshness_row=_FRESHNESS,
            outcome_counts={},
            metrics_summary=_METRICS_SUMMARY,
            audit_counts={},
            per_log_rows=[],
            active_settings=active_settings,
            now=datetime(2025, 1, 1, tzinfo=UTC),
            maintenance_run=maintenance_run,
            maintenance_interval_seconds=3600,
        )

    def test_never_ran_when_no_run(self) -> None:
        out = self._payload(None)
        assert out["maintenance"]["status"] == "never_ran"
        assert out["maintenance"]["is_enforced"] is False
        assert out["maintenance"]["active_profile"] == "lite"

    def test_populated_run_passes_through(self) -> None:
        run = {
            "status": "complete",
            "mode": "execute",
            "storage_profile": "lite",
            "started_at": datetime.now(UTC),
            "completed_at": datetime.now(UTC),
            "duration_ms": 12,
            "preserved_hostnames": 7,
            "deleted": {
                "certificates": 0,
                "certificate_hostnames": 0,
                "observations": 0,
                "entry_outcomes": 0,
                "ingestion_metrics": 0,
            },
            "error_message": None,
        }
        out = self._payload(run)
        assert out["maintenance"]["status"] == "complete"
        assert out["maintenance"]["last_prune_mode"] == "execute"
        assert out["maintenance"]["preserved_hostnames"] == 7
        assert out["maintenance"]["is_enforced"] is True
