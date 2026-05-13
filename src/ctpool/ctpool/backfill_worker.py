"""CT log backfill worker entry point.

The historical implementation here drove dispatch through
``ct_log_backfill_ranges``. As of Sprint 1B the default normal-runtime
path is **per-log dispatch** through ``ct_log_backfill_state`` — see
:mod:`ctpool.backfill_per_log`. The legacy range-based loop is preserved
in this module under :func:`run_backfill_legacy` for compatibility with
range repair, audit findings, and migration scenarios; it is selected
only when ``Settings.ct_backfill_dispatch_mode == 'legacy-ranges'``.

Exports:
    run_backfill        — Dispatcher: routes to per-log or legacy by config.
    run_backfill_legacy — Legacy range-based loop (kept for compatibility).
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
import uuid as _uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from os import getpid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.audit_constants import RANGE_KIND_REPAIR
from ctpool.audit_repair import resolve_repair_finding
from ctpool.backfill_seeder import seed_ranges_for_log
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
from ctpool.dispatcher import (
    claim_backfill_range,
    get_eligible_backfill_logs,
    mark_range_complete,
    mark_range_failed,
    mark_range_pending,
    reap_stale_backfill_claims,
    update_range_heartbeat,
)
from ctpool.entry_persistence import persist_entry_with_retry, persist_failure_outcome
from ctpool.exceptions import (
    FetchError,
    ParseError,
    RateLimitError,
    UnsupportedEntryTypeError,
)
from ctpool.fetcher import fetch_entries
from ctpool.metrics import LogMetricsAccumulator
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.log_source import CtLogSource
from ctpool.normalizer import build_normalized_entry
from ctpool.outcome_constants import (
    OUTCOME_PARSE_ERROR,
    OUTCOME_UNSUPPORTED_ENTRY_TYPE,
    OUTCOME_WRITE_ERROR,
)
from ctpool.parser import parse_leaf_entry
from ctpool.storage_modes import CertStorageMode, flags_for_mode
from ctpool.worker_activity_details import build_worker_counters
from ctpool.worker_registry import (
    WorkerCounters,
    heartbeat_worker,
    mark_worker_stopped,
    register_worker,
)

_logger = logging.getLogger(__name__)

_SLEEP_NO_RANGES_SECONDS = 30
_SLEEP_DISK_LOW_SECONDS = 60


def _worker_id() -> str:
    """Return a stable identity string: ``hostname:PID``."""
    return f"{socket.gethostname()}:{getpid()}"


async def _resolve_log_url(session: AsyncSession, claimed: CtLogBackfillRange) -> str:
    """Return the URL for the CT log that owns *claimed*.

    Raises:
        FetchError: If the parent CtLogSource row is not found.
    """
    log = await session.get(CtLogSource, claimed.log_source_id)
    if log is None:
        raise FetchError(
            f"CtLogSource {claimed.log_source_id} not found for range {claimed.id}"
        )
    return log.url


async def _process_range_batch(
    claimed: CtLogBackfillRange,
    log_url: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    batch_size: int,
    metrics: LogMetricsAccumulator,
    limit_remaining: int | None,
    settings: Settings,
) -> tuple[int, DbContentionObservation]:
    """Fetch and write one batch of entries within *claimed*.

    Returns the number of entries successfully written plus one retry sample.
    """
    start = claimed.next_index
    batch = batch_size
    if limit_remaining is not None:
        batch = min(batch, limit_remaining)
    end = min(start + batch - 1, claimed.end_index)

    response = await fetch_entries(log_url, start, end, client)
    cert_flags = flags_for_mode(CertStorageMode(settings.ct_cert_storage_mode))
    count = 0
    parsed_count = 0
    retry_accumulator = DbRetryPressureAccumulator()
    for i, raw_entry in enumerate(response.entries):
        entry_index = start + i
        try:
            parsed = parse_leaf_entry(raw_entry.leaf_input)
            normalized = build_normalized_entry(
                parsed, claimed.log_source_id, entry_index
            )
            parsed_count += 1

            def _on_retry(
                attempt: int,
                exc: BaseException,
                delay: float,
                *,
                idx: int = entry_index,
            ) -> None:
                _logger.warning(
                    "deadlock retry backfill range=%s index=%d attempt=%d "
                    "delay=%.3fs: %s",
                    claimed.id,
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
                flags=cert_flags,
            )
            count += 1
            metrics.record_entry_write_metrics(write_metrics)
        except UnsupportedEntryTypeError as exc:
            _logger.warning(
                "unsupported entry type backfill range=%s index=%d: %s",
                claimed.id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                claimed.log_source_id,
                entry_index,
                OUTCOME_UNSUPPORTED_ENTRY_TYPE,
                exc,
            )
        except ParseError as exc:
            _logger.warning(
                "parse error backfill range=%s index=%d: %s",
                claimed.id,
                entry_index,
                exc,
            )
            metrics.record_parse_error()
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                claimed.log_source_id,
                entry_index,
                OUTCOME_PARSE_ERROR,
                exc,
            )
        except Exception as exc:
            _logger.warning(
                "unexpected cert error backfill range=%s index=%d type=%s detail=%r",
                claimed.id,
                entry_index,
                exc.__class__.__name__,
                exc,
            )
            metrics.record_terminal_entry_errors(1)
            await persist_failure_outcome(
                session,
                claimed.log_source_id,
                entry_index,
                OUTCOME_WRITE_ERROR,
                exc,
            )

    metrics.record_entries_fetched(len(response.entries))
    metrics.record_entries_parsed(parsed_count)
    observation = retry_accumulator.drain()
    metrics.record_retryable_errors(observation.retryable_errors)
    return count, observation


async def _run_one_range(
    claimed: CtLogBackfillRange,
    session_factory: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    settings: Settings,
    batch_size: int,
    limit_remaining: int | None,
) -> tuple[int, str, bool, DbContentionObservation, int | None, WorkerCounters]:
    """Process *claimed* range; mark complete or failed.

    Returns:
        ``(entries_written, log_url, was_rate_limited, contention,
        retry_after_seconds, worker_counters)``.
    """
    metrics = LogMetricsAccumulator()
    try:
        async with session_factory() as session:
            async with session.begin():
                log_url = await _resolve_log_url(session, claimed)
            async with session.begin():
                await update_range_heartbeat(session, claimed.id)
            count, observation = await _process_range_batch(
                claimed,
                log_url,
                session,
                client,
                batch_size,
                metrics,
                limit_remaining,
                settings,
            )
            worker_counters = build_worker_counters(
                metrics,
                checkpoint_index=claimed.end_index + 1,
            )
            if metrics.has_activity():
                async with session.begin():
                    await metrics.persist_snapshot(session, claimed.log_source_id)

        async with session_factory() as session:
            async with session.begin():
                await mark_range_complete(session, claimed.id)
                if (
                    claimed.range_kind == RANGE_KIND_REPAIR
                    and claimed.repair_for_finding_id is not None
                ):
                    await resolve_repair_finding(session, claimed.repair_for_finding_id)

        return count, log_url, False, observation, None, worker_counters
    except RateLimitError as exc:
        _logger.warning("rate limited backfill range=%s: %s", claimed.id, exc)
        metrics.record_retryable_errors(1)
        worker_counters = build_worker_counters(
            metrics,
            last_error_type=exc.__class__.__name__,
            last_error_message=str(exc),
            checkpoint_index=claimed.next_index,
        )
        if metrics.has_activity():
            async with session_factory() as session:
                async with session.begin():
                    await metrics.persist_snapshot(session, claimed.log_source_id)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_pending(session, claimed.id)
        return (
            0,
            "",
            True,
            DbContentionObservation(0, 0),
            exc.retry_after_seconds,
            worker_counters,
        )
    except FetchError as exc:
        _logger.error("fetch error backfill range=%s: %s", claimed.id, exc)
        metrics.record_retryable_errors(1)
        worker_counters = build_worker_counters(
            metrics,
            last_error_type=exc.__class__.__name__,
            last_error_message=str(exc),
            checkpoint_index=claimed.next_index,
        )
        if metrics.has_activity():
            async with session_factory() as session:
                async with session.begin():
                    await metrics.persist_snapshot(session, claimed.log_source_id)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_failed(session, claimed.id, str(exc))
        return 0, "", False, DbContentionObservation(0, 0), None, worker_counters
    except Exception as exc:
        _logger.error(
            "unexpected error backfill range=%s type=%s: %s",
            claimed.id,
            exc.__class__.__name__,
            exc,
        )
        worker_counters = build_worker_counters(
            metrics,
            last_error_type=exc.__class__.__name__,
            last_error_message=str(exc),
            checkpoint_index=claimed.next_index,
        )
        if metrics.has_activity():
            async with session_factory() as session:
                async with session.begin():
                    await metrics.persist_snapshot(session, claimed.log_source_id)
        async with session_factory() as session:
            async with session.begin():
                await mark_range_failed(session, claimed.id, str(exc))
        return 0, "", False, DbContentionObservation(0, 0), None, worker_counters


async def run_backfill(
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
    dispatch_mode: str | None = None,
    worker_id: str | None = None,
) -> None:
    """Backfill worker entry point — dispatches to per-log or legacy mode.

    The selected mode comes from ``settings.ct_backfill_dispatch_mode``
    (default ``per-log``) unless ``dispatch_mode`` overrides it explicitly.

    The ``per-log`` path is the normal runtime model and uses
    ``ct_log_backfill_state``. The ``legacy-ranges`` path uses the historical
    ``ct_log_backfill_ranges`` table and is retained for repair/audit/legacy
    workflows.
    """
    from ctpool.backfill_per_log import run_backfill_per_log

    mode = dispatch_mode or settings.ct_backfill_dispatch_mode
    if mode == "per-log":
        await run_backfill_per_log(
            session_factory,
            settings,
            once=once,
            limit=limit,
            days=days,
            log_id=log_id,
            on_batch=on_batch,
            on_status=on_status,
            batch_size=batch_size,
            worker_id=worker_id,
        )
        return
    if mode == "legacy-ranges":
        await run_backfill_legacy(
            session_factory,
            settings,
            once=once,
            limit=limit,
            days=days,
            log_id=log_id,
            on_batch=on_batch,
            on_status=on_status,
            batch_size=batch_size,
        )
        return
    raise ValueError(
        f"unknown ct_backfill_dispatch_mode={mode!r}; "
        "expected 'per-log' or 'legacy-ranges'"
    )


async def run_backfill_legacy(
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
    """Legacy range-based backfill loop (compatibility / repair only).

    Claims pending ranges from the database and processes them sequentially.
    Seeds new ranges from the current STH on first run. Pauses when disk is
    low; halts when disk is critical.

    Args:
        session_factory: Factory for creating database sessions.
        settings:        Validated application settings.
        once:            Exit after processing one range.
        limit:           Stop after this many total entries.
        days:            Override ct_backfill_days for range seeding.
        log_id:          Restrict to a single CT log UUID.
        on_batch:        Optional callback(log_url, batch_count, total_count)
                         called after each non-empty range. Use for progress
                         reporting; omit for silent/daemon operation.
    """
    worker = _worker_id()
    _logger.info("backfill worker starting worker_id=%s", worker)
    total_processed = 0
    _batch = batch_size or settings.ct_default_batch_size
    _days: int = days if days is not None else settings.ct_backfill_days
    client = httpx.AsyncClient(timeout=settings.ct_http_timeout_seconds)
    rate_limited_until: dict[_uuid.UUID, float] = {}
    rate_limit_hits: dict[_uuid.UUID, int] = {}

    async with client:
        async with session_factory() as session:
            logs = await get_eligible_backfill_logs(session)
        if log_id is not None:
            logs = [lg for lg in logs if lg.id == log_id]
        for log in logs:
            await seed_ranges_for_log(
                log, session_factory, settings, client, _days, on_status
            )

        async with session_factory() as session:
            async with session.begin():
                _registry_row = await register_worker(
                    session,
                    worker_id=worker,
                    worker_kind="backfill",
                )
        _registry_id = _registry_row.id

        try:
            while True:
                async with session_factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=_registry_id,
                            status="idle",
                            current_index=None,
                            batch_start_index=None,
                            batch_end_index=None,
                            counters=WorkerCounters(),
                        )

                if is_disk_critical(
                    settings.ct_critical_free_disk_gb, settings.ct_disk_check_path
                ):
                    _logger.critical("disk critical — halting backfill worker")
                    # Exit non-zero so Docker applies restart backoff instead of
                    # immediately relaunching and looping on the same condition.
                    raise SystemExit(1)

                check_path = settings.ct_disk_check_path
                if is_disk_low(settings.ct_min_free_disk_gb, check_path):
                    _logger.warning(
                        "disk low — pausing backfill for %ds", _SLEEP_DISK_LOW_SECONDS
                    )
                    if on_status is not None:
                        on_status(f"Disk low — pausing {_SLEEP_DISK_LOW_SECONDS} s")
                    await asyncio.sleep(_SLEEP_DISK_LOW_SECONDS)
                    if once:
                        break
                    continue

                if limit is not None and total_processed >= limit:
                    return

                limit_remaining = (
                    (limit - total_processed) if limit is not None else None
                )
                now = time.monotonic()
                excluded_log_ids = {
                    lid for lid, until in rate_limited_until.items() if now < until
                }

                async with session_factory() as session:
                    async with session.begin():
                        reaped = await reap_stale_backfill_claims(
                            session,
                            settings.ct_backfill_claim_timeout_seconds,
                        )
                if reaped:
                    _logger.info("backfill reaper: reset %d stale claims", len(reaped))
                    for r in reaped:
                        _logger.debug(
                            "backfill reaper: range=%s log=%s next_index=%d",
                            r.id,
                            r.log_source_id,
                            r.next_index,
                        )

                directive = await get_db_contention_directive(
                    session_factory,
                    settings,
                    _batch,
                )
                effective_batch = resolve_effective_batch_size(_batch, directive)
                db_sleep = await sleep_for_db_contention(directive, settings)
                if db_sleep > 0.0 and on_status is not None:
                    on_status(f"DB contention — pacing {db_sleep:.2f} s")

                async with session_factory() as session:
                    async with session.begin():
                        claimed = await claim_backfill_range(
                            session,
                            log_id,
                            worker,
                            excluded_log_source_ids=excluded_log_ids,
                        )

                if claimed is None:
                    _logger.debug(
                        "backfill: no pending ranges — sleeping %ds",
                        _SLEEP_NO_RANGES_SECONDS,
                    )
                    if on_status is not None:
                        on_status(
                            f"No pending ranges — sleeping {_SLEEP_NO_RANGES_SECONDS} s"
                        )
                    if once:
                        return
                    await asyncio.sleep(_SLEEP_NO_RANGES_SECONDS)
                    continue

                if on_status is not None:
                    on_status(
                        f"Fetching [{claimed.start_index:,}–{claimed.end_index:,}]"
                        f" ({claimed.end_index - claimed.start_index + 1:,} entries)…"
                    )
                async with session_factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=_registry_id,
                            status="processing",
                            log_source_id=claimed.log_source_id,
                            direction="backfill",
                            current_index=claimed.next_index,
                            last_successful_index=claimed.next_index,
                            batch_start_index=claimed.next_index,
                            batch_end_index=claimed.end_index,
                            counters=WorkerCounters(),
                        )
                (
                    batch_count,
                    log_url,
                    was_rate_limited,
                    observation,
                    retry_after,
                    worker_counters,
                ) = await _run_one_range(
                    claimed,
                    session_factory,
                    client,
                    settings,
                    effective_batch,
                    limit_remaining,
                )
                status = "processing" if batch_count > 0 else "idle"
                if was_rate_limited:
                    hit_count = rate_limit_hits.get(claimed.log_source_id, 0) + 1
                    rate_limit_hits[claimed.log_source_id] = hit_count
                    if retry_after is not None:
                        backoff_seconds: float = min(
                            settings.ct_retry_after_max_seconds, retry_after
                        )
                    else:
                        backoff_seconds = min(
                            settings.ct_rate_limit_backoff_max_seconds,
                            settings.ct_rate_limit_backoff_seconds
                            * (2 ** (hit_count - 1)),
                        )
                    until = now + float(backoff_seconds)
                    rate_limited_until[claimed.log_source_id] = until
                    retry_deadline = datetime.now(UTC) + timedelta(
                        seconds=float(backoff_seconds)
                    )
                    worker_counters.extra["retry_count"] = hit_count
                    worker_counters.extra["next_retry_at"] = retry_deadline.isoformat()
                    worker_counters.extra["rate_limited_until"] = (
                        retry_deadline.isoformat()
                    )
                    status = "retrying"
                    if on_status is not None:
                        on_status(
                            "Rate limited for log "
                            f"{claimed.log_source_id} — pausing {backoff_seconds} s"
                        )
                elif worker_counters.last_error_type is not None:
                    status = "error"

                current_index = (
                    claimed.next_index if batch_count == 0 else claimed.end_index + 1
                )
                async with session_factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=_registry_id,
                            status=status,
                            log_source_id=claimed.log_source_id,
                            direction="backfill",
                            current_index=current_index,
                            last_successful_index=current_index,
                            batch_start_index=claimed.next_index,
                            batch_end_index=claimed.end_index,
                            counters=worker_counters,
                        )

                if was_rate_limited:
                    if once:
                        return
                    continue

                if observation.has_activity:
                    await submit_db_contention_observation(
                        session_factory,
                        settings,
                        observation,
                        _batch,
                    )

                if batch_count == 0 and on_status is not None:
                    on_status("  └ fetch error — range marked failed")

                if batch_count > 0:
                    rate_limit_hits.pop(claimed.log_source_id, None)
                    rate_limited_until.pop(claimed.log_source_id, None)

                total_processed += batch_count
                if batch_count > 0 and on_batch is not None:
                    on_batch(log_url, batch_count, total_processed)

                if once:
                    return
        finally:
            async with session_factory() as session:
                async with session.begin():
                    await mark_worker_stopped(session, row_id=_registry_id)
