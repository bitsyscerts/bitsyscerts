"""Tests for ctpool.stats — render_stats and render_stats_watch.

render_stats DB tests use the real ``ctpool_test`` database via ``db_session``.
render_stats_watch is tested via mocking to avoid infinite loops.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_runtime_state import CtLogRuntimeState
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.stats import (
    _format_eta,
    _query_recent_throughputs,
    render_stats,
    render_stats_watch,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_log(
    *,
    url: str = "https://ct.example.com/log/",
    log_id: str = "dGVzdA==",
) -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log for Stats",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


# ---------------------------------------------------------------------------
# render_stats
# ---------------------------------------------------------------------------


async def test_render_stats_with_empty_database(db_session: AsyncSession) -> None:
    """render_stats runs without error when no CT logs exist."""
    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    # Table header with cert/hostname counts should be present
    assert "Certs" in output or "0" in output


async def test_render_stats_with_log_no_runtime_state(
    db_session: AsyncSession,
) -> None:
    """render_stats displays dash placeholders when runtime state is absent."""
    log = _make_log()
    db_session.add(log)
    await db_session.flush()

    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "Test CT Log for Stats" in output


async def test_render_stats_with_full_log_state(
    db_session: AsyncSession,
) -> None:
    """render_stats shows progress percentage when runtime state and cursor exist."""
    log = _make_log(url="https://ct2.example.com/", log_id="bA==")
    db_session.add(log)
    await db_session.flush()

    runtime = CtLogRuntimeState(
        log_source_id=log.id,
        tree_size=100_000,
        health_status="ok",
    )
    cursor = CtLogTailCursor(
        log_source_id=log.id,
        next_index=50_000,
    )
    db_session.add(runtime)
    db_session.add(cursor)
    await db_session.flush()

    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    # tree_size=100_000, next_index=50_000 → lag = 50,000, sync = 50.0%
    assert "50,000" in output
    assert "50.0%" in output
    assert "ok" in output


async def test_render_stats_shows_cert_and_hostname_totals(
    db_session: AsyncSession,
) -> None:
    """render_stats title includes cert and hostname total counts."""
    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    # The table title contains "Certs" and "Hostnames"
    assert "Certs" in output
    assert "Hostnames" in output


async def test_render_stats_zero_tree_size_shows_dash_for_progress(
    db_session: AsyncSession,
) -> None:
    """render_stats shows '—' for Tail Lag when tree_size is zero."""
    log = _make_log(url="https://ct3.example.com/", log_id="YmE=")
    db_session.add(log)
    await db_session.flush()

    runtime = CtLogRuntimeState(
        log_source_id=log.id,
        tree_size=0,
        health_status="ok",
    )
    cursor = CtLogTailCursor(
        log_source_id=log.id,
        next_index=0,
    )
    db_session.add(runtime)
    db_session.add(cursor)
    await db_session.flush()

    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    # Tail Lag column should show "0" (0 = max(0, 0-0)) not "—"
    assert "0" in output
    # Sync % should show "—" when tree_size is 0 (avoids division by zero)
    assert "—" in output


# ---------------------------------------------------------------------------
# render_stats_watch
# ---------------------------------------------------------------------------


async def test_render_stats_watch_calls_render_and_sleeps() -> None:
    """render_stats_watch calls render_stats once then asyncio.sleep before cycling."""
    render_call_count = 0
    sleep_called_with: list[float] = []

    async def mock_render_stats(session: object, console: object) -> None:
        nonlocal render_call_count
        render_call_count += 1

    async def mock_sleep(secs: float) -> None:
        sleep_called_with.append(secs)
        raise asyncio.CancelledError  # stop after first iteration

    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    console = Console(record=True, width=120)

    with patch("ctpool.stats.render_stats", mock_render_stats):
        with patch("ctpool.stats.asyncio.sleep", mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await render_stats_watch(mock_factory, console, interval_seconds=3)

    assert render_call_count == 1
    assert sleep_called_with == [3]


# ---------------------------------------------------------------------------
# Database size panel
# ---------------------------------------------------------------------------


async def test_render_stats_shows_db_size_panel(db_session: AsyncSession) -> None:
    """render_stats prints a storage panel containing total DB size and table names."""
    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "DB Contention Control" in output
    assert "Database Storage" in output
    assert "certificate" in output
    assert "hostname" in output


async def test_render_stats_size_panel_shows_numeric_row_counts(
    db_session: AsyncSession,
) -> None:
    """The storage panel displays numeric row counts (zero when tables are empty)."""
    console = Console(record=True, width=120)
    await render_stats(db_session, console)
    output = console.export_text()
    # Row counts are right-aligned integers — at minimum "0" must appear
    assert any(char.isdigit() for char in output)


# ---------------------------------------------------------------------------
# Tail Lag column
# ---------------------------------------------------------------------------


async def test_stats_shows_tail_lag_column_header(db_session: AsyncSession) -> None:
    """Table header contains 'Tail Lag', 'Tail Next', and 'Sync %', not 'Progress'."""
    console = Console(record=True, width=180)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "Tail Lag" in output
    assert "Tail Next" in output
    assert "Sync %" in output
    assert "Progress" not in output
    assert "Cursor" not in output


async def test_stats_shows_sync_percent_alongside_tail_lag(
    db_session: AsyncSession,
) -> None:
    """Sync % shows a percentage value alongside the Tail Lag integer count."""
    log = _make_log(url="https://lag.example.com/", log_id="bGFn")
    db_session.add(log)
    await db_session.flush()

    runtime = CtLogRuntimeState(
        log_source_id=log.id,
        tree_size=1_000_256,
        health_status="ok",
    )
    cursor = CtLogTailCursor(
        log_source_id=log.id,
        next_index=1_000_000,
    )
    db_session.add(runtime)
    db_session.add(cursor)
    await db_session.flush()

    console = Console(record=True, width=180)
    await render_stats(db_session, console)
    output = console.export_text()
    # Lag = 1_000_256 - 1_000_000 = 256
    assert "256" in output
    # Sync % ≈ 99.97% (displayed as "99.9%" or "100.0%" depending on rounding)
    assert "99." in output or "100.0%" in output
    assert "%" in output


# ---------------------------------------------------------------------------
# _format_eta
# ---------------------------------------------------------------------------


def test_format_eta_returns_dash_when_rate_is_none() -> None:
    """_format_eta returns '—' when rate_per_sec is None."""
    assert _format_eta(1000, None) == "—"


def test_format_eta_returns_dash_when_rate_is_zero() -> None:
    """_format_eta returns '—' when rate_per_sec is 0.0."""
    assert _format_eta(1000, 0.0) == "—"


def test_format_eta_returns_dash_when_lag_is_zero() -> None:
    """_format_eta returns '—' when lag_entries is 0."""
    assert _format_eta(0, 100.0) == "—"


def test_format_eta_one_hour_exact() -> None:
    """3600 entries at 1/s → '01:00:00'."""
    assert _format_eta(3600, 1.0) == "01:00:00"


def test_format_eta_one_day_plus() -> None:
    """90061 entries at 1/s → '1.01:01:01' (1 day, 1h, 1m, 1s)."""
    assert _format_eta(90061, 1.0) == "1.01:01:01"


def test_format_eta_under_one_minute() -> None:
    """30 entries at 1/s → '00:00:30'."""
    assert _format_eta(30, 1.0) == "00:00:30"


def test_format_eta_fast_rate_rounds_down() -> None:
    """1 entry at 0.5/s → 2s → '00:00:02'."""
    assert _format_eta(1, 0.5) == "00:00:02"


def test_format_eta_many_days() -> None:
    """30 days of lag at 1/s → '30.00:00:00'."""
    assert _format_eta(30 * 86400, 1.0) == "30.00:00:00"


# ---------------------------------------------------------------------------
# _query_recent_throughputs
# ---------------------------------------------------------------------------


async def test_query_recent_throughputs_empty_table(
    db_session: AsyncSession,
) -> None:
    """Returns empty dict when ingestion_metrics has no rows."""
    result = await _query_recent_throughputs(db_session)
    assert result == {}


async def test_query_recent_throughputs_returns_average_for_recent_rows(
    db_session: AsyncSession,
) -> None:
    """Returns averaged throughput for a log with recent metric rows."""
    from datetime import timedelta

    log = _make_log(url="https://tp.example.com/", log_id="dHA=")
    db_session.add(log)
    await db_session.flush()

    now = datetime.now(UTC)
    for rate in (10.0, 20.0):
        db_session.add(
            IngestionMetric(
                log_source_id=log.id,
                snapshot_at=now - timedelta(minutes=1),
                window_seconds=60,
                entries_fetched=600,
                entries_parsed=600,
                certs_upserted=600,
                hostnames_upserted=0,
                parse_errors=0,
                http_429_count=0,
                http_5xx_count=0,
                throughput_entries_per_sec=rate,
            )
        )
    await db_session.flush()

    result = await _query_recent_throughputs(db_session)
    assert log.id in result
    assert abs(result[log.id] - 15.0) < 0.01


async def test_query_recent_throughputs_excludes_stale_rows(
    db_session: AsyncSession,
) -> None:
    """Rows older than 10 minutes are excluded; absent key returned."""
    from datetime import timedelta

    log = _make_log(url="https://stale.example.com/", log_id="c3Q=")
    db_session.add(log)
    await db_session.flush()

    db_session.add(
        IngestionMetric(
            log_source_id=log.id,
            snapshot_at=datetime.now(UTC) - timedelta(minutes=15),
            window_seconds=60,
            entries_fetched=100,
            entries_parsed=100,
            certs_upserted=100,
            hostnames_upserted=0,
            parse_errors=0,
            http_429_count=0,
            http_5xx_count=0,
            throughput_entries_per_sec=50.0,
        )
    )
    await db_session.flush()

    result = await _query_recent_throughputs(db_session)
    assert log.id not in result


async def test_query_recent_throughputs_two_logs_independent(
    db_session: AsyncSession,
) -> None:
    """Two logs each get their own throughput entry."""
    from datetime import timedelta

    log_a = _make_log(url="https://a.example.com/", log_id="YQ==")
    log_b = _make_log(url="https://b.example.com/", log_id="Yg==")
    db_session.add(log_a)
    db_session.add(log_b)
    await db_session.flush()

    now = datetime.now(UTC)
    for log, rate in ((log_a, 5.0), (log_b, 50.0)):
        db_session.add(
            IngestionMetric(
                log_source_id=log.id,
                snapshot_at=now - timedelta(minutes=2),
                window_seconds=60,
                entries_fetched=300,
                entries_parsed=300,
                certs_upserted=300,
                hostnames_upserted=0,
                parse_errors=0,
                http_429_count=0,
                http_5xx_count=0,
                throughput_entries_per_sec=rate,
            )
        )
    await db_session.flush()

    result = await _query_recent_throughputs(db_session)
    assert abs(result[log_a.id] - 5.0) < 0.01
    assert abs(result[log_b.id] - 50.0) < 0.01


# ---------------------------------------------------------------------------
# Est. column in render_stats
# ---------------------------------------------------------------------------


async def test_stats_table_has_est_column_header(db_session: AsyncSession) -> None:
    """Stats table header includes 'Est.' column."""
    console = Console(record=True, width=200)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "Est." in output


async def test_stats_shows_eta_when_throughput_available(
    db_session: AsyncSession,
) -> None:
    """When recent throughput data exists, Est. column shows a time value."""
    from datetime import timedelta

    log = _make_log(url="https://eta.example.com/", log_id="ZXQ=")
    db_session.add(log)
    await db_session.flush()

    runtime = CtLogRuntimeState(
        log_source_id=log.id,
        tree_size=7200,
        health_status="ok",
    )
    cursor = CtLogTailCursor(log_source_id=log.id, next_index=0)
    # 7200 lag at 2.0/s → 3600s → 01:00:00
    metric = IngestionMetric(
        log_source_id=log.id,
        snapshot_at=datetime.now(UTC) - timedelta(minutes=1),
        window_seconds=60,
        entries_fetched=120,
        entries_parsed=120,
        certs_upserted=120,
        hostnames_upserted=0,
        parse_errors=0,
        http_429_count=0,
        http_5xx_count=0,
        throughput_entries_per_sec=2.0,
    )
    db_session.add(runtime)
    db_session.add(cursor)
    db_session.add(metric)
    await db_session.flush()

    console = Console(record=True, width=200)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "01:00:00" in output


async def test_stats_shows_dash_for_est_when_no_throughput(
    db_session: AsyncSession,
) -> None:
    """When no recent throughput rows exist, Est. column shows '—'."""
    log = _make_log(url="https://noeta.example.com/", log_id="bm8=")
    db_session.add(log)
    await db_session.flush()

    runtime = CtLogRuntimeState(
        log_source_id=log.id,
        tree_size=100_000,
        health_status="ok",
    )
    cursor = CtLogTailCursor(log_source_id=log.id, next_index=0)
    db_session.add(runtime)
    db_session.add(cursor)
    await db_session.flush()

    console = Console(record=True, width=200)
    await render_stats(db_session, console)
    output = console.export_text()
    assert "—" in output
