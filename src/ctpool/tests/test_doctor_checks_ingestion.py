"""Unit tests for ctpool.doctor_checks_ingestion.

All DB-dependent checks use AsyncMock to avoid requiring a live database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ctpool.config import Settings
from ctpool.doctor_checks_ingestion import (
    check_disk_space,
    check_failed_ranges,
    check_http_errors,
    check_log_discovery,
    check_migration_head,
    check_stale_claims,
    check_tail_lag,
)
from ctpool.doctor_models import Severity


def _settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+psycopg://x:x@localhost/x",
        "ct_doctor_tail_lag_warning_seconds": 600,
        "ct_doctor_tail_lag_critical_seconds": 3600,
        "ct_doctor_disk_warning_pct": 80.0,
        "ct_doctor_disk_critical_pct": 90.0,
        "ct_doctor_http_error_warning": 1,
        "ct_doctor_http_error_critical": 100,
        "ct_backfill_claim_timeout_seconds": 1800,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[call-arg]


def _async_scalar(value) -> AsyncMock:
    mock = AsyncMock()
    mock.scalar_one = MagicMock(return_value=value)
    return mock


def _async_first(value) -> AsyncMock:
    mock = AsyncMock()
    mock.first = MagicMock(return_value=value)
    return mock


# ---------------------------------------------------------------------------
# check_migration_head
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_migration_head_ok():
    settings = _settings()
    with (
        patch("ctpool.doctor_checks_ingestion.get_alembic_head", return_value="rev1"),
        patch(
            "ctpool.doctor_checks_ingestion.get_current_revision", return_value="rev1"
        ),
    ):
        result = await check_migration_head(settings)
    assert result.severity == Severity.OK
    assert "rev1" in result.message


@pytest.mark.asyncio
async def test_check_migration_head_out_of_date():
    settings = _settings()
    with (
        patch("ctpool.doctor_checks_ingestion.get_alembic_head", return_value="rev2"),
        patch(
            "ctpool.doctor_checks_ingestion.get_current_revision", return_value="rev1"
        ),
    ):
        result = await check_migration_head(settings)
    assert result.severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_check_migration_head_exception():
    settings = _settings()
    with patch(
        "ctpool.doctor_checks_ingestion.get_alembic_head",
        side_effect=RuntimeError("boom"),
    ):
        result = await check_migration_head(settings)
    assert result.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# check_log_discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_log_discovery_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(5))
    result = await check_log_discovery(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_log_discovery_no_logs():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_log_discovery(session)
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_tail_lag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_tail_lag_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(60.0))
    result = await check_tail_lag(session, _settings())
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_tail_lag_warning():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(700.0))
    result = await check_tail_lag(session, _settings())
    assert result.severity == Severity.WARNING


@pytest.mark.asyncio
async def test_check_tail_lag_critical():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(4000.0))
    result = await check_tail_lag(session, _settings())
    assert result.severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_check_tail_lag_no_cursors():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(None))
    result = await check_tail_lag(session, _settings())
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


def test_check_disk_space_ok(tmp_path):
    settings = _settings(ct_disk_check_path=str(tmp_path))
    with patch("shutil.disk_usage") as mock_du:
        mock_du.return_value = MagicMock(used=50, total=100, free=50)
        result = check_disk_space(settings)
    assert result.severity == Severity.OK


def test_check_disk_space_warning(tmp_path):
    settings = _settings(ct_disk_check_path=str(tmp_path))
    with patch("shutil.disk_usage") as mock_du:
        mock_du.return_value = MagicMock(used=85, total=100, free=15)
        result = check_disk_space(settings)
    assert result.severity == Severity.WARNING


def test_check_disk_space_critical(tmp_path):
    settings = _settings(ct_disk_check_path=str(tmp_path))
    with patch("shutil.disk_usage") as mock_du:
        mock_du.return_value = MagicMock(used=95, total=100, free=5)
        result = check_disk_space(settings)
    assert result.severity == Severity.CRITICAL


def test_check_disk_space_path_missing():
    settings = _settings(ct_disk_check_path="/nonexistent/path")
    result = check_disk_space(settings)
    assert result.severity == Severity.WARNING


# ---------------------------------------------------------------------------
# check_http_errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_http_errors_ok():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_http_errors(session, _settings())
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_http_errors_warning():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(5))
    result = await check_http_errors(session, _settings())
    assert result.severity == Severity.WARNING


@pytest.mark.asyncio
async def test_check_http_errors_critical():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(200))
    result = await check_http_errors(session, _settings())
    assert result.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# check_failed_ranges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_failed_ranges_none():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_failed_ranges(session)
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_failed_ranges_some():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(3))
    result = await check_failed_ranges(session)
    assert result.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# check_stale_claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_stale_claims_none():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(0))
    result = await check_stale_claims(session, _settings())
    assert result.severity == Severity.OK


@pytest.mark.asyncio
async def test_check_stale_claims_some():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_async_scalar(2))
    result = await check_stale_claims(session, _settings())
    assert result.severity == Severity.WARNING
