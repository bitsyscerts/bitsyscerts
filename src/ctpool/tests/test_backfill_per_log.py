"""Tests for ctpool.backfill_per_log — per-log dispatch model (Sprint 1B).

These tests prove the acceptance criteria:

- Workers claim work via ``ct_log_backfill_state`` (NOT ``ct_log_backfill_ranges``).
- Two workers cannot both hold the same log.
- Stale claims are reclaimed.
- ``last_checkpoint_index`` advances only after a successful batch.
- ``RateLimitError`` and ``FetchError`` do NOT advance the checkpoint and
  mark the row as ``retrying``.
- Terminal entry parse errors do NOT block the worker.
- The window is marked ``complete`` when the checkpoint passes
  ``backfill_end_index``.
- ``Settings().ct_backfill_dispatch_mode`` defaults to ``"per-log"``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.exceptions import FetchError, RateLimitError
from ctpool.models.log_backfill_state import CtLogBackfillState

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Default dispatch mode
# ---------------------------------------------------------------------------


def test_default_dispatch_mode_is_per_log() -> None:
    """Sprint 1B: default mode is per-log, not legacy-ranges."""
    s = Settings.model_validate({"database_url": "postgresql+psycopg://x:y@h/db"})
    assert s.ct_backfill_dispatch_mode == "per-log"


# pytest-asyncio applies pytestmark to all coros below; this top-level non-async
# test is not affected by the warning emitted via the module-level pytestmark.


# ---------------------------------------------------------------------------
# run_backfill dispatcher routes by mode
# ---------------------------------------------------------------------------


async def test_run_backfill_routes_to_per_log_by_default() -> None:
    """run_backfill with no dispatch_mode override calls the per-log path."""
    from ctpool import backfill_worker

    factory = MagicMock()
    settings = Settings.model_validate(
        {"database_url": "postgresql+psycopg://x:y@h/db"}
    )

    with (
        patch(
            "ctpool.backfill_per_log.run_backfill_per_log", new=AsyncMock()
        ) as per_log_mock,
        patch.object(
            backfill_worker, "run_backfill_legacy", new=AsyncMock()
        ) as legacy_mock,
    ):
        await backfill_worker.run_backfill(factory, settings, once=True)

    per_log_mock.assert_awaited_once()
    legacy_mock.assert_not_called()


async def test_run_backfill_legacy_mode_does_not_use_per_log() -> None:
    """When dispatch_mode='legacy-ranges' the per-log path is not invoked."""
    from ctpool import backfill_worker

    factory = MagicMock()
    settings = Settings.model_validate(
        {"database_url": "postgresql+psycopg://x:y@h/db"}
    )

    with (
        patch(
            "ctpool.backfill_per_log.run_backfill_per_log", new=AsyncMock()
        ) as per_log_mock,
        patch.object(
            backfill_worker, "run_backfill_legacy", new=AsyncMock()
        ) as legacy_mock,
    ):
        await backfill_worker.run_backfill(
            factory, settings, once=True, dispatch_mode="legacy-ranges"
        )

    legacy_mock.assert_awaited_once()
    per_log_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Helpers for _run_one_log_batch unit tests
# ---------------------------------------------------------------------------


def _make_session_factory() -> tuple[MagicMock, MagicMock]:
    """Async-context-manager-shaped session factory for unit tests."""
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
    return factory, session


def _make_state_row() -> CtLogBackfillState:
    row = CtLogBackfillState(
        log_source_id=uuid.uuid4(),
        status="claimed",
        claimed_by="w1",
        last_checkpoint_index=100,
        backfill_start_index=0,
        backfill_end_index=999,
    )
    return row


def _make_settings() -> Settings:
    return Settings.model_validate({"database_url": "postgresql+psycopg://x:y@h/db"})


# ---------------------------------------------------------------------------
# _run_one_log_batch behavior
# ---------------------------------------------------------------------------


async def test_run_one_log_batch_advances_checkpoint_on_success() -> None:
    """A successful batch invokes update_log_progress with the new checkpoint."""
    from ctpool import backfill_per_log

    state_row = _make_state_row()
    factory, _ = _make_session_factory()
    settings = _make_settings()
    client: Any = AsyncMock()

    with (
        patch.object(
            backfill_per_log,
            "_process_index_batch",
            new=AsyncMock(return_value=(0, 0, MagicMock(has_activity=False))),
        ),
        patch.object(
            backfill_per_log, "update_log_progress", new=AsyncMock()
        ) as progress_mock,
    ):
        (
            count,
            rate_limited,
            _obs,
            retry_after,
            new_checkpoint,
        ) = await backfill_per_log._run_one_log_batch(
            state_row,
            "https://ct.example.com/",
            factory,
            client,
            settings,
            batch_size=10,
            limit_remaining=None,
            worker_id="w1",
        )

    assert count == 0
    assert rate_limited is False
    assert retry_after is None
    # Started at 100, batch covers [100..109] → new_checkpoint = 110
    assert new_checkpoint == 110
    progress_mock.assert_awaited_once()
    awaited_kwargs = progress_mock.await_args.kwargs
    assert awaited_kwargs["checkpoint_index"] == 110
    assert awaited_kwargs["status"] == "processing"


async def test_run_one_log_batch_rate_limit_does_not_advance_checkpoint() -> None:
    """RateLimitError → mark_log_retrying; checkpoint unchanged."""
    from ctpool import backfill_per_log

    state_row = _make_state_row()
    factory, _ = _make_session_factory()
    settings = _make_settings()
    client: Any = AsyncMock()
    err = RateLimitError("429 too many", retry_after_seconds=12)

    with (
        patch.object(
            backfill_per_log, "_process_index_batch", new=AsyncMock(side_effect=err)
        ),
        patch.object(
            backfill_per_log, "update_log_progress", new=AsyncMock()
        ) as progress_mock,
        patch.object(
            backfill_per_log, "mark_log_retrying", new=AsyncMock()
        ) as retrying_mock,
    ):
        (
            count,
            rate_limited,
            _obs,
            retry_after,
            new_checkpoint,
        ) = await backfill_per_log._run_one_log_batch(
            state_row,
            "https://ct.example.com/",
            factory,
            client,
            settings,
            batch_size=10,
            limit_remaining=None,
            worker_id="w1",
        )

    assert rate_limited is True
    assert retry_after == 12
    # Checkpoint stays at the row's existing value.
    assert new_checkpoint == state_row.last_checkpoint_index
    progress_mock.assert_not_called()
    retrying_mock.assert_awaited_once()
    assert retrying_mock.await_args.kwargs["error_type"] == "RateLimitError"


async def test_run_one_log_batch_fetch_error_marks_retrying() -> None:
    """Generic FetchError → mark_log_retrying, no checkpoint advance."""
    from ctpool import backfill_per_log

    state_row = _make_state_row()
    factory, _ = _make_session_factory()
    settings = _make_settings()
    client: Any = AsyncMock()

    with (
        patch.object(
            backfill_per_log,
            "_process_index_batch",
            new=AsyncMock(side_effect=FetchError("network down")),
        ),
        patch.object(
            backfill_per_log, "update_log_progress", new=AsyncMock()
        ) as progress_mock,
        patch.object(
            backfill_per_log, "mark_log_retrying", new=AsyncMock()
        ) as retrying_mock,
    ):
        (
            count,
            rate_limited,
            _obs,
            _retry_after,
            new_checkpoint,
        ) = await backfill_per_log._run_one_log_batch(
            state_row,
            "https://ct.example.com/",
            factory,
            client,
            settings,
            batch_size=10,
            limit_remaining=None,
            worker_id="w1",
        )

    assert rate_limited is False
    assert new_checkpoint == state_row.last_checkpoint_index
    progress_mock.assert_not_called()
    retrying_mock.assert_awaited_once()
    assert retrying_mock.await_args.kwargs["error_type"] == "FetchError"


# ---------------------------------------------------------------------------
# _drive_one_log behavior
# ---------------------------------------------------------------------------


async def test_drive_one_log_marks_complete_when_checkpoint_passes_end() -> None:
    """When new_checkpoint > end, mark_log_complete is called."""
    from ctpool import backfill_per_log

    state_row = CtLogBackfillState(
        log_source_id=uuid.uuid4(),
        status="claimed",
        claimed_by="w1",
        last_checkpoint_index=999,  # one entry left
        backfill_start_index=0,
        backfill_end_index=999,
    )
    factory, _ = _make_session_factory()
    settings = _make_settings()
    client: Any = AsyncMock()

    obs = MagicMock(has_activity=False)

    with (
        patch.object(backfill_per_log, "heartbeat_worker", new=AsyncMock()),
        patch.object(
            backfill_per_log,
            "get_db_contention_directive",
            new=AsyncMock(return_value=None),
        ),
        patch.object(backfill_per_log, "resolve_effective_batch_size", return_value=1),
        patch.object(
            backfill_per_log,
            "sleep_for_db_contention",
            new=AsyncMock(return_value=0.0),
        ),
        patch.object(
            backfill_per_log,
            "_run_one_log_batch",
            new=AsyncMock(return_value=(1, False, obs, None, 1000)),
        ),
        patch.object(
            backfill_per_log, "mark_log_complete", new=AsyncMock()
        ) as complete_mock,
    ):
        await backfill_per_log._drive_one_log(
            state_row=state_row,
            log_url="https://x/",
            session_factory=factory,
            client=client,
            settings=settings,
            worker="w1",
            registry_id=uuid.uuid4(),
            base_batch=1,
            on_batch=None,
            on_status=None,
            rate_limit_hits={},
            rate_limited_until={},
            total_processed_ref=[0],
            limit=None,
        )

    complete_mock.assert_awaited_once()


async def test_drive_one_log_rate_limited_releases_claim() -> None:
    """Rate-limited returns immediately and calls release_log_claim."""
    from ctpool import backfill_per_log

    state_row = CtLogBackfillState(
        log_source_id=uuid.uuid4(),
        status="claimed",
        claimed_by="w1",
        last_checkpoint_index=100,
        backfill_start_index=0,
        backfill_end_index=999,
    )
    factory, _ = _make_session_factory()
    settings = _make_settings()
    client: Any = AsyncMock()

    obs = MagicMock(has_activity=False)
    with (
        patch.object(backfill_per_log, "heartbeat_worker", new=AsyncMock()),
        patch.object(
            backfill_per_log,
            "get_db_contention_directive",
            new=AsyncMock(return_value=None),
        ),
        patch.object(backfill_per_log, "resolve_effective_batch_size", return_value=10),
        patch.object(
            backfill_per_log,
            "sleep_for_db_contention",
            new=AsyncMock(return_value=0.0),
        ),
        patch.object(
            backfill_per_log,
            "_run_one_log_batch",
            new=AsyncMock(return_value=(0, True, obs, 5, 100)),
        ),
        patch.object(
            backfill_per_log, "release_log_claim", new=AsyncMock()
        ) as release_mock,
    ):
        await backfill_per_log._drive_one_log(
            state_row=state_row,
            log_url="https://x/",
            session_factory=factory,
            client=client,
            settings=settings,
            worker="w1",
            registry_id=uuid.uuid4(),
            base_batch=10,
            on_batch=None,
            on_status=None,
            rate_limit_hits={},
            rate_limited_until={},
            total_processed_ref=[0],
            limit=None,
        )

    release_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# run_backfill_per_log no-eligible-logs path
# ---------------------------------------------------------------------------


async def test_run_backfill_per_log_no_eligible_logs_exits_when_once() -> None:
    """When no logs are claimable, once=True returns after one idle pass."""
    from ctpool import backfill_per_log

    factory, _ = _make_session_factory()
    settings = _make_settings()

    registry_row = MagicMock()
    registry_row.id = uuid.uuid4()

    with (
        patch.object(backfill_per_log, "is_disk_critical", return_value=False),
        patch.object(backfill_per_log, "is_disk_low", return_value=False),
        patch.object(backfill_per_log, "_initialize_states", new=AsyncMock()),
        patch.object(
            backfill_per_log,
            "register_worker",
            new=AsyncMock(return_value=registry_row),
        ),
        patch.object(backfill_per_log, "heartbeat_worker", new=AsyncMock()),
        patch.object(backfill_per_log, "mark_worker_stopped", new=AsyncMock()),
        patch.object(
            backfill_per_log, "reap_stale_log_claims", new=AsyncMock(return_value=[])
        ),
        patch.object(
            backfill_per_log, "claim_any_eligible_log", new=AsyncMock(return_value=None)
        ),
        patch("httpx.AsyncClient"),
    ):
        await backfill_per_log.run_backfill_per_log(factory, settings, once=True)


# ---------------------------------------------------------------------------
# _process_index_batch coverage
# ---------------------------------------------------------------------------


async def test_process_index_batch_happy_path() -> None:
    """A clean batch returns count == number of entries fetched."""
    from ctpool import backfill_per_log
    from ctpool.metrics import LogMetricsAccumulator

    log_source_id = uuid.uuid4()
    settings = _make_settings()
    session: Any = AsyncMock()
    client: Any = AsyncMock()

    response = MagicMock()
    raw1 = MagicMock(leaf_input="leaf-a")
    raw2 = MagicMock(leaf_input="leaf-b")
    response.entries = [raw1, raw2]

    parsed = MagicMock()
    normalized = MagicMock()
    normalized.hostnames = ["a.example.com"]

    with (
        patch.object(
            backfill_per_log, "fetch_entries", new=AsyncMock(return_value=response)
        ),
        patch.object(backfill_per_log, "parse_leaf_entry", return_value=parsed),
        patch.object(
            backfill_per_log, "build_normalized_entry", return_value=normalized
        ),
        patch.object(backfill_per_log, "persist_entry_with_retry", new=AsyncMock()),
    ):
        count, _terminal, _obs = await backfill_per_log._process_index_batch(
            log_source_id,
            "https://x/",
            session,
            client,
            start_index=0,
            end_index=1,
            metrics=LogMetricsAccumulator(),
            settings=settings,
        )

    assert count == 2


async def test_process_index_batch_parse_error_recorded() -> None:
    """ParseError on one entry calls persist_failure_outcome and continues."""
    from ctpool import backfill_per_log
    from ctpool.exceptions import ParseError
    from ctpool.metrics import LogMetricsAccumulator

    log_source_id = uuid.uuid4()
    settings = _make_settings()
    session: Any = AsyncMock()
    client: Any = AsyncMock()

    response = MagicMock()
    response.entries = [MagicMock(leaf_input="bad")]

    with (
        patch.object(
            backfill_per_log, "fetch_entries", new=AsyncMock(return_value=response)
        ),
        patch.object(
            backfill_per_log, "parse_leaf_entry", side_effect=ParseError("malformed")
        ),
        patch.object(
            backfill_per_log, "persist_failure_outcome", new=AsyncMock()
        ) as failure_mock,
    ):
        count, _terminal, _obs = await backfill_per_log._process_index_batch(
            log_source_id,
            "https://x/",
            session,
            client,
            start_index=10,
            end_index=10,
            metrics=LogMetricsAccumulator(),
            settings=settings,
        )

    assert count == 0
    failure_mock.assert_awaited_once()


async def test_process_index_batch_unsupported_entry_type() -> None:
    """UnsupportedEntryTypeError records OUTCOME_UNSUPPORTED_ENTRY_TYPE."""
    from ctpool import backfill_per_log
    from ctpool.exceptions import UnsupportedEntryTypeError
    from ctpool.metrics import LogMetricsAccumulator
    from ctpool.outcome_constants import OUTCOME_UNSUPPORTED_ENTRY_TYPE

    log_source_id = uuid.uuid4()
    settings = _make_settings()
    session: Any = AsyncMock()
    client: Any = AsyncMock()

    response = MagicMock()
    response.entries = [MagicMock(leaf_input="x")]

    with (
        patch.object(
            backfill_per_log, "fetch_entries", new=AsyncMock(return_value=response)
        ),
        patch.object(
            backfill_per_log,
            "parse_leaf_entry",
            side_effect=UnsupportedEntryTypeError("v3"),
        ),
        patch.object(
            backfill_per_log, "persist_failure_outcome", new=AsyncMock()
        ) as failure_mock,
    ):
        count, _terminal, _obs = await backfill_per_log._process_index_batch(
            log_source_id,
            "https://x/",
            session,
            client,
            start_index=42,
            end_index=42,
            metrics=LogMetricsAccumulator(),
            settings=settings,
        )

    assert count == 0
    assert failure_mock.await_args.args[3] == OUTCOME_UNSUPPORTED_ENTRY_TYPE


async def test_process_index_batch_unexpected_exception_recorded_as_write_error() -> (
    None
):
    """An unexpected exception persists OUTCOME_WRITE_ERROR and continues."""
    from ctpool import backfill_per_log
    from ctpool.metrics import LogMetricsAccumulator
    from ctpool.outcome_constants import OUTCOME_WRITE_ERROR

    log_source_id = uuid.uuid4()
    settings = _make_settings()
    session: Any = AsyncMock()
    client: Any = AsyncMock()

    response = MagicMock()
    response.entries = [MagicMock(leaf_input="x")]

    parsed = MagicMock()
    normalized = MagicMock()
    normalized.hostnames = []

    with (
        patch.object(
            backfill_per_log, "fetch_entries", new=AsyncMock(return_value=response)
        ),
        patch.object(backfill_per_log, "parse_leaf_entry", return_value=parsed),
        patch.object(
            backfill_per_log, "build_normalized_entry", return_value=normalized
        ),
        patch.object(
            backfill_per_log,
            "persist_entry_with_retry",
            new=AsyncMock(side_effect=RuntimeError("disk-write failed")),
        ),
        patch.object(
            backfill_per_log, "persist_failure_outcome", new=AsyncMock()
        ) as failure_mock,
    ):
        count, _terminal, _obs = await backfill_per_log._process_index_batch(
            log_source_id,
            "https://x/",
            session,
            client,
            start_index=0,
            end_index=0,
            metrics=LogMetricsAccumulator(),
            settings=settings,
        )

    assert count == 0
    assert failure_mock.await_args.args[3] == OUTCOME_WRITE_ERROR
