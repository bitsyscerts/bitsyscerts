"""Per-log backfill dispatch loop.

This is the new normal-runtime backfill path. A worker claims one CT log
through ``ct_log_backfill_state`` and processes batches of that log using
the per-log durable checkpoint. The legacy ``ct_log_backfill_ranges``
table is not touched by this loop.

Exports:
    run_backfill_per_log — Per-log dispatch loop entry point.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
import uuid as _uuid
from collections.abc import Callable
from os import getpid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.backfill_state_init import initialize_backfill_state_for_log
from ctpool.config import Settings
from ctpool.db_contention_accumulator import DbRetryPressureAccumulator
from ctpool.db_contention_coordinator import (
    build_db_retry_callback,
    get_db_contention_directive,
    resolve_effective_batch_size,
    sleep_for_db_contention,
    submit_db_contention_observation,
)
from ctpool.db_contention_types import DbContentionObservation
from ctpool.disk_guard import is_disk_critical, is_disk_low
from ctpool.dispatcher import get_eligible_backfill_logs
from ctpool.entry_persistence import persist_entry_with_retry, persist_failure_outcome
from ctpool.exceptions import (
    FetchError,
    ParseError,
    UnsupportedEntryTypeError,
)
from ctpool.fetcher import fetch_entries
from ctpool.ingestion_errors import (
    IngestionFailureClass,
    classify_ingestion_error,
)
from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.log_backfill_state import CtLogBackfillState
from ctpool.models.log_source import CtLogSource
from ctpool.normalizer import build_normalized_entry
from ctpool.outcome_constants import (
    OUTCOME_PARSE_ERROR,
    OUTCOME_UNSUPPORTED_ENTRY_TYPE,
    OUTCOME_WRITE_ERROR,
)
from ctpool.parser import parse_leaf_entry
from ctpool.worker_claim import (
    claim_any_eligible_log,
    increment_terminal_error_count,
    mark_log_complete,
    mark_log_paused,
    mark_log_retrying,
    reap_stale_log_claims,
    release_log_claim,
    update_log_progress,
)
from ctpool.worker_registry import (
    WorkerCounters,
    heartbeat_worker,
    mark_worker_stopped,
    register_worker,
)

_logger = logging.getLogger(__name__)

_SLEEP_NO_LOGS_SECONDS = 30
_SLEEP_DISK_LOW_SECONDS = 60


def _worker_id() -> str:
    """Return a stable identity string: ``hostname:PID``."""
    return f"{socket.gethostname()}:{getpid()}"


async def _process_index_batch(
    log_source_id: _uuid.UUID,
    log_url: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    start_index: int,
    end_index: int,
    metrics: LogMetricsAccumulator,
    settings: Settings,
) -> tuple[int, int, DbContentionObservation]:
    """Fetch and write one batch of entries in ``[start_index, end_index]``.

    Mirrors the legacy ``_process_range_batch`` but is keyed by raw indices
    rather than a range row. Terminal entry failures (parse / unsupported /
    write error) are recorded via ``persist_failure_outcome`` and do not
    abort the batch.
    """
    response = await fetch_entries(log_url, start_index, end_index, client)
    count = 0
    parsed_count = 0
    terminal_count = 0
    retry_accumulator = DbRetryPressureAccumulator()
    for i, raw_entry in enumerate(response.entries):
        entry_index = start_index + i
        try:
            parsed = parse_leaf_entry(raw_entry.leaf_input)
            normalized = build_normalized_entry(parsed, log_source_id, entry_index)
            parsed_count += 1

            def _on_retry(
                attempt: int,
                exc: BaseException,
                delay: float,
                *,
                idx: int = entry_index,
            ) -> None:
                _logger.warning(
                    "deadlock retry backfill log=%s index=%d attempt=%d "
                    "delay=%.3fs: %s",
                    log_source_id,
                    idx,
                    attempt,
                    delay,
                    exc,
                )

            retry_accumulator.record_entry_attempt()
            write_metrics = await persist_entry_with_retry(
                session,
                normalized,
                max_retries=settings.ct_deadlock_max_retries,
                base_backoff_seconds=settings.ct_deadlock_base_backoff_seconds,
                max_backoff_seconds=settings.ct_deadlock_max_backoff_seconds,
                on_retry=build_db_retry_callback(retry_accumulator, _on_retry),
            )
            count += 1
            metrics.record_entry_write_metrics(write_metrics)
        except UnsupportedEntryTypeError as exc:
            _logger.warning(
                "unsupported entry type backfill log=%s index=%d: %s",
                log_source_id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                log_source_id,
                entry_index,
                OUTCOME_UNSUPPORTED_ENTRY_TYPE,
                exc,
            )
            terminal_count += 1
        except ParseError as exc:
            _logger.warning(
                "parse error backfill log=%s index=%d: %s",
                log_source_id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                log_source_id,
                entry_index,
                OUTCOME_PARSE_ERROR,
                exc,
            )
            terminal_count += 1
        except Exception as exc:
            _logger.warning(
                "unexpected cert error backfill log=%s index=%d type=%s detail=%r",
                log_source_id,
                entry_index,
                exc.__class__.__name__,
                exc,
            )
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                log_source_id,
                entry_index,
                OUTCOME_WRITE_ERROR,
                exc,
            )
            terminal_count += 1

    metrics.record_entries_fetched(len(response.entries))
    metrics.record_entries_parsed(parsed_count)
    observation = retry_accumulator.drain()
    metrics.record_retryable_errors(observation.retryable_errors)
    return count, terminal_count, observation


async def _run_one_log_batch(
    state_row: CtLogBackfillState,
    log_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    settings: Settings,
    batch_size: int,
    limit_remaining: int | None,
    worker_id: str,
) -> tuple[int, bool, DbContentionObservation, int | None, int]:
    """Process one batch for a claimed log and persist progress.

    Computes the next batch from the durable checkpoint and the configured
    window, processes the entries, and on success advances the checkpoint
    in ``ct_log_backfill_state``.

    Returns:
        ``(entries_processed, was_rate_limited, contention, retry_after_seconds,
        next_checkpoint)``. ``next_checkpoint`` is the new
        ``last_checkpoint_index`` after this batch (regardless of how many
        cert rows were written, since terminal entry outcomes also advance
        the checkpoint).
    """
    assert state_row.last_checkpoint_index is not None  # noqa: S101
    assert state_row.backfill_end_index is not None  # noqa: S101
    next_index = int(state_row.last_checkpoint_index)
    end_window = int(state_row.backfill_end_index)
    batch = batch_size
    if limit_remaining is not None:
        batch = min(batch, limit_remaining)
    last_index = min(next_index + batch - 1, end_window)

    metrics = LogMetricsAccumulator()
    log_source_id = state_row.log_source_id
    try:
        async with session_factory() as session:
            count, terminal_count, observation = await _process_index_batch(
                log_source_id,
                log_url,
                session,
                client,
                next_index,
                last_index,
                metrics,
                settings,
            )
            if metrics.has_activity():
                async with session.begin():
                    await metrics.persist_snapshot(session, log_source_id)

        new_checkpoint = last_index + 1
        async with session_factory() as session:
            async with session.begin():
                await update_log_progress(
                    session,
                    log_source_id=log_source_id,
                    worker_id=worker_id,
                    checkpoint_index=new_checkpoint,
                    status="processing",
                )
                if terminal_count > 0:
                    await increment_terminal_error_count(
                        session, log_source_id=log_source_id
                    )
        return count, False, observation, None, new_checkpoint
    except Exception as exc:
        failure = classify_ingestion_error(exc)
        if failure.is_retryable:
            metrics.record_retryable_errors(1)
        if metrics.has_activity():
            async with session_factory() as session:
                async with session.begin():
                    await metrics.persist_snapshot(session, log_source_id)
        return await _handle_batch_failure(
            session_factory,
            log_source_id=log_source_id,
            worker_id=worker_id,
            settings=settings,
            current_retry_count=int(state_row.retry_count or 0),
            next_index=next_index,
            failure_class=failure.failure_class,
            error_type=failure.error_type,
            error_message=failure.error_message,
            retry_after_seconds=failure.retry_after_seconds,
        )


async def _handle_batch_failure(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    log_source_id: _uuid.UUID,
    worker_id: str,
    settings: Settings,
    current_retry_count: int,
    next_index: int,
    failure_class: IngestionFailureClass,
    error_type: str,
    error_message: str,
    retry_after_seconds: int | None,
) -> tuple[int, bool, DbContentionObservation, int | None, int]:
    """Persist a classified per-batch failure and return the loop tuple.

    Enforces the retry budget: when the per-log ``retry_count`` has reached
    ``ct_batch_retry_max_attempts`` the log is paused so an operator can
    intervene; otherwise the failure is recorded as ``retrying`` (or
    ``rate_limited`` when the upstream supplied a ``Retry-After`` hint).
    """
    is_rate_limit = failure_class is IngestionFailureClass.RETRYABLE_RATE_LIMIT
    is_fatal = failure_class in (
        IngestionFailureClass.FATAL_LOG,
        IngestionFailureClass.FATAL_CONFIGURATION,
    )
    budget_exceeded = current_retry_count + 1 >= settings.ct_batch_retry_max_attempts

    log_level = logging.WARNING if is_rate_limit else logging.ERROR
    _logger.log(
        log_level,
        "ingestion failure log=%s class=%s type=%s detail=%s",
        log_source_id,
        failure_class.value,
        error_type,
        error_message,
    )

    async with session_factory() as session:
        async with session.begin():
            if is_fatal or budget_exceeded:
                await mark_log_paused(
                    session,
                    log_source_id=log_source_id,
                    worker_id=worker_id,
                    error_type=error_type,
                    error_message=error_message,
                )
            else:
                await mark_log_retrying(
                    session,
                    log_source_id=log_source_id,
                    worker_id=worker_id,
                    error_type=error_type,
                    error_message=error_message,
                    retry_after_seconds=retry_after_seconds,
                )
    return (
        0,
        is_rate_limit,
        DbContentionObservation(0, 0),
        retry_after_seconds,
        next_index,
    )


async def _initialize_states(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    client: httpx.AsyncClient,
    days: int,
    log_id: _uuid.UUID | None,
    on_status: Callable[[str], None] | None,
) -> None:
    """Probe each eligible log and initialize its per-log backfill window."""
    async with session_factory() as session:
        logs = await get_eligible_backfill_logs(session)
    if log_id is not None:
        logs = [lg for lg in logs if lg.id == log_id]
    for log in logs:
        await initialize_backfill_state_for_log(
            log, session_factory, client, days, on_status
        )


async def _resolve_log_url(
    session_factory: async_sessionmaker[AsyncSession],
    log_source_id: _uuid.UUID,
) -> str:
    """Return the URL for a CT log given its UUID."""
    async with session_factory() as session:
        log = await session.get(CtLogSource, log_source_id)
        if log is None:
            raise FetchError(
                f"CtLogSource {log_source_id} not found for backfill state"
            )
        return log.url


async def run_backfill_per_log(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    once: bool = False,
    limit: int | None = None,
    days: int | None = None,
    log_id: _uuid.UUID | None = None,
    on_batch: Callable[[str, int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    batch_size: int | None = None,
) -> None:
    """Per-log backfill dispatch loop entry point.

    Each iteration the worker claims one eligible CT log via
    ``ct_log_backfill_state`` (atomic, ``SELECT FOR UPDATE SKIP LOCKED``),
    then drives that log's checkpoint forward batch by batch until the
    window is complete, the claim becomes stale, or a terminal condition
    occurs. The ``ct_log_backfill_ranges`` table is not consulted.

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        once:            Exit after one batch on one log (used by tests/CI).
        limit:           Stop after this many total entries.
        days:            Override ``ct_backfill_days`` for window seeding.
        log_id:          Restrict to a single CT log UUID.
        on_batch:        Optional callback(log_url, batch_count, total_count).
        on_status:       Optional callback(status_string) for operator output.
        batch_size:      Optional batch size override.
    """
    worker = _worker_id()
    _logger.info("backfill (per-log) starting worker_id=%s", worker)
    total_processed = 0
    _batch = batch_size or settings.ct_default_batch_size
    _days: int = days if days is not None else settings.ct_backfill_days
    rate_limited_until: dict[_uuid.UUID, float] = {}
    rate_limit_hits: dict[_uuid.UUID, int] = {}
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)

    async with client:
        await _initialize_states(
            session_factory, settings, client, _days, log_id, on_status
        )

        async with session_factory() as session:
            async with session.begin():
                _registry_row = await register_worker(
                    session, worker_id=worker, worker_kind="backfill"
                )
        _registry_id = _registry_row.id

        try:
            while True:
                if is_disk_critical(
                    settings.ct_critical_free_disk_gb, settings.ct_disk_check_path
                ):
                    _logger.critical("disk critical — halting backfill worker")
                    raise SystemExit(1)
                if is_disk_low(
                    settings.ct_min_free_disk_gb, settings.ct_disk_check_path
                ):
                    _logger.warning(
                        "disk low — pausing backfill for %ds",
                        _SLEEP_DISK_LOW_SECONDS,
                    )
                    if on_status is not None:
                        on_status(f"Disk low — pausing {_SLEEP_DISK_LOW_SECONDS} s")
                    await asyncio.sleep(_SLEEP_DISK_LOW_SECONDS)
                    if once:
                        break
                    continue

                if limit is not None and total_processed >= limit:
                    return

                # Reap stale claims so other workers can take over.
                async with session_factory() as session:
                    async with session.begin():
                        await reap_stale_log_claims(
                            session,
                            stale_seconds=settings.ct_worker_stale_seconds,
                        )

                # Compute the set of logs in rate-limit cooldown right now.
                now_mono = time.monotonic()
                excluded = {
                    lid for lid, until in rate_limited_until.items() if now_mono < until
                }

                # Claim one log atomically.
                async with session_factory() as session:
                    async with session.begin():
                        state_row = await claim_any_eligible_log(
                            session,
                            worker_id=worker,
                            stale_seconds=settings.ct_worker_stale_seconds,
                            log_id_filter=log_id,
                            excluded_log_ids=excluded,
                        )

                if state_row is None:
                    async with session_factory() as session:
                        async with session.begin():
                            await heartbeat_worker(
                                session,
                                row_id=_registry_id,
                                status="idle",
                                counters=WorkerCounters(),
                            )
                    if on_status is not None:
                        on_status(
                            f"No eligible logs — sleeping {_SLEEP_NO_LOGS_SECONDS} s"
                        )
                    if once:
                        return
                    await asyncio.sleep(_SLEEP_NO_LOGS_SECONDS)
                    continue

                # Resolve URL and drive the log forward.
                log_url = await _resolve_log_url(
                    session_factory, state_row.log_source_id
                )
                await _drive_one_log(
                    state_row=state_row,
                    log_url=log_url,
                    session_factory=session_factory,
                    client=client,
                    settings=settings,
                    worker=worker,
                    registry_id=_registry_id,
                    base_batch=_batch,
                    on_batch=on_batch,
                    on_status=on_status,
                    rate_limit_hits=rate_limit_hits,
                    rate_limited_until=rate_limited_until,
                    total_processed_ref=[total_processed],
                    limit=limit,
                )
                # _drive_one_log mutates total_processed_ref[0]; read it back.
                # (Using a single-element list keeps the helper signature compact.)

                if once:
                    return
        finally:
            async with session_factory() as session:
                async with session.begin():
                    await mark_worker_stopped(session, row_id=_registry_id)


async def _drive_one_log(
    *,
    state_row: CtLogBackfillState,
    log_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    settings: Settings,
    worker: str,
    registry_id: _uuid.UUID,
    base_batch: int,
    on_batch: Callable[[str, int, int], None] | None,
    on_status: Callable[[str], None] | None,
    rate_limit_hits: dict[_uuid.UUID, int],
    rate_limited_until: dict[_uuid.UUID, float],
    total_processed_ref: list[int],
    limit: int | None,
) -> None:
    """Drive batches for one claimed log until window complete or claim ends.

    The claim is released or marked complete before this function returns.
    """
    log_source_id = state_row.log_source_id
    current = state_row
    while True:
        # Pre-batch heartbeat and disk safety + rate-limit check.
        async with session_factory() as session:
            async with session.begin():
                await heartbeat_worker(
                    session,
                    row_id=registry_id,
                    status="processing",
                    current_index=current.last_checkpoint_index,
                    counters=WorkerCounters(),
                )

        directive = await get_db_contention_directive(
            session_factory, settings, base_batch
        )
        effective_batch = resolve_effective_batch_size(base_batch, directive)
        db_sleep = await sleep_for_db_contention(directive, settings)
        if db_sleep > 0.0 and on_status is not None:
            on_status(f"DB contention — pacing {db_sleep:.2f} s")

        limit_remaining = (
            (limit - total_processed_ref[0]) if limit is not None else None
        )

        if on_status is not None:
            assert current.last_checkpoint_index is not None  # noqa: S101
            assert current.backfill_end_index is not None  # noqa: S101
            on_status(
                "Fetching ["
                f"{int(current.last_checkpoint_index):,}–"
                f"{int(current.backfill_end_index):,}]"
            )

        (
            count,
            was_rate_limited,
            observation,
            retry_after,
            new_checkpoint,
        ) = await _run_one_log_batch(
            current,
            log_url,
            session_factory,
            client,
            settings,
            effective_batch,
            limit_remaining,
            worker,
        )

        if was_rate_limited:
            hit_count = rate_limit_hits.get(log_source_id, 0) + 1
            rate_limit_hits[log_source_id] = hit_count
            if retry_after is not None:
                backoff = float(min(settings.ct_retry_after_max_seconds, retry_after))
            else:
                backoff = float(
                    min(
                        settings.ct_rate_limit_backoff_max_seconds,
                        settings.ct_rate_limit_backoff_seconds * (2 ** (hit_count - 1)),
                    )
                )
            rate_limited_until[log_source_id] = time.monotonic() + backoff
            if on_status is not None:
                on_status(f"Rate limited for log {log_source_id} — pausing {backoff} s")
            # Release claim so other workers / other logs can be picked up.
            async with session_factory() as session:
                async with session.begin():
                    await release_log_claim(session, log_source_id=log_source_id)
            return

        if observation.has_activity:
            await submit_db_contention_observation(
                session_factory, settings, observation, base_batch
            )

        if count > 0:
            rate_limit_hits.pop(log_source_id, None)
            rate_limited_until.pop(log_source_id, None)
            total_processed_ref[0] += count
            if on_batch is not None:
                on_batch(log_url, count, total_processed_ref[0])

        # Window complete?
        assert current.backfill_end_index is not None  # noqa: S101
        if new_checkpoint > int(current.backfill_end_index):
            async with session_factory() as session:
                async with session.begin():
                    await mark_log_complete(session, log_source_id=log_source_id)
            if on_status is not None:
                on_status(f"Backfill complete for log {log_source_id}")
            return

        # Refresh the in-memory state so the next iteration sees the new checkpoint.
        async with session_factory() as session:
            from sqlalchemy import select as _select

            stmt = _select(CtLogBackfillState).where(
                CtLogBackfillState.log_source_id == log_source_id
            )
            result = await session.execute(stmt)
            refreshed = result.scalar_one_or_none()
            if refreshed is None or refreshed.claimed_by != worker:
                # Lost the claim (e.g. reaped). Stop driving this log.
                return
            current = refreshed

        if limit is not None and total_processed_ref[0] >= limit:
            return
