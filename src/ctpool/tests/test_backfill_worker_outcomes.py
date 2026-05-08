"""Tests for durable outcome recording in the backfill worker.

Verifies that:
  - parse errors record OUTCOME_PARSE_ERROR during backfill
  - unsupported entry types record OUTCOME_UNSUPPORTED_ENTRY_TYPE during backfill
  - backfill range next_index does NOT advance if persist_failure_outcome raises
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.backfill_worker import run_backfill
from ctpool.config import Settings
from ctpool.ct_api_schemas import CtEntriesResponse, CtLeafEntry, SignedTreeHead
from ctpool.exceptions import ParseError, UnsupportedEntryTypeError
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.outcome_constants import (
    OUTCOME_PARSE_ERROR,
    OUTCOME_UNSUPPORTED_ENTRY_TYPE,
    OUTCOME_WRITE_ERROR,
)

pytestmark = pytest.mark.asyncio

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
_FAKE_LEAF = "AAAA"


@pytest.fixture(autouse=True)
def _patch_reap_stale():
    """Prevent reap_stale_backfill_claims from hitting the mock session."""
    with patch(
        "ctpool.backfill_worker.reap_stale_backfill_claims",
        AsyncMock(return_value=[]),
    ):
        yield


def _settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 5,
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
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _range(log_id: uuid.UUID) -> CtLogBackfillRange:
    return CtLogBackfillRange(
        id=uuid.uuid4(),
        log_source_id=log_id,
        start_index=0,
        end_index=2,
        next_index=0,
        status="in_progress",
    )


def _sth(tree_size: int = 10) -> SignedTreeHead:
    return SignedTreeHead(
        tree_size=tree_size,
        timestamp=0,
        sha256_root_hash="aa" * 32,
        tree_head_signature="bb",
    )


def _entries(n: int) -> CtEntriesResponse:
    return CtEntriesResponse(
        entries=[CtLeafEntry(leaf_input=_FAKE_LEAF, extra_data="") for _ in range(n)]
    )


def _session_factory(
    log: CtLogSource,
    rng: CtLogBackfillRange | None = None,
) -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    async def _fake_get(model_cls: object, pk: object) -> object:
        if model_cls is CtLogSource:
            return log
        return None

    session.get = _fake_get
    factory = MagicMock()
    factory.session = session
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


async def test_backfill_parse_error_records_outcome() -> None:
    """ParseError during backfill writes OUTCOME_PARSE_ERROR."""
    log = _log()
    rng = _range(log.id)
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
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges",
            AsyncMock(return_value=True),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(side_effect=[rng, None]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(side_effect=ParseError("bad DER")),
        ),
        patch(
            "ctpool.backfill_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log, rng)
        await run_backfill(factory, _settings(), once=True)

    assert OUTCOME_PARSE_ERROR in failure_outcomes


async def test_backfill_unsupported_entry_type_records_outcome() -> None:
    """UnsupportedEntryTypeError during backfill writes
    OUTCOME_UNSUPPORTED_ENTRY_TYPE.
    """
    log = _log()
    rng = _range(log.id)
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
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges",
            AsyncMock(return_value=True),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(side_effect=[rng, None]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(
                side_effect=UnsupportedEntryTypeError("Unknown LogEntryType: 0x0002")
            ),
        ),
        patch(
            "ctpool.backfill_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log, rng)
        await run_backfill(factory, _settings(), once=True)

    assert OUTCOME_UNSUPPORTED_ENTRY_TYPE in failure_outcomes


async def test_backfill_range_marked_failed_if_outcome_write_raises() -> None:
    """If persist_failure_outcome raises, range is marked failed (not complete)."""
    log = _log()
    rng = _range(log.id)
    mark_complete_mock = AsyncMock()
    mark_failed_mock = AsyncMock()

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges",
            AsyncMock(return_value=True),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(side_effect=[rng, None]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(side_effect=ParseError("bad bytes")),
        ),
        patch(
            "ctpool.backfill_worker.persist_failure_outcome",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        patch("ctpool.backfill_worker.mark_range_complete", mark_complete_mock),
        patch("ctpool.backfill_worker.mark_range_failed", mark_failed_mock),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log, rng)
        await run_backfill(factory, _settings(), once=True)

    mark_complete_mock.assert_not_called()
    mark_failed_mock.assert_called_once()


async def test_backfill_unexpected_exception_records_write_error_outcome() -> None:
    """An unexpected exception from persist_entry_with_retry writes OUTCOME_WRITE_ERROR.

    This is the accounting gap that previously caused missing_entry_outcomes audit
    findings: the entry was parsed but the write failed after retry exhaustion, and
    no outcome row was recorded.  The range still completes; only the specific index
    is marked write_error so the audit checker and repair process can re-queue it.
    """
    log = _log()
    rng = _range(log.id)
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
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges",
            AsyncMock(return_value=True),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(side_effect=[rng, None]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.backfill_worker.build_normalized_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.backfill_worker.persist_entry_with_retry",
            AsyncMock(side_effect=RuntimeError("retry exhausted")),
        ),
        patch(
            "ctpool.backfill_worker.persist_failure_outcome",
            _fake_failure_outcome,
        ),
        patch("ctpool.backfill_worker.mark_range_complete", AsyncMock()),
        patch("ctpool.backfill_worker.mark_range_failed", AsyncMock()),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log, rng)
        await run_backfill(factory, _settings(), once=True)

    assert OUTCOME_WRITE_ERROR in failure_outcomes


async def test_backfill_write_error_range_still_completes() -> None:
    """A range with a write_error index is still marked complete, not failed.

    The write_error outcome records the accounting gap durably.  The range
    completion allows progress to continue; the audit checker and repair process
    handle re-queuing the affected span.
    """
    log = _log()
    rng = _range(log.id)
    mark_complete_mock = AsyncMock()
    mark_failed_mock = AsyncMock()

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges",
            AsyncMock(return_value=True),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range",
            AsyncMock(side_effect=[rng, None]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_entries",
            AsyncMock(return_value=_entries(1)),
        ),
        patch(
            "ctpool.backfill_worker.parse_leaf_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.backfill_worker.build_normalized_entry",
            MagicMock(return_value=MagicMock()),
        ),
        patch(
            "ctpool.backfill_worker.persist_entry_with_retry",
            AsyncMock(side_effect=RuntimeError("retry exhausted")),
        ),
        patch(
            "ctpool.backfill_worker.persist_failure_outcome",
            AsyncMock(),
        ),
        patch("ctpool.backfill_worker.mark_range_complete", mark_complete_mock),
        patch("ctpool.backfill_worker.mark_range_failed", mark_failed_mock),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        factory = _session_factory(log, rng)
        await run_backfill(factory, _settings(), once=True)

    mark_complete_mock.assert_called_once()
    mark_failed_mock.assert_not_called()
