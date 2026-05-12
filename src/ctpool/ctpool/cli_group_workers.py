"""``ctpool worker`` sub-command group.

Thin wrappers around existing worker and worker-management implementations.
All advanced options (progress callbacks, dispatch-mode override) remain
accessible via the legacy top-level commands (``ctpool tail``,
``ctpool backfill``).

Sub-commands:
    worker tail       — Run the tail (forward-scan) ingestion worker.
    worker backfill   — Run the backfill (historical-scan) ingestion worker.
    worker list       — Show all non-stopped worker rows.
    worker reap-stale — Mark stale worker rows as stopped.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

import typer
from rich.console import Console

_console = Console()


def register(app: typer.Typer) -> None:
    """Add the ``worker`` sub-app to *app*."""
    worker_app = typer.Typer(
        help="Run CT ingestion workers and inspect worker heartbeat rows.",
        no_args_is_help=True,
    )
    app.add_typer(worker_app, name="worker")

    @worker_app.command("tail")
    def tail(
        once: Annotated[
            bool,
            typer.Option("--once", help="Exit after one full pass."),
        ] = False,
        limit: Annotated[
            int | None,
            typer.Option("--limit", help="Stop after N entries."),
        ] = None,
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Restrict to one CT log UUID."),
        ] = None,
        init_from_end: Annotated[
            int,
            typer.Option(
                "--init-from-end",
                help=(
                    "On first run (no cursor), start this many entries "
                    "before the current tree edge."
                ),
            ),
        ] = 0,
    ) -> None:
        """Run the tail worker (forward-scan new CT log entries)."""
        from ctpool.config import get_settings
        from ctpool.db import create_engine, create_session_factory
        from ctpool.worker_pool import run_tail_pool

        settings = get_settings()
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        concurrency = 1 if (once or log_id is not None) else None
        asyncio.run(
            run_tail_pool(
                factory,
                settings,
                concurrency=concurrency,
                once=once,
                limit=limit,
                log_id=log_id,
                init_from_end=init_from_end,
            )
        )

    @worker_app.command("backfill")
    def backfill(
        once: Annotated[
            bool,
            typer.Option("--once", help="Process one batch then exit."),
        ] = False,
        limit: Annotated[
            int | None,
            typer.Option("--limit", help="Stop after N entries."),
        ] = None,
        days: Annotated[
            int | None,
            typer.Option("--days", help="Override CT_BACKFILL_DAYS."),
        ] = None,
        log_id: Annotated[
            uuid.UUID | None,
            typer.Option("--log-id", help="Restrict to one CT log UUID."),
        ] = None,
    ) -> None:
        """Run the backfill worker (historical-scan CT log entries)."""
        from ctpool.config import get_settings
        from ctpool.db import create_engine, create_session_factory
        from ctpool.worker_pool import run_backfill_pool

        settings = get_settings()
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        concurrency = 1 if (once or log_id is not None) else None
        asyncio.run(
            run_backfill_pool(
                factory,
                settings,
                concurrency=concurrency,
                once=once,
                limit=limit,
                days=days,
                log_id=log_id,
            )
        )

    @worker_app.command("list")
    def list_workers(
        stale_seconds: Annotated[
            int | None,
            typer.Option(
                "--stale-seconds",
                help="Age threshold (default: from settings).",
            ),
        ] = None,
    ) -> None:
        """List all active worker rows from ct_worker_runtime."""
        from ctpool._cli_workers_impl import run_list_workers

        asyncio.run(run_list_workers(stale_seconds=stale_seconds))

    @worker_app.command("reap-stale")
    def reap_stale(
        stale_seconds: Annotated[
            int | None,
            typer.Option(
                "--stale-seconds",
                help="Age threshold (default: from settings).",
            ),
        ] = None,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Report stale workers without modifying any rows.",
            ),
        ] = False,
    ) -> None:
        """Mark stale worker rows as stopped in ct_worker_runtime."""
        from ctpool._cli_workers_impl import run_reap_workers

        asyncio.run(run_reap_workers(stale_seconds=stale_seconds, dry_run=dry_run))
