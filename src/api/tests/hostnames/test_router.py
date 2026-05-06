"""HTTP-level tests for GET /v1/hostnames using mocked HostnameService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings
from certsapi.hostnames.dependencies import get_hostname_service
from certsapi.hostnames.models import HostnameListResponse, HostnameResult

_UNIT_TEST_SETTINGS = Settings.model_validate(
    {"database_url": "postgresql+psycopg://localhost/test"}
)


def _make_result(hostname: str = "api.example.com") -> HostnameResult:
    ts = datetime(2024, 6, 1, tzinfo=UTC)
    return HostnameResult(
        id=uuid.uuid4(),
        hostname=hostname,
        registrable_domain="example.com",
        is_wildcard=False,
        first_seen_ct=None,
        last_seen_ct=None,
        latest_cert_not_before=ts,
        latest_cert_not_after=ts,
        latest_cert=None,
    )


def _empty_response() -> HostnameListResponse:
    return HostnameListResponse(items=[], next_cursor=None, total_returned=0)


@pytest.fixture()
def mock_service() -> AsyncMock:
    svc = AsyncMock()
    svc.search.return_value = _empty_response()
    return svc


@pytest.fixture()
def client_with_mock(app: object, mock_service: AsyncMock) -> AsyncClient:
    _app = create_app(settings=_UNIT_TEST_SETTINGS)
    _app.dependency_overrides[get_hostname_service] = lambda: mock_service  # type: ignore[attr-defined]
    return AsyncClient(transport=ASGITransport(app=_app), base_url="http://test")


class TestSearchHostnamesRouter:
    async def test_missing_q_returns_422(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/v1/hostnames")
        assert resp.status_code == 422

    async def test_valid_request_returns_200(
        self, app: object, mock_service: AsyncMock
    ) -> None:
        _app = create_app(settings=_UNIT_TEST_SETTINGS)
        _app.dependency_overrides[get_hostname_service] = lambda: mock_service  # type: ignore[attr-defined]
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/hostnames", params={"q": "example.com"})
        assert resp.status_code == 200

    async def test_response_has_items_and_next_cursor_keys(
        self, app: object, mock_service: AsyncMock
    ) -> None:
        mock_service.search.return_value = HostnameListResponse(
            items=[_make_result()], next_cursor=None, total_returned=1
        )
        _app = create_app(settings=_UNIT_TEST_SETTINGS)
        _app.dependency_overrides[get_hostname_service] = lambda: mock_service  # type: ignore[attr-defined]
        async with AsyncClient(
            transport=ASGITransport(app=_app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/hostnames", params={"q": "example.com"})
        body = resp.json()
        assert "items" in body
        assert "next_cursor" in body
        assert "total_returned" in body

    async def test_invalid_sort_returns_422(self, http_client: AsyncClient) -> None:
        resp = await http_client.get(
            "/v1/hostnames", params={"q": "x", "sort": "invalid_sort"}
        )
        assert resp.status_code == 422

    async def test_limit_above_200_returns_422(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/v1/hostnames", params={"q": "x", "limit": "201"})
        assert resp.status_code == 422

    async def test_limit_below_1_returns_422(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/v1/hostnames", params={"q": "x", "limit": "0"})
        assert resp.status_code == 422
