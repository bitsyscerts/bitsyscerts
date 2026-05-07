"""Typer CLI entry-point for ctpool.

All command implementations live in domain-specific cli_*_commands.py modules.
This file is intentionally thin: it creates the Typer app and delegates
registration to each module's ``register(app)`` function.

Command groups:
    cli_db_commands       — apply-migrations, db-init, init-db, db-status
    cli_ingestion_commands — sync-logs, tail, reset-tail-cursors, backfill,
                             reap-stale-backfill-claims, stats, logs-follow,
                             rebuild-hostname-latest-certs
    cli_audit_commands    — check-audit-gaps, fix-audit-findings, doctor
    cli_prune_commands    — prune-metrics, prune-expired-certs
    cli_storage_commands  — storage-profile
    cli_settings_commands — profile show, profile list
"""

from __future__ import annotations

import typer

import ctpool.cli_audit_commands as _audit
import ctpool.cli_db_commands as _db
import ctpool.cli_ingestion_commands as _ingestion
import ctpool.cli_prune_commands as _prune
import ctpool.cli_storage_commands as _storage
from ctpool.cli_settings_commands import profile_app

app = typer.Typer(name="ctpool", no_args_is_help=True, add_completion=False)

_db.register(app)
_ingestion.register(app)
_audit.register(app)
_prune.register(app)
_storage.register(app)
app.add_typer(profile_app)
