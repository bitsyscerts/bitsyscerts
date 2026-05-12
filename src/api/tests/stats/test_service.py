"""Tests for StatsService — mocked repository."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from ctpool.db_contention_types import DbContentionOperatorSnapshot

from certsapi.stats.models import StatsResponse
from certsapi.stats.response_builders import (
    build_ingestion_rate_stats as _build_ingestion_rate_stats,
)
from certsapi.stats.response_builders import (
    build_tail_freshness_stats as _build_tail_freshness_stats,
)
from certsapi.stats.service import StatsService


def _make_row(
    log_id: uuid.UUID | None = None,
    complete: int = 5,
    total: int = 10,
    tail_pos: int = 500,
    last_tail_sync: datetime | None = None,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: {
        "id": log_id or uuid.uuid4(),
        "description": "Test Log",
        "url": "https://ct.test/",
        "log_state": "usable",
        "tail_position": tail_pos,
        "last_tail_sync": last_tail_sync or datetime.now(UTC),
        "complete_ranges": complete,
        "total_ranges": total,
    }[k]
    return row


def _make_freshness_row(
    oldest: int | None = None,
    median: int | None = None,
    stale: int = 0,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: {
        "oldest_lag_seconds": oldest,
        "median_lag_seconds": median,
        "stale_log_count": stale,
    }[k]
    return row


def _make_storage_data(
    total_bytes: int = 1024 * 1024,
    pretty: str = "1 MB",
) -> dict:
    return {
        "total": {
            "total_size_bytes": total_bytes,
            "total_size_pretty": pretty,
        },
        "tables": [
            {
                "table_name": "hostnames",
                "row_estimate": 100,
                "size_bytes": 512 * 1024,
                "size_pretty": "512 kB",
            }
        ],
    }


def _repo_with_defaults(**overrides: object) -> AsyncMock:
    repo = AsyncMock()
    repo.total_hostnames.return_value = overrides.get("total_hostnames", 0)
    repo.total_certificates.return_value = overrides.get("total_certificates", 0)
    repo.total_logs.return_value = overrides.get("total_logs", 0)
    repo.total_ct_observations.return_value = overrides.get("total_ct_observations", 0)
    repo.total_certificate_hostnames.return_value = overrides.get(
        "total_certificate_hostnames",
        0,
    )
    repo.per_log_stats.return_value = overrides.get("per_log_stats", [])
    repo.backfill_observation_progress.return_value = overrides.get(
        "backfill_observation_progress",
        {
            "planned_observations_total": 0,
            "planned_observations_completed": 0,
        },
    )
    repo.db_storage.return_value = overrides.get("db_storage", _make_storage_data())
    repo.db_contention_snapshot.return_value = overrides.get(
        "db_contention_snapshot",
        DbContentionOperatorSnapshot(
            status="initializing",
            degraded_mode_active=False,
            pressure_ema=0.0,
            base_sleep_seconds=0.0,
            shared_batch_size_cap=None,
            effective_batch_size_cap=None,
            updated_at=None,
            notes=["No shared DB contention state has been recorded yet."],
        ),
    )
    repo.ingestion_rate_stats.return_value = overrides.get(
        "ingestion_rate_stats",
        [
            {
                "window_seconds": 300,
                "entries_fetched": 0,
                "entries_parsed": 0,
                "certs_upserted": 0,
                "hostnames_upserted": 0,
                "new_unique_certificates": 0,
                "duplicate_certificates": 0,
                "new_unique_hostnames": 0,
                "known_hostnames": 0,
                "retryable_errors": 0,
                "terminal_entry_errors": 0,
            }
        ],
    )
    repo.tail_freshness_summary.return_value = overrides.get(
        "tail_freshness_summary",
        _make_freshness_row(),
    )
    repo.entry_outcome_counts.return_value = overrides.get(
        "entry_outcome_counts",
        {
            "stored": 0,
            "parse_error": 0,
            "unsupported_entry_type": 0,
            "skipped_by_policy": 0,
        },
    )
    repo.backfill_range_status_counts.return_value = overrides.get(
        "backfill_range_status_counts",
        {
            "pending": 0,
            "in_progress": 0,
            "stale_in_progress": 0,
            "completed": 0,
            "failed": 0,
        },
    )
    repo.worker_summary.return_value = overrides.get(
        "worker_summary",
        {
            "active_total": 0,
            "stale_total": 0,
            "tail_active": 0,
            "backfill_active": 0,
            "stats_active": 0,
            "maintenance_active": 0,
            "unknown_active": 0,
            "items": [],
        },
    )
    repo.backfill_state_summary.return_value = overrides.get(
        "backfill_state_summary",
        {
            "total_logs": 0,
            "pending": 0,
            "claimed": 0,
            "processing": 0,
            "retrying": 0,
            "rate_limited": 0,
            "paused": 0,
            "complete": 0,
            "error": 0,
            "stale": 0,
            "items": [],
        },
    )
    repo.latest_maintenance_run.return_value = overrides.get(
        "latest_maintenance_run",
        None,
    )
    repo.ingestion_metrics_summary.return_value = overrides.get(
        "ingestion_metrics_summary",
        {
            "row_count": 0,
            "oldest_at": None,
        },
    )
    repo.audit_health_counts.return_value = overrides.get(
        "audit_health_counts",
        {"critical": 0, "error": 0, "warning": 0, "info": 0},
    )
    repo.get_active_instance_settings.return_value = overrides.get(
        "active_instance_settings",
        None,
    )
    repo.get_snapshot_age_seconds.return_value = overrides.get(
        "snapshot_age_seconds",
        None,
    )
    repo.get_latest_snapshot.return_value = overrides.get(
        "latest_snapshot",
        None,
    )
    repo.ct_log_progress_totals.return_value = overrides.get(
        "ct_log_progress_totals",
        {"planned_total": 0, "planned_completed": 0},
    )
    repo._ctpool_settings = overrides.get("ctpool_settings", None)
    return repo


class TestStatsService:
    async def test_returns_stats_response(self) -> None:
        repo = _repo_with_defaults(
            total_hostnames=100,
            total_certificates=50,
            total_logs=3,
            per_log_stats=[_make_row()],
        )
        result = await StatsService(repo).get_stats()
        assert isinstance(result, StatsResponse)
        assert result.total_hostnames == 100
        assert result.total_certificates == 50
        assert result.total_logs == 3

    async def test_snapshot_metadata_marks_fresh_payload_not_stale(self) -> None:
        """Sprint 5: a young snapshot age yields ``is_stale=false``."""
        repo = _repo_with_defaults(snapshot_age_seconds=12.0)
        result = await StatsService(repo).get_stats()
        assert result.snapshot is not None
        assert result.snapshot.age_seconds == pytest.approx(12.0)
        assert result.snapshot.is_stale is False
        assert result.snapshot.source in {"snapshot", "live"}

    async def test_snapshot_metadata_flags_stale_payload(self) -> None:
        """Sprint 5: an old snapshot age yields ``is_stale=true``."""
        repo = _repo_with_defaults(snapshot_age_seconds=999.0)
        result = await StatsService(repo).get_stats()
        assert result.snapshot is not None
        assert result.snapshot.is_stale is True

    async def test_snapshot_metadata_source_none_when_no_snapshot(self) -> None:
        """Sprint 5: ``source='none'`` when there has never been a snapshot."""
        repo = _repo_with_defaults(snapshot_age_seconds=None)
        result = await StatsService(repo).get_stats()
        assert result.snapshot is not None
        assert result.snapshot.age_seconds is None
        assert result.snapshot.source == "none"

    async def test_ingestion_rate_window_exposes_precise_aliases(self) -> None:
        """Sprint 5: precise ``*_per_min`` aliases populated alongside legacy."""
        repo = _repo_with_defaults(
            ingestion_rate_stats=[
                {
                    "window_seconds": 300,
                    "entries_fetched": 6000,
                    "entries_parsed": 1500,
                    "certs_upserted": 1500,
                    "hostnames_upserted": 3000,
                    "new_unique_certificates": 400,
                    "duplicate_certificates": 1100,
                    "new_unique_hostnames": 120,
                    "known_hostnames": 2880,
                    "retryable_errors": 5,
                    "terminal_entry_errors": 1,
                }
            ]
        )
        result = await StatsService(repo).get_stats()
        assert result.ingestion_rate.windows
        win = result.ingestion_rate.windows[0]
        assert win.observations_per_min == pytest.approx(6000 / 300 * 60)
        assert win.certificates_parsed_per_min == pytest.approx(300.0)
        assert win.new_unique_certificates_per_min == pytest.approx(80.0)
        assert win.duplicate_certificates_per_min == pytest.approx(220.0)
        assert win.hostnames_observed_per_min == pytest.approx(win.hostnames_per_min)
        assert win.new_unique_hostnames_per_min == pytest.approx(24.0)
        assert win.known_hostnames_per_min == pytest.approx(576.0)
        assert win.retryable_errors_per_min == pytest.approx(1.0)
        assert win.terminal_entry_errors_per_min == pytest.approx(0.2)

    async def test_logs_list_populated(self) -> None:
        repo = _repo_with_defaults(total_logs=1, per_log_stats=[_make_row()])
        result = await StatsService(repo).get_stats()
        assert len(result.logs) == 1

    async def test_live_stats_include_worker_summary(self) -> None:
        repo = _repo_with_defaults(
            worker_summary={
                "active_total": 1,
                "stale_total": 0,
                "tail_active": 1,
                "backfill_active": 0,
                "stats_active": 0,
                "maintenance_active": 0,
                "unknown_active": 0,
                "items": [
                    {
                        "worker_id": "host:1234",
                        "worker_kind": "tail",
                        "log_source_id": None,
                        "log_name": "Test Log",
                        "log_url": None,
                        "log_operator": None,
                        "direction": "forward",
                        "status": "processing",
                        "is_stale": False,
                        "last_heartbeat_at": "2025-01-01T00:00:00Z",
                        "last_heartbeat_age_seconds": 5,
                        "started_at": "2025-01-01T00:00:00Z",
                        "current_index": 12,
                        "checkpoint_index": 11,
                        "batch_start_index": None,
                        "batch_end_index": None,
                        "processed_entries": 10,
                        "stored_certificates": 8,
                        "duplicate_certificates": 2,
                        "observed_hostnames": 4,
                        "new_hostnames": 1,
                        "parse_errors": 0,
                        "retryable_errors": 0,
                        "terminal_errors": 0,
                        "observations_per_min": 60.0,
                        "new_unique_certificates_per_min": 12.0,
                        "duplicate_certificates_per_min": 3.0,
                        "new_unique_hostnames_per_min": 2.0,
                        "known_hostnames_per_min": 2.0,
                        "retry_count": None,
                        "next_retry_at": None,
                        "rate_limited_until": None,
                        "last_error_type": None,
                        "last_error_message": None,
                    }
                ],
            }
        )

        result = await StatsService(repo).get_stats()

        assert result.workers is not None
        assert result.workers.active_total == 1
        assert result.workers.items[0].worker_id == "host:1234"

    async def test_backfill_pct_computed_correctly(self) -> None:
        repo = _repo_with_defaults(
            total_logs=1, per_log_stats=[_make_row(complete=3, total=4)]
        )
        result = await StatsService(repo).get_stats()
        assert result.logs[0].backfill_complete_pct == pytest.approx(75.0)

    async def test_backfill_pct_null_when_no_ranges(self) -> None:
        repo = _repo_with_defaults(
            total_logs=1, per_log_stats=[_make_row(complete=0, total=0)]
        )
        result = await StatsService(repo).get_stats()
        assert result.logs[0].backfill_complete_pct is None

    async def test_empty_logs_when_no_log_sources(self) -> None:
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.logs == []

    async def test_storage_totals_populated(self) -> None:
        repo = _repo_with_defaults(
            db_storage=_make_storage_data(
                total_bytes=700 * 1024 * 1024, pretty="700 MB"
            )
        )
        result = await StatsService(repo).get_stats()
        assert result.storage.total_size_bytes == 700 * 1024 * 1024
        assert result.storage.total_size_pretty == "700 MB"

    async def test_storage_tables_populated(self) -> None:
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert len(result.storage.tables) == 1
        assert result.storage.tables[0].table_name == "hostnames"
        assert result.storage.tables[0].size_pretty == "512 kB"

    async def test_storage_projection_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "certsapi.stats.service.read_disk_safety_snapshot",
            lambda: None,
        )
        repo = _repo_with_defaults(
            total_hostnames=25,
            total_certificates=10,
            total_ct_observations=100,
            total_certificate_hostnames=30,
            backfill_observation_progress={
                "planned_observations_total": 1_000,
                "planned_observations_completed": 250,
            },
            db_storage=_make_storage_data(total_bytes=10_000, pretty="10 KB"),
        )
        result = await StatsService(repo).get_stats()
        assert result.storage_projection.status == "available"
        assert result.storage_projection.bytes_per_observation_current == pytest.approx(
            100.0
        )
        assert (
            result.storage_projection.projected_remaining_database_size_bytes == 75_000
        )
        assert result.storage_projection.projected_final_database_size_bytes == 85_000
        assert result.storage_projection.sync_percent_by_observation == pytest.approx(
            0.25
        )

    async def test_storage_projection_unavailable_without_backfill_plan(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "certsapi.stats.service.read_disk_safety_snapshot",
            lambda: None,
        )
        repo = _repo_with_defaults(total_ct_observations=100)
        result = await StatsService(repo).get_stats()
        assert result.storage_projection.status == "insufficient_backfill_plan"
        assert result.storage_projection.sync_percent_by_observation is None

    async def test_db_contention_snapshot_included(self) -> None:
        repo = _repo_with_defaults(
            db_contention_snapshot=DbContentionOperatorSnapshot(
                status="throttling",
                degraded_mode_active=False,
                pressure_ema=0.25,
                base_sleep_seconds=0.5,
                shared_batch_size_cap=32,
                effective_batch_size_cap=32,
                updated_at=datetime.now(UTC),
                notes=["Shared DB contention throttling is currently active."],
            )
        )

        result = await StatsService(repo).get_stats()

        assert result.db_contention.status == "throttling"
        assert result.db_contention.effective_batch_size_cap == 32
        assert result.db_contention.base_sleep_seconds == pytest.approx(0.5)

    async def test_db_contention_retry_fields_populated(self) -> None:
        repo = _repo_with_defaults(
            db_contention_snapshot=DbContentionOperatorSnapshot(
                status="healthy",
                degraded_mode_active=False,
                pressure_ema=0.0,
                base_sleep_seconds=0.0,
                shared_batch_size_cap=None,
                effective_batch_size_cap=None,
                updated_at=datetime.now(UTC),
                notes=[],
                total_retryable_errors=15,
                retryable_errors_per_min_5min=3.0,
            )
        )
        result = await StatsService(repo).get_stats()
        assert result.db_contention.total_retryable_errors == 15
        assert result.db_contention.retryable_errors_per_min_5min == pytest.approx(3.0)

    async def test_ingestion_rate_windows_assembled(self) -> None:
        repo = _repo_with_defaults(
            ingestion_rate_stats=[
                {
                    "window_seconds": 300,
                    "entries_fetched": 600,
                    "entries_parsed": 120,
                    "certs_upserted": 120,
                    "hostnames_upserted": 60,
                    "new_unique_certificates": 20,
                    "duplicate_certificates": 100,
                    "new_unique_hostnames": 12,
                    "known_hostnames": 48,
                    "retryable_errors": 3,
                    "terminal_entry_errors": 1,
                }
            ]
        )
        result = await StatsService(repo).get_stats()
        assert len(result.ingestion_rate.windows) == 1
        w = result.ingestion_rate.windows[0]
        assert w.window_seconds == 300
        assert w.observations_per_sec == pytest.approx(2.0)
        assert w.certs_per_min == pytest.approx(24.0)
        assert w.hostnames_per_min == pytest.approx(12.0)

    async def test_ingestion_rate_zero_when_no_metrics(self) -> None:
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        w = result.ingestion_rate.windows[0]
        assert w.observations_per_sec == pytest.approx(0.0)
        assert w.certs_per_min == pytest.approx(0.0)

    async def test_tail_freshness_populated(self) -> None:
        repo = _repo_with_defaults(
            tail_freshness_summary=_make_freshness_row(oldest=900, median=300, stale=2)
        )
        result = await StatsService(repo).get_stats()
        assert result.tail_freshness.stale_log_count == 2
        assert result.tail_freshness.oldest_lag_seconds == 900
        assert result.tail_freshness.median_lag_seconds == 300

    async def test_tail_freshness_none_when_no_cursors(self) -> None:
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.tail_freshness.stale_log_count == 0
        assert result.tail_freshness.oldest_lag_seconds is None

    async def test_log_item_includes_freshness_lag(self) -> None:
        repo = _repo_with_defaults(total_logs=1, per_log_stats=[_make_row()])
        result = await StatsService(repo).get_stats()
        assert result.logs[0].tail_freshness_lag_seconds is not None
        assert result.logs[0].tail_freshness_lag_seconds >= 0

    async def test_log_item_lag_none_when_no_last_sync(self) -> None:
        row = _make_row()
        row.__getitem__.side_effect = lambda k: {
            "id": uuid.uuid4(),
            "description": "X",
            "url": "https://ct.test/",
            "log_state": "usable",
            "tail_position": None,
            "last_tail_sync": None,
            "complete_ranges": 0,
            "total_ranges": 0,
        }[k]
        repo = _repo_with_defaults(total_logs=1, per_log_stats=[row])
        result = await StatsService(repo).get_stats()
        assert result.logs[0].tail_freshness_lag_seconds is None

    async def test_entry_outcomes_defaults_to_zero(self) -> None:
        """When repository returns all-zero outcome counts, response reflects zeros."""
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.entry_outcomes.stored == 0
        assert result.entry_outcomes.parse_error == 0
        assert result.entry_outcomes.unsupported_entry_type == 0
        assert result.entry_outcomes.skipped_by_policy == 0

    async def test_entry_outcomes_populated_from_repository(self) -> None:
        """StatsService maps repository outcome counts into EntryOutcomeStats."""
        repo = _repo_with_defaults(
            entry_outcome_counts={
                "stored": 12345,
                "parse_error": 7,
                "unsupported_entry_type": 3,
                "skipped_by_policy": 1,
            }
        )
        result = await StatsService(repo).get_stats()
        assert result.entry_outcomes.stored == 12345
        assert result.entry_outcomes.parse_error == 7
        assert result.entry_outcomes.unsupported_entry_type == 3
        assert result.entry_outcomes.skipped_by_policy == 1


# ---------------------------------------------------------------------------
# _build_ingestion_rate_stats (pure function)
# ---------------------------------------------------------------------------


class TestBuildIngestionRateStats:
    def test_single_window_rates_computed_correctly(self) -> None:
        rows = cast(
            Sequence[Mapping[str, object]],
            [
                {
                    "window_seconds": 300,
                    "entries_fetched": 300,
                    "entries_parsed": 270,
                    "certs_upserted": 150,
                    "hostnames_upserted": 60,
                    "new_unique_certificates": 30,
                    "duplicate_certificates": 120,
                    "new_unique_hostnames": 9,
                    "known_hostnames": 51,
                    "retryable_errors": 3,
                    "terminal_entry_errors": 1,
                }
            ],
        )
        result = _build_ingestion_rate_stats(rows)
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.observations_per_sec == pytest.approx(1.0)
        assert w.certs_per_min == pytest.approx(54.0)
        assert w.hostnames_per_min == pytest.approx(12.0)
        assert w.new_unique_certificates_per_min == pytest.approx(6.0)
        assert w.duplicate_certificates_per_min == pytest.approx(24.0)
        assert w.new_unique_hostnames_per_min == pytest.approx(1.8)
        assert w.known_hostnames_per_min == pytest.approx(10.2)
        assert w.retryable_errors_per_min == pytest.approx(0.6)
        assert w.terminal_entry_errors_per_min == pytest.approx(0.2)

    def test_zero_counts_produce_zero_rates(self) -> None:
        rows = cast(
            Sequence[Mapping[str, object]],
            [
                {
                    "window_seconds": 300,
                    "entries_fetched": 0,
                    "entries_parsed": 0,
                    "certs_upserted": 0,
                    "hostnames_upserted": 0,
                    "new_unique_certificates": 0,
                    "duplicate_certificates": 0,
                    "new_unique_hostnames": 0,
                    "known_hostnames": 0,
                    "retryable_errors": 0,
                    "terminal_entry_errors": 0,
                }
            ],
        )
        result = _build_ingestion_rate_stats(rows)
        assert result.windows[0].observations_per_sec == pytest.approx(0.0)

    def test_empty_rows_produces_empty_windows(self) -> None:
        assert _build_ingestion_rate_stats([]).windows == []


# ---------------------------------------------------------------------------
# _build_tail_freshness_stats (pure function)
# ---------------------------------------------------------------------------


class TestBuildTailFreshnessStats:
    def test_happy_path(self) -> None:
        row = _make_freshness_row(oldest=600, median=120, stale=1)
        result = _build_tail_freshness_stats(row, stale_threshold_seconds=300)
        assert result.stale_log_count == 1
        assert result.oldest_lag_seconds == 600
        assert result.median_lag_seconds == 120
        assert result.stale_threshold_seconds == 300

    def test_none_values_surfaced_as_none(self) -> None:
        row = _make_freshness_row()
        result = _build_tail_freshness_stats(row, stale_threshold_seconds=300)
        assert result.oldest_lag_seconds is None
        assert result.median_lag_seconds is None


# ---------------------------------------------------------------------------
# BackfillRangeStats
# ---------------------------------------------------------------------------


class TestBackfillRangeStats:
    async def test_backfill_ranges_defaults_to_zero(self) -> None:
        """backfill_ranges fields default to zero when repository returns zeros."""
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.backfill_ranges.pending == 0
        assert result.backfill_ranges.in_progress == 0
        assert result.backfill_ranges.stale_in_progress == 0
        assert result.backfill_ranges.completed == 0
        assert result.backfill_ranges.failed == 0

    async def test_backfill_ranges_default_to_secondary_in_per_log_mode(self) -> None:
        """Live range counts are compatibility-only when per-log dispatch is active."""
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.backfill_ranges.dispatch_mode == "per-log"
        assert result.backfill_ranges.is_primary is False

    async def test_backfill_ranges_populated_from_repository(self) -> None:
        """backfill_ranges mirrors values returned by the repository."""
        repo = _repo_with_defaults(
            backfill_range_status_counts={
                "pending": 10,
                "in_progress": 2,
                "stale_in_progress": 1,
                "completed": 500,
                "failed": 3,
            }
        )
        result = await StatsService(repo).get_stats()
        assert result.backfill_ranges.pending == 10
        assert result.backfill_ranges.in_progress == 2
        assert result.backfill_ranges.stale_in_progress == 1
        assert result.backfill_ranges.completed == 500
        assert result.backfill_ranges.failed == 3

    async def test_backfill_ranges_are_primary_in_legacy_range_mode(self) -> None:
        """Legacy dispatch marks range status as the primary backfill signal."""
        repo = _repo_with_defaults()
        repo._ctpool_settings = MagicMock(ct_backfill_dispatch_mode="legacy-ranges")
        result = await StatsService(repo).get_stats()
        assert result.backfill_ranges.dispatch_mode == "legacy-ranges"
        assert result.backfill_ranges.is_primary is True

    async def test_backfill_range_status_counts_called_with_default_timeout(
        self,
    ) -> None:
        """backfill_range_status_counts is called with 1800 when no ctpool settings."""
        repo = _repo_with_defaults()
        repo._ctpool_settings = None
        await StatsService(repo).get_stats()
        repo.backfill_range_status_counts.assert_awaited_once_with(1800)

    async def test_backfill_health_ok_when_no_failures(self) -> None:
        """backfill_health.status is 'ok' when no failed or stale ranges."""
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.backfill_health is not None
        assert result.backfill_health.status == "ok"
        assert result.backfill_health.failed_ranges == 0
        assert result.backfill_health.stale_ranges == 0

    async def test_backfill_health_warning_when_failed_ranges(self) -> None:
        """backfill_health.status is 'warning' when failed > 0."""
        repo = _repo_with_defaults(
            backfill_range_status_counts={
                "pending": 0,
                "in_progress": 0,
                "stale_in_progress": 0,
                "completed": 10,
                "failed": 3,
            }
        )
        result = await StatsService(repo).get_stats()
        assert result.backfill_health is not None
        assert result.backfill_health.status == "warning"
        assert result.backfill_health.failed_ranges == 3

    async def test_backfill_health_warning_when_stale_ranges(self) -> None:
        """backfill_health.status is 'warning' when stale_in_progress > 0."""
        repo = _repo_with_defaults(
            backfill_range_status_counts={
                "pending": 0,
                "in_progress": 2,
                "stale_in_progress": 1,
                "completed": 10,
                "failed": 0,
            }
        )
        result = await StatsService(repo).get_stats()
        assert result.backfill_health is not None
        assert result.backfill_health.status == "warning"
        assert result.backfill_health.stale_ranges == 1

    async def test_metrics_retention_populated(self) -> None:
        """metrics_retention reflects ingestion_metrics_summary and settings."""
        from datetime import timedelta

        oldest = datetime.now(UTC) - timedelta(days=20)
        repo = _repo_with_defaults(
            ingestion_metrics_summary={
                "row_count": 150,
                "oldest_at": oldest,
            }
        )
        result = await StatsService(repo).get_stats()
        assert result.metrics_retention is not None
        assert result.metrics_retention.ingestion_metrics_rows == 150
        assert result.metrics_retention.oldest_ingestion_metric_at == oldest
        assert result.metrics_retention.metrics_retention_days == 30

    async def test_metrics_retention_null_oldest_when_no_rows(self) -> None:
        """metrics_retention.oldest_ingestion_metric_at is None when table is empty."""
        repo = _repo_with_defaults()
        result = await StatsService(repo).get_stats()
        assert result.metrics_retention is not None
        assert result.metrics_retention.oldest_ingestion_metric_at is None
        assert result.metrics_retention.ingestion_metrics_rows == 0

    async def test_audit_health_ok_when_no_open_findings(self) -> None:
        """audit_health.status is 'ok' when all severity counts are zero."""
        repo = _repo_with_defaults(
            audit_health_counts={"critical": 0, "error": 0, "warning": 0, "info": 0}
        )
        result = await StatsService(repo).get_stats()
        assert result.audit_health is not None
        assert result.audit_health.status == "ok"
        assert result.audit_health.total_open == 0

    async def test_audit_health_attention_when_critical_findings(self) -> None:
        """audit_health.status is 'attention_needed' when critical count > 0."""
        repo = _repo_with_defaults(
            audit_health_counts={"critical": 2, "error": 0, "warning": 0, "info": 0}
        )
        result = await StatsService(repo).get_stats()
        assert result.audit_health is not None
        assert result.audit_health.status == "attention_needed"
        assert result.audit_health.open_critical == 2
        assert result.audit_health.total_open == 2

    async def test_audit_health_attention_when_error_findings(self) -> None:
        """audit_health.status is 'attention_needed' when error count > 0."""
        repo = _repo_with_defaults(
            audit_health_counts={"critical": 0, "error": 1, "warning": 0, "info": 0}
        )
        result = await StatsService(repo).get_stats()
        assert result.audit_health is not None
        assert result.audit_health.status == "attention_needed"
        assert result.audit_health.open_error == 1

    async def test_audit_health_ok_when_only_info_findings(self) -> None:
        """audit_health.status is 'ok' when only info-severity findings are open."""
        repo = _repo_with_defaults(
            audit_health_counts={"critical": 0, "error": 0, "warning": 0, "info": 3}
        )
        result = await StatsService(repo).get_stats()
        assert result.audit_health is not None
        assert result.audit_health.status == "ok"
        assert result.audit_health.total_open == 3

    async def test_audit_health_total_open_sums_all_severities(self) -> None:
        """audit_health.total_open is the sum of all per-severity counts."""
        repo = _repo_with_defaults(
            audit_health_counts={"critical": 1, "error": 2, "warning": 3, "info": 4}
        )
        result = await StatsService(repo).get_stats()
        assert result.audit_health is not None
        assert result.audit_health.total_open == 10
