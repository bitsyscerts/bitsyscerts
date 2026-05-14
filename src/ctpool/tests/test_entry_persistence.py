"""Tests for per-entry transactional persistence helpers."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

from sqlalchemy.exc import DBAPIError

from ctpool.entry_persistence import persist_entry_with_retry
from ctpool.entry_write_result import EntryWriteMetrics


class _DeadlockError(Exception):
    """Minimal DBAPI-like exception exposing PostgreSQL deadlock SQLSTATE."""

    sqlstate = "40P01"


def _deadlock_error() -> DBAPIError:
    """Return a retryable SQLAlchemy DBAPIError instance."""

    return DBAPIError("stmt", {}, _DeadlockError())


def _session_with_begin() -> AsyncMock:
    """Return an async session mock with a reusable begin context manager."""

    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


async def test_persist_entry_with_retry_uses_short_transaction() -> None:
    """Each entry write is wrapped in a dedicated transaction."""

    session = _session_with_begin()
    entry = MagicMock()

    with (
        patch(
            "ctpool.entry_persistence.write_normalized_entry",
            AsyncMock(return_value=EntryWriteMetrics()),
        ) as write_mock,
        patch("ctpool.entry_persistence.upsert_entry_outcome", AsyncMock()),
    ):
        result = await persist_entry_with_retry(
            session,
            entry,
            max_retries=3,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.1,
        )

    session.begin.assert_called_once()
    write_mock.assert_awaited_once_with(session, entry, flags=ANY)
    assert result == EntryWriteMetrics()


async def test_persist_entry_with_retry_retries_with_new_transaction() -> None:
    """A retryable deadlock opens a fresh transaction on the retry attempt."""

    session = _session_with_begin()
    entry = MagicMock()
    write_mock = AsyncMock(side_effect=[_deadlock_error(), EntryWriteMetrics()])

    with (
        patch(
            "ctpool.entry_persistence.write_normalized_entry",
            write_mock,
        ),
        patch("ctpool.entry_persistence.upsert_entry_outcome", AsyncMock()),
        patch("ctpool.retry.asyncio.sleep", AsyncMock()),
    ):
        result = await persist_entry_with_retry(
            session,
            entry,
            max_retries=3,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.1,
        )

    assert session.begin.call_count == 2
    assert write_mock.await_count == 2
    assert all(
        c == ((session, entry), {"flags": ANY}) for c in write_mock.await_args_list
    )
    assert result == EntryWriteMetrics()
