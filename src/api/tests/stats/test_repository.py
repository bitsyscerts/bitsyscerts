"""Integration tests for StatsRepository against the test database."""

from __future__ import annotations

import pytest
import pytest_asyncio
from ctpool.config import Settings as CtPoolSettings
from ctpool.models import CtLogBackfillRange, CtLogObservation, CtLogTailCursor
from ctpool.models.db_contention_state import CtDbContentionState
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.stats.repository import StatsRepository
from tests.conftest import make_certificate, make_hostname, make_log_source


def _ctpool_settings(**overrides: object) -> CtPoolSettings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 64,
        "ct_db_contention_enabled": True,
        "ct_db_contention_stale_after_seconds": 30,
    }
    base.update(overrides)
    return CtPoolSettings.model_validate(base)


@pytest_asyncio.fixture()
async def empty_session(db_session: AsyncSession) -> AsyncSession:
    """Fresh session with no extra data (schema exists, tables empty)."""
    return db_session


@pytest_asyncio.fixture()
async def session_with_data(db_session: AsyncSession) -> AsyncSession:
    """Seed one log, one hostname, one cert, and one backfill range."""
    from datetime import UTC, datetime

    log = make_log_source()
    db_session.add(log)
    await db_session.flush()

    cursor = CtLogTailCursor(
        log_source_id=log.id,
        next_index=1000,
        updated_at=datetime.now(UTC),
    )
    db_session.add(cursor)

    h = make_hostname()
    c = make_certificate()
    db_session.add_all([h, c])
    await db_session.flush()

    observation = CtLogObservation(
        log_source_id=log.id,
        log_index=0,
        certificate_id=c.id,
    )
    db_session.add(observation)

    br = CtLogBackfillRange(
        log_source_id=log.id,
        start_index=0,
        end_index=999,
        next_index=1000,
        status="complete",
    )
    db_session.add(br)
    await db_session.flush()
    return db_session


@pytest.mark.integration
class TestStatsRepository:
    async def test_total_hostnames_reflects_seeded_count(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        count = await repo.total_hostnames()
        assert count >= 1

    async def test_total_certificates_reflects_seeded_count(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        count = await repo.total_certificates()
        assert count >= 1

    async def test_total_logs_reflects_seeded_count(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        count = await repo.total_logs()
        assert count >= 1

    async def test_per_log_stats_returns_log_row(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        rows = await repo.per_log_stats()
        assert len(rows) >= 1

    async def test_db_storage_returns_total_size(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        result = await repo.db_storage()
        assert result["total"]["total_size_bytes"] > 0
        assert isinstance(result["total"]["total_size_pretty"], str)

    async def test_db_storage_tables_include_known_tables(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        result = await repo.db_storage()
        table_names = {row["table_name"] for row in result["tables"]}
        assert "hostnames" in table_names
        assert "certificates" in table_names

    async def test_backfill_complete_pct_all_complete(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        rows = await repo.per_log_stats()
        row = rows[0]
        assert row["complete_ranges"] == row["total_ranges"]

    async def test_backfill_total_zero_when_no_ranges(
        self, empty_session: AsyncSession
    ) -> None:
        log = make_log_source()
        empty_session.add(log)
        await empty_session.flush()
        repo = StatsRepository(empty_session)
        rows = await repo.per_log_stats()
        row = next(r for r in rows if r["id"] == log.id)
        assert row["total_ranges"] == 0

    async def test_tail_position_present_when_cursor_exists(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        rows = await repo.per_log_stats()
        row = rows[0]
        assert row["tail_position"] == 1000

    async def test_total_ct_observations_reflects_seeded_count(
        self, session_with_data: AsyncSession
    ) -> None:
        repo = StatsRepository(session_with_data)
        count = await repo.total_ct_observations()
        assert count == 1

    async def test_backfill_observation_progress_counts_partial_ranges(
        self, session_with_data: AsyncSession
    ) -> None:
        rows = await session_with_data.execute(select(CtLogBackfillRange.log_source_id))
        log_source_id = rows.scalar_one()
        session_with_data.add(
            CtLogBackfillRange(
                log_source_id=log_source_id,
                start_index=1000,
                end_index=1999,
                next_index=1500,
                status="in_progress",
            )
        )
        await session_with_data.flush()
        repo = StatsRepository(session_with_data)
        progress = await repo.backfill_observation_progress()
        assert progress["planned_observations_total"] == 2000
        assert progress["planned_observations_completed"] == 1500

    async def test_db_contention_snapshot_reads_shared_status(
        self, session_with_data: AsyncSession
    ) -> None:
        session_with_data.add(
            CtDbContentionState(
                scope="global",
                pressure_ema=0.2,
                extra_sleep_seconds=0.5,
                batch_size_cap=16,
            )
        )
        await session_with_data.flush()

        repo = StatsRepository(session_with_data, ctpool_settings=_ctpool_settings())
        snapshot = await repo.db_contention_snapshot()

        assert snapshot.status == "throttling"
        assert snapshot.effective_batch_size_cap == 16
