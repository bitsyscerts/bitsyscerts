"""Unit tests for ctpool._cli_bootstrap_impl.

All heavy external calls (DB, network) are mocked.  The tests focus on:
* The full happy-path sequence runs in order.
* Soft-fail steps (3–5) catch exceptions and print a warning.
* Hard-fail steps (1–2) propagate exceptions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from ctpool._cli_bootstrap_impl import run_bootstrap
from ctpool.config import Settings


@pytest.fixture()
def console() -> Console:
    from pathlib import Path

    return Console(file=Path("/dev/null").open("w"), highlight=False)


@pytest.fixture()
def settings() -> Settings:
    return MagicMock(spec=Settings)


# ---------------------------------------------------------------------------
# Happy path — all steps succeed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_bootstrap_calls_all_steps_in_order(
    settings: Settings,
    console: Console,
) -> None:
    """All six steps are executed when no errors occur."""
    row_mock = MagicMock(storage_profile="current-osint")
    engine_mock = AsyncMock()
    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "ctpool._cli_bootstrap_impl.run_upgrade_head",
            new_callable=AsyncMock,
        ) as mock_migrate,
        patch(
            "ctpool._cli_bootstrap_impl.create_engine",
            return_value=engine_mock,
        ),
        patch("ctpool._cli_bootstrap_impl.create_session_factory"),
        patch(
            "ctpool._cli_bootstrap_impl.get_session",
            return_value=session_ctx,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.bootstrap_settings_from_env",
            new_callable=AsyncMock,
            return_value=row_mock,
        ) as mock_settings,
        patch(
            "ctpool._cli_bootstrap_impl.run_sync_logs",
            new_callable=AsyncMock,
        ) as mock_sync,
        patch(
            "ctpool._cli_bootstrap_impl.take_snapshot_once",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "ctpool._cli_bootstrap_impl.run_maintenance_once",
            new_callable=AsyncMock,
        ) as mock_maint,
        patch(
            "ctpool._cli_bootstrap_impl.run_status",
            new_callable=AsyncMock,
        ) as mock_status,
    ):
        await run_bootstrap(settings=settings, console=console)

    mock_migrate.assert_awaited_once()
    mock_settings.assert_awaited_once()
    mock_sync.assert_awaited_once()
    mock_snapshot.assert_awaited_once_with(settings)
    mock_maint.assert_awaited_once_with(settings)
    mock_status.assert_awaited_once()


# ---------------------------------------------------------------------------
# Soft-fail steps (3–5) do not propagate exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_logs_failure_is_soft_fail(
    settings: Settings,
    console: Console,
) -> None:
    """A log-sync failure does not abort the bootstrap sequence."""
    row_mock = MagicMock(storage_profile="current-osint")
    engine_mock = AsyncMock()
    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "ctpool._cli_bootstrap_impl.run_upgrade_head",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.create_engine",
            return_value=engine_mock,
        ),
        patch("ctpool._cli_bootstrap_impl.create_session_factory"),
        patch(
            "ctpool._cli_bootstrap_impl.get_session",
            return_value=session_ctx,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.bootstrap_settings_from_env",
            new_callable=AsyncMock,
            return_value=row_mock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_sync_logs",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network failure"),
        ),
        patch(
            "ctpool._cli_bootstrap_impl.take_snapshot_once",
            new_callable=AsyncMock,
        ) as mock_snapshot,
        patch(
            "ctpool._cli_bootstrap_impl.run_maintenance_once",
            new_callable=AsyncMock,
        ) as mock_maint,
        patch(
            "ctpool._cli_bootstrap_impl.run_status",
            new_callable=AsyncMock,
        ) as mock_status,
    ):
        # Must not raise.
        await run_bootstrap(settings=settings, console=console)

    # Steps 4–6 still execute.
    mock_snapshot.assert_awaited_once()
    mock_maint.assert_awaited_once()
    mock_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_snapshot_failure_is_soft_fail(
    settings: Settings,
    console: Console,
) -> None:
    """A snapshot failure does not abort bootstrap; maintenance still runs."""
    row_mock = MagicMock(storage_profile="current-osint")
    engine_mock = AsyncMock()
    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "ctpool._cli_bootstrap_impl.run_upgrade_head",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.create_engine",
            return_value=engine_mock,
        ),
        patch("ctpool._cli_bootstrap_impl.create_session_factory"),
        patch(
            "ctpool._cli_bootstrap_impl.get_session",
            return_value=session_ctx,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.bootstrap_settings_from_env",
            new_callable=AsyncMock,
            return_value=row_mock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_sync_logs",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.take_snapshot_once",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db error"),
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_maintenance_once",
            new_callable=AsyncMock,
        ) as mock_maint,
        patch(
            "ctpool._cli_bootstrap_impl.run_status",
            new_callable=AsyncMock,
        ) as mock_status,
    ):
        await run_bootstrap(settings=settings, console=console)

    mock_maint.assert_awaited_once()
    mock_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_maintenance_failure_is_soft_fail(
    settings: Settings,
    console: Console,
) -> None:
    """A maintenance failure does not abort bootstrap; status still prints."""
    row_mock = MagicMock(storage_profile="current-osint")
    engine_mock = AsyncMock()
    session_ctx = AsyncMock()
    session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "ctpool._cli_bootstrap_impl.run_upgrade_head",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.create_engine",
            return_value=engine_mock,
        ),
        patch("ctpool._cli_bootstrap_impl.create_session_factory"),
        patch(
            "ctpool._cli_bootstrap_impl.get_session",
            return_value=session_ctx,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.bootstrap_settings_from_env",
            new_callable=AsyncMock,
            return_value=row_mock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_sync_logs",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.take_snapshot_once",
            new_callable=AsyncMock,
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_maintenance_once",
            new_callable=AsyncMock,
            side_effect=RuntimeError("prune error"),
        ),
        patch(
            "ctpool._cli_bootstrap_impl.run_status",
            new_callable=AsyncMock,
        ) as mock_status,
    ):
        await run_bootstrap(settings=settings, console=console)

    mock_status.assert_awaited_once()


# ---------------------------------------------------------------------------
# Hard-fail steps (1–2) propagate exceptions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_failure_propagates(
    settings: Settings,
    console: Console,
) -> None:
    """A migration failure raises immediately — bootstrap does not continue."""
    with (
        patch(
            "ctpool._cli_bootstrap_impl.run_upgrade_head",
            new_callable=AsyncMock,
            side_effect=RuntimeError("migration failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="migration failed"):
            await run_bootstrap(settings=settings, console=console)
