"""Tests for entry_persistence — outcome recording behavior.

Verifies that:
  - successful entry writes also record outcome=stored
  - persist_failure_outcome writes a terminal failure row
  - cursor/range does NOT advance if the outcome write fails
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.entry_persistence import persist_entry_with_retry, persist_failure_outcome
from ctpool.exceptions import ParseError
from ctpool.outcome_constants import OUTCOME_PARSE_ERROR, OUTCOME_STORED

pytestmark = pytest.mark.asyncio


def _session_with_begin() -> AsyncMock:
    """Return an async session mock with a reusable begin context manager."""
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


def _make_entry(
    fingerprint: str = "abc123",
    log_source_id: uuid.UUID | None = None,
    log_index: int = 0,
) -> MagicMock:
    entry = MagicMock()
    entry.log_source_id = log_source_id or uuid.uuid4()
    entry.log_index = log_index
    entry.parsed_certificate.fingerprint_sha256 = fingerprint
    return entry


async def test_persist_entry_writes_stored_outcome() -> None:
    """Successful entry persist also calls upsert_entry_outcome with OUTCOME_STORED."""
    session = _session_with_begin()
    entry = _make_entry(fingerprint="deadbeef")

    with (
        patch("ctpool.entry_persistence.write_normalized_entry", AsyncMock()),
        patch(
            "ctpool.entry_persistence.upsert_entry_outcome", AsyncMock()
        ) as outcome_mock,
    ):
        await persist_entry_with_retry(
            session,
            entry,
            max_retries=1,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.1,
        )

    outcome_mock.assert_awaited_once_with(
        session,
        entry.log_source_id,
        entry.log_index,
        OUTCOME_STORED,
        certificate_fingerprint_sha256="deadbeef",
    )


async def test_persist_entry_outcome_and_cert_in_same_transaction() -> None:
    """cert write and outcome write share the same session.begin() call."""
    session = _session_with_begin()
    entry = _make_entry()

    call_order: list[str] = []

    async def _fake_write(*_args: object, **_kwargs: object) -> None:
        call_order.append("cert")

    async def _fake_outcome(*_args: object, **_kwargs: object) -> None:
        call_order.append("outcome")

    with (
        patch("ctpool.entry_persistence.write_normalized_entry", _fake_write),
        patch("ctpool.entry_persistence.upsert_entry_outcome", _fake_outcome),
    ):
        await persist_entry_with_retry(
            session,
            entry,
            max_retries=1,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.1,
        )

    # Both writes happen inside ONE transaction
    assert session.begin.call_count == 1
    assert call_order == ["cert", "outcome"]


async def test_cursor_does_not_advance_if_outcome_write_fails() -> None:
    """If upsert_entry_outcome raises, the exception propagates (no silent swallow)."""
    session = _session_with_begin()
    entry = _make_entry()

    with (
        patch("ctpool.entry_persistence.write_normalized_entry", AsyncMock()),
        patch(
            "ctpool.entry_persistence.upsert_entry_outcome",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
        patch("ctpool.retry.asyncio.sleep", AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="db down"):
            await persist_entry_with_retry(
                session,
                entry,
                max_retries=1,
                base_backoff_seconds=0.01,
                max_backoff_seconds=0.1,
            )


async def test_persist_failure_outcome_writes_parse_error() -> None:
    """persist_failure_outcome opens its own transaction and writes the outcome."""
    session = _session_with_begin()
    log_source_id = uuid.uuid4()
    exc = ParseError("bad DER bytes")

    with patch(
        "ctpool.entry_persistence.upsert_entry_outcome", AsyncMock()
    ) as outcome_mock:
        await persist_failure_outcome(
            session, log_source_id, 42, OUTCOME_PARSE_ERROR, exc
        )

    session.begin.assert_called_once()
    outcome_mock.assert_awaited_once_with(
        session,
        log_source_id,
        42,
        OUTCOME_PARSE_ERROR,
        error_type="ParseError",
        error_message="bad DER bytes",
    )


async def test_persist_failure_outcome_truncates_long_message() -> None:
    """Error messages exceeding 500 chars are truncated before storage."""
    session = _session_with_begin()
    log_source_id = uuid.uuid4()
    long_message = "x" * 600
    exc = ParseError(long_message)

    captured: list[str] = []

    async def _capture(*_args: object, **kwargs: object) -> None:
        msg = kwargs.get("error_message", "")
        captured.append(str(msg))

    with patch("ctpool.entry_persistence.upsert_entry_outcome", _capture):
        await persist_failure_outcome(
            session, log_source_id, 0, OUTCOME_PARSE_ERROR, exc
        )

    assert len(captured[0]) == 500


async def test_persist_failure_outcome_propagates_db_error() -> None:
    """If the outcome write fails, the exception is not swallowed."""
    session = _session_with_begin()
    exc = ParseError("parse fail")

    with patch(
        "ctpool.entry_persistence.upsert_entry_outcome",
        AsyncMock(side_effect=RuntimeError("connection lost")),
    ):
        with pytest.raises(RuntimeError, match="connection lost"):
            await persist_failure_outcome(
                session, uuid.uuid4(), 0, OUTCOME_PARSE_ERROR, exc
            )
