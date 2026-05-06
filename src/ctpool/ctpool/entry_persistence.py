"""Persist normalized CT entries in short-lived retryable transactions.

Exports:
    persist_entry_with_retry — Write one normalized entry using its own
    transaction and bounded retry policy.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.pipeline_schemas import NormalizedEntry
from ctpool.retry import run_with_db_retry
from ctpool.writer import write_normalized_entry


async def persist_entry_with_retry(
    session: AsyncSession,
    entry: NormalizedEntry,
    *,
    max_retries: int,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> None:
    """Write one normalized entry in its own retryable transaction.

    Keeping each entry inside a short-lived transaction ensures row locks are
    released promptly after success, rather than being retained for an entire
    worker batch.

    Args:
        session: Active async database session.
        entry: Normalized CT entry ready for persistence.
        max_retries: Maximum transient DB retries.
        base_backoff_seconds: Initial retry delay.
        max_backoff_seconds: Maximum retry delay.
        on_retry: Optional retry callback for logging.
    """

    async def _write_once() -> None:
        async with session.begin():
            await write_normalized_entry(session, entry)

    await run_with_db_retry(
        _write_once,
        max_retries=max_retries,
        base_backoff_seconds=base_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        on_retry=on_retry,
    )
