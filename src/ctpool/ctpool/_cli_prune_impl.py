"""Implementation for the prune-expired-certs CLI command.

Exports:
    run_prune_expired_certs — Execute or dry-run the prune operation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from rich.console import Console
from sqlalchemy import update

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.prune_run import CtPruneRun
from ctpool.prune_queries import (
    count_blocked_latest,
    count_blocked_missing_summary,
    count_prunable_certificates,
    find_prunable_certificate_ids,
)
from ctpool.prune_reporter import PruneReporter, PruneSummary
from ctpool.prune_safety import delete_certificates_batch

_logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE: int = 500
_DEFAULT_LIMIT: int = 0  # 0 = no limit


async def run_prune_expired_certs(
    *,
    execute: bool = False,
    retention_days: int | None = None,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    limit: int = _DEFAULT_LIMIT,
    console: Console,
) -> None:
    """Prune expired certificate rows that are not the latest cert for any hostname.

    Args:
        execute:        If False (default), performs a dry-run only.
        retention_days: Override config ct_expired_cert_retention_days.
        batch_size:     Certificates to delete per transaction.
        limit:          Max certs to delete total (0 = unlimited).
        console:        Rich console for output.
    """
    settings = get_settings()
    days = (
        retention_days
        if retention_days is not None
        else settings.ct_expired_cert_retention_days
    )
    mode = "execute" if execute else "dry_run"
    cutoff = datetime.now(UTC) - timedelta(days=days)

    summary = PruneSummary(mode=mode, retention_days=days, cutoff=cutoff)
    reporter = PruneReporter(console)
    reporter.announce(summary)

    engine = create_engine(settings)
    factory = create_session_factory(engine)

    # --- Gather stats ---
    async with factory() as session:
        summary.candidate_certificates = await count_prunable_certificates(
            session, cutoff
        )
        summary.blocked_latest_certificates = await count_blocked_latest(
            session, cutoff
        )
        summary.blocked_missing_summary = await count_blocked_missing_summary(session)

    console.print(
        f"  candidates: [cyan]{summary.candidate_certificates:,}[/cyan]  "
        f"blocked-latest: [yellow]{summary.blocked_latest_certificates:,}[/yellow]  "
        f"blocked-no-summary: [yellow]{summary.blocked_missing_summary:,}[/yellow]"
    )

    if not execute:
        summary.status = "dry_run"
        reporter.print_summary(summary)
        return

    # --- Create a prune_run audit row ---
    async with factory() as session:
        async with session.begin():
            prune_run = CtPruneRun(
                id=uuid.uuid4(),
                mode=mode,
                cutoff=cutoff,
                retention_days=days,
                candidate_certificates=summary.candidate_certificates,
                blocked_latest_certificates=summary.blocked_latest_certificates,
                blocked_missing_summary=summary.blocked_missing_summary,
            )
            session.add(prune_run)
    run_id = prune_run.id

    try:
        total_deleted = 0
        while True:
            if limit and total_deleted >= limit:
                break
            async with factory() as session:
                async with session.begin():
                    effective_batch = (
                        min(batch_size, limit - total_deleted) if limit else batch_size
                    )
                    cert_ids = await find_prunable_certificate_ids(
                        session, cutoff, effective_batch
                    )
                    if not cert_ids:
                        break
                    counts = await delete_certificates_batch(session, cert_ids)
            summary.deleted_certificates += counts.deleted_certificates
            summary.deleted_certificate_hostnames += (
                counts.deleted_certificate_hostnames
            )
            summary.deleted_ct_observations += counts.deleted_ct_observations
            total_deleted += counts.deleted_certificates
            summary.batches_processed += 1
            reporter.batch_progress(summary)

        summary.status = "complete"
        _logger.info(
            "prune_expired_certs: deleted=%d obs=%d run_id=%s",
            summary.deleted_certificates,
            summary.deleted_ct_observations,
            run_id,
        )

    except Exception as exc:  # noqa: BLE001
        summary.status = "failed"
        summary.error_message = str(exc)
        _logger.exception("prune_expired_certs failed: run_id=%s", run_id)

    # --- Update the prune_run audit row with final counts ---
    async with factory() as session:
        async with session.begin():
            await session.execute(
                update(CtPruneRun)
                .where(CtPruneRun.id == run_id)
                .values(
                    completed_at=datetime.now(UTC),
                    deleted_certificates=summary.deleted_certificates,
                    deleted_certificate_hostnames=summary.deleted_certificate_hostnames,
                    deleted_ct_observations=summary.deleted_ct_observations,
                    status=summary.status,
                    error_message=summary.error_message,
                )
            )

    reporter.print_summary(summary)
