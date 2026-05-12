"""Unit tests for the Sprint 4B maintenance loop.

The default cycle is now lightweight: it always runs
``prune-for-storage-profile`` and **only** runs the deep audit-gap scan
when the operator explicitly opts in via
``BITSYSCERTS_ENABLE_SCHEDULED_AUDIT=true`` AND the audit interval has
elapsed.  Audit failures must never block the prune step.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool import maintenance_runner
from ctpool.maintenance_runner import run_maintenance_loop, run_maintenance_once


def _make_registry_session_factory() -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _settings(
    *,
    enable_audit: bool = False,
    audit_interval: int = 21600,
) -> MagicMock:
    s = MagicMock()
    s.ct_maintenance_interval_seconds = 3600
    s.bitsyscerts_enable_scheduled_audit = enable_audit
    s.bitsyscerts_audit_interval_seconds = audit_interval
    return s


@pytest.fixture(autouse=True)
def _reset_audit_clock() -> None:
    """Reset the module-level audit interval clock between tests."""
    maintenance_runner._LAST_SCHEDULED_AUDIT_AT = 0.0  # type: ignore[attr-defined]


class TestRunMaintenanceOnce:
    @pytest.mark.asyncio
    async def test_prune_runs_audit_does_not_by_default(self) -> None:
        """Default settings (audit disabled) must not run audit-gaps."""
        prune_mock = AsyncMock()
        audit_mock = AsyncMock()
        with (
            patch("ctpool.maintenance_runner._prune_for_profile", prune_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", audit_mock),
        ):
            await run_maintenance_once(_settings())
        prune_mock.assert_awaited_once()
        audit_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_audit_runs_when_opted_in_and_due(self) -> None:
        prune_mock = AsyncMock()
        audit_mock = AsyncMock()
        with (
            patch("ctpool.maintenance_runner._prune_for_profile", prune_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", audit_mock),
        ):
            await run_maintenance_once(_settings(enable_audit=True))
        prune_mock.assert_awaited_once()
        audit_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_does_not_rerun_within_interval(self) -> None:
        """Second invocation inside the interval window must not re-run audit."""
        prune_mock = AsyncMock()
        audit_mock = AsyncMock()
        with (
            patch("ctpool.maintenance_runner._prune_for_profile", prune_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", audit_mock),
        ):
            settings = _settings(enable_audit=True, audit_interval=21600)
            await run_maintenance_once(settings)
            await run_maintenance_once(settings)
        assert prune_mock.await_count == 2
        audit_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_block_prune(self) -> None:
        async def _audit_fail(_s: object, _c: object) -> None:
            raise RuntimeError("audit blew up")

        prune_mock = AsyncMock()
        with (
            patch("ctpool.maintenance_runner._prune_for_profile", prune_mock),
            patch("ctpool.maintenance_runner._check_audit_gaps", _audit_fail),
        ):
            # Must not raise; prune must still have run.
            await run_maintenance_once(_settings(enable_audit=True))
        prune_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_prune_failure_does_not_propagate(self) -> None:
        async def _prune_fail(_s: object, _c: object) -> None:
            raise RuntimeError("prune blew up")

        with patch("ctpool.maintenance_runner._prune_for_profile", _prune_fail):
            await run_maintenance_once(_settings())


class TestPruneForProfile:
    @pytest.mark.asyncio
    async def test_invokes_orchestrator_with_execute_true(self) -> None:
        from ctpool.maintenance_runner import _prune_for_profile

        run_mock = AsyncMock()
        with patch(
            "ctpool._cli_prune_storage_profile_impl.run_prune_for_storage_profile",
            run_mock,
        ):
            from rich.console import Console  # noqa: PLC0415

            await _prune_for_profile(_settings(), Console(quiet=True))

        run_mock.assert_awaited_once()
        assert run_mock.await_args.kwargs["execute"] is True


class TestCheckAuditGaps:
    @pytest.mark.asyncio
    async def test_skips_gracefully_when_module_not_available(self) -> None:
        with patch.dict(
            "sys.modules",
            {"ctpool._cli_check_audit_impl": None},  # type: ignore[dict-item]
        ):
            from rich.console import Console  # noqa: PLC0415

            from ctpool.maintenance_runner import _check_audit_gaps  # noqa: PLC0415

            await _check_audit_gaps(_settings(), Console(quiet=True))


@pytest.mark.asyncio
async def test_run_maintenance_loop_registers_and_heartbeats_worker() -> None:
    """Maintenance loop registers a singleton worker and heartbeats each cycle."""
    settings = _settings()
    factory = _make_registry_session_factory()
    engine = MagicMock()
    engine.dispose = AsyncMock()
    row = MagicMock(id=uuid.uuid4())
    heartbeat_mock = AsyncMock()

    with (
        patch("ctpool.maintenance_runner.create_engine", return_value=engine),
        patch("ctpool.maintenance_runner.create_session_factory", return_value=factory),
        patch(
            "ctpool.maintenance_runner.register_worker",
            AsyncMock(return_value=row),
        ) as register_mock,
        patch("ctpool.maintenance_runner.heartbeat_worker", heartbeat_mock),
        patch(
            "ctpool.maintenance_runner.mark_worker_stopped",
            AsyncMock(),
        ) as stop_mock,
        patch("ctpool.maintenance_runner.run_maintenance_once", AsyncMock()),
        patch(
            "ctpool.maintenance_runner.asyncio.sleep",
            AsyncMock(side_effect=asyncio.CancelledError()),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await run_maintenance_loop(settings)

    register_mock.assert_awaited_once()
    assert [call.kwargs["status"] for call in heartbeat_mock.await_args_list] == [
        "processing",
        "idle",
    ]
    stop_mock.assert_awaited_once()
    engine.dispose.assert_awaited_once()
