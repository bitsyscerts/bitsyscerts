"""Unit tests for _cli_prune_observations_impl and _cli_prune_entry_outcomes_impl.

These test the public API surface via dry-run mode with mocked DB interactions,
so no live database is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from rich.console import Console

_QUIET_CONSOLE = Console(quiet=True)


class TestRunPruneObservationsDryRun:
    """Tests for run_prune_observations in dry-run (default) mode."""

    async def test_dry_run_returns_zero(self) -> None:
        """Dry-run mode must not delete any rows and must return 0."""
        from ctpool._cli_prune_observations_impl import run_prune_observations

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 100
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_factory = MagicMock(return_value=mock_session)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch(
                "ctpool._cli_prune_observations_impl.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "ctpool._cli_prune_observations_impl.create_session_factory",
                return_value=mock_factory,
            ),
        ):
            deleted = await run_prune_observations(
                dry_run=True,
                retention_days=7,
                console=_QUIET_CONSOLE,
            )

        assert deleted == 0

    async def test_retention_days_uses_settings_when_not_provided(self) -> None:
        """When retention_days is None, settings.ct_observation_retention_days is used."""  # noqa: E501
        from ctpool._cli_prune_observations_impl import run_prune_observations

        mock_settings = MagicMock()
        mock_settings.ct_observation_retention_days = 14

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch(
                "ctpool._cli_prune_observations_impl.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "ctpool._cli_prune_observations_impl.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "ctpool._cli_prune_observations_impl.create_session_factory",
                return_value=MagicMock(return_value=mock_session),
            ),
        ):
            deleted = await run_prune_observations(
                dry_run=True,
                retention_days=None,
                console=_QUIET_CONSOLE,
            )

        assert deleted == 0


class TestRunPruneEntryOutcomesDryRun:
    """Tests for run_prune_entry_outcomes in dry-run mode."""

    async def test_dry_run_returns_zero(self) -> None:
        from ctpool._cli_prune_entry_outcomes_impl import run_prune_entry_outcomes

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 50
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.create_session_factory",
                return_value=MagicMock(return_value=mock_session),
            ),
        ):
            deleted = await run_prune_entry_outcomes(
                dry_run=True,
                retention_days=7,
                console=_QUIET_CONSOLE,
            )

        assert deleted == 0

    async def test_execute_mode_dispatches_batch_deletes(self) -> None:
        """Execute mode should issue delete statements until 0 rows remain."""
        from ctpool._cli_prune_entry_outcomes_impl import run_prune_entry_outcomes

        # First batch deletes 3 rows, second returns 0 (done)
        delete_results = [MagicMock(rowcount=3), MagicMock(rowcount=0)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        call_count = 0

        async def execute_side_effect(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return count_result
            return delete_results[min(call_count - 2, len(delete_results) - 1)]

        begin_ctx = AsyncMock()
        begin_ctx.__aenter__ = AsyncMock(return_value=None)
        begin_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=execute_side_effect)
        mock_session.begin = MagicMock(return_value=begin_ctx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.create_engine",
                return_value=mock_engine,
            ),
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.create_session_factory",
                return_value=MagicMock(return_value=mock_session),
            ),
        ):
            deleted = await run_prune_entry_outcomes(
                dry_run=False,
                retention_days=7,
                console=_QUIET_CONSOLE,
            )

        assert deleted == 3
