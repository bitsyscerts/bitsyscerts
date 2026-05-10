"""Unit tests for ``ctpool status`` rendering logic.

The status command must be a thin formatter over the most recent stats
snapshot — it must never run heavy live queries.  These tests inject a
canned snapshot via a stub repository so they verify exactly what gets
printed without touching the database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from ctpool import _cli_status_impl


def _payload() -> dict[str, object]:
    return {
        "storage_profile": {"storage_profile": "lite"},
        "maintenance": {
            "is_enforced": True,
            "last_prune_status": "complete",
            "last_prune_completed_at": None,
        },
        "workers": {
            "items": [
                {"is_active": True},
                {"is_active": True},
                {"is_active": False},
            ],
            "stale_count": 1,
        },
        "backfill_state": {
            "status_counts": {
                "processing": 4,
                "retrying": 1,
                "rate_limited": 0,
                "paused": 0,
                "complete": 7,
            }
        },
        "tail_freshness": {
            "stale_log_count": 0,
            "oldest_lag_seconds": 12,
        },
        "ingestion_rate": {
            "windows": [
                {
                    "window_seconds": 300,
                    "observations_per_sec": 100.0,
                    "certs_per_min": 600.0,
                    "hostnames_per_min": 1200.0,
                    "observations_per_min": 6000.0,
                    "certificates_parsed_per_min": 600.0,
                    "new_unique_certificates_per_min": 120.0,
                    "duplicate_certificates_per_min": 480.0,
                    "hostnames_observed_per_min": 1200.0,
                    "new_unique_hostnames_per_min": 30.0,
                    "known_hostnames_per_min": 1170.0,
                    "retryable_errors_per_min": 2.0,
                    "terminal_entry_errors_per_min": 1.0,
                }
            ]
        },
    }


@pytest.fixture
def _patched_repo() -> tuple[MagicMock, AsyncMock]:
    engine = MagicMock()
    engine.dispose = AsyncMock(return_value=None)

    factory_session = MagicMock()
    factory_cm = MagicMock()
    factory_cm.__aenter__ = AsyncMock(return_value=factory_session)
    factory_cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=factory_cm)

    return engine, factory


@pytest.mark.asyncio
async def test_status_prints_fresh_snapshot(_patched_repo) -> None:
    engine, factory = _patched_repo
    repo = MagicMock()
    repo.get_latest_snapshot = AsyncMock(return_value=_payload())
    repo.get_latest_snapshot_age_seconds = AsyncMock(return_value=8.0)

    console = Console(record=True, width=120)
    with (
        patch("ctpool._cli_status_impl.create_engine", return_value=engine),
        patch("ctpool._cli_status_impl.create_session_factory", return_value=factory),
        patch("ctpool._cli_status_impl.StatsSnapshotRepository", return_value=repo),
    ):
        await _cli_status_impl.run_status(
            settings=MagicMock(),
            stale_threshold_seconds=120,
            console=console,
        )

    out = console.export_text()
    assert "BitsysCerts Status" in out
    assert "fresh" in out
    assert "Storage profile: lite" in out
    assert "Workers: 2 active, 1 stale" in out
    assert "Backfill:" in out
    assert "new certs/min" in out
    assert "duplicate certs/min" in out
    assert "known hostnames/min" in out
    assert "retryable/min" in out


@pytest.mark.asyncio
async def test_status_marks_stale_snapshot(_patched_repo) -> None:
    engine, factory = _patched_repo
    repo = MagicMock()
    repo.get_latest_snapshot = AsyncMock(return_value=_payload())
    repo.get_latest_snapshot_age_seconds = AsyncMock(return_value=999.0)

    console = Console(record=True, width=120)
    with (
        patch("ctpool._cli_status_impl.create_engine", return_value=engine),
        patch("ctpool._cli_status_impl.create_session_factory", return_value=factory),
        patch("ctpool._cli_status_impl.StatsSnapshotRepository", return_value=repo),
    ):
        await _cli_status_impl.run_status(
            settings=MagicMock(),
            stale_threshold_seconds=120,
            console=console,
        )

    out = console.export_text()
    assert "stale" in out


@pytest.mark.asyncio
async def test_status_prints_clear_message_when_no_snapshot(_patched_repo) -> None:
    engine, factory = _patched_repo
    repo = MagicMock()
    repo.get_latest_snapshot = AsyncMock(return_value=None)
    repo.get_latest_snapshot_age_seconds = AsyncMock(return_value=None)

    console = Console(record=True, width=120)
    with (
        patch("ctpool._cli_status_impl.create_engine", return_value=engine),
        patch("ctpool._cli_status_impl.create_session_factory", return_value=factory),
        patch("ctpool._cli_status_impl.StatsSnapshotRepository", return_value=repo),
    ):
        await _cli_status_impl.run_status(
            settings=MagicMock(),
            stale_threshold_seconds=120,
            console=console,
        )

    out = console.export_text()
    assert "No stats snapshot is available" in out


@pytest.mark.asyncio
async def test_status_notes_when_uniqueness_metrics_absent(_patched_repo) -> None:
    engine, factory = _patched_repo
    repo = MagicMock()
    payload = _payload()
    window = payload["ingestion_rate"]["windows"][0]
    for field in (
        "new_unique_certificates_per_min",
        "duplicate_certificates_per_min",
        "new_unique_hostnames_per_min",
        "known_hostnames_per_min",
    ):
        window.pop(field)
    repo.get_latest_snapshot = AsyncMock(return_value=payload)
    repo.get_latest_snapshot_age_seconds = AsyncMock(return_value=8.0)

    console = Console(record=True, width=120)
    with (
        patch("ctpool._cli_status_impl.create_engine", return_value=engine),
        patch("ctpool._cli_status_impl.create_session_factory", return_value=factory),
        patch("ctpool._cli_status_impl.StatsSnapshotRepository", return_value=repo),
    ):
        await _cli_status_impl.run_status(
            settings=MagicMock(),
            stale_threshold_seconds=120,
            console=console,
        )

    assert "uniqueness metrics unavailable" in console.export_text()
