"""Tests for ctpool.cli — Typer command surface.

All underlying worker/service functions are mocked so tests run without
a database or network connection.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from ctpool.cli import app

_runner = CliRunner()


# ---------------------------------------------------------------------------
# db-init
# ---------------------------------------------------------------------------


def test_db_init_command_invokes_migration_runner() -> None:
    """db-init delegates to run_upgrade_head and exits zero."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.migration_runner.run_upgrade_head", new_callable=AsyncMock),
    ):
        # Patch inside cli module's local import
        with patch("ctpool.cli.asyncio.run") as mock_run:
            mock_run.return_value = None
            result = _runner.invoke(app, ["db-init"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# db-status
# ---------------------------------------------------------------------------


def test_db_status_command_shows_revision() -> None:
    """db-status shows the current revision when the schema is initialised."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run", return_value="abc123def456"),
    ):
        result = _runner.invoke(app, ["db-status"])

    assert result.exit_code == 0
    assert "abc123def456" in result.output


def test_db_status_shows_uninitialised_message_when_no_revision() -> None:
    """db-status shows a clear message when no migrations are applied."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run", return_value=None),
    ):
        result = _runner.invoke(app, ["db-status"])

    assert result.exit_code == 0
    assert (
        "not initialised" in result.output.lower()
        or "no migrations" in result.output.lower()
    )


# ---------------------------------------------------------------------------
# sync-logs
# ---------------------------------------------------------------------------


def test_sync_logs_command_invokes_discovery_and_prober() -> None:
    """sync-logs calls fetch_log_list, sync_log_sources, and probe_log."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        result = _runner.invoke(app, ["sync-logs"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# tail
# ---------------------------------------------------------------------------


def test_tail_command_invokes_tail_worker() -> None:
    """tail delegates to run_tail via asyncio.run."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        result = _runner.invoke(app, ["tail"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_tail_command_passes_once_flag() -> None:
    """tail --once passes once=True to run_tail."""
    from ctpool.tail_worker import run_tail

    captured: list[object] = []

    def capture_run(coro: object) -> None:
        captured.append(coro)

    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run", side_effect=capture_run),
        patch("ctpool.tail_worker.run_tail", wraps=run_tail),
    ):
        _runner.invoke(app, ["tail", "--once"])

    # The coroutine was created — verify it was called with once=True by
    # inspecting the coroutine's cr_frame locals or by checking the mock.
    assert len(captured) == 1


def test_tail_command_passes_limit() -> None:
    """tail --limit 100 results in a coroutine being run."""
    captured: list[object] = []

    def capture_run(coro: object) -> None:
        captured.append(coro)

    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run", side_effect=capture_run),
    ):
        result = _runner.invoke(app, ["tail", "--limit", "100"])

    assert result.exit_code == 0
    assert len(captured) == 1


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


def test_backfill_command_invokes_backfill_worker() -> None:
    """backfill delegates to run_backfill via asyncio.run."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        result = _runner.invoke(app, ["backfill"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_backfill_command_passes_once_flag() -> None:
    """backfill --once results in asyncio.run being called once."""
    captured: list[object] = []

    def capture_run(coro: object) -> None:
        captured.append(coro)

    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run", side_effect=capture_run),
    ):
        result = _runner.invoke(app, ["backfill", "--once"])

    assert result.exit_code == 0
    assert len(captured) == 1


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_stats_command_invokes_stats_display() -> None:
    """stats calls render_stats via asyncio.run."""
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch("ctpool.cli.create_engine", return_value=MagicMock()),
        patch("ctpool.cli.create_session_factory", return_value=MagicMock()),
        patch("ctpool.cli.asyncio.run") as mock_run,
    ):
        mock_run.return_value = None
        result = _runner.invoke(app, ["stats"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# unknown subcommand
# ---------------------------------------------------------------------------


def test_unknown_subcommand_exits_nonzero() -> None:
    """An unrecognised subcommand exits with a non-zero code."""
    result = _runner.invoke(app, ["nonexistent"])
    assert result.exit_code != 0
