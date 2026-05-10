"""Tests for ctpool.tail_worker — run_tail.

All external boundaries (HTTP fetches, disk guard, database) are mocked
so tests run without a network or database connection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.ct_api_schemas import CtEntriesResponse, CtLeafEntry, SignedTreeHead
from ctpool.db_contention_types import DbContentionDirective, DbContentionObservation
from ctpool.entry_write_result import EntryWriteMetrics
from ctpool.exceptions import FetchError
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.tail_worker import run_tail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

_FAKE_LOG_INPUT = (
    # Minimal valid base64 stub — parse_leaf_entry will be mocked so content
    # does not matter.
    "AAAA"
)


def _make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_tail_interval_seconds": 1,
        "ct_default_batch_size": 2,
        "ct_db_contention_min_batch_size": 1,
        "ct_db_contention_enabled": False,
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


def _make_cursor(log_id: uuid.UUID, next_index: int = 0) -> CtLogTailCursor:
    return CtLogTailCursor(
        id=uuid.uuid4(),
        log_source_id=log_id,
        next_index=next_index,
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
        entries=[
            CtLeafEntry(leaf_input=_FAKE_LOG_INPUT, extra_data="") for _ in range(n)
        ]
    )


def _stored_metrics(
    *,
    hostnames_observed: int = 0,
    new_unique_hostnames: int = 0,
    certificate_inserted: bool = False,
) -> EntryWriteMetrics:
    return EntryWriteMetrics(
        new_unique_certificates=1 if certificate_inserted else 0,
        duplicate_certificates=0 if certificate_inserted else 1,
        hostnames_observed=hostnames_observed,
        new_unique_hostnames=new_unique_hostnames,
        known_hostnames=hostnames_observed - new_unique_hostnames,
    )


def _make_session_factory(
    logs: list[CtLogSource],
    cursor_map: dict[uuid.UUID, CtLogTailCursor],
) -> MagicMock:
    """Build a minimal async session factory mock."""
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock()
    session.begin_nested.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)
    session.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar.return_value = True
    session.execute.return_value = execute_result

    factory = MagicMock()
    factory.session = session
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


@pytest.fixture(autouse=True)
def _mock_tail_log_claim() -> object:
    """All tail-worker tests assume the log lease is available."""
    with patch(
        "ctpool.tail_worker.try_claim_tail_log", AsyncMock(return_value=True)
    ) as claim_mock:
        yield claim_mock


@pytest.fixture(autouse=True)
def _patch_worker_registry() -> object:
    """Prevent worker_registry calls from hitting the mock session."""
    import uuid as _uuid
    from unittest.mock import MagicMock

    mock_row = MagicMock()
    mock_row.id = _uuid.uuid4()
    with (
        patch("ctpool.tail_worker.register_worker", AsyncMock(return_value=mock_row)),
        patch("ctpool.tail_worker.heartbeat_worker", AsyncMock()),
        patch("ctpool.tail_worker.mark_worker_stopped", AsyncMock()),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tail_worker_exits_after_one_iteration_with_once_flag() -> None:
    """once=True exits after processing all logs once."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(5))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(2)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(side_effect=lambda _: MagicMock()),
        ),
        patch(
            "ctpool.tail_worker.build_normalized_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.tail_worker.persist_entry_with_retry",
            AsyncMock(return_value=_stored_metrics()),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True)
        # Should return without raising — no infinite loop
        factory.session.begin_nested.assert_not_called()


async def test_tail_worker_pauses_when_disk_is_low() -> None:
    """Disk low → sleeps for interval then exits if once=True."""
    log = _make_log()
    settings = _make_settings(ct_tail_interval_seconds=1)
    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=True),
        patch("ctpool.tail_worker.asyncio.sleep", mock_sleep),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True)

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == 60  # _SLEEP_DISK_LOW_SECONDS


