"""Persist normalized CT entries in short-lived retryable transactions.

Exports:
    persist_entry_with_retry — Write one normalized entry plus outcome=stored
                               in an atomic transaction, with bounded retry.
    persist_failure_outcome  — Write a terminal failure outcome for one index
                               that could not be stored (parse error, unsupported
                               entry type, etc.).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.entry_write_result import EntryWriteMetrics
from ctpool.outcome_constants import OUTCOME_STORED
from ctpool.outcome_writer import upsert_entry_outcome
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
) -> EntryWriteMetrics:
    """Write one normalized entry and record outcome=stored atomically.

    Both the certificate/hostname/observation data and the terminal outcome
    row are committed in the same transaction.  This ensures the cursor or
    backfill range can only advance after durable accounting exists.

    Args:
        session: Active async database session.
        entry: Normalized CT entry ready for persistence.
        max_retries: Maximum transient DB retries.
        base_backoff_seconds: Initial retry delay.
        max_backoff_seconds: Maximum retry delay.
        on_retry: Optional retry callback for logging.
    """

    async def _write_once() -> EntryWriteMetrics:
        async with session.begin():
            result = await write_normalized_entry(session, entry)
            await upsert_entry_outcome(
                session,
                entry.log_source_id,
                entry.log_index,
                OUTCOME_STORED,
                certificate_fingerprint_sha256=(
                    entry.parsed_certificate.fingerprint_sha256
                ),
            )
            return result

    return await run_with_db_retry(
        _write_once,
        max_retries=max_retries,
        base_backoff_seconds=base_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds,
        on_retry=on_retry,
    )


async def persist_failure_outcome(
    session: AsyncSession,
    log_source_id: uuid.UUID,
    log_index: int,
    outcome: str,
    error: BaseException,
) -> None:
    """Write a terminal failure outcome for a CT log index that could not be stored.

    Opens its own short transaction so the outcome is durable before the
    worker loop continues.  If this write fails, the exception propagates and
    the cursor/range does not advance — preserving the durability invariant.

    Args:
        session:       Active async database session.
        log_source_id: FK to ``ct_log_sources.id``.
        log_index:     Zero-based CT log index.
        outcome:       OUTCOME_PARSE_ERROR or OUTCOME_UNSUPPORTED_ENTRY_TYPE.
        error:         The exception that caused the failure.
    """
    async with session.begin():
        await upsert_entry_outcome(
            session,
            log_source_id,
            log_index,
            outcome,
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        )
