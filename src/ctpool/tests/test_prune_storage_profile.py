"""Unit tests for _cli_prune_storage_profile_impl."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from rich.console import Console

_QUIET_CONSOLE = Console(quiet=True)


def _make_settings(
    storage_profile: str = "lite",
    metrics_retention_days: int = 30,
    observation_retention_days: int = 7,
    entry_outcome_retention_days: int = 7,
) -> MagicMock:
    s = MagicMock()
    s.ct_storage_profile = storage_profile
    s.ct_metrics_retention_days = metrics_retention_days
    s.ct_observation_retention_days = observation_retention_days
    s.ct_entry_outcome_retention_days = entry_outcome_retention_days
    return s


class TestRunPruneForStorageProfile:
    async def test_dry_run_calls_all_three_prune_functions(self) -> None:
        """In dry-run mode all three prune helpers must be invoked."""
        settings = _make_settings()

        prune_metrics = AsyncMock(return_value=0)
        prune_obs = AsyncMock(return_value=0)
        prune_eo = AsyncMock(return_value=0)

        with (
            patch(
                "ctpool._cli_prune_storage_profile_impl.get_settings",
                return_value=settings,
            ),
            patch("ctpool._cli_reap_impl.run_prune_metrics", prune_metrics),
            patch(
                "ctpool._cli_prune_observations_impl.run_prune_observations", prune_obs
            ),
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.run_prune_entry_outcomes",
                prune_eo,
            ),
        ):
            from ctpool._cli_prune_storage_profile_impl import (
                run_prune_for_storage_profile,
            )

            await run_prune_for_storage_profile(execute=False, console=_QUIET_CONSOLE)

    async def test_passes_dry_run_true_when_execute_is_false(self) -> None:
        """execute=False passes dry_run=True to each sub-command."""
        settings = _make_settings()
        captured: list[bool] = []

        async def _capture(**kwargs: object) -> int:
            captured.append(bool(kwargs["dry_run"]))
            return 0

        with (
            patch(
                "ctpool._cli_prune_storage_profile_impl.get_settings",
                return_value=settings,
            ),
            patch("ctpool._cli_reap_impl.run_prune_metrics", _capture),
            patch(
                "ctpool._cli_prune_observations_impl.run_prune_observations", _capture
            ),
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.run_prune_entry_outcomes",
                _capture,
            ),
        ):
            from ctpool._cli_prune_storage_profile_impl import (
                run_prune_for_storage_profile,
            )

            await run_prune_for_storage_profile(execute=False, console=_QUIET_CONSOLE)

        assert len(captured) == 3
        assert all(captured), "All sub-commands should receive dry_run=True"

    async def test_passes_dry_run_false_when_execute_is_true(self) -> None:
        """execute=True passes dry_run=False to each sub-command."""
        settings = _make_settings()
        captured: list[bool] = []

        async def _capture(**kwargs: object) -> int:
            captured.append(bool(kwargs["dry_run"]))
            return 0

        with (
            patch(
                "ctpool._cli_prune_storage_profile_impl.get_settings",
                return_value=settings,
            ),
            patch("ctpool._cli_reap_impl.run_prune_metrics", _capture),
            patch(
                "ctpool._cli_prune_observations_impl.run_prune_observations", _capture
            ),
            patch(
                "ctpool._cli_prune_entry_outcomes_impl.run_prune_entry_outcomes",
                _capture,
            ),
        ):
            from ctpool._cli_prune_storage_profile_impl import (
                run_prune_for_storage_profile,
            )

            await run_prune_for_storage_profile(execute=True, console=_QUIET_CONSOLE)

        assert len(captured) == 3
        assert not any(captured), "All sub-commands should receive dry_run=False"
