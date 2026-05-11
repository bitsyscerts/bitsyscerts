"""Unit tests for the updated _tail_one_log claim/release contract.

Verifies that _tail_one_log:
  - calls claim_tail_log before processing
  - calls release_tail_log after success (in finally)
  - calls release_tail_log after FetchError (in finally)
  - calls release_tail_log after RateLimitError (in finally)
  - never calls the deprecated try_claim_tail_log
  - skips processing when claim_tail_log returns False

All external boundaries are mocked; no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.ct_api_schemas import SignedTreeHead
from ctpool.db_contention_types import DbContentionObservation
from ctpool.exceptions import FetchError, RateLimitError
from ctpool.models.log_source import CtLogSource
from ctpool.models.log_tail_cursor import CtLogTailCursor
from ctpool.tail_worker import _tail_one_log

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_WORKER = "test-host:99"


def _make_settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_tail_interval_seconds": 1,
        "ct_default_batch_size": 2,
        "ct_db_contention_min_batch_size": 1,
        "ct_db_contention_enabled": False,
        "ct_min_free_disk_gb": 1,
        "ct_critical_free_disk_gb": 0,
        "ct_http_timeout_seconds": 5,
        "ct_worker_stale_seconds": 120,
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _make_log() -> CtLogSource:
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


def _make_cursor(log_id: uuid.UUID) -> CtLogTailCursor:
    return CtLogTailCursor(id=uuid.uuid4(), log_source_id=log_id, next_index=0)


def _make_sth(tree_size: int = 0) -> SignedTreeHead:
    return SignedTreeHead(
        tree_size=tree_size,
        timestamp=0,
        sha256_root_hash="aa" * 32,
        tree_head_signature="bb",
    )


def _make_session_factory() -> MagicMock:
    """Return a session factory whose context manager yields an AsyncMock session."""
    txn_cm = MagicMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.begin = MagicMock(return_value=txn_cm)

    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = cm
    return factory


# ---------------------------------------------------------------------------
# Helpers: set up standard patches shared across tests
# ---------------------------------------------------------------------------

_PATCH_CLAIM = "ctpool.tail_worker.claim_tail_log"
_PATCH_RELEASE = "ctpool.tail_worker.release_tail_log"
_PATCH_HEARTBEAT = "ctpool.tail_worker.heartbeat_tail_lease"
_PATCH_PROCESS = "ctpool.tail_worker._process_log_batch"
_PATCH_WORKER_ID = "ctpool.tail_worker._worker_id"
_PATCH_OLD_CLAIM = "ctpool.tail_worker.try_claim_tail_log"


async def _run_with_patches(
    log: CtLogSource,
    *,
    claim_returns: bool = True,
    process_side_effect: object = None,
) -> tuple[object, AsyncMock, AsyncMock]:
    """Run _tail_one_log with standard patches.

    Returns (result, claim_mock, release_mock).
    """
    factory = _make_session_factory()
    settings = _make_settings()
    client = AsyncMock()

    process_return = (0, True, DbContentionObservation(0, 0))

    with (
        patch(_PATCH_WORKER_ID, return_value=_WORKER),
        patch(
            _PATCH_CLAIM, new_callable=AsyncMock, return_value=claim_returns
        ) as mock_claim,
        patch(_PATCH_RELEASE, new_callable=AsyncMock) as mock_release,
        patch(_PATCH_HEARTBEAT, new_callable=AsyncMock),
        patch(
            _PATCH_PROCESS,
            new_callable=AsyncMock,
            return_value=process_return,
            side_effect=process_side_effect,
        ),
    ):
        result = await _tail_one_log(
            log,
            factory,
            client,
            MagicMock(has_activity=MagicMock(return_value=False)),
            settings,
            batch_size=2,
            limit_remaining=None,
        )
        return result, mock_claim, mock_release


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_claim_called_before_processing() -> None:
    """claim_tail_log is called; _process_log_batch only runs after a True claim."""
    log = _make_log()
    factory = _make_session_factory()
    settings = _make_settings()
    call_order: list[str] = []

    async def fake_claim(*_a: object, **_kw: object) -> bool:
        call_order.append("claim")
        return True

    async def fake_process(*_a: object, **_kw: object) -> tuple:
        call_order.append("process")
        return (0, True, DbContentionObservation(0, 0))

    with (
        patch(_PATCH_WORKER_ID, return_value=_WORKER),
        patch(_PATCH_CLAIM, side_effect=fake_claim),
        patch(_PATCH_RELEASE, new_callable=AsyncMock),
        patch(_PATCH_HEARTBEAT, new_callable=AsyncMock),
        patch(_PATCH_PROCESS, side_effect=fake_process),
    ):
        await _tail_one_log(
            log,
            factory,
            AsyncMock(),
            MagicMock(has_activity=MagicMock(return_value=False)),
            settings,
            batch_size=2,
            limit_remaining=None,
        )

    assert call_order == ["claim", "process"]


async def test_release_called_after_successful_processing() -> None:
    """release_tail_log is called in finally after normal return."""
    log = _make_log()
    _, _, mock_release = await _run_with_patches(log, claim_returns=True)
    mock_release.assert_awaited_once()


async def test_release_called_after_fetch_error() -> None:
    """release_tail_log is called even when _process_log_batch raises FetchError."""
    log = _make_log()
    _, _, mock_release = await _run_with_patches(
        log,
        claim_returns=True,
        process_side_effect=FetchError("network down"),
    )
    mock_release.assert_awaited_once()


async def test_release_called_after_rate_limit_error() -> None:
    """release_tail_log is called even when _process_log_batch raises RateLimitError."""
    log = _make_log()
    err = RateLimitError("429", retry_after_seconds=30)
    _, _, mock_release = await _run_with_patches(
        log,
        claim_returns=True,
        process_side_effect=err,
    )
    mock_release.assert_awaited_once()


async def test_old_try_claim_tail_log_not_called() -> None:
    """The deprecated try_claim_tail_log is not imported by tail_worker."""
    import ctpool.tail_worker as tw

    assert not hasattr(tw, "try_claim_tail_log"), (
        "try_claim_tail_log must not be imported in tail_worker; "
        "use claim_tail_log instead"
    )


async def test_skips_processing_when_claim_returns_false() -> None:
    """_process_log_batch is not called when claim_tail_log returns False."""
    log = _make_log()
    factory = _make_session_factory()
    settings = _make_settings()

    with (
        patch(_PATCH_WORKER_ID, return_value=_WORKER),
        patch(_PATCH_CLAIM, new_callable=AsyncMock, return_value=False),
        patch(_PATCH_RELEASE, new_callable=AsyncMock) as mock_release,
        patch(_PATCH_HEARTBEAT, new_callable=AsyncMock),
        patch(_PATCH_PROCESS, new_callable=AsyncMock) as mock_process,
    ):
        result = await _tail_one_log(
            log,
            factory,
            AsyncMock(),
            MagicMock(has_activity=MagicMock(return_value=False)),
            settings,
            batch_size=2,
            limit_remaining=None,
        )

    entries, is_empty, *_ = result
    assert entries == 0
    assert is_empty is True
    mock_process.assert_not_awaited()
    # release is NOT called when we never claimed
    mock_release.assert_not_awaited()
