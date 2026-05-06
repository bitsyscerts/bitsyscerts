"""Tests for ctpool.metrics — LogMetricsAccumulator.

Covers counter increments, snapshot calculation, and DB persistence.
DB tests use the real ``ctpool_test`` database via ``db_session`` fixture.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.integration


def _make_log_source() -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="Operator",
        description="Log",
        url="https://ct.example.com/log/",
        public_key_b64="a2V5",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Counter increment tests (pure Python, no DB)
# ---------------------------------------------------------------------------


def test_initial_counters_are_zero() -> None:
    """All counters start at zero."""
    acc = LogMetricsAccumulator()
    snap = acc.get_snapshot()
    assert snap["entries_fetched"] == 0
    assert snap["entries_parsed"] == 0
    assert snap["certs_upserted"] == 0
    assert snap["hostnames_upserted"] == 0
    assert snap["parse_errors"] == 0
    assert snap["http_429_count"] == 0
    assert snap["http_5xx_count"] == 0


def test_record_entries_fetched_increments() -> None:
    """record_entries_fetched adds the supplied count."""
    acc = LogMetricsAccumulator()
    acc.record_entries_fetched(100)
    acc.record_entries_fetched(50)
    assert acc.get_snapshot()["entries_fetched"] == 150


def test_record_entries_parsed_increments() -> None:
    """record_entries_parsed adds the supplied count."""
    acc = LogMetricsAccumulator()
    acc.record_entries_parsed(80)
    assert acc.get_snapshot()["entries_parsed"] == 80


def test_record_certs_upserted_increments() -> None:
    """record_certs_upserted adds the supplied count."""
    acc = LogMetricsAccumulator()
    acc.record_certs_upserted(5)
    acc.record_certs_upserted(3)
    assert acc.get_snapshot()["certs_upserted"] == 8


def test_record_hostnames_upserted_increments() -> None:
    """record_hostnames_upserted adds the supplied count."""
    acc = LogMetricsAccumulator()
    acc.record_hostnames_upserted(12)
    assert acc.get_snapshot()["hostnames_upserted"] == 12


def test_record_parse_error_increments_by_one() -> None:
    """Each record_parse_error call increments by exactly 1."""
    acc = LogMetricsAccumulator()
    acc.record_parse_error()
    acc.record_parse_error()
    assert acc.get_snapshot()["parse_errors"] == 2


def test_record_http_429_increments_by_one() -> None:
    """Each record_http_429 call increments by exactly 1."""
    acc = LogMetricsAccumulator()
    acc.record_http_429()
    assert acc.get_snapshot()["http_429_count"] == 1


def test_record_http_5xx_increments_by_one() -> None:
    """Each record_http_5xx call increments by exactly 1."""
    acc = LogMetricsAccumulator()
    acc.record_http_5xx()
    acc.record_http_5xx()
    assert acc.get_snapshot()["http_5xx_count"] == 2


def test_get_snapshot_window_seconds_default() -> None:
    """window_seconds defaults to 60 in the snapshot."""
    acc = LogMetricsAccumulator()
    assert acc.get_snapshot()["window_seconds"] == 60


def test_get_snapshot_window_seconds_custom() -> None:
    """window_seconds uses the supplied value."""
    acc = LogMetricsAccumulator()
    assert acc.get_snapshot(window_seconds=300)["window_seconds"] == 300


def test_get_snapshot_throughput_is_positive() -> None:
    """Throughput is a positive float."""
    acc = LogMetricsAccumulator()
    acc.record_entries_fetched(1)
    snap = acc.get_snapshot()
    assert isinstance(snap["throughput_entries_per_sec"], float)
    assert snap["throughput_entries_per_sec"] > 0


# ---------------------------------------------------------------------------
# persist_snapshot + reset (DB)
# ---------------------------------------------------------------------------


async def test_persist_snapshot_writes_row(db_session: AsyncSession) -> None:
    """persist_snapshot inserts a row in ingestion_metrics."""
    source = _make_log_source()
    db_session.add(source)
    await db_session.flush()

    acc = LogMetricsAccumulator()
    acc.record_entries_fetched(200)
    acc.record_parse_error()

    await acc.persist_snapshot(db_session, source.id)
    await db_session.flush()

    result = await db_session.execute(
        select(IngestionMetric).where(IngestionMetric.log_source_id == source.id)
    )
    row = result.scalars().first()
    assert row is not None
    assert row.entries_fetched == 200
    assert row.parse_errors == 1


async def test_persist_snapshot_resets_counters(db_session: AsyncSession) -> None:
    """After persist_snapshot, counters are reset to zero."""
    source = _make_log_source()
    db_session.add(source)
    await db_session.flush()

    acc = LogMetricsAccumulator()
    acc.record_entries_fetched(50)
    await acc.persist_snapshot(db_session, source.id)

    snap_after = acc.get_snapshot()
    assert snap_after["entries_fetched"] == 0


async def test_persist_snapshot_twice_writes_two_rows(
    db_session: AsyncSession,
) -> None:
    """Two calls to persist_snapshot produce two separate rows."""
    source = _make_log_source()
    db_session.add(source)
    await db_session.flush()

    acc = LogMetricsAccumulator()
    acc.record_entries_fetched(10)
    await acc.persist_snapshot(db_session, source.id)
    acc.record_entries_fetched(20)
    await acc.persist_snapshot(db_session, source.id)
    await db_session.flush()

    result = await db_session.execute(
        select(IngestionMetric).where(IngestionMetric.log_source_id == source.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 2
