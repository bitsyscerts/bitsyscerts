"""HTTP-level tests for GET /v1/stats."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings
from certsapi.stats.models import (
    BackfillRangeStats,
    DbContentionStats,
    EntryOutcomeStats,
    IngestionRateStats,
    LogStatsItem,
    StatsResponse,
    StorageProjection,
    StorageStats,
    TailFreshnessStats,
    WorkerSummary,
    WorkerSummaryItem,
)
from certsapi.stats.router import _get_stats_service

_UNIT_TEST_SETTINGS = Settings.model_validate(
    {
        "database_url": "postgresql+psycopg://localhost/test",
        "expose_stats_api": True,
    }
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
        "db_contention": DbContentionStats(
            status="initializing",
            degraded_mode_active=False,
            pressure_ema=0.0,
            base_sleep_seconds=0.0,
            shared_batch_size_cap=None,
            effective_batch_size_cap=None,
            updated_at=None,
            notes=["No shared DB contention state has been recorded yet."],
        ),
        "ingestion_rate": IngestionRateStats(windows=[]),
        "tail_freshness": TailFreshnessStats(
            stale_threshold_seconds=300,
            stale_log_count=0,
            oldest_lag_seconds=None,
            median_lag_seconds=None,
        ),
        "entry_outcomes": EntryOutcomeStats(
            stored=0,
            parse_error=0,
            unsupported_entry_type=0,
            skipped_by_policy=0,
        ),
        "backfill_ranges": BackfillRangeStats(
            pending=0,
            in_progress=0,
            stale_in_progress=0,
            completed=0,
            failed=0,
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
            "db_contention",
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

    async def test_worker_summary_serializes_rich_activity_fields(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats(
            workers=WorkerSummary(
                active_total=1,
                stale_total=0,
                tail_active=1,
                backfill_active=0,
                stats_active=0,
                maintenance_active=0,
                unknown_active=0,
                items=[
                    WorkerSummaryItem(
                        worker_id="host:1234",
                        worker_kind="tail",
                        log_source_id=str(uuid.uuid4()),
                        log_name="Test Log",
                        log_url="https://ct.test/",
                        log_operator="Test Operator",
                        direction="forward",
                        status="processing",
                        is_stale=False,
                        last_heartbeat_at="2025-01-01T00:00:00Z",
                        last_heartbeat_age_seconds=5,
                        started_at="2025-01-01T00:00:00Z",
                        current_index=123,
                        checkpoint_index=120,
                        batch_start_index=123,
                        batch_end_index=223,
                        processed_entries=50,
                        stored_certificates=40,
                        duplicate_certificates=10,
                        observed_hostnames=20,
                        new_hostnames=5,
                        parse_errors=0,
                        retryable_errors=1,
                        terminal_errors=0,
                        observations_per_min=60.0,
                        new_unique_certificates_per_min=24.0,
                        duplicate_certificates_per_min=6.0,
                        new_unique_hostnames_per_min=3.0,
                        known_hostnames_per_min=9.0,
                        retry_count=2,
                        next_retry_at="2025-01-01T00:05:00Z",
                        rate_limited_until="2025-01-01T00:10:00Z",
                        last_error_type="RateLimitError",
                        last_error_message="too many requests",
                    )
                ],
            )
        )
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")

        worker = resp.json()["workers"]["items"][0]
        assert worker["log_url"] == "https://ct.test/"
        assert worker["log_operator"] == "Test Operator"
        assert worker["checkpoint_index"] == 120
        assert worker["observations_per_min"] == 60.0
        assert worker["rate_limited_until"] == "2025-01-01T00:10:00Z"

    async def test_db_contention_block_serializes(self) -> None:
        svc = AsyncMock()
        svc.get_stats.return_value = _make_stats(
            db_contention=DbContentionStats(
                status="throttling",
                degraded_mode_active=False,
                pressure_ema=0.25,
                base_sleep_seconds=0.5,
                shared_batch_size_cap=32,
                effective_batch_size_cap=32,
                updated_at=datetime.now(UTC),
                notes=["Shared DB contention throttling is currently active."],
            )
        )
        async with _client_with_service(svc) as client:
            resp = await client.get("/v1/stats")

        contention = resp.json()["db_contention"]
        assert contention["status"] == "throttling"
        assert contention["effective_batch_size_cap"] == 32
