"""Ingestion-plane CLI commands.

Commands:
    sync-logs                    — Fetch CT log list and probe each log.
    tail                         — Run the tail worker loop.
    reset-tail-cursors           — Reset tail cursors to the current edge.
    backfill                     — Run the backfill worker loop.
    reap-stale-backfill-claims   — Reset stale in_progress backfill claims.
    stats                        — Display per-log ingestion statistics.
    logs-follow                  — Stream application log output.
    rebuild-hostname-latest-certs — Rebuild latest-cert summary for all hostnames.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Annotated

import typer
from rich.console import Console

from ctpool._cli_ops_impl import _make_progress_callback, _make_status_callback
from ctpool.config import get_settings
from ctpool.db import create_engine, create_session_factory

_console = Console()
_PROGRESS_BATCH_SIZE: int = 64


def register(app: typer.Typer) -> None:
    """Register all ingestion-plane commands on *app*."""

    @app.command("sync-logs")
    def sync_logs() -> None:
        """Fetch the CT log list, upsert log sources, and probe each log."""
        from ctpool._cli_ops_impl import run_sync_logs

        asyncio.run(run_sync_logs(_console))

    @app.command("tail")
    def tail(
        once: Annotated[
            bool, typer.Option("--once", help="Exit after one pass.")
        ] = False,
        limit: Annotated[
            int | None, typer.Option("--limit", help="Stop after N entries.")
        ] = None,
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Restrict to one log UUID."),
        ] = None,
        progress: Annotated[
            bool, typer.Option("--progress", help="Print a line per batch.")
        ] = False,
        init_from_end: Annotated[
            int,
            typer.Option(
                "--init-from-end",
                help=(
                    "On first run (no cursor), start this many entries before the "
                    "current tree edge."
                ),
            ),
        ] = 0,
    ) -> None:
        """Tail new CT log entries continuously."""
        from ctpool.tail_worker import run_tail

        settings = get_settings()
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        if progress:
            _console.print(
                "[yellow]⚠️  NOTICE: Processing is slowed significantly with "
                "--progress. Use only for interactive use.[/yellow]"
            )
            on_batch: Callable[[str, int, int], None] | None = _make_progress_callback(
                _console
            )
            on_status: Callable[[str], None] | None = _make_status_callback(_console)
            batch_size = _PROGRESS_BATCH_SIZE
        else:
            on_batch = None
            on_status = None
            batch_size = settings.ct_default_batch_size
        asyncio.run(
            run_tail(
                factory,
                settings,
                once=once,
                limit=limit,
                log_id=log_id,
                on_batch=on_batch,
                on_status=on_status,
                init_from_end=init_from_end,
                batch_size=batch_size,
            )
        )

    @app.command("reset-tail-cursors")
    def reset_tail_cursors_cmd(
        to_current: Annotated[
            bool,
            typer.Option(
                "--to-current",
                help="Required: confirm cursors should be reset to the current edge.",
            ),
        ] = False,
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Restrict to one log UUID."),
        ] = None,
    ) -> None:
        """Reset tail cursors to the current tree edge (requires --to-current)."""
        if not to_current:
            _console.print(
                "[red]Error:[/red] Pass --to-current to confirm the reset. "
                "This will move all tail cursors to the live tree edge."
            )
            raise typer.Exit(code=1)
        from ctpool.tail_worker import reset_tail_cursors

        settings = get_settings()
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        asyncio.run(reset_tail_cursors(factory, settings, log_id=log_id))

    @app.command("backfill")
    def backfill(
        once: Annotated[
            bool, typer.Option("--once", help="Process one range then exit.")
        ] = False,
        limit: Annotated[
            int | None, typer.Option("--limit", help="Stop after N entries.")
        ] = None,
        days: Annotated[
            int | None,
            typer.Option("--days", help="Override CT_BACKFILL_DAYS."),
        ] = None,
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Restrict to one log UUID."),
        ] = None,
        progress: Annotated[
            bool, typer.Option("--progress", help="Print a line per batch.")
        ] = False,
    ) -> None:
        """Claim and process historical CT log backfill ranges."""
        from ctpool.backfill_worker import run_backfill

        settings = get_settings()
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        if progress:
            _console.print(
                "[yellow]⚠️  NOTICE: Processing is slowed significantly with "
                "--progress. Use only for interactive use.[/yellow]"
            )
            on_batch: Callable[[str, int, int], None] | None = _make_progress_callback(
                _console
            )
            on_status: Callable[[str], None] | None = _make_status_callback(_console)
            batch_size = _PROGRESS_BATCH_SIZE
        else:
            on_batch = None
            on_status = None
            batch_size = settings.ct_default_batch_size
        asyncio.run(
            run_backfill(
                factory,
                settings,
                once=once,
                limit=limit,
                days=days,
                log_id=log_id,
                on_batch=on_batch,
                on_status=on_status,
                batch_size=batch_size,
            )
        )

    @app.command("reap-stale-backfill-claims")
    def reap_stale_backfill_claims(
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run", help="Report stale claims without resetting them."
            ),
        ] = False,
        timeout_seconds: Annotated[
            int | None,
            typer.Option(
                "--timeout-seconds",
                help="Override ct_backfill_claim_timeout_seconds from config.",
            ),
        ] = None,
    ) -> None:
        """Reset in_progress backfill ranges with stale heartbeats to pending."""
        from ctpool._cli_reap_impl import run_reap_stale

        asyncio.run(
            run_reap_stale(
                dry_run=dry_run,
                timeout_seconds=timeout_seconds,
                console=_console,
            )
        )

    @app.command("logs-follow")
    def logs_follow(
        level: Annotated[
            str, typer.Option("--level", help="Minimum log level.")
        ] = "INFO",
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Filter to a specific CT log UUID."),
        ] = None,
    ) -> None:
        """Stream application log output to the terminal with Rich formatting."""
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        _console.print(
            f"Following logs at level [cyan]{level.upper()}[/cyan]. "
            "Press Ctrl-C to stop."
        )
        from ctpool._cli_ops_impl import block_forever

        try:
            asyncio.run(block_forever())
        except KeyboardInterrupt:
            pass

    @app.command("rebuild-hostname-latest-certs")
    def rebuild_hostname_latest_certs(
        batch_size: Annotated[
            int,
            typer.Option("--batch-size", help="Hostnames to process per transaction."),
        ] = 1000,
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count candidates without writing."),
        ] = False,
    ) -> None:
        """Rebuild the latest-cert summary for every hostname from stored cert data."""
        from ctpool._cli_rebuild_impl import run_rebuild_hostname_latest_certs

        asyncio.run(
            run_rebuild_hostname_latest_certs(
                batch_size=batch_size,
                dry_run=dry_run,
                console=_console,
            )
        )
