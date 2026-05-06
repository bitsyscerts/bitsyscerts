"""Tests for StatsService — mocked repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from ctpool.db_contention_types import DbContentionOperatorSnapshot

from certsapi.stats.models import StatsResponse
from certsapi.stats.service import StatsService


def _make_row(
    log_id: uuid.UUID | None = None,
    complete: int = 5,
    total: int = 10,
    tail_pos: int = 500,
) -> MagicMock:
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: {
        "id": log_id or uuid.uuid4(),
        "description": "Test Log",
        "url": "https://ct.test/",
        "log_state": "usable",
        "tail_position": tail_pos,
        "last_tail_sync": datetime.now(UTC),
        "complete_ranges": complete,
        "total_ranges": total,
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
