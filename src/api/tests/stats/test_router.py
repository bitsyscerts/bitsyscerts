"""HTTP-level tests for GET /v1/stats."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings
from certsapi.stats.models import (
    LogStatsItem,
    StatsResponse,
    StorageProjection,
    StorageStats,
)
from certsapi.stats.router import _get_stats_service

_UNIT_TEST_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)


def _make_storage() -> StorageStats:
    return StorageStats(
        total_size_bytes=1024 * 1024,
        total_size_pretty="1 MB",
        tables=[],
    )


def _make_stats(**kwargs: object) -> StatsResponse:
    defaults: dict[str, object] = {
        "total_hostnames": 0,
        "total_certificates": 0,
        "total_logs": 0,
        "storage": _make_storage(),
        "storage_projection": StorageProjection(
            status="insufficient_backfill_plan",
            database_size_bytes=1024,
            ct_observations_count=0,
            certificates_count=0,
            hostnames_count=0,
            certificate_hostnames_count=0,
            planned_observations_total=0,
            planned_observations_completed=0,
            planned_observations_remaining=0,
            sync_percent_by_observation=None,
            bytes_per_observation_current=None,
            projected_remaining_database_size_bytes=None,
            projected_final_database_size_bytes=None,
            storage_percent_of_projected=None,
            projection_low_bytes=None,
            projection_current_bytes=None,
            projection_high_bytes=None,
            notes=[],
        ),
        "logs": [],
    }
    defaults.update(kwargs)
    return StatsResponse(**defaults)  # type: ignore[arg-type]


def _client_with_service(service: object) -> AsyncClient:
    app = create_app(settings=_UNIT_TEST_SETTINGS)
    app.dependency_overrides[_get_stats_service] = lambda: service  # type: ignore[attr-defined]
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestStatsRouter:
    async def test_returns_200(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats()
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")
        assert resp.status_code == 200

    async def test_response_has_required_top_level_keys(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats(total_hostnames=5)
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")
        body = resp.json()
        for key in (
            "total_hostnames",
            "total_certificates",
            "total_logs",
            "storage",
            "storage_projection",
            "logs",
        ):
            assert key in body

    async def test_logs_array_present_when_empty(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats()
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")
        assert resp.json()["logs"] == []

    async def test_logs_array_contains_per_log_data(self) -> None:
        now = datetime.now(UTC)
        log_item = LogStatsItem(
            log_id=uuid.uuid4(),
            description="Test",
            url="https://ct.test/",
            log_state="usable",
            tail_position=100,
            last_tail_sync=now,
            backfill_complete_pct=50.0,
        )
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats(total_logs=1, logs=[log_item])
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")
        logs = resp.json()["logs"]
        assert len(logs) == 1
        assert logs[0]["description"] == "Test"

    async def test_storage_projection_serializes_nullable_disk_fields(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats()
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")
        projection = resp.json()["storage_projection"]
        assert projection["disk_total_bytes"] is None
        assert projection["projected_fits_on_disk"] is None
