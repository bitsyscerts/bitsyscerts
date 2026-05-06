"""Tests for the ctpool init-db CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from ctpool.cli import app
from ctpool.exceptions import DatabaseInitError

_runner = CliRunner()


def test_init_db_command_invokes_orchestrator() -> None:
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch(
            "ctpool.database_init.run_init_db",
            new_callable=AsyncMock,
            return_value="created",
        ),
    ):
        result = _runner.invoke(app, ["init-db"])

    assert result.exit_code == 0
    assert "created and migrated" in result.output.lower()


def test_init_db_force_passes_force_flag() -> None:
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch(
            "ctpool.database_init.run_init_db",
            new_callable=AsyncMock,
            return_value="recreated",
        ) as mock_run,
    ):
        result = _runner.invoke(app, ["init-db", "--force"])

    assert result.exit_code == 0
    mock_run.assert_awaited_once()
    assert mock_run.await_args.kwargs["force"] is True


def test_init_db_command_exits_nonzero_for_database_init_error() -> None:
    with (
        patch("ctpool.cli.get_settings", return_value=MagicMock()),
        patch(
            "ctpool.database_init.run_init_db",
            new_callable=AsyncMock,
            side_effect=DatabaseInitError("run init-db --force"),
        ),
    ):
        result = _runner.invoke(app, ["init-db"])

    assert result.exit_code == 1
    assert "run init-db --force" in result.output
