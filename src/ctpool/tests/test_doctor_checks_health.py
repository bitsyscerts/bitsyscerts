"""Unit tests for ctpool.doctor_checks_health.

All DB-dependent checks use AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ctpool.config import Settings
from ctpool.doctor_checks_health import (
    check_cert_count,
    check_entry_outcomes_backlog,
    check_hostname_count,
    check_metrics_freshness,
    check_observation_orphans,
    check_open_audit_findings,
    check_prune_run_health,
)
from ctpool.doctor_models import Severity


def _settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+psycopg://x:x@localhost/x",
        "ct_doctor_metrics_stale_warning_seconds": 900,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[call-arg]


def _async_scalar(value) -> AsyncMock:
    m = AsyncMock()
    m.scalar_one = MagicMock(return_value=value)
    return m


def _async_first(value) -> AsyncMock:
    m = AsyncMock()
    m.first = MagicMock(return_value=value)
    return m


def _async_one(values) -> AsyncMock:
    m = AsyncMock()
    m.one = MagicMock(return_value=values)
    return m


# ---------------------------------------------------------------------------
# check_hostname_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_hostname_count_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(500))
    result = await check_hostname_count(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_hostname_count_zero():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_hostname_count(session)
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_cert_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_cert_count_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(100))
    result = await check_cert_count(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_cert_count_zero():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_cert_count(session)
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_open_audit_findings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_open_audit_findings_none():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_open_audit_findings(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_open_audit_findings_critical():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(2))
    result = await check_open_audit_findings(session)
    assert result.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# check_metrics_freshness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_metrics_freshness_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(30.0))
    result = await check_metrics_freshness(session, _settings())
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_metrics_freshness_stale_no_workers():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(2000.0))
    result = await check_metrics_freshness(session, _settings(), expect_workers=False)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_metrics_freshness_stale_with_workers():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(2000.0))
    result = await check_metrics_freshness(session, _settings(), expect_workers=True)
    assert result.severity == Severity.WARNING


@pytest.mark.asyncio
async def test_check_metrics_freshness_no_rows_with_workers():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(None))
    result = await check_metrics_freshness(session, _settings(), expect_workers=True)
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_entry_outcomes_backlog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_entry_outcomes_backlog_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(100))
    result = await check_entry_outcomes_backlog(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_entry_outcomes_backlog_warning():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(600_000))
    result = await check_entry_outcomes_backlog(session)
    assert result.severity == Severity.WARNING


@pytest.mark.asyncio
async def test_check_entry_outcomes_backlog_critical():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(6_000_000))
    result = await check_entry_outcomes_backlog(session)
    assert result.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# check_prune_run_health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_prune_run_health_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_first(("complete", None)))
    result = await check_prune_run_health(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_prune_run_health_no_rows():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_first(None))
    result = await check_prune_run_health(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_prune_run_health_failed():
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=_async_first(("failed", "DB connection lost"))
    )
    result = await check_prune_run_health(session)
    assert result.severity == Severity.WARNING
    assert "DB connection lost" in result.detail


# ---------------------------------------------------------------------------
# check_observation_orphans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_observation_orphans_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_one((0, 1000)))
    result = await check_observation_orphans(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_observation_orphans_no_rows():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_one((0, 0)))
    result = await check_observation_orphans(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_observation_orphans_warning():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_one((100, 1000)))
    result = await check_observation_orphans(session)
    assert result.severity == Severity.WARNING


@pytest.mark.asyncio
async def test_check_observation_orphans_critical():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_one((300, 1000)))
    result = await check_observation_orphans(session)
    assert result.severity == Severity.CRITICAL