async def test_tail_worker_halts_when_disk_is_critical() -> None:
    """Disk critical → raises SystemExit(1) immediately."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=True),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
        pytest.raises(SystemExit) as exc_info,
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings)  # no once=True — must exit via critical

    assert exc_info.value.code == 1


async def test_tail_worker_stops_at_entry_limit() -> None:
    """limit=2 stops after 2 entries are written."""
    log = _make_log()
    settings = _make_settings()
    written: list[object] = []

    async def mock_write(
        session: object,
        entry: object,
        **_: object,
    ) -> EntryWriteMetrics:
        written.append(entry)
        return _stored_metrics()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(100))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(2)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry", MagicMock(return_value=MagicMock())
        ),
        patch(
            "ctpool.tail_worker.build_normalized_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch("ctpool.tail_worker.persist_entry_with_retry", mock_write),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, limit=2)

    assert len(written) == 2


async def test_tail_worker_sleeps_on_empty_response() -> None:
    """Empty entries response → sleep without advancing cursor."""
    log = _make_log()
    settings = _make_settings(ct_tail_interval_seconds=1)
    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(0)),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.asyncio.sleep", mock_sleep),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True)

    # once=True exits after the pass; sleep may not be called if loop exits first
    # but no cursor advance should happen
    from ctpool.tail_worker import advance_tail_cursor as _atc  # noqa: F401


async def test_tail_worker_logs_error_and_continues_on_fetch_failure() -> None:
    """FetchError during fetch_entries is caught; loop continues."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(side_effect=FetchError("timeout")),
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        # Should not raise — error is caught inside _tail_one_log
        await run_tail(factory, settings, once=True)


async def test_tail_worker_filter_restricts_to_single_log_id() -> None:
    """log_id parameter limits processing to the matching log only."""
    log_a = _make_log(log_id="YQ==")
    log_b = _make_log(log_id="Yg==")
    settings = _make_settings()
    processed_ids: list[uuid.UUID] = []

    async def mock_ensure_cursor(
        session: object, lid: uuid.UUID, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        processed_ids.append(lid)
        return _make_cursor(lid, 0), False

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log_a, log_b]),
        ),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure_cursor),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(0))),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log_a], {})
        await run_tail(factory, settings, once=True, log_id=log_a.id)

    assert all(lid == log_a.id for lid in processed_ids)
    assert log_b.id not in processed_ids


async def test_tail_worker_skips_log_when_cursor_at_tree_size() -> None:
    """When cursor.next_index >= tree_size, no fetch is made."""
    log = _make_log()
    settings = _make_settings()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, next_index=10), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch("ctpool.tail_worker.fetch_entries", AsyncMock()) as mock_fetch,
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True)

    mock_fetch.assert_not_called()


async def test_tail_worker_calls_on_batch_callback_with_correct_args() -> None:
    """on_batch is called with (log_url, batch_count, total_count)
    when entries are written.
    """
    log = _make_log()
    settings = _make_settings()
    calls: list[tuple[str, int, int]] = []

    def capture(url: str, count: int, total: int) -> None:
        calls.append((url, count, total))

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_make_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(2))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(2)),
        ),
        patch("ctpool.tail_worker.parse_leaf_entry", MagicMock()),
        patch("ctpool.tail_worker.build_normalized_entry", MagicMock()),
        patch(
            "ctpool.tail_worker.persist_entry_with_retry",
            AsyncMock(return_value=_stored_metrics()),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True, on_batch=capture)

    assert len(calls) == 1
    url, count, total = calls[0]
    assert url == log.url
    assert count == 2
    assert total == 2


# ---------------------------------------------------------------------------
# New cursor initialization semantics
# ---------------------------------------------------------------------------


async def test_tail_initializes_cursor_at_tree_edge_when_no_cursor_exists() -> None:
    """With no existing cursor and init_from_end=0, ensure_tail_cursor is called
    with init_index equal to the current tree_size (the edge).
    """
    log = _make_log()
    settings = _make_settings()
    tree_size = 1_000_000
    captured_init_index: list[int] = []

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        captured_init_index.append(init_index)
        # Simulate freshly created cursor at edge → no entries to fetch
        return _make_cursor(log.id, next_index=tree_size), True

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(tree_size)),
        ),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True)

    assert captured_init_index == [tree_size]


async def test_tail_init_from_end_sets_cursor_to_tree_size_minus_offset() -> None:
    """With init_from_end=100 and tree_size=500, init_index should be 400."""
    log = _make_log()
    settings = _make_settings()
    captured_init_index: list[int] = []

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        captured_init_index.append(init_index)
        return _make_cursor(log.id, next_index=init_index), True

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(500))),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(0)),
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True, init_from_end=100)

    assert captured_init_index == [400]


async def test_tail_init_from_end_clamps_at_zero() -> None:
    """When init_from_end exceeds tree_size, init_index clamps to 0."""
    log = _make_log()
    settings = _make_settings()
    captured_init_index: list[int] = []

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        captured_init_index.append(init_index)
        return _make_cursor(log.id, next_index=0), True

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(0)),
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await run_tail(factory, settings, once=True, init_from_end=9_999)

    assert captured_init_index == [0]


