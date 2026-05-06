"""HTTP-level tests for GET /health."""

from __future__ import annotations

from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings
from certsapi.health.models import HealthResponse
from certsapi.health.router import _get_health_service

_UNIT_TEST_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)


def _client_with_service(service: object) -> AsyncClient:
    app = create_app(settings=_UNIT_TEST_SETTINGS)
    app.dependency_overrides[_get_health_service] = lambda: service  # type: ignore[attr-defined]
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestHealthRouter:
    async def test_healthy_db_returns_200_ok(self) -> None:
        svc = AsyncMock()
        svc.check.return_value = HealthResponse(db="ok")
        async with _client_with_service(svc) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "db": "ok"}

    async def test_unhealthy_db_still_returns_200(self) -> None:
        svc = AsyncMock()
        svc.check.return_value = HealthResponse(db="error")
        async with _client_with_service(svc) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["db"] == "error"

    async def test_response_always_has_status_ok(self) -> None:
        svc = AsyncMock()
        svc.check.return_value = HealthResponse(db="error")
        async with _client_with_service(svc) as client:
            resp = await client.get("/health")
        assert resp.json()["status"] == "ok"
