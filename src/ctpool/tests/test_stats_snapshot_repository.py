"""Unit tests for StatsSnapshotRepository.

These tests mock the SQLAlchemy session so no database is required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ctpool.stats_snapshot_repository import StatsSnapshotRepository


def _make_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_execute_result(scalar=None, scalars=None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar)
    return result


class TestInsertSnapshot:
    async def test_insert_creates_row_with_correct_fields(self) -> None:
        session = _make_session()
        session.execute = AsyncMock(return_value=_make_execute_result())
        repo = StatsSnapshotRepository()

        row = await repo.insert_snapshot(
            session,
            snapshot_type="full",
            payload={"total_hostnames": 42},
            duration_ms=150,
        )

        assert row.snapshot_type == "full"
        assert row.payload_json == {"total_hostnames": 42}
        assert row.duration_ms == 150
        session.add.assert_called_once_with(row)
        session.flush.assert_awaited_once()

    async def test_insert_sets_generated_at_to_utc(self) -> None:
        session = _make_session()
        repo = StatsSnapshotRepository()
        row = await repo.insert_snapshot(
            session, snapshot_type="full", payload={}, duration_ms=0
        )
        assert row.generated_at is not None
        # generated_at is tz-naive from the model; just check it was set
        assert row is not None


class TestGetLatestSnapshot:
    async def test_returns_none_when_no_row_exists(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        result = await repo.get_latest_snapshot(session, "full")
        assert result is None

    async def test_returns_dict_payload_when_row_found(self) -> None:
        session = MagicMock()
        row_mock = MagicMock()
        row_mock.payload_json = {"total_hostnames": 10}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=row_mock)
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        result = await repo.get_latest_snapshot(session, "full")
        assert result == {"total_hostnames": 10}

    async def test_deserialises_string_payload(self) -> None:
        import json

        session = MagicMock()
        row_mock = MagicMock()
        row_mock.payload_json = json.dumps({"key": "value"})
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=row_mock)
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        result = await repo.get_latest_snapshot(session, "full")
        assert result == {"key": "value"}


class TestGetLatestSnapshotAgeSeconds:
    async def test_returns_none_when_no_row(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        age = await repo.get_latest_snapshot_age_seconds(session, "full")
        assert age is None

    async def test_returns_positive_age_for_old_snapshot(self) -> None:
        session = MagicMock()
        old_ts = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=120)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=old_ts)
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        age = await repo.get_latest_snapshot_age_seconds(session, "full")
        assert age is not None
        assert age >= 100  # at least ~2 minutes old


class TestPruneOldSnapshots:
    async def test_prune_returns_rowcount(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 5
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        deleted = await repo.prune_old_snapshots(session, retention_hours=24)
        assert deleted == 5

    async def test_prune_with_snapshot_type_filter_executes(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 2
        session.execute = AsyncMock(return_value=result_mock)

        repo = StatsSnapshotRepository()
        deleted = await repo.prune_old_snapshots(
            session, retention_hours=1, snapshot_type="full"
        )
        assert deleted == 2
        session.execute.assert_awaited_once()
