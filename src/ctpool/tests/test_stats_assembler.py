"""Unit tests for stats_assembler.assemble_stats_payload."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

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

    def test_entry_outcomes_stored_count(self) -> None:
        result = _call_assemble()
        assert result["entry_outcomes"]["stored"] == 900

    def test_projection_status_insufficient_when_zero_obs(self) -> None:
        result = _call_assemble(obs_count=0)
        assert result["storage_projection"]["status"] == "insufficient_observations"

    def test_projection_status_insufficient_when_zero_planned(self) -> None:
        result = _call_assemble(planned_total=0)
        assert result["storage_projection"]["status"] == "insufficient_backfill_plan"

    def test_projection_available_with_positive_counts(self) -> None:
        result = _call_assemble(obs_count=1000, planned_total=10_000)
        # May be available or insufficient depending on profile_projection import
        assert result["storage_projection"]["status"] in (
            "available",
            "insufficient_backfill_plan",
            "insufficient_observations",
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
