"""Tests for ctpool.backfill_worker — run_backfill.

All external boundaries (HTTP fetches, disk guard, database) are mocked
so tests run without a network or database connection.
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
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 2,
        "ct_min_free_disk_gb": 1,
        "ct_critical_free_disk_gb": 0,
        "ct_http_timeout_seconds": 5,
    }
    base.update(kwargs)
    return Settings.model_validate(base)


def _make_log(log_id: str = "dGVzdA==") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test Log",
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
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_backfill_worker_exits_when_no_pending_ranges() -> None:
    """No ranges to claim → once=True exits cleanly."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)


async def test_backfill_worker_marks_range_complete_on_success() -> None:
    """Successful range processing marks the range as complete."""
    log = _make_log()
    claimed = _make_range(log.id)
    settings = _make_settings()
    completed_ids: list[uuid.UUID] = []

    async def mock_mark_complete(session: object, range_id: uuid.UUID) -> None:
        completed_ids.append(range_id)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
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
        patch("ctpool.backfill_worker.write_normalized_entry", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_complete", mock_mark_complete),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert claimed.id in completed_ids


async def test_backfill_worker_marks_range_failed_on_fetch_error() -> None:
    """FetchError during entry fetch marks the range as failed."""
    log = _make_log()
    claimed = _make_range(log.id)
    settings = _make_settings()
    failed_ids: list[uuid.UUID] = []

    async def mock_mark_failed(
        session: object, range_id: uuid.UUID, reason: str
    ) -> None:
        failed_ids.append(range_id)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(return_value=claimed),
        ),
        patch(
            "ctpool.backfill_worker._resolve_log_url",
            AsyncMock(return_value="https://ct.example.com/"),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(side_effect=FetchError("boom")),
        ),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", mock_mark_failed),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert claimed.id in failed_ids


async def test_backfill_worker_pauses_when_disk_is_low() -> None:
    """Disk low → sleeps and exits when once=True."""
    log = _make_log()
    settings = _make_settings()
    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=True),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
        ),
        patch("ctpool.backfill_worker.asyncio.sleep", mock_sleep),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert 60 in sleep_calls  # _SLEEP_DISK_LOW_SECONDS


async def test_backfill_worker_halts_when_disk_is_critical() -> None:
    """Disk critical → raises SystemExit(1) without claiming a range."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=True),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
        ),
        patch("ctpool.backfill_worker.claim_backfill_range", AsyncMock()) as mock_claim,
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
        pytest.raises(SystemExit) as exc_info,
    ):
        await run_backfill(_make_session_factory(), settings)

    assert exc_info.value.code == 1
    mock_claim.assert_not_called()


async def test_backfill_worker_exits_at_entry_limit() -> None:
    """limit=1 stops after 1 entry is written."""
    log = _make_log()
    claimed = _make_range(log.id)
    settings = _make_settings()
    written: list[object] = []

    async def mock_write(session: object, entry: object) -> None:
        written.append(entry)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges", AsyncMock(return_value=0)
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(return_value=claimed),
        ),
        patch(
            "ctpool.backfill_worker._resolve_log_url",
            AsyncMock(return_value="https://ct.example.com/"),
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
        patch("ctpool.backfill_worker.write_normalized_entry", mock_write),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, limit=1)

    assert len(written) == 1


# ---------------------------------------------------------------------------
# on_status callback
# ---------------------------------------------------------------------------


async def test_backfill_worker_on_status_fires_when_no_pending_ranges() -> None:
    """on_status is called when there are no pending ranges to claim."""
    log = _make_log()
    settings = _make_settings()
    status_messages: list[str] = []

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=True)
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        await run_backfill(
            _make_session_factory(),
            settings,
            once=True,
            on_status=status_messages.append,
        )

    assert any("No pending ranges" in m for m in status_messages)


async def test_backfill_worker_on_status_fires_before_fetching_range() -> None:
    """on_status is called with range bounds before processing each range."""
    log = _make_log()
    claimed = _make_range(log.id, start=0, end=63)
    settings = _make_settings()
    status_messages: list[str] = []

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=True)
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
        patch("ctpool.backfill_worker.write_normalized_entry", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        await run_backfill(
            _make_session_factory(),
            settings,
            once=True,
            on_status=status_messages.append,
        )

    assert any("Fetching" in m and "0" in m and "63" in m for m in status_messages)
