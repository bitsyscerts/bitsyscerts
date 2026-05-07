"""Tests for StatsService — mocked repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from ctpool.db_contention_types import DbContentionOperatorSnapshot

from certsapi.stats.models import StatsResponse
from certsapi.stats.service import (
    StatsService,
    _build_ingestion_rate_stats,
    _build_tail_freshness_stats,
)


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
                "certs_upserted": 0,
                "hostnames_upserted": 0,
            }
        ],
    )
    repo.tail_freshness_summary.return_value = overrides.get(
        "tail_freshness_summary",
        _make_freshness_row(),
    )
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

    async def test_logs_list_populated(self) -> None:
        repo = _repo_with_defaults(total_logs=1, per_log_stats=[_make_row()])
        result = await StatsService(repo).get_stats()
        assert len(result.logs) == 1

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
                    "certs_upserted": 120,
                    "hostnames_upserted": 60,
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


# ---------------------------------------------------------------------------
# _build_ingestion_rate_stats (pure function)
# ---------------------------------------------------------------------------


class TestBuildIngestionRateStats:
    def test_single_window_rates_computed_correctly(self) -> None:
        rows = [
            {
                "window_seconds": 300,
                "entries_fetched": 300,
                "certs_upserted": 150,
                "hostnames_upserted": 60,
            }
        ]
        result = _build_ingestion_rate_stats(rows)
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.observations_per_sec == pytest.approx(1.0)
        assert w.certs_per_min == pytest.approx(30.0)
        assert w.hostnames_per_min == pytest.approx(12.0)

    def test_zero_counts_produce_zero_rates(self) -> None:
        rows = [
            {
                "window_seconds": 300,
                "entries_fetched": 0,
                "certs_upserted": 0,
                "hostnames_upserted": 0,
            }
        ]
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
