"""``ctpool bootstrap`` command registration.

Registers the top-level ``bootstrap`` command which runs the six-step
idempotent first-run setup sequence defined in
:mod:`ctpool._cli_bootstrap_impl`.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from ctpool._cli_bootstrap_impl import run_bootstrap
from ctpool.config import get_settings

_console = Console()


def register(app: typer.Typer) -> None:
    """Register the ``bootstrap`` command on *app*."""

    @app.command("bootstrap")
    def bootstrap() -> None:
        """Idempotent first-run setup: migrate → settings → sync → snapshot.

        Safe to run more than once.  Steps 3–5 (log sync, snapshot,
        maintenance) are soft-fail; a warning is printed if they error
        and the sequence continues.  The final step prints a concise
        operator status summary.
        """
        settings = get_settings()
        asyncio.run(run_bootstrap(settings=settings, console=_console))
