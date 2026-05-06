"""Transient database retry helpers for ingestion workers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import DBAPIError

_RETRYABLE_SQLSTATES = {"40P01", "40001"}


def _extract_sqlstate(exc: BaseException) -> str | None:
    """Return SQLSTATE code from a SQLAlchemy DBAPIError chain if available."""
    if not isinstance(exc, DBAPIError):
        return None
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    sqlstate = getattr(orig, "sqlstate", None)
    if isinstance(sqlstate, str):
        return sqlstate
    pgcode = getattr(orig, "pgcode", None)
    if isinstance(pgcode, str):
        return pgcode
    return None


def is_retryable_db_error(exc: BaseException) -> bool:
    """Return True when *exc* looks like a transient lock/serialization error."""
    sqlstate = _extract_sqlstate(exc)
    return sqlstate in _RETRYABLE_SQLSTATES


async def run_with_db_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """Run an async DB operation with bounded exponential retry.

    Retries only transient PostgreSQL deadlock/serialization errors.
    """
    attempt = 0
    while True:
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001
            if not is_retryable_db_error(exc) or attempt >= max_retries:
                raise
            attempt += 1
            delay = min(
                max_backoff_seconds,
                base_backoff_seconds * (2 ** (attempt - 1)),
            )
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            await asyncio.sleep(delay)
