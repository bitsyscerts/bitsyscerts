"""Implementation for the ``prune-for-storage-profile`` CLI command.

This is the operator-facing maintenance entry point introduced in
Sprint 4.  It dispatches all profile-appropriate retention pruning in
one safe, batched, recorded run.

Behaviour:
    * Default is **dry-run** — destructive deletes require ``execute=True``.
    * Reads active database-backed storage settings (``CtInstanceSettings``)
      and falls back to ``Settings`` (env) when no DB row is present.
    * ``retention_days == 0`` means *retain indefinitely* — that category
      is skipped.
    * Hostnames and the latest-cert summary fields are never deleted.
    * Every invocation (including dry-runs) writes one ``ct_maintenance_runs``
      row so the dashboard can show the latest status.

File size justification (Warning band):
    This module is the single orchestration point for retention.  It must
    keep the per-category count/delete logic co-located with the
    plan-builder, recorder, and Rich/JSON renderer because splitting them
    fractures the safety invariant that *every* path writes one — and
    only one — ``ct_maintenance_runs`` row.  This will be reduced when
    the per-category helpers move to a generic
    ``time_based_pruner.py`` once the certificate path stops needing its
    bespoke ``run_prune_expired_certs`` delegation.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from rich.console import Console
from sqlalchemy import func, select, text

from ctpool.config import Settings, get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.instance_settings import get_active_settings
from ctpool.maintenance_recorder import (
    finalize_maintenance_run,
    insert_maintenance_run,
)
from ctpool.models.entry_outcome import CtEntryOutcome
from ctpool.models.hostname import Hostname
from ctpool.models.ingestion_error import IngestionError
from ctpool.models.ingestion_metric import IngestionMetric
from ctpool.models.log_backfill_range import CtLogBackfillRange
from ctpool.models.maintenance_run import CtMaintenanceRun
from ctpool.models.observation import CtLogObservation
from ctpool.models.prune_run import CtPruneRun
from ctpool.prune_profile_plan import (
    PruneAggregate,
    PruneCategory,
    build_prune_plan,
    summarize_plan_as_json,
    summarize_plan_for_console,
)

_logger = logging.getLogger(__name__)

_RUN_TYPE = "prune_for_storage_profile"

# Stable Postgres advisory-lock key used to prevent overlapping
# profile-prune invocations.  Random 32-bit constant — value does not
# matter as long as it is unique within the database.
_ADVISORY_LOCK_KEY = 0x42495343  # 'BISC' in ASCII

# Dispatch table for categories that map directly to one model + timestamp
# column.  Entries here are handled generically by _process_simple_category.
# Certificates and completed_backfill_ranges require special handling.
_SIMPLE_CATEGORIES: dict[str, tuple[type, str]] = {
    "observations": (CtLogObservation, "observed_at"),
    "entry_outcomes": (CtEntryOutcome, "first_seen_at"),
    "ingestion_metrics": (IngestionMetric, "snapshot_at"),
    "ingestion_errors": (IngestionError, "occurred_at"),
    "maintenance_runs": (CtMaintenanceRun, "started_at"),
    "prune_runs": (CtPruneRun, "started_at"),
}

# Aggregate field that records deletion count for a simple category.
_SIMPLE_AGG_FIELD: dict[str, str] = {
    "observations": "deleted_observations",
    "entry_outcomes": "deleted_entry_outcomes",
    "ingestion_metrics": "deleted_ingestion_metrics",
}


class ConcurrentPruneError(RuntimeError):
    """Raised when another profile prune is already running."""


async def _read_prune_params(factory: Any, settings: Settings) -> dict[str, Any]:
    """Return effective prune parameters: DB row first, env vars as fallback.

    Reads ``CtInstanceSettings`` via an async session.  If no row exists
    (e.g. before first bootstrap) the Settings (env) values are used.
    """
    async with factory() as session:
        db_row = await get_active_settings(session)
    if db_row is not None:
        _logger.debug(
            "prune: using DB-backed settings (profile=%s)", db_row.storage_profile
        )
        return {
            "storage_profile": db_row.storage_profile,
            "cert_storage_mode": db_row.cert_storage_mode,
            "hostname_retention_mode": db_row.hostname_retention_mode,
            "cert_retention_days": db_row.cert_retention_days,
            "observation_retention_days": db_row.observation_retention_days,
            "entry_outcome_retention_days": db_row.entry_outcome_retention_days,
            "metrics_retention_days": db_row.metrics_retention_days,
        }
    _logger.debug("prune: no DB settings row; falling back to env vars")
    return {
        "storage_profile": settings.ct_storage_profile,
        "cert_storage_mode": settings.ct_cert_storage_mode,
        "hostname_retention_mode": settings.ct_hostname_retention_mode,
        "cert_retention_days": settings.ct_cert_retention_days,
        "observation_retention_days": settings.ct_observation_retention_days,
        "entry_outcome_retention_days": settings.ct_entry_outcome_retention_days,
        "metrics_retention_days": settings.ct_metrics_retention_days,
    }


async def run_prune_for_storage_profile(
    *,
    execute: bool = False,
    limit: int = 0,
    batch_size: int = 5_000,
    json_output: bool = False,
    console: Console,
) -> PruneAggregate:
    """Run the profile-aware prune pipeline.

    Args:
        execute:     If False (default), only count candidates.
        limit:       Maximum rows to delete per category (0 = unlimited).
        batch_size:  Per-transaction batch size for DELETE statements.
        json_output: Suppress Rich rendering and emit one JSON object.
        console:     Rich console for human-friendly output.

    Returns:
        The :class:`PruneAggregate` describing the run.
    """
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    params = await _read_prune_params(factory, settings)
    aggregate = build_prune_plan(
        storage_profile=params["storage_profile"],
        cert_storage_mode=params["cert_storage_mode"],
        hostname_retention_mode=params["hostname_retention_mode"],
        cert_retention_days=params["cert_retention_days"],
        observation_retention_days=params["observation_retention_days"],
        entry_outcome_retention_days=params["entry_outcome_retention_days"],
        metrics_retention_days=params["metrics_retention_days"],
        started_at=datetime.now(UTC),
        mode="execute" if execute else "dry_run",
    )
    started_monotonic = time.monotonic()

    lock_acquired = await _try_acquire_lock(factory)
    if not lock_acquired:
        await engine.dispose()
        msg = "Another profile prune is already running; refusing to run concurrently."
        _logger.warning(msg)
        aggregate.status = "failed"
        aggregate.error_message = msg
        _render(aggregate, console=console, json_output=json_output)
        raise ConcurrentPruneError(msg)

    run_id = await insert_maintenance_run(
        factory,
        run_type=_RUN_TYPE,
        mode=aggregate.mode,
        storage_profile=aggregate.storage_profile,
    )

    try:
        for category in aggregate.categories:
            if category.is_disabled:
                continue
            await _process_category(
                aggregate=aggregate,
                category=category,
                factory=factory,
                settings=settings,
                execute=execute,
                limit=limit,
                batch_size=batch_size,
            )
        aggregate.preserved_hostnames = await _count_hostnames(factory)
        aggregate.status = "complete"
    except Exception as exc:  # noqa: BLE001 — surface any error to the row
        aggregate.status = "failed"
        aggregate.error_message = str(exc)
        _logger.exception("prune-for-storage-profile failed")

    duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    await finalize_maintenance_run(
        factory,
        run_id,
        status=aggregate.status,
        deleted_certificates=aggregate.deleted_certificates,
        deleted_certificate_hostnames=aggregate.deleted_certificate_hostnames,
        deleted_observations=aggregate.deleted_observations,
        deleted_entry_outcomes=aggregate.deleted_entry_outcomes,
        deleted_ingestion_metrics=aggregate.deleted_ingestion_metrics,
        preserved_hostnames=aggregate.preserved_hostnames,
        duration_ms=duration_ms,
        error_message=aggregate.error_message,
        details=summarize_plan_as_json(aggregate),
    )

    await _release_lock(factory)
    await engine.dispose()
    _render(aggregate, console=console, json_output=json_output)
    return aggregate


async def _try_acquire_lock(factory: Any) -> bool:
    """Try to acquire the profile-prune advisory lock; return True on success.

    Uses session-level ``pg_try_advisory_lock`` so the lock survives across
    the many short transactions used by the orchestrator.  Returns False
    (without blocking) when another prune holds the lock.  Returns True on
    SQLite or any backend that does not implement advisory locks.
    """
    try:
        async with factory() as session:
            result = await session.execute(
                text("SELECT pg_try_advisory_lock(:key)").bindparams(
                    key=_ADVISORY_LOCK_KEY
                )
            )
            row = result.scalar()
            return bool(row) if row is not None else True
    except Exception:  # noqa: BLE001 — non-PG dialects, missing fn, etc.
        _logger.debug("Advisory lock unsupported on this dialect; continuing.")
        return True


async def _release_lock(factory: Any) -> None:
    """Release the profile-prune advisory lock; no-op when unsupported."""
    try:
        async with factory() as session:
            await session.execute(
                text("SELECT pg_advisory_unlock(:key)").bindparams(
                    key=_ADVISORY_LOCK_KEY
                )
            )
    except Exception:  # noqa: BLE001
        _logger.debug("Advisory unlock skipped (unsupported dialect or error).")


async def _process_category(
    *,
    aggregate: PruneAggregate,
    category: PruneCategory,
    factory: Any,
    settings: Settings,
    execute: bool,
    limit: int,
    batch_size: int,
) -> None:
    """Dispatch one retention category to the appropriate handler."""
    cutoff = datetime.now(UTC) - timedelta(days=category.retention_days)
    if category.name in _SIMPLE_CATEGORIES:
        await _process_simple_category(
            aggregate=aggregate,
            category=category,
            factory=factory,
            execute=execute,
            limit=limit,
            batch_size=batch_size,
            cutoff=cutoff,
        )
    elif category.name == "certificates":
        await _process_certificates(
            aggregate=aggregate,
            category=category,
            settings=settings,
            execute=execute,
            limit=limit,
            batch_size=batch_size,
            cutoff=cutoff,
        )
    elif category.name == "completed_backfill_ranges":
        await _process_backfill_ranges(
            category=category,
            factory=factory,
            execute=execute,
            limit=limit,
            batch_size=batch_size,
            cutoff=cutoff,
        )


async def _process_simple_category(
    *,
    aggregate: PruneAggregate,
    category: PruneCategory,
    factory: Any,
    execute: bool,
    limit: int,
    batch_size: int,
    cutoff: datetime,
) -> None:
    """Count and optionally delete rows for a dispatch-table category."""
    model, col = _SIMPLE_CATEGORIES[category.name]
    category.candidate_count = await _count_before(factory, model, col, cutoff)
    if not execute:
        return
    deleted = await _delete_before(
        factory, model, col, cutoff, limit=limit, batch_size=batch_size
    )
    category.deleted_count = deleted
    agg_field = _SIMPLE_AGG_FIELD.get(category.name)
    if agg_field:
        setattr(aggregate, agg_field, deleted)


async def _process_backfill_ranges(
    *,
    category: PruneCategory,
    factory: Any,
    execute: bool,
    limit: int,
    batch_size: int,
    cutoff: datetime,
) -> None:
    """Count and optionally delete completed backfill range rows."""
    category.candidate_count = await _count_completed_backfill_ranges(factory, cutoff)
    if execute:
        category.deleted_count = await _delete_completed_backfill_ranges(
            factory, cutoff, limit=limit, batch_size=batch_size
        )


async def _process_certificates(
    *,
    aggregate: PruneAggregate,
    category: PruneCategory,
    settings: Settings,
    execute: bool,
    limit: int,
    batch_size: int,
    cutoff: datetime,
) -> None:
    """Delegate certificate pruning to the existing safe path.

    Uses exact deletion counts returned by ``run_prune_expired_certs``;
    we never infer counts from a pre/post candidate differential.
    """
    pre_count = await _certificate_candidate_count(settings, cutoff)
    category.candidate_count = pre_count
    if not execute:
        return

    from ctpool._cli_prune_impl import run_prune_expired_certs

    quiet = Console(quiet=True)
    summary = await run_prune_expired_certs(
        execute=True,
        retention_days=category.retention_days,
        batch_size=batch_size,
        limit=limit,
        console=quiet,
    )
    category.deleted_count = int(summary.deleted_certificates)
    aggregate.deleted_certificates = int(summary.deleted_certificates)
    aggregate.deleted_certificate_hostnames = int(summary.deleted_certificate_hostnames)


async def _certificate_candidate_count(settings: Settings, cutoff: datetime) -> int:
    """Return the count of expired non-latest certificates ready to prune."""
    from ctpool.prune_queries import count_prunable_certificates

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        count = await count_prunable_certificates(session, cutoff)
    await engine.dispose()
    return int(count)


async def _latest_link_deletes(settings: Settings) -> int:
    """Deprecated since Sprint 4B.

    The orchestrator now reads exact certificate-hostname deletion counts
    from ``PruneSummary``; this helper is retained for backwards
    compatibility with any callers that still inspect the latest
    ``ct_prune_runs`` row directly.
    """
    from ctpool.models.prune_run import CtPruneRun

    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        row = (
            await session.execute(
                select(CtPruneRun.deleted_certificate_hostnames)
                .order_by(CtPruneRun.started_at.desc())
                .limit(1)
            )
        ).scalar()
    await engine.dispose()
    return int(row or 0)


async def _count_completed_backfill_ranges(factory: Any, cutoff: datetime) -> int:
    """Count completed backfill ranges older than *cutoff*."""
    async with factory() as session:
        result = await session.execute(
            select(func.count())
            .where(
                CtLogBackfillRange.status == "complete",
                CtLogBackfillRange.completed_at < cutoff,
            )
            .select_from(CtLogBackfillRange)
        )
    return int(result.scalar_one())


async def _delete_completed_backfill_ranges(
    factory: Any, cutoff: datetime, *, limit: int, batch_size: int
) -> int:
    """Batched DELETE of completed backfill ranges older than *cutoff*."""
    from sqlalchemy import delete as sa_delete

    total = 0
    while True:
        if limit and total >= limit:
            break
        effective_batch = min(batch_size, limit - total) if limit else batch_size
        async with factory() as session:
            async with session.begin():
                subq = (
                    select(CtLogBackfillRange.id)
                    .where(
                        CtLogBackfillRange.status == "complete",
                        CtLogBackfillRange.completed_at < cutoff,
                    )
                    .limit(effective_batch)
                    .scalar_subquery()
                )
                result = await session.execute(
                    sa_delete(CtLogBackfillRange).where(CtLogBackfillRange.id.in_(subq))
                )
                deleted = result.rowcount or 0
        if deleted == 0:
            break
        total += deleted
    return total


async def _count_before(
    factory: Any, model: Any, column_name: str, cutoff: datetime
) -> int:
    """Count rows whose timestamp column is older than *cutoff*."""
    column = getattr(model, column_name)
    async with factory() as session:
        result = await session.execute(
            select(func.count()).where(column < cutoff).select_from(model)
        )
    return int(result.scalar_one())


async def _delete_before(
    factory: Any,
    model: Any,
    column_name: str,
    cutoff: datetime,
    *,
    limit: int,
    batch_size: int,
) -> int:
    """Batched DELETE for rows whose timestamp column is older than *cutoff*."""
    from sqlalchemy import delete

    column = getattr(model, column_name)
    total = 0
    while True:
        if limit and total >= limit:
            break
        effective_batch = min(batch_size, limit - total) if limit else batch_size
        async with factory() as session:
            async with session.begin():
                subq = (
                    select(model.id)
                    .where(column < cutoff)
                    .limit(effective_batch)
                    .scalar_subquery()
                )
                result = await session.execute(delete(model).where(model.id.in_(subq)))
                deleted = result.rowcount or 0
        if deleted == 0:
            break
        total += deleted
    return total


async def _count_hostnames(factory: Any) -> int:
    """Return the total preserved hostname count for reporting."""
    async with factory() as session:
        result = await session.execute(select(func.count(Hostname.id)))
    return int(result.scalar_one())


def _render(aggregate: PruneAggregate, *, console: Console, json_output: bool) -> None:
    """Print the run summary (Rich or JSON)."""
    if json_output:
        import json as _json

        console.print(_json.dumps(aggregate.as_serialisable_dict(), default=str))
        return
    for line in summarize_plan_for_console(aggregate):
        console.print(line)
    if aggregate.status == "failed":
        console.print(f"[red]Maintenance run failed: {aggregate.error_message}[/red]")
    elif aggregate.mode == "execute":
        console.print("[bold green]prune-for-storage-profile complete.[/bold green]")