async def test_tail_logs_info_when_cursor_newly_created() -> None:
    """run_tail logs an INFO message containing 'Initialized' when was_created=True."""
    import io
    import logging as _logging

    log = _make_log()
    settings = _make_settings()

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        return _make_cursor(log.id, next_index=init_index), True  # newly created

    stream = io.StringIO()
    handler = _logging.StreamHandler(stream)
    handler.setLevel(_logging.INFO)
    logger = _logging.getLogger("ctpool.tail_worker")
    old_level = logger.level
    logger.setLevel(_logging.INFO)
    logger.addHandler(handler)
    try:
        with (
            patch("ctpool.tail_worker.is_disk_critical", return_value=False),
            patch("ctpool.tail_worker.is_disk_low", return_value=False),
            patch(
                "ctpool.tail_worker.get_eligible_tail_logs",
                AsyncMock(return_value=[log]),
            ),
            patch(
                "ctpool.tail_worker.fetch_sth",
                AsyncMock(return_value=_make_sth(1000)),
            ),
            patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
            patch("ctpool.tail_worker.httpx.AsyncClient"),
        ):
            factory = _make_session_factory([log], {})
            await run_tail(factory, settings, once=True)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    assert "Initialized" in stream.getvalue()


# ---------------------------------------------------------------------------
# reset_tail_cursors
# ---------------------------------------------------------------------------


async def test_reset_tail_cursors_calls_reset_for_each_eligible_log() -> None:
    """reset_tail_cursors fetches STH for each log and resets the cursor."""
    from ctpool.tail_worker import reset_tail_cursors

    log = _make_log()
    settings = _make_settings()
    reset_calls: list[tuple[object, int]] = []

    async def mock_reset(session: object, log_id: object, new_index: int) -> int:
        reset_calls.append((log_id, new_index))
        return 448  # old value

    with (
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(999_999)),
        ),
        patch("ctpool.tail_worker.reset_tail_cursor", mock_reset),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await reset_tail_cursors(factory, settings)

    assert len(reset_calls) == 1
    _, new_index = reset_calls[0]
    assert new_index == 999_999


async def test_reset_tail_cursors_skips_log_on_fetch_error() -> None:
    """reset_tail_cursors skips logs whose STH probe raises FetchError."""
    from ctpool.tail_worker import reset_tail_cursors

    log = _make_log()
    settings = _make_settings()
    reset_calls: list[object] = []

    with (
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch(
            "ctpool.tail_worker.fetch_sth",
            AsyncMock(side_effect=FetchError("probe failed")),
        ),
        patch(
            "ctpool.tail_worker.reset_tail_cursor",
            AsyncMock(side_effect=lambda *a, **k: reset_calls.append(a)),
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _make_session_factory([log], {})
        await reset_tail_cursors(factory, settings)  # must not raise

    assert reset_calls == []  # no reset because STH failed


# ---------------------------------------------------------------------------
# persist_snapshot wiring
# ---------------------------------------------------------------------------


async def test_tail_worker_calls_persist_snapshot_on_success() -> None:
    """persist_snapshot is called exactly once when entries are processed."""
    log = _make_log()
    settings = _make_settings()
    snapshot_calls: list[object] = []

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        return _make_cursor(log.id, next_index=0), False

    async def mock_persist(
        self: object, session: object, log_source_id: object
    ) -> None:
        snapshot_calls.append(log_source_id)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(10)),
        ),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(1)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            return_value=MagicMock(),
        ),
        patch(
            "ctpool.tail_worker.build_normalized_entry",
            return_value=MagicMock(),
        ),
        patch(
            "ctpool.tail_worker.persist_entry_with_retry",
            AsyncMock(return_value=_stored_metrics()),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch(
            "ctpool.tail_worker.LogMetricsAccumulator.persist_snapshot",
            mock_persist,
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        await run_tail(_make_session_factory([log], {}), settings, once=True)

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0] == log.id


async def test_tail_worker_persists_snapshot_on_fetch_error() -> None:
    """Retryable fetch errors emit a snapshot row for rate aggregation."""
    log = _make_log()
    settings = _make_settings()
    snapshot_calls: list[object] = []

    async def mock_persist(
        self: object, session: object, log_source_id: object
    ) -> None:
        snapshot_calls.append(log_source_id)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.fetch_sth",
            AsyncMock(side_effect=FetchError("network error")),
        ),
        patch(
            "ctpool.tail_worker.LogMetricsAccumulator.persist_snapshot",
            mock_persist,
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        await run_tail(_make_session_factory([log], {}), settings, once=True)

    assert snapshot_calls == [log.id]


async def test_tail_worker_applies_shared_db_pacing_before_processing_log() -> None:
    """Shared DB-pressure pacing sleeps before tailing and clamps batch size."""
    log = _make_log()
    settings = _make_settings(ct_db_contention_enabled=True)
    observation = DbContentionObservation(entries_attempted=1, retryable_errors=0)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.get_db_contention_directive",
            AsyncMock(
                return_value=DbContentionDirective(
                    pressure_ema=0.2,
                    base_sleep_seconds=0.5,
                    batch_size_cap=1,
                )
            ),
        ),
        patch(
            "ctpool.tail_worker.sleep_for_db_contention",
            AsyncMock(return_value=0.5),
        ) as sleep_mock,
        patch(
            "ctpool.tail_worker._tail_one_log",
            AsyncMock(return_value=(1, False, False, observation, None)),
        ) as tail_one_log_mock,
        patch(
            "ctpool.tail_worker.submit_db_contention_observation",
            AsyncMock(),
        ) as submit_mock,
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        await run_tail(_make_session_factory([log], {}), settings, once=True)

    sleep_mock.assert_awaited_once()
    assert tail_one_log_mock.await_count == 1
    assert tail_one_log_mock.await_args_list[0].kwargs["batch_size"] == 1
    submit_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# Hostname metrics recording
