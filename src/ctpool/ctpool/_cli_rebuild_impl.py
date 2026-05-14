"""Implementation for the rebuild-hostname-latest-certs CLI command.

Exports:
    run_rebuild_hostname_latest_certs — Batch-rebuild the hostname latest-cert
                                        summary for every hostname row.
"""

from __future__ import annotations

import logging

from rich.console import Console
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory
from ctpool.models.hostname import Hostname

_logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE: int = 1000


async def _rebuild_batch(
    session: AsyncSession,
    after_id: object,
    batch_size: int,
) -> tuple[int, object]:
    """Process one batch of hostnames; return (updated_count, last_id_seen)."""
    # Select the next batch of hostname IDs ordered by id for stable pagination.
    id_stmt = (
        select(Hostname.id)
        .where(Hostname.id > after_id)
        .order_by(Hostname.id)
        .limit(batch_size)
    )
    id_rows = (await session.execute(id_stmt)).scalars().all()
    if not id_rows:
        return 0, after_id

    last_id = id_rows[-1]

    # For each hostname, find its latest cert using DISTINCT ON (hostname_id)
    # ordered by the ranking columns descending.
    stmt = text(
        """
        WITH ranked AS (
            SELECT DISTINCT ON (ch.hostname_id)
                ch.hostname_id,
                c.fingerprint_sha256,
                c.not_before,
                c.not_after,
                c.issuer_common_name,
                c.issuer_organization,
                c.subject_common_name,
                c.is_precertificate,
                now() AS seen_at
            FROM certificate_hostnames ch
            JOIN certificates c ON c.id = ch.certificate_id
            WHERE ch.hostname_id = ANY(:ids)
            ORDER BY
                ch.hostname_id,
                c.not_after DESC NULLS LAST,
                c.not_before DESC NULLS LAST,
                c.fingerprint_sha256 ASC
        )
        UPDATE hostnames h
        SET
            latest_cert_fingerprint_sha256 = ranked.fingerprint_sha256,
            latest_cert_not_before         = ranked.not_before,
            latest_cert_not_after          = ranked.not_after,
            latest_cert_issuer_cn          = ranked.issuer_common_name,
            latest_cert_issuer_org         = ranked.issuer_organization,
            latest_cert_subject_cn         = ranked.subject_common_name,
            latest_cert_is_precert         = ranked.is_precertificate,
            latest_cert_seen_at            = ranked.seen_at
        FROM ranked
        WHERE h.id = ranked.hostname_id
        """
    )
    result = await session.execute(stmt, {"ids": [str(i) for i in id_rows]})  # noqa: E501
    updated = result.rowcount
    return updated, last_id


async def run_rebuild_hostname_latest_certs(
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    console: Console,
) -> None:
    """Rebuild the latest-cert summary for every hostname from stored cert data.

    Uses DISTINCT ON with the canonical ranking order to select the best
    certificate per hostname, then bulk-updates the ``hostnames`` table in
    batches.

    Args:
        batch_size: Hostnames to process per database transaction.
        dry_run:    If True, count candidates without writing.
        console:    Rich console for progress output.
    """
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    if dry_run:
        async with factory() as session:
            count_result = await session.execute(
                select(func.count()).select_from(Hostname)
            )
            total = int(count_result.scalar_one())
        console.print(
            f"[dry-run] Would rebuild latest-cert summary for "
            f"[cyan]{total:,}[/cyan] hostname(s)."
        )
        return

    total_updated = 0
    # Use a zero UUID as the starting cursor (all UUIDs are >= this).
    after_id: object = "00000000-0000-0000-0000-000000000000"

    while True:
        async with factory() as session:
            async with session.begin():
                updated, after_id = await _rebuild_batch(session, after_id, batch_size)
        if updated == 0:
            break
        total_updated += updated
        console.print(
            f"  rebuilt [cyan]{total_updated:,}[/cyan] hostnames so far…",
            end="\r",
        )

    console.print(
        f"\n[green]Rebuild complete.[/green] "
        f"Updated [cyan]{total_updated:,}[/cyan] hostname(s)."
    )
    _logger.info("rebuild_hostname_latest_certs: updated=%d", total_updated)
