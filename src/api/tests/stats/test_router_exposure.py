"""Tests for default and opt-out stats API exposure semantics."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings
from certsapi.stats.router import _get_stats_service

_DEFAULT_STATS_SETTINGS = Settings.model_validate(
    {
        "database_url": "postgresql+psycopg://localhost/test",
    }
)

_DISABLED_STATS_SETTINGS = Settings.model_validate(
    {
        "database_url": "postgresql+psycopg://localhost/test",
        "expose_stats_api": False,
    }
)


def _default_stats_service() -> AsyncMock:
    service = AsyncMock()
    service.get_stats.return_value = {
        "snapshot": {
            "generated_at": None,
            "age_seconds": None,
            "is_stale": False,
            "stale_threshold_seconds": 120,
            "source": "none",
        },
        "total_hostnames": 0,
        "storage_profile": None,
        "total_certificates": 0,
        "total_logs": 0,
        "storage": {
            "total_size_bytes": 0,
            "total_size_pretty": "0 B",
            "tables": [],
        },
        "storage_projection": {
            "status": "insufficient_backfill_plan",
            "database_size_bytes": 0,
            "ct_observations_count": 0,
            "certificates_count": 0,
            "hostnames_count": 0,
            "certificate_hostnames_count": 0,
            "planned_observations_total": 0,
            "planned_observations_completed": 0,
            "planned_observations_remaining": 0,
            "sync_percent_by_observation": None,
            "bytes_per_observation_current": None,
            "projected_remaining_database_size_bytes": None,
            "projected_final_database_size_bytes": None,
            "storage_percent_of_projected": None,
            "projection_low_bytes": None,
            "projection_current_bytes": None,
            "projection_high_bytes": None,
            "disk_total_bytes": None,
            "disk_used_bytes": None,
            "disk_free_bytes": None,
            "disk_free_percent": None,
            "configured_min_free_disk_bytes": None,
            "projected_disk_free_after_sync_bytes": None,
            "projected_fits_on_disk": None,
            "notes": [],
        },
        "db_contention": {
            "status": "initializing",
            "degraded_mode_active": False,
            "pressure_ema": 0.0,
            "base_sleep_seconds": 0.0,
            "shared_batch_size_cap": None,
            "effective_batch_size_cap": None,
            "updated_at": None,
            "notes": ["No shared DB contention state has been recorded yet."],
        },
        "ingestion_rate": {"windows": []},
        "tail_freshness": {
            "stale_threshold_seconds": 300,
            "stale_log_count": 0,
            "oldest_lag_seconds": None,
            "median_lag_seconds": None,
        },
        "entry_outcomes": {
            "stored": 0,
            "parse_error": 0,
            "unsupported_entry_type": 0,
            "skipped_by_policy": 0,
        },
        "backfill_ranges": {
            "pending": 0,
            "in_progress": 0,
            "stale_in_progress": 0,
            "completed": 0,
            "failed": 0,
        },
        "backfill_health": None,
        "metrics_retention": None,
        "audit_health": None,
        "logs": [],
        "workers": None,
        "backfill_state": None,
        "ingestion_health": None,
        "maintenance": None,
    }
    return service


def _default_enabled_app() -> FastAPI:
    app = create_app(settings=_DEFAULT_STATS_SETTINGS)
    app.dependency_overrides[_get_stats_service] = _default_stats_service
    return app


async def test_stats_endpoint_is_registered_by_default() -> None:
    """GET /v1/stats is available under default self-hosted settings."""
    app = _default_enabled_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/v1/stats")

    assert response.status_code == 200


async def test_openapi_includes_stats_endpoint_by_default() -> None:
    """OpenAPI advertises /v1/stats under default settings."""
    app = _default_enabled_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/v1/stats" in response.json()["paths"]


async def test_root_advertises_stats_endpoint_by_default() -> None:
    """Root inventory includes /v1/stats under default settings."""
    app = _default_enabled_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    paths = [entry["path"] for entry in response.json()["endpoints"]]
    assert "/v1/stats" in paths


async def test_stats_endpoint_returns_404_when_exposure_disabled() -> None:
    """GET /v1/stats is not available when exposure is disabled."""
    app = create_app(settings=_DISABLED_STATS_SETTINGS)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/v1/stats")
    assert response.status_code == 404


async def test_openapi_omits_stats_endpoint_when_exposure_disabled() -> None:
    """OpenAPI does not advertise /v1/stats when exposure is disabled."""
    app = create_app(settings=_DISABLED_STATS_SETTINGS)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/v1/stats" not in response.json()["paths"]


async def test_root_omits_stats_endpoint_when_exposure_disabled() -> None:
    """Root inventory omits /v1/stats when exposure is explicitly disabled."""
    app = create_app(settings=_DISABLED_STATS_SETTINGS)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    paths = [entry["path"] for entry in response.json()["endpoints"]]
    assert "/v1/stats" not in paths
