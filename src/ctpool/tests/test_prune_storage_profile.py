"""Unit tests for the Sprint 4 ``prune-for-storage-profile`` orchestrator.

The orchestrator is responsible for:
    * recording every invocation as a ``ct_maintenance_runs`` row,
    * reading effective settings from the DB row (with env-var fallback),
    * skipping categories whose ``retention_days`` is ``0`` (retain forever),
    * defaulting to dry-run unless ``execute=True``,
    * surfacing failures via ``status='failed'`` + ``error_message``,
    * including pruners for previously-unbounded tables (ingestion_errors,
      maintenance_runs, prune_runs, completed_backfill_ranges).

The tests stub out database I/O and category-level processing so each
behavioural requirement can be exercised in isolation.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from ctpool._cli_prune_storage_profile_impl import run_prune_for_storage_profile

_QUIET_CONSOLE = Console(quiet=True)


def _make_settings(**overrides: Any) -> MagicMock:
    """Return a Settings stub with reasonable Lite-profile defaults."""
    defaults = {
        "ct_storage_profile": "lite",
        "ct_cert_storage_mode": "metadata",
        "ct_hostname_retention_mode": "current",
        "ct_cert_retention_days": 7,
        "ct_observation_retention_days": 7,
        "ct_entry_outcome_retention_days": 7,
        "ct_metrics_retention_days": 14,
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _params_from_settings(settings: MagicMock) -> dict[str, Any]:
    """Return the dict that _read_prune_params would produce from env settings."""
    return {
        "storage_profile": settings.ct_storage_profile,
        "cert_storage_mode": settings.ct_cert_storage_mode,
        "hostname_retention_mode": settings.ct_hostname_retention_mode,
        "cert_retention_days": settings.ct_cert_retention_days,
        "observation_retention_days": settings.ct_observation_retention_days,
        "entry_outcome_retention_days": settings.ct_entry_outcome_retention_days,
        "metrics_retention_days": settings.ct_metrics_retention_days,
    }


class _Patches:
    """Context bundle that stubs all DB-touching helpers used by the run."""

    def __init__(self, settings: MagicMock) -> None:
        self.settings = settings
        self.run_id = uuid.uuid4()
        self.insert_mock = AsyncMock(return_value=self.run_id)
        self.finalize_mock = AsyncMock(return_value=None)
        self.process_mock = AsyncMock(return_value=None)
        self.count_hostnames_mock = AsyncMock(return_value=42)
        self.try_lock_mock = AsyncMock(return_value=True)
        self.release_lock_mock = AsyncMock(return_value=None)
        self.read_prune_params_mock = AsyncMock(
            return_value=_params_from_settings(settings)
        )
        self.engine = MagicMock()
        self.engine.dispose = AsyncMock(return_value=None)

    def __enter__(self) -> _Patches:
        self._stack = [
            patch(
                "ctpool._cli_prune_storage_profile_impl.get_settings",
                return_value=self.settings,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl.create_engine",
                return_value=self.engine,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl.create_session_factory",
                return_value=MagicMock(),
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl._read_prune_params",
                self.read_prune_params_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl.insert_maintenance_run",
                self.insert_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl.finalize_maintenance_run",
                self.finalize_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl._process_category",
                self.process_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl._count_hostnames",
                self.count_hostnames_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl._try_acquire_lock",
                self.try_lock_mock,
            ),
            patch(
                "ctpool._cli_prune_storage_profile_impl._release_lock",
                self.release_lock_mock,
            ),
        ]
        for p in self._stack:
            p.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        for p in reversed(self._stack):
            p.stop()


class TestRunPruneForStorageProfile:
    @pytest.mark.asyncio
    async def test_dry_run_records_dry_run_mode(self) -> None:
        """Default invocation must record a dry_run row and never fail."""
        with _Patches(_make_settings()) as ctx:
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        assert agg.mode == "dry_run"
        assert agg.status == "complete"
        ctx.insert_mock.assert_awaited_once()
        assert ctx.insert_mock.await_args.kwargs["mode"] == "dry_run"
        ctx.finalize_mock.assert_awaited_once()
        assert ctx.finalize_mock.await_args.kwargs["status"] == "complete"

    @pytest.mark.asyncio
    async def test_execute_records_execute_mode(self) -> None:
        with _Patches(_make_settings()) as ctx:
            agg = await run_prune_for_storage_profile(
                execute=True, console=_QUIET_CONSOLE
            )
        assert agg.mode == "execute"
        assert ctx.insert_mock.await_args.kwargs["mode"] == "execute"

    @pytest.mark.asyncio
    async def test_retention_zero_skips_category(self) -> None:
        """retention_days=0 (Archive profile) → category not processed."""
        settings = _make_settings(ct_metrics_retention_days=0)
        with _Patches(settings) as ctx:
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        processed = [
            call.kwargs["category"].name for call in ctx.process_mock.await_args_list
        ]
        assert "ingestion_metrics" not in processed
        assert any(c.is_disabled for c in agg.categories)

    @pytest.mark.asyncio
    async def test_failure_path_records_failed_status(self) -> None:
        with _Patches(_make_settings()) as ctx:
            ctx.process_mock.side_effect = RuntimeError("boom")
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        assert agg.status == "failed"
        assert agg.error_message == "boom"
        assert ctx.finalize_mock.await_args.kwargs["status"] == "failed"
        assert ctx.finalize_mock.await_args.kwargs["error_message"] == "boom"

    @pytest.mark.asyncio
    async def test_preserved_hostnames_are_recorded(self) -> None:
        with _Patches(_make_settings()) as ctx:
            ctx.count_hostnames_mock.return_value = 1234
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        assert agg.preserved_hostnames == 1234
        assert ctx.finalize_mock.await_args.kwargs["preserved_hostnames"] == 1234

    @pytest.mark.asyncio
    async def test_json_output_does_not_raise(self) -> None:
        with _Patches(_make_settings()):
            agg = await run_prune_for_storage_profile(
                json_output=True, console=_QUIET_CONSOLE
            )
        assert agg.status == "complete"

    @pytest.mark.asyncio
    async def test_concurrent_prune_is_rejected(self) -> None:
        """When the advisory lock is held, the second prune raises clearly."""
        from ctpool._cli_prune_storage_profile_impl import ConcurrentPruneError

        with _Patches(_make_settings()) as ctx:
            ctx.try_lock_mock.return_value = False
            with pytest.raises(ConcurrentPruneError):
                await run_prune_for_storage_profile(
                    execute=True, console=_QUIET_CONSOLE
                )
        # No maintenance row is recorded when the lock is unavailable.
        ctx.insert_mock.assert_not_awaited()
        ctx.finalize_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_backed_settings_override_env(self) -> None:
        """DB-backed settings are used when present; env values are ignored."""
        env_settings = _make_settings(ct_observation_retention_days=7)
        db_params = dict(_params_from_settings(env_settings))
        # Simulate UI change: DB says 1 day, env says 7 days.
        db_params["observation_retention_days"] = 1
        with _Patches(env_settings) as ctx:
            ctx.read_prune_params_mock.return_value = db_params
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        obs_cat = next(c for c in agg.categories if c.name == "observations")
        assert obs_cat.retention_days == 1

    @pytest.mark.asyncio
    async def test_plan_includes_unbounded_table_categories(self) -> None:
        """Plan must include pruners for previously-unbounded operational tables."""
        with _Patches(_make_settings()):
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        category_names = {c.name for c in agg.categories}
        assert "ingestion_errors" in category_names
        assert "maintenance_runs" in category_names
        assert "prune_runs" in category_names
        assert "completed_backfill_ranges" in category_names

    @pytest.mark.asyncio
    async def test_operational_categories_have_fixed_retention(self) -> None:
        """Operational table categories use fixed retention windows."""
        with _Patches(_make_settings()):
            agg = await run_prune_for_storage_profile(console=_QUIET_CONSOLE)
        cats = {c.name: c for c in agg.categories}
        assert cats["maintenance_runs"].retention_days == 90
        assert cats["prune_runs"].retention_days == 90
        assert cats["completed_backfill_ranges"].retention_days == 30
