"""Tests for ctpool.backfill_state_init.

The module composes already-tested primitives (fetch_sth, compute_pivot_index,
ensure_log_backfill_state, initialize_log_window) so these tests focus on
control flow: the empty-tree short-circuit and the wiring of pivot/end into
initialize_log_window.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.backfill_state_init import initialize_backfill_state_for_log
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.asyncio


@dataclass
class _StubSth:
    tree_size: int
    timestamp: int


def _make_session_factory_mock() -> MagicMock:
    """Return a callable behaving as an async context manager."""
    session = MagicMock()

    @asynccontextmanager
    async def _begin() -> AsyncIterator[MagicMock]:
        yield session

    session.begin = _begin

    factory = MagicMock()

    @asynccontextmanager
    async def _factory_ctx() -> AsyncIterator[MagicMock]:
        yield session

    factory.side_effect = lambda: _factory_ctx()
    return factory


def _make_log() -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="Op",
        description="Test Log",
        url="https://ct.example.com/",
        public_key_b64="a2V5",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
    )


async def test_initialize_skips_when_tree_size_zero() -> None:
    """An empty CT log short-circuits without writing anything."""
    log = _make_log()
    factory = _make_session_factory_mock()

    with (
        patch(
            "ctpool.backfill_state_init.fetch_sth",
            new=AsyncMock(return_value=_StubSth(0, 0)),
        ),
        patch(
            "ctpool.backfill_state_init.ensure_log_backfill_state",
            new=AsyncMock(),
        ) as ensure_mock,
        patch(
            "ctpool.backfill_state_init.initialize_log_window",
            new=AsyncMock(),
        ) as init_mock,
    ):
        client: Any = AsyncMock()
        await initialize_backfill_state_for_log(log, factory, client, days=1)

    ensure_mock.assert_not_called()
    init_mock.assert_not_called()


async def test_initialize_seeds_window_from_sth() -> None:
    """A non-empty STH is converted into a backfill window."""
    log = _make_log()
    factory = _make_session_factory_mock()

    with (
        patch(
            "ctpool.backfill_state_init.fetch_sth",
            new=AsyncMock(return_value=_StubSth(1000, 0)),
        ),
        patch(
            "ctpool.backfill_state_init.compute_pivot_index",
            return_value=900,
        ),
        patch(
            "ctpool.backfill_state_init.ensure_log_backfill_state",
            new=AsyncMock(),
        ),
        patch(
            "ctpool.backfill_state_init.initialize_log_window",
            new=AsyncMock(),
        ) as init_mock,
    ):
        client: Any = AsyncMock()
        await initialize_backfill_state_for_log(log, factory, client, days=1)

    init_mock.assert_awaited_once()
    kwargs = init_mock.await_args.kwargs
    assert kwargs["log_source_id"] == log.id
    assert kwargs["backfill_start_index"] == 900
    assert kwargs["backfill_end_index"] == 999
