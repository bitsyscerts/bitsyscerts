"""Sprint 2 dispatch-positioning tests.

Verifies that audit/repair CLI help text positions those commands as
advanced/debug, that the legacy-ranges command group is registered and
also marked advanced/debug, and that the dispatch-mode default remains
per-log.
"""

from __future__ import annotations

import typer
from typer.testing import CliRunner

import ctpool.cli_audit_commands as audit_commands
import ctpool.cli_ingestion_commands as ingestion_commands
import ctpool.cli_legacy_commands as legacy_commands
from ctpool.config import Settings


def _build_audit_app() -> typer.Typer:
    app = typer.Typer()
    audit_commands.register(app)
    return app


def _build_legacy_app() -> typer.Typer:
    app = typer.Typer()
    legacy_commands.register(app)
    return app


def _build_ingestion_app() -> typer.Typer:
    app = typer.Typer()
    ingestion_commands.register(app)
    return app


class TestAuditCommandsAreAdvanced:
    """check-audit-gaps and fix-audit-findings must be marked advanced/debug."""

    def test_module_docstring_marks_audit_advanced_debug(self) -> None:
        doc = audit_commands.__doc__ or ""
        assert "advanced/debug" in doc.lower()
        assert "per-log" in doc.lower()

    def test_check_audit_gaps_help_marks_advanced(self) -> None:
        runner = CliRunner()
        app = _build_audit_app()
        result = runner.invoke(app, ["check-audit-gaps", "--help"])
        assert result.exit_code == 0
        assert "advanced" in result.output.lower()

    def test_fix_audit_findings_help_marks_advanced(self) -> None:
        runner = CliRunner()
        app = _build_audit_app()
        result = runner.invoke(app, ["fix-audit-findings", "--help"])
        assert result.exit_code == 0
        assert "advanced" in result.output.lower()


class TestLegacyRangesCommandGroup:
    """legacy-ranges command group is registered and advanced-positioned."""

    def test_legacy_ranges_help_lists_subcommands(self) -> None:
        runner = CliRunner()
        app = _build_legacy_app()
        result = runner.invoke(app, ["legacy-ranges", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "clear" in result.output
        # The Typer-rendered help text may wrap; check the docstring source
        # of truth directly so the assertion is robust.
        assert "advanced/debug" in (legacy_commands.legacy_app.info.help or "").lower()

    def test_legacy_ranges_clear_help_defaults_dry_run(self) -> None:
        runner = CliRunner()
        app = _build_legacy_app()
        result = runner.invoke(app, ["legacy-ranges", "clear", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower()


class TestDispatchModeDefaultIsPerLog:
    """Settings default dispatch mode must remain per-log in Sprint 2."""

    def test_default_is_per_log(self) -> None:
        settings = Settings.model_validate(
            {"database_url": "postgresql+psycopg://x:y@h/db"}
        )
        assert settings.ct_backfill_dispatch_mode == "per-log"


class TestIngestionHelpClarifiesLegacyCompatibility:
    """Routine ingestion help must demote legacy range operations."""

    def test_backfill_help_marks_legacy_ranges_as_compatibility_only(self) -> None:
        runner = CliRunner()
        app = _build_ingestion_app()
        result = runner.invoke(app, ["backfill", "--help"])
        assert result.exit_code == 0
        output = result.output.lower()
        assert "per-log" in output
        assert "legacy-ranges" in output
        assert "compatibility" in output or "debug" in output

    def test_reap_stale_backfill_claims_help_mentions_legacy_ranges(self) -> None:
        runner = CliRunner()
        app = _build_ingestion_app()
        result = runner.invoke(app, ["reap-stale-backfill-claims", "--help"])
        assert result.exit_code == 0
        assert "legacy" in result.output.lower()

    def test_backfill_rejects_unknown_dispatch_mode(self) -> None:
        runner = CliRunner()
        app = _build_ingestion_app()
        result = runner.invoke(app, ["backfill", "--dispatch-mode", "invalid"])
        assert result.exit_code != 0
        assert "per-log" in result.output.lower()
        assert "legacy-ranges" in result.output.lower()
