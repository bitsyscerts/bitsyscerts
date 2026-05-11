"""Typer CLI entry-point for ctpool.

All command implementations live in domain-specific cli_*_commands.py modules.
This file is intentionally thin: it creates the Typer app and delegates
registration to each module's ``register(app)`` function.

Legacy top-level commands (backwards-compatible):
    cli_db_commands          — apply-migrations, db-init, init-db, db-status
    cli_ingestion_commands   — sync-logs, tail, reset-tail-cursors, backfill,
                               reap-stale-backfill-claims, logs-follow,
                               rebuild-hostname-latest-certs
    cli_audit_commands       — check-audit-gaps, fix-audit-findings, doctor
    cli_prune_commands       — prune-metrics, prune-expired-certs,
                               prune-observations, prune-entry-outcomes,
                               prune-for-storage-profile
    cli_storage_commands     — storage-profile
    cli_settings_commands    — profile show, profile list
    cli_stats_commands       — stats, stats-snapshot
    cli_maintenance_commands — maintenance
    cli_workers_commands     — workers list, workers reap-stale

Grouped command surface (Sprint 8):
    cli_bootstrap_command    — bootstrap (idempotent first-run setup)
    cli_group_db             — db migrate / db init / db status
    cli_group_logs           — logs sync / logs follow
    cli_group_stats          — stats show / stats snapshot
    cli_group_storage        — storage profile / storage prune
    cli_group_maintenance    — maintenance run / maintenance loop
    cli_group_workers        — worker tail / worker backfill / worker list
    cli_group_diagnostics    — diagnostics doctor / entry-errors / …
"""

from __future__ import annotations

import typer

import ctpool.cli_audit_commands as _audit
import ctpool.cli_bootstrap_command as _bootstrap
import ctpool.cli_db_commands as _db
import ctpool.cli_diagnostics_commands as _diagnostics
import ctpool.cli_group_db as _group_db
import ctpool.cli_group_diagnostics as _group_diagnostics
import ctpool.cli_group_logs as _group_logs
import ctpool.cli_group_stats as _group_stats
import ctpool.cli_group_storage as _group_storage
import ctpool.cli_group_workers as _group_workers
import ctpool.cli_ingestion_commands as _ingestion
import ctpool.cli_legacy_commands as _legacy
import ctpool.cli_maintenance_commands as _maintenance
import ctpool.cli_prune_commands as _prune
import ctpool.cli_stats_commands as _stats
import ctpool.cli_status_commands as _status
import ctpool.cli_storage_commands as _storage
import ctpool.cli_workers_commands as _workers
from ctpool.cli_settings_commands import profile_app

app = typer.Typer(name="ctpool", no_args_is_help=True, add_completion=False)

# Grouped commands (Sprint 8).
_bootstrap.register(app)
_group_db.register(app)
_group_logs.register(app)
_group_stats.register(app)
_group_storage.register(app)
_group_workers.register(app)
_group_diagnostics.register(app)

# Legacy top-level commands (backwards-compatible).
_db.register(app)
_ingestion.register(app)
_audit.register(app)
_diagnostics.register(app)
_prune.register(app)
_storage.register(app)
_stats.register(app)
_status.register(app)
_maintenance.register(app)
_workers.register(app)
_legacy.register(app)
app.add_typer(profile_app)
