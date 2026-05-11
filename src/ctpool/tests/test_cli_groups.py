"""CLI integration tests for the Sprint 8 grouped command surface.

These tests exercise the Typer command registration and argument passing
without touching a real database or network.  Each test mocks
``asyncio.run`` (or the underlying impl function) within the relevant
module and asserts that the correct async coroutine is dispatched.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ctpool.cli import app

_runner = CliRunner()


def _discard_asyncio_run(return_value: object = None):
    """Return a side_effect that closes the coroutine without running it."""

    def _run(coro: object) -> object:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return return_value

    return _run


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_command_is_registered() -> None:
    """``ctpool bootstrap`` appears in --help."""
    result = _runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "bootstrap" in result.output


def test_bootstrap_command_invokes_run_bootstrap() -> None:
    """``ctpool bootstrap`` calls ``run_bootstrap`` via asyncio.run."""
    with (
        patch("ctpool.cli_bootstrap_command.get_settings", return_value=MagicMock()),
        patch("ctpool.cli_bootstrap_command.asyncio.run") as mock_run,
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["bootstrap"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# db group
# ---------------------------------------------------------------------------


def test_db_group_help_is_registered() -> None:
    """``ctpool db --help`` lists sub-commands."""
    result = _runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output
    assert "init" in result.output
    assert "status" in result.output


def test_db_migrate_invokes_run_upgrade_head() -> None:
    """``ctpool db migrate`` dispatches to asyncio.run."""
    with (
        patch("ctpool.cli_group_db.asyncio.run") as mock_run,
        patch(
            "ctpool.cli_group_db.get_settings",
            return_value=MagicMock(),
            create=True,
        ),
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["db", "migrate"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_db_status_invokes_get_current_revision() -> None:
    """``ctpool db status`` dispatches to asyncio.run."""
    with patch("ctpool.cli_group_db.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["db", "status"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# logs group
# ---------------------------------------------------------------------------


def test_logs_group_help_is_registered() -> None:
    """``ctpool logs --help`` lists sub-commands."""
    result = _runner.invoke(app, ["logs", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.output
    assert "follow" in result.output


def test_logs_sync_invokes_run_sync_logs() -> None:
    """``ctpool logs sync`` calls asyncio.run with run_sync_logs coroutine."""
    with patch("ctpool.cli_group_logs.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["logs", "sync"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# stats group
# ---------------------------------------------------------------------------


def test_stats_group_help_is_registered() -> None:
    """``ctpool stats --help`` lists sub-commands."""
    result = _runner.invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output
    assert "snapshot" in result.output


def test_stats_show_invokes_run_stats() -> None:
    """``ctpool stats show`` calls asyncio.run."""
    with patch("ctpool.cli_group_stats.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["stats", "show"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_stats_snapshot_once_invokes_take_snapshot_once() -> None:
    """``ctpool stats snapshot`` calls asyncio.run with take_snapshot_once."""
    with (
        patch("ctpool.cli_group_stats.asyncio.run") as mock_run,
        patch(
            "ctpool.cli_group_stats.get_settings",
            return_value=MagicMock(),
            create=True,
        ),
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["stats", "snapshot"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# storage group
# ---------------------------------------------------------------------------


def test_storage_group_help_is_registered() -> None:
    """``ctpool storage --help`` lists sub-commands."""
    result = _runner.invoke(app, ["storage", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.output
    assert "prune" in result.output


def test_storage_profile_renders_table() -> None:
    """``ctpool storage profile`` renders a table without errors."""
    from ctpool.storage_modes import CertStorageMode, StorageProfile

    profile_mock = StorageProfile("standard")
    cert_mode_mock = CertStorageMode("metadata")
    settings_mock = MagicMock()
    settings_mock.ct_hostname_retention_mode = "all"
    settings_mock.ct_cert_retention_days = 30
    settings_mock.ct_observation_retention_days = 30
    settings_mock.ct_entry_outcome_retention_days = 30

    with (
        patch(
            "ctpool.config.get_settings",
            return_value=settings_mock,
        ),
        patch(
            "ctpool.storage_modes.resolve_profile_defaults",
            return_value=(profile_mock, cert_mode_mock),
        ),
        patch(
            "ctpool.profile_projection.bytes_per_observation_range",
            return_value=(100, 200),
        ),
    ):
        result = _runner.invoke(app, ["storage", "profile"])
    assert result.exit_code == 0


def test_storage_prune_dry_run_dispatches_asyncio_run() -> None:
    """``ctpool storage prune`` calls asyncio.run (default dry-run)."""
    with patch("ctpool.cli_group_storage.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["storage", "prune"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# maintenance group
# ---------------------------------------------------------------------------


def test_maintenance_group_help_is_registered() -> None:
    """``ctpool maintenance --help`` shows --loop option."""
    result = _runner.invoke(app, ["maintenance", "--help"])
    assert result.exit_code == 0
    # Strip ANSI escape codes before asserting — CI runs with FORCE_COLOR=1
    # which causes Rich to inject codes that split "--loop" into "-\x1b[...]loop".
    import re

    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--loop" in plain


def test_maintenance_run_invokes_run_maintenance_once() -> None:
    """``ctpool maintenance`` (no flags) calls run_maintenance_once."""
    with (
        patch("ctpool.cli_maintenance_commands.asyncio.run") as mock_run,
        patch(
            "ctpool.cli_maintenance_commands.get_settings",
            return_value=MagicMock(),
            create=True,
        ),
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["maintenance"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# worker group
# ---------------------------------------------------------------------------


def test_worker_group_help_is_registered() -> None:
    """``ctpool worker --help`` lists sub-commands."""
    result = _runner.invoke(app, ["worker", "--help"])
    assert result.exit_code == 0
    assert "tail" in result.output
    assert "backfill" in result.output
    assert "list" in result.output
    assert "reap-stale" in result.output


def test_worker_tail_once_invokes_asyncio_run() -> None:
    """``ctpool worker tail --once`` calls asyncio.run."""
    with (
        patch("ctpool.cli_group_workers.asyncio.run") as mock_run,
        patch(
            "ctpool.cli_group_workers.get_settings",
            return_value=MagicMock(),
            create=True,
        ),
        patch(
            "ctpool.cli_group_workers.create_engine",
            return_value=MagicMock(),
            create=True,
        ),
        patch(
            "ctpool.cli_group_workers.create_session_factory",
            return_value=MagicMock(),
            create=True,
        ),
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["worker", "tail", "--once"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_worker_backfill_invokes_asyncio_run() -> None:
    """``ctpool worker backfill`` calls asyncio.run."""
    with (
        patch("ctpool.cli_group_workers.asyncio.run") as mock_run,
        patch(
            "ctpool.cli_group_workers.get_settings",
            return_value=MagicMock(),
            create=True,
        ),
        patch(
            "ctpool.cli_group_workers.create_engine",
            return_value=MagicMock(),
            create=True,
        ),
        patch(
            "ctpool.cli_group_workers.create_session_factory",
            return_value=MagicMock(),
            create=True,
        ),
    ):
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["worker", "backfill", "--once"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_worker_list_invokes_asyncio_run() -> None:
    """``ctpool worker list`` calls asyncio.run."""
    with patch("ctpool.cli_group_workers.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["worker", "list"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_worker_reap_stale_dry_run_invokes_asyncio_run() -> None:
    """``ctpool worker reap-stale --dry-run`` calls asyncio.run."""
    with patch("ctpool.cli_group_workers.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["worker", "reap-stale", "--dry-run"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# diagnostics group
# ---------------------------------------------------------------------------


def test_diagnostics_group_help_is_registered() -> None:
    """``ctpool diagnostics --help`` lists sub-commands."""
    result = _runner.invoke(app, ["diagnostics", "--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output
    assert "entry-errors" in result.output
    assert "audit-gaps" in result.output


def test_diagnostics_doctor_invokes_run_doctor_command() -> None:
    """``ctpool diagnostics doctor`` calls asyncio.run."""
    with patch("ctpool.cli_group_diagnostics.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run(return_value=0)
        result = _runner.invoke(app, ["diagnostics", "doctor"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_diagnostics_entry_errors_invokes_asyncio_run() -> None:
    """``ctpool diagnostics entry-errors`` calls asyncio.run."""
    with patch("ctpool.cli_group_diagnostics.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["diagnostics", "entry-errors"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_diagnostics_audit_gaps_invokes_asyncio_run() -> None:
    """``ctpool diagnostics audit-gaps`` calls asyncio.run."""
    with patch("ctpool.cli_group_diagnostics.asyncio.run") as mock_run:
        mock_run.side_effect = _discard_asyncio_run()
        result = _runner.invoke(app, ["diagnostics", "audit-gaps"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
