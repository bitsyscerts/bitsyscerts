"""Maintenance loop: periodic pruning and audit-gap checks.

Responsibilities:
    - ``run_maintenance_once`` — runs one maintenance cycle.
    - ``run_maintenance_loop`` — runs cycles on the configured interval.

A maintenance cycle runs:
    1. Prune ingestion_metrics (``ct_metrics_prune_interval_seconds`` gate).
    2. Prune observations (``ct_prune_interval_seconds`` gate).
    3. Prune entry outcomes (``ct_prune_interval_seconds`` gate).
    4. Audit-gap check (``ct_audit_interval_seconds`` gate).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from rich.console import Console

from ctpool.config import Settings

_logger = logging.getLogger(__name__)

_DEV_NULL_CONSOLE = Console(quiet=True)


async def run_maintenance_once(settings: Settings) -> None:
    """Execute one full maintenance cycle.

    Runs metrics pruning, observation pruning, entry-outcome pruning, and
    optionally an audit-gap check.  Each step is run independently — a failure
    in one step is logged but does not block subsequent steps.

    Args:
        settings: Active application settings.
    """
    console = _DEV_NULL_CONSOLE

    await _step("prune-metrics", _prune_metrics, settings, console)
    await _step("prune-observations", _prune_observations, settings, console)
    await _step("prune-entry-outcomes", _prune_entry_outcomes, settings, console)
    await _step("audit-gaps", _check_audit_gaps, settings, console)


async def run_maintenance_loop(settings: Settings) -> None:
    """Run maintenance cycles at the configured interval.

    Runs indefinitely.  Errors are logged and the loop continues.

    Args:
        settings: Active application settings.
    """
    interval = settings.ct_maintenance_interval_seconds
    _logger.info("Maintenance loop starting (interval=%d s)", interval)
    while True:
        try:
            await run_maintenance_once(settings)
        except Exception:
            _logger.exception("Maintenance cycle failed; will retry after interval")
        await asyncio.sleep(interval)


async def _step(name: str, coro_fn: Any, settings: Settings, console: Console) -> None:
    """Run a single maintenance step, logging errors without raising."""
    try:
        t0 = time.monotonic()
        await coro_fn(settings, console)
        elapsed = time.monotonic() - t0
        _logger.debug("Maintenance step %s completed in %.2f s", name, elapsed)
    except Exception:
        _logger.exception("Maintenance step %s failed", name)


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

        await run_check_audit_gaps(console=console)
    except ImportError:
        _logger.debug("Audit gap check skipped: module not available")
