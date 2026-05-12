"""Tests for ctpool._cli_backfill_state_impl — Rich-table per-log report."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool._cli_backfill_state_impl import (
    _build_state_table,
    _format_index,
    _format_progress,
    run_list_backfill_state,
)


def test_format_progress_handles_none() -> None:
    assert _format_progress(None) == "-"


def test_format_progress_formats_value() -> None:
    assert _format_progress(12.345) == "12.3%"


def test_format_index_handles_none() -> None:
    assert _format_index(None) == "-"


def test_format_index_thousands_separator() -> None:
    assert _format_index(1234567) == "1,234,567"


def test_build_state_table_row_count() -> None:
    items = [
        {
            "log_source_id": "abc",
            "log_name": "Test Log",
            "log_url": "https://ct.example.com/",
            "status": "processing",
            "claimed_by": "host:1",
            "is_stale": False,
            "checkpoint_index": 100,
            "backfill_start_index": 0,
            "backfill_end_index": 999,
            "progress_percent": 10.0,
            "last_heartbeat_age_seconds": 1.5,
            "last_error_type": None,
            "last_error_message": None,
            "completed_at": None,
        }
    ]
    table = _build_state_table(items)
    assert table.row_count == 1


@pytest.mark.asyncio
async def test_run_list_backfill_state_no_rows_prints_hint() -> None:
    """Empty state table prints the operator hint and disposes the engine."""
    from ctpool import _cli_backfill_state_impl as impl

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    session = MagicMock()

    class _SessionCtx:
        async def __aenter__(self) -> MagicMock:
            return session

        async def __aexit__(self, *_: object) -> None:
            return None

    factory: Any = MagicMock(side_effect=lambda: _SessionCtx())

    with (
        patch.object(impl, "create_engine", return_value=mock_engine),
        patch.object(impl, "create_session_factory", return_value=factory),
        patch.object(
            impl,
            "query_backfill_state_summary",
            new=AsyncMock(return_value={"items": [], "total_logs": 0}),
        ),
    ):
        await run_list_backfill_state()

    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_list_backfill_state_with_rows_renders_table() -> None:
    """A summary with items prints the Rich table and disposes the engine."""
    from ctpool import _cli_backfill_state_impl as impl

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    session = MagicMock()

    class _SessionCtx:
        async def __aenter__(self) -> MagicMock:
            return session

        async def __aexit__(self, *_: object) -> None:
            return None

    factory: Any = MagicMock(side_effect=lambda: _SessionCtx())

    summary = {
        "total_logs": 1,
        "pending": 0,
        "claimed": 0,
        "processing": 1,
        "retrying": 0,
        "paused": 0,
        "complete": 0,
        "error": 0,
        "stale": 0,
        "items": [
            {
                "log_source_id": "abc",
                "log_name": "L",
                "log_url": "https://x/",
                "status": "processing",
                "claimed_by": "h:1",
                "is_stale": False,
                "checkpoint_index": 50,
                "backfill_start_index": 0,
                "backfill_end_index": 99,
                "progress_percent": 50.5,
                "last_heartbeat_age_seconds": 2.0,
                "last_error_type": None,
                "last_error_message": None,
                "completed_at": None,
            }
        ],
    }

    with (
        patch.object(impl, "create_engine", return_value=mock_engine),
        patch.object(impl, "create_session_factory", return_value=factory),
        patch.object(
            impl, "query_backfill_state_summary", new=AsyncMock(return_value=summary)
        ),
    ):
        await run_list_backfill_state()

    mock_engine.dispose.assert_awaited_once()