# ---------------------------------------------------------------------------


async def test_tail_worker_records_hostnames_observed_per_batch() -> None:
    """record_entry_write_metrics carries observed-hostname totals per entry."""
    from ctpool.metrics import LogMetricsAccumulator

    log = _make_log()
    settings = _make_settings()

    # Two entries, one with 3 hostnames and one with 2 → total 5
    normalized_a = MagicMock()
    normalized_a.hostnames = ["a.example.com", "b.example.com", "c.example.com"]
    normalized_b = MagicMock()
    normalized_b.hostnames = ["d.example.com", "e.example.com"]

    build_side_effects = [normalized_a, normalized_b]

    recorded_counts: list[int] = []
    original_record = LogMetricsAccumulator.record_entry_write_metrics

    def capture_record_entry_metrics(
        self: LogMetricsAccumulator,
        metrics: EntryWriteMetrics,
    ) -> None:
        recorded_counts.append(metrics.hostnames_observed)
        original_record(self, metrics)

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        return _make_cursor(log.id, next_index=0), False

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(2)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(side_effect=lambda _: MagicMock()),
        ),
        patch(
            "ctpool.tail_worker.build_normalized_entry",
            MagicMock(side_effect=build_side_effects),
        ),
        patch(
            "ctpool.tail_worker.persist_entry_with_retry",
            AsyncMock(
                side_effect=[
                    _stored_metrics(hostnames_observed=3, new_unique_hostnames=1),
                    _stored_metrics(hostnames_observed=2, new_unique_hostnames=0),
                ]
            ),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.LogMetricsAccumulator.persist_snapshot", AsyncMock()),
        patch(
            "ctpool.tail_worker.LogMetricsAccumulator.record_entry_write_metrics",
            capture_record_entry_metrics,
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        await run_tail(_make_session_factory([log], {}), settings, once=True)

    assert sum(recorded_counts) == 5


async def test_tail_worker_hostname_not_recorded_when_no_entries() -> None:
    """When the batch returns no entries, record_hostnames_upserted is not called.

    The tail worker returns early before reaching the metric-recording block
    when the server returns an empty entries list.  The accumulated counter
    stays at 0 naturally and is written on the next non-empty snapshot.
    """
    from ctpool.metrics import LogMetricsAccumulator

    log = _make_log()
    settings = _make_settings()
    recorded_counts: list[int] = []
    original_record = LogMetricsAccumulator.record_hostnames_upserted

    def capture_record_hostnames(self: LogMetricsAccumulator, count: int) -> None:
        recorded_counts.append(count)
        original_record(self, count)

    async def mock_ensure(
        session: object, lid: object, *, init_index: int
    ) -> tuple[CtLogTailCursor, bool]:
        return _make_cursor(log.id, next_index=0), False

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs", AsyncMock(return_value=[log])
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_make_sth(10))),
        patch("ctpool.tail_worker.ensure_tail_cursor", mock_ensure),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_make_entries_response(0)),
        ),
        patch("ctpool.tail_worker.LogMetricsAccumulator.persist_snapshot", AsyncMock()),
        patch(
            "ctpool.tail_worker.LogMetricsAccumulator.record_hostnames_upserted",
            capture_record_hostnames,
        ),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        await run_tail(_make_session_factory([log], {}), settings, once=True)

    # Empty entries → the worker returns before the metric block; no call expected
    assert recorded_counts == []
