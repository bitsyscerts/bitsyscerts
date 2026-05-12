"""Tests for worker CLI rendering helpers."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from ctpool._cli_workers_impl import run_list_workers, run_reap_workers


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.ct_worker_stale_seconds = 300
    return settings


def _session_factory() -> MagicMock:
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.mark.asyncio
async def test_run_list_workers_renders_enriched_worker_summary() -> None:
    """Workers CLI renders log assignment, current work, and last error."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=160)
    engine = MagicMock()
    engine.dispose = AsyncMock()
    summary = {
        "active_total": 2,
        "stale_total": 1,
        "tail_active": 1,
        "backfill_active": 1,
        "stats_active": 0,
        "maintenance_active": 0,
        "unknown_active": 0,
        "items": [
            {
                "worker_id": "host:1234",
                "worker_kind": "backfill",
                "log_source_id": "log-1",
                "log_name": "Test Log",
                "log_operator": "Test Operator",
                "direction": "backfill",
                "status": "retrying",
                "is_stale": False,
                "last_heartbeat_age_seconds": 12,
                "current_index": 150,
                "checkpoint_index": 140,
                "batch_start_index": 150,
                "batch_end_index": 199,
                "last_error_type": "RateLimitError",
                "last_error_message": "Upstream rate limit",
                "rate_limited_until": None,
            },
            {
                "worker_id": "host:5678",
                "worker_kind": "stats-snapshotter",
                "log_source_id": None,
                "log_name": None,
                "log_operator": None,
                "direction": "snapshot",
                "status": "idle",
                "is_stale": True,
                "last_heartbeat_age_seconds": 900,
                "current_index": None,
                "checkpoint_index": None,
                "batch_start_index": None,
                "batch_end_index": None,
                "last_error_type": None,
                "last_error_message": None,
                "rate_limited_until": None,
            },
        ],
    }

    with (
        patch("ctpool._cli_workers_impl.get_settings", return_value=_settings()),
        patch("ctpool._cli_workers_impl.create_engine", return_value=engine),
        patch(
            "ctpool._cli_workers_impl.create_session_factory",
            return_value=_session_factory(),
        ),
        patch(
            "ctpool._cli_workers_impl.query_worker_summary",
            AsyncMock(return_value=summary),
        ),
        patch("ctpool._cli_workers_impl.Console", return_value=console),
    ):
        await run_list_workers(stale_seconds=None)

    rendered = output.getvalue()
    assert "Workers:" in rendered
    assert "Test Log (Test Operator)" in rendered
    assert "backfill | 150-199 | ckpt 140" in rendered
    assert "RateLimitError: Upstream rate limit" in rendered
    assert "idle (stale)" in rendered


@pytest.mark.asyncio
async def test_run_reap_workers_uses_shared_reaper() -> None:
    """Reap CLI uses the shared stale-worker cleanup helper."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=160)
    engine = MagicMock()
    engine.dispose = AsyncMock()
    factory = _session_factory()
    session = factory.return_value.__aenter__.return_value
    result = MagicMock()
    result.all.return_value = [MagicMock(id="row-1", worker_id="host:1234")]
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    reap_mock = AsyncMock(return_value=["host:1234"])

    with (
        patch("ctpool._cli_workers_impl.get_settings", return_value=_settings()),
        patch("ctpool._cli_workers_impl.create_engine", return_value=engine),
        patch(
            "ctpool._cli_workers_impl.create_session_factory",
            return_value=factory,
        ),
        patch("ctpool._cli_workers_impl.reap_stale_worker_rows", reap_mock),
        patch("ctpool._cli_workers_impl.Console", return_value=console),
    ):
        await run_reap_workers(stale_seconds=None, dry_run=False)

    reap_mock.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert "Reaped 1 stale worker row(s)" in output.getvalue()
