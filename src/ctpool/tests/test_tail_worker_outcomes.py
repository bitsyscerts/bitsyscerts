"""Tests for durable outcome recording in the tail worker.

Verifies that:
  - parse errors record OUTCOME_PARSE_ERROR before cursor advances
  - unsupported entry types record OUTCOME_UNSUPPORTED_ENTRY_TYPE before cursor advances
  - cursor does NOT advance if persist_failure_outcome raises
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.ct_api_schemas import CtEntriesResponse, CtLeafEntry, SignedTreeHead
from ctpool.exceptions import ParseError, UnsupportedEntryTypeError
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.outcome_constants import OUTCOME_PARSE_ERROR, OUTCOME_UNSUPPORTED_ENTRY_TYPE
from ctpool.tail_worker import run_tail

pytestmark = pytest.mark.asyncio

_FAKE_LEAF = "AAAA"


def _settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_tail_interval_seconds": 1,
        "ct_default_batch_size": 10,
        "ct_db_contention_min_batch_size": 1,
        "ct_db_contention_enabled": False,
        "ct_min_free_disk_gb": 1,
        "ct_critical_free_disk_gb": 0,
        "ct_http_timeout_seconds": 5,
    }
    base.update(kwargs)
    return Settings.model_validate(base)


def _log() -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="dGVzdA==",
        operator_name="TestOp",
        description="Test Log",
        url="https://ct.example.com/log/",
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=None,
        last_synced_at=None,
    )


def _cursor(log_id: uuid.UUID, next_index: int = 0) -> CtLogTailCursor:
    return CtLogTailCursor(id=uuid.uuid4(), log_source_id=log_id, next_index=next_index)


def _sth(tree_size: int = 5) -> SignedTreeHead:
    return SignedTreeHead(
        tree_size=tree_size,
        timestamp=0,
        sha256_root_hash="aa" * 32,
        tree_head_signature="bb",
    )


def _entries(n: int = 1) -> CtEntriesResponse:
    return CtEntriesResponse(
        entries=[CtLeafEntry(leaf_input=_FAKE_LEAF, extra_data="") for _ in range(n)]
    )


def _session_factory(log: CtLogSource) -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
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
def _claim_ok() -> object:
    with patch("ctpool.tail_worker.try_claim_tail_log", AsyncMock(return_value=True)):
        yield


async def test_parse_error_records_outcome_before_cursor_advances() -> None:
    """A ParseError during processing writes OUTCOME_PARSE_ERROR.

    The cursor must still advance (the outcome is durable so the entry is
    accounted for). We verify persist_failure_outcome is called.
    """
    log = _log()
    failure_outcomes: list[str] = []

    async def _fake_failure_outcome(
        session: object,
        log_source_id: object,
        log_index: object,
        outcome: str,
        error: object,
    ) -> None:
        failure_outcomes.append(outcome)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_sth(1))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(side_effect=ParseError("bad DER")),
        ),
        patch(
            "ctpool.tail_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log)
        await run_tail(factory, _settings(), once=True)

    assert OUTCOME_PARSE_ERROR in failure_outcomes


async def test_unsupported_entry_type_records_outcome_before_cursor_advances() -> None:
    """An UnsupportedEntryTypeError writes OUTCOME_UNSUPPORTED_ENTRY_TYPE."""
    log = _log()
    failure_outcomes: list[str] = []

    async def _fake_failure_outcome(
        session: object,
        log_source_id: object,
        log_index: object,
        outcome: str,
        error: object,
    ) -> None:
        failure_outcomes.append(outcome)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_sth(1))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(
                side_effect=UnsupportedEntryTypeError("Unknown LogEntryType: 0x0002")
            ),
        ),
        patch(
            "ctpool.tail_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log)
        await run_tail(factory, _settings(), once=True)

    assert OUTCOME_UNSUPPORTED_ENTRY_TYPE in failure_outcomes


async def test_cursor_does_not_advance_if_failure_outcome_write_raises() -> None:
    """If persist_failure_outcome raises, the cursor does NOT advance.

    The RuntimeError propagates out of run_tail (no general exception
    handler; the supervisor is expected to restart the worker and the cursor
    stays at the pre-batch position so entries are retried on restart).
    """
    log = _log()
    advance_mock = AsyncMock()

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_sth(1))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(side_effect=ParseError("bad bytes")),
        ),
        patch(
            "ctpool.tail_worker.persist_failure_outcome",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", advance_mock),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
        pytest.raises(RuntimeError, match="db down"),
    ):
        factory = _session_factory(log)
        await run_tail(factory, _settings(), once=True)

    advance_mock.assert_not_called()


async def test_outcome_recorded_for_each_failing_entry_in_batch() -> None:
    """Each of N parse-failing entries in a batch gets its own outcome call."""
    log = _log()
    failure_outcomes: list[str] = []

    async def _fake_failure_outcome(
        session: object,
        log_source_id: object,
        log_index: object,
        outcome: str,
        error: object,
    ) -> None:
        failure_outcomes.append(outcome)

    with (
        patch("ctpool.tail_worker.is_disk_critical", return_value=False),
        patch("ctpool.tail_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.tail_worker.get_eligible_tail_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.tail_worker.ensure_tail_cursor",
            AsyncMock(return_value=(_cursor(log.id, 0), False)),
        ),
        patch("ctpool.tail_worker.fetch_sth", AsyncMock(return_value=_sth(3))),
        patch(
            "ctpool.tail_worker.fetch_entries",
            AsyncMock(return_value=_entries(3)),
        ),
        patch(
            "ctpool.tail_worker.parse_leaf_entry",
            MagicMock(side_effect=ParseError("bad")),
        ),
        patch(
            "ctpool.tail_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.tail_worker.advance_tail_cursor", AsyncMock()),
        patch("ctpool.tail_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log)
        await run_tail(factory, _settings(), once=True)

    assert len(failure_outcomes) == 3
    assert all(o == OUTCOME_PARSE_ERROR for o in failure_outcomes)
