"""Maintenance loop: periodic profile-aware pruning.

Responsibilities:
    - ``run_maintenance_once`` — runs one maintenance cycle.
    - ``run_maintenance_loop`` — runs cycles on the configured interval.

By default the cycle is intentionally lightweight:

    1. ``prune-for-storage-profile`` (always).

Deep ``check-audit-gaps`` scans are **opt-in** via
``BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=true`` and run on their own interval
``BITSYSCERTS_AUDIT_INTERVAL_SECONDS``.  A failure in scheduled audit must
not block pruning.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from os import getpid
from typing import Any

from rich.console import Console

from ctpool.config import Settings
from ctpool.db import create_engine, create_session_factory
from ctpool.worker_registry import (
    WorkerCounters,
    heartbeat_worker,
    mark_worker_stopped,
    register_worker,
)

_logger = logging.getLogger(__name__)

_DEV_NULL_CONSOLE = Console(quiet=True)

# Module-level state for the scheduled-audit interval gate.  The loop holds a
# single Settings + cycle time so this is correct for the in-process loop
# without needing a database column.
_LAST_SCHEDULED_AUDIT_AT: float = 0.0


def _worker_id() -> str:
    """Return a stable identity string for the maintenance singleton worker."""
    return f"{socket.gethostname()}:{getpid()}"


async def run_maintenance_once(settings: Settings) -> None:
    """Execute one full maintenance cycle.

    Always runs the profile-aware prune.  Runs scheduled audit only when
    the operator has explicitly enabled it AND the configured interval has
    elapsed since the last scheduled audit.  Audit failures are logged but
    do not block pruning.

    Args:
        settings: Active application settings.
    """
    console = _DEV_NULL_CONSOLE

    await _step("prune-for-storage-profile", _prune_for_profile, settings, console)
    if _scheduled_audit_due(settings):
        await _step("scheduled-audit-gaps", _check_audit_gaps, settings, console)
        _record_scheduled_audit_ran()


async def run_maintenance_loop(settings: Settings) -> None:
    """Run maintenance cycles at the configured interval.

    Runs indefinitely.  Errors are logged and the loop continues.

    Args:
        settings: Active application settings.
    """
    interval = settings.ct_maintenance_interval_seconds
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        async with session.begin():
            registry_row = await register_worker(
                session,
                worker_id=_worker_id(),
                worker_kind="maintenance",
            )
    registry_id = registry_row.id

    _logger.info("Maintenance loop starting (interval=%d s)", interval)
    try:
        while True:
            try:
                async with factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=registry_id,
                            status="processing",
                            direction="maintenance",
                            counters=WorkerCounters(),
                        )
                await run_maintenance_once(settings)
                async with factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=registry_id,
                            status="idle",
                            direction="maintenance",
                            counters=WorkerCounters(),
                        )
            except Exception as exc:
                async with factory() as session:
                    async with session.begin():
                        await heartbeat_worker(
                            session,
                            row_id=registry_id,
                            status="error",
                            direction="maintenance",
                            counters=WorkerCounters(
                                last_error_type=exc.__class__.__name__,
                                last_error_message=str(exc),
                            ),
                        )
                _logger.exception("Maintenance cycle failed; will retry after interval")
            await asyncio.sleep(interval)
    finally:
        async with factory() as session:
            async with session.begin():
                await mark_worker_stopped(session, row_id=registry_id)
        await engine.dispose()


def _scheduled_audit_due(settings: Settings) -> bool:
    """Return True when scheduled audit is opt-in enabled AND its interval is up.

    Always False when ``BITSYSCERTS_ENABLE_SCHEDULED_AUDIT`` is False.
    """
    if not getattr(settings, "bitsyscerts_enable_scheduled_audit", False):
        return False
    interval = getattr(settings, "bitsyscerts_audit_interval_seconds", 21600)
    if interval <= 0:
        return False
    if _LAST_SCHEDULED_AUDIT_AT <= 0.0:
        return True
    return (time.monotonic() - _LAST_SCHEDULED_AUDIT_AT) >= interval


def _record_scheduled_audit_ran() -> None:
    """Stamp the last-audit timestamp so the interval gate works next cycle."""
    global _LAST_SCHEDULED_AUDIT_AT
    _LAST_SCHEDULED_AUDIT_AT = time.monotonic()


async def _step(name: str, coro_fn: Any, settings: Settings, console: Console) -> None:
    """Run a single maintenance step, logging errors without raising."""
    try:
        t0 = time.monotonic()
        await coro_fn(settings, console)
        elapsed = time.monotonic() - t0
        _logger.debug("Maintenance step %s completed in %.2f s", name, elapsed)
    except Exception:
        _logger.exception("Maintenance step %s failed", name)


async def _prune_for_profile(_settings: Settings, console: Console) -> None:
    """Run the unified storage-profile retention enforcer."""
    from ctpool._cli_prune_storage_profile_impl import (
        run_prune_for_storage_profile,
    )

    await run_prune_for_storage_profile(execute=True, console=console)


async def _prune_metrics(settings: Settings, console: Console) -> None:
    """Prune old ingestion_metrics rows."""
    from ctpool._cli_reap_impl import run_prune_metrics

    await run_prune_metrics(
        dry_run=False,
        retention_days=settings.ct_metrics_retention_days,
        console=console,
    )


async def _prune_observations(settings: Settings, console: Console) -> None:
    """Prune old ct_log_observations rows."""
    from ctpool._cli_prune_observations_impl import run_prune_observations

    await run_prune_observations(
        dry_run=False,
        retention_days=settings.ct_observation_retention_days,
        console=console,
    )


async def _prune_entry_outcomes(settings: Settings, console: Console) -> None:
    """Prune old ct_entry_outcomes rows."""
    from ctpool._cli_prune_entry_outcomes_impl import run_prune_entry_outcomes

    await run_prune_entry_outcomes(
        dry_run=False,
        retention_days=settings.ct_entry_outcome_retention_days,
        console=console,
    )


async def _check_audit_gaps(_settings: Settings, console: Console) -> None:
    """Run an audit-gap check if the ctpool audit module is available."""
    try:
        from ctpool._cli_check_audit_impl import run_check_audit_gaps

        await run_check_audit_gaps(dry_run=False, console=console)
    except ImportError:
        _logger.debug("Audit gap check skipped: module not available")
