"""Unit tests for maintenance_runner module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ctpool.maintenance_runner import run_maintenance_once


def _make_settings(
    maintenance_interval: int = 3600,
    metrics_retention_days: int = 30,
    observation_retention_days: int = 7,
    entry_outcome_retention_days: int = 7,
) -> MagicMock:
    s = MagicMock()
    s.ct_maintenance_interval_seconds = maintenance_interval
    s.ct_metrics_retention_days = metrics_retention_days
    s.ct_observation_retention_days = observation_retention_days
    s.ct_entry_outcome_retention_days = entry_outcome_retention_days
    return s


class TestRunMaintenanceOnce:
    async def test_runs_all_four_steps_without_error(self) -> None:
        settings = _make_settings()
        with (
            patch(
                "ctpool.maintenance_runner._prune_metrics",
                new_callable=lambda: lambda: AsyncMock(),
            ) as pm,
            patch(
                "ctpool.maintenance_runner._prune_observations",
                new_callable=lambda: lambda: AsyncMock(),
            ) as po,
            patch(
                "ctpool.maintenance_runner._prune_entry_outcomes",
                new_callable=lambda: lambda: AsyncMock(),
            ) as pe,
            patch(
                "ctpool.maintenance_runner._check_audit_gaps",
                new_callable=lambda: lambda: AsyncMock(),
            ) as ca,
        ):
            pm.return_value = AsyncMock()
            po.return_value = AsyncMock()
            pe.return_value = AsyncMock()
            ca.return_value = AsyncMock()
            # The patching approach above won't work for coroutine functions.
            # Use a simpler patch strategy:
            pass

        # Simpler: patch the helper coroutines directly
        prune_metrics_mock = AsyncMock()
        prune_obs_mock = AsyncMock()
        prune_eo_mock = AsyncMock()
        audit_mock = AsyncMock()

        with (
            patch("ctpool.maintenance_runner._prune_metrics", prune_metrics_mock),
            patch("ctpool.maintenance_runner._prune_observations", prune_obs_mock),
            patch("ctpool.maintenance_runner._prune_entry_outcomes", prune_eo_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", audit_mock),
        ):
            await run_maintenance_once(settings)

        prune_metrics_mock.assert_awaited_once()
        prune_obs_mock.assert_awaited_once()
        prune_eo_mock.assert_awaited_once()
        audit_mock.assert_awaited_once()

    async def test_continues_after_step_failure(self) -> None:
        """A failure in one step should not block subsequent steps."""
        settings = _make_settings()

        async def _fail(s: object, c: object) -> None:
            raise RuntimeError("step failed")

        obs_mock = AsyncMock()
        eo_mock = AsyncMock()
        audit_mock = AsyncMock()

        with (
            patch("ctpool.maintenance_runner._prune_metrics", _fail),
            patch("ctpool.maintenance_runner._prune_observations", obs_mock),
            patch("ctpool.maintenance_runner._prune_entry_outcomes", eo_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", audit_mock),
        ):
            # Should not raise even though _prune_metrics raises
            await run_maintenance_once(settings)

        obs_mock.assert_awaited_once()
        eo_mock.assert_awaited_once()
        audit_mock.assert_awaited_once()


class TestCheckAuditGaps:
    async def test_skips_gracefully_when_module_not_available(self) -> None:
        """_check_audit_gaps should not raise when ImportError occurs."""
        settings = _make_settings()

        with patch.dict(
            "sys.modules",
            {"ctpool._cli_check_audit_impl": None},  # type: ignore[dict-item]
        ):
            from rich.console import Console  # noqa: PLC0415

            from ctpool.maintenance_runner import _check_audit_gaps  # noqa: PLC0415

            console = Console(quiet=True)
            # Should complete without raising
            await _check_audit_gaps(settings, console)
