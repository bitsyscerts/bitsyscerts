"""Unit tests for stats_queries module using mocked SQLAlchemy sessions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from ctpool.stats_queries import (
    query_backfill_planned_counts,
    query_backfill_range_status_counts,
    query_database_size_bytes,
    query_entry_outcome_counts,
    query_global_counts,
    query_ingestion_metrics_summary,
    query_ingestion_rate_windows,
    query_tail_freshness,
)


def _mock_session_with_scalar(scalar_value: object) -> MagicMock:
    """Return a mock session whose execute returns a scalar result."""
    result = MagicMock()
    result.scalar_one = MagicMock(return_value=scalar_value)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _mock_session_with_one(row: object) -> MagicMock:
    """Return a mock session whose execute returns a row via .one()."""
    result = MagicMock()
    result.one = MagicMock(return_value=row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _mock_session_with_mappings(rows: list) -> MagicMock:
    """Return a mock session whose execute returns a mappings all() result."""
    result = MagicMock()
    result.mappings = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=rows))
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


class TestQueryDatabaseSizeBytes:
    async def test_returns_int_from_scalar(self) -> None:
        session = _mock_session_with_scalar(1_000_000)
        result = await query_database_size_bytes(session)
        assert result == 1_000_000
        assert isinstance(result, int)

    async def test_handles_string_result(self) -> None:
        session = _mock_session_with_scalar("2000000")
        result = await query_database_size_bytes(session)
        assert result == 2_000_000


class TestQueryGlobalCounts:
    async def test_returns_dict_with_all_keys(self) -> None:
        row = MagicMock()
        row.hostnames = 100
        row.certificates = 50
        row.observations = 1000
        row.cert_hostnames = 200
        session = _mock_session_with_one(row)

        result = await query_global_counts(session)

        assert result["hostnames"] == 100
        assert result["certificates"] == 50
        assert result["observations"] == 1000
        assert result["cert_hostnames"] == 200

    async def test_all_values_are_ints(self) -> None:
        row = MagicMock()
        row.hostnames = "5"
        row.certificates = "3"
        row.observations = "10"
        row.cert_hostnames = "7"
        session = _mock_session_with_one(row)

        result = await query_global_counts(session)
        assert all(isinstance(v, int) for v in result.values())


class TestQueryBackfillPlannedCounts:
    async def test_returns_planned_total_and_completed(self) -> None:
        row = MagicMock()
        row.total = 50_000
        row.completed = 25_000
        # query_backfill_planned_counts uses result.one()
        result_mock = MagicMock()
        result_mock.one = MagicMock(return_value=row)
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_backfill_planned_counts(session)

        assert result["planned_total"] == 50_000
        assert result["planned_completed"] == 25_000

    async def test_zero_values_when_no_ranges(self) -> None:
        row = MagicMock()
        row.total = 0
        row.completed = 0
        result_mock = MagicMock()
        result_mock.one = MagicMock(return_value=row)
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_backfill_planned_counts(session)
        assert result["planned_total"] == 0
        assert result["planned_completed"] == 0


class TestQueryBackfillRangeStatusCounts:
    async def test_returns_all_five_status_keys(self) -> None:
        row = MagicMock()
        row.pending = 10
        row.in_progress = 2
        row.stale_in_progress = 1
        row.completed = 100
        row.failed = 0
        session = _mock_session_with_one(row)

        result = await query_backfill_range_status_counts(session, 1800)

        assert set(result.keys()) == {
            "pending",
            "in_progress",
            "stale_in_progress",
            "completed",
            "failed",
        }
        assert result["pending"] == 10
        assert result["stale_in_progress"] == 1


class TestQueryEntryOutcomeCounts:
    async def test_returns_dict_of_outcomes(self) -> None:
        stored_row = MagicMock()
        stored_row.outcome = "stored"
        stored_row.cnt = 900
        error_row = MagicMock()
        error_row.outcome = "parse_error"
        error_row.cnt = 5

        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([stored_row, error_row]))
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_entry_outcome_counts(session)
        assert result["stored"] == 900
        assert result["parse_error"] == 5

    async def test_initialises_all_known_outcomes_to_zero(self) -> None:
        """All outcomes from ALL_OUTCOMES should default to 0 even when absent."""
        from ctpool.outcome_constants import ALL_OUTCOMES

        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([]))
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_entry_outcome_counts(session)
        assert isinstance(result, dict)
        # All known outcomes should be present with value 0
        for outcome in ALL_OUTCOMES:
            assert outcome in result
            assert result[outcome] == 0


class TestQueryIngestionMetricsSummary:
    async def test_returns_row_count_and_oldest_at(self) -> None:
        row = MagicMock()
        row.row_count = 500
        row.oldest_at = None
        session = _mock_session_with_one(row)

        result = await query_ingestion_metrics_summary(session)
        assert result["row_count"] == 500
        assert result["oldest_at"] is None


class TestQueryIngestionRateWindows:
    async def test_returns_one_entry_per_window(self) -> None:
        """One execute call per window, results combined into a list."""
        mapping_row = {
            "entries_fetched": 100,
            "entries_parsed": 80,
            "certs_upserted": 50,
            "hostnames_upserted": 20,
            "new_unique_certificates": 10,
            "duplicate_certificates": 40,
            "new_unique_hostnames": 5,
            "known_hostnames": 15,
            "retryable_errors": 2,
            "terminal_entry_errors": 1,
        }
        result_mock = MagicMock()
        result_mock.mappings = MagicMock(
            return_value=MagicMock(one=MagicMock(return_value=mapping_row))
        )
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_ingestion_rate_windows(session, [300, 3600])
        # Two windows → two rows
        assert len(result) == 2
        assert result[0]["window_seconds"] == 300
        assert result[1]["window_seconds"] == 3600
        assert result[0]["entries_fetched"] == 100
        assert result[0]["new_unique_certificates"] == 10

    async def test_returns_empty_list_for_empty_windows(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock()  # should not be called
        result = await query_ingestion_rate_windows(session, [])
        assert result == []
        session.execute.assert_not_called()


class TestQueryTailFreshness:
    async def test_returns_expected_shape(self) -> None:
        """query_tail_freshness returns dict from mappings().one()."""
        mapping_row = {
            "oldest_lag_seconds": 350,
            "median_lag_seconds": 30,
            "stale_log_count": 1,
        }
        result_mock = MagicMock()
        result_mock.mappings = MagicMock(
            return_value=MagicMock(one=MagicMock(return_value=mapping_row))
        )
        session = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)

        result = await query_tail_freshness(session, stale_threshold_seconds=300)
        assert result["oldest_lag_seconds"] == 350
        assert result["stale_log_count"] == 1
