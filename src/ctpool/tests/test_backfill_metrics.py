"""Tests for LogMetricsAccumulator.persist_snapshot wiring in run_backfill.

Verifies that persist_snapshot is (or is not) called based on whether a
batch completes successfully.  All external boundaries are mocked.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.backfill_worker import run_backfill
from ctpool.config import Settings
from ctpool.ct_api_schemas import CtEntriesResponse, CtLeafEntry, SignedTreeHead
from ctpool.exceptions import FetchError
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource

# ---------------------------------------------------------------------------
# Helpers (minimal copies — see test_backfill_worker.py for full set)
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 2,
        "ct_backfill_days": 180,
        "ct_db_contention_enabled": False,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _make_log(*, log_id: str = "dGVzdA==") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log",
        url="https://ct.example.com/log/",
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _make_range(
    log_id: uuid.UUID,
    start: int = 0,
    end: int = 9,
    next_index: int = 0,
) -> CtLogBackfillRange:
    return CtLogBackfillRange(
        id=uuid.uuid4(),
        log_source_id=log_id,
        start_index=start,
        end_index=end,
        next_index=next_index,
        status="in_progress",
    )


def _make_sth(tree_size: int = 10) -> SignedTreeHead:
    return SignedTreeHead(
        tree_size=tree_size,
        timestamp=0,
        sha256_root_hash="aa" * 32,
        tree_head_signature="bb",
    )


def _make_entries_response(n: int = 1) -> CtEntriesResponse:
    return CtEntriesResponse(
        entries=[CtLeafEntry(leaf_input="AAAA", extra_data="") for _ in range(n)]
    )


def _make_session_factory() -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock()
    session.begin_nested.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_reap_stale():
    """Prevent reap_stale_backfill_claims from hitting the mock session."""
    with patch(
        "ctpool.backfill_worker.reap_stale_backfill_claims",
        AsyncMock(return_value=[]),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_backfill_worker_calls_persist_snapshot_on_success() -> None:
    """persist_snapshot is called once after a successful non-empty batch."""
    log = _make_log()
    claimed = _make_range(log.id)
    settings = _make_settings()
    snapshot_calls: list[object] = []

    async def mock_persist(
        self: object, session: object, log_source_id: object
    ) -> None:
        snapshot_calls.append(log_source_id)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(0)),
        ),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges",
            AsyncMock(return_value=0),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(return_value=claimed),
        ),
        patch(
            "ctpool.backfill_worker._resolve_log_url",
            AsyncMock(return_value="https://ct.example.com/log/"),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.backfill_worker.build_normalized_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch("ctpool.backfill_worker.persist_entry_with_retry", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch(
            "ctpool.backfill_worker.LogMetricsAccumulator.persist_snapshot",
            mock_persist,
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0] == log.id


async def test_backfill_worker_does_not_call_persist_snapshot_on_fetch_error() -> None:
    """persist_snapshot is NOT called when a FetchError aborts the batch."""
    log = _make_log()
    claimed = _make_range(log.id)
    settings = _make_settings()
    snapshot_calls: list[object] = []

    async def mock_persist(
        self: object, session: object, log_source_id: object
    ) -> None:
        snapshot_calls.append(log_source_id)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(0)),
        ),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges",
            AsyncMock(return_value=0),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(return_value=claimed),
        ),
        patch(
            "ctpool.backfill_worker._resolve_log_url",
            AsyncMock(return_value="https://ct.example.com/log/"),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(side_effect=FetchError("timeout")),
        ),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch(
            "ctpool.backfill_worker.LogMetricsAccumulator.persist_snapshot",
            mock_persist,
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert snapshot_calls == []
