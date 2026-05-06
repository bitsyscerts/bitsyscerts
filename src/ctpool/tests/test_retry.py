"""Tests for ctpool.retry transient DB retry helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import DBAPIError

from ctpool.retry import is_retryable_db_error, run_with_db_retry


class _OrigDeadlockError(Exception):
    sqlstate = "40P01"


class _OrigSerializationError(Exception):
    sqlstate = "40001"


class _OrigOtherError(Exception):
    sqlstate = "23505"


def _dbapi_error(orig: BaseException) -> DBAPIError:
    return DBAPIError("stmt", {}, orig)


def test_is_retryable_db_error_deadlock_true() -> None:
    """Deadlock SQLSTATE is classified as retryable."""
    assert is_retryable_db_error(_dbapi_error(_OrigDeadlockError())) is True


def test_is_retryable_db_error_serialization_true() -> None:
    """Serialization failure SQLSTATE is classified as retryable."""
    assert is_retryable_db_error(_dbapi_error(_OrigSerializationError())) is True


def test_is_retryable_db_error_other_false() -> None:
    """Non-transient SQLSTATE is not retryable."""
    assert is_retryable_db_error(_dbapi_error(_OrigOtherError())) is False


async def test_run_with_db_retry_retries_then_succeeds() -> None:
    """run_with_db_retry retries transient failures and then returns result."""
    attempts = 0

    async def op() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _dbapi_error(_OrigDeadlockError())
        return "ok"

    out = await run_with_db_retry(
        op,
        max_retries=2,
        base_backoff_seconds=0.0,
        max_backoff_seconds=0.0,
    )

    assert out == "ok"
    assert attempts == 2


async def test_run_with_db_retry_does_not_retry_non_transient() -> None:
    """run_with_db_retry raises immediately for non-retryable DB errors."""

    async def op() -> str:
        raise _dbapi_error(_OrigOtherError())

    with pytest.raises(DBAPIError):
        await run_with_db_retry(
            op,
            max_retries=2,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )


async def test_run_with_db_retry_calls_on_retry_callback() -> None:
    """on_retry receives attempt count, exception, and computed delay."""
    calls: list[int] = []
    callback = MagicMock()

    async def op() -> str:
        if not calls:
            calls.append(1)
            raise _dbapi_error(_OrigDeadlockError())
        return "ok"

    def on_retry(attempt: int, exc: BaseException, delay: float) -> None:
        callback(attempt, exc, delay)

    out = await run_with_db_retry(
        op,
        max_retries=1,
        base_backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        on_retry=on_retry,
    )

    assert out == "ok"
    callback.assert_called_once()
