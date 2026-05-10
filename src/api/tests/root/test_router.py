"""HTTP-level tests for GET / (root index endpoint)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from certsapi.app import create_app
from certsapi.config import Settings

_DISABLED_STATS_SETTINGS = Settings.model_validate(
    {
        "database_url": "postgresql+psycopg://localhost/test",
        "expose_stats_api": False,
    }
)


class TestRootRouter:
    async def test_returns_200(self, http_client: AsyncClient) -> None:
        resp = await http_client.get("/")
        assert resp.status_code == 200

    async def test_response_lists_hostnames_endpoint(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/")
        paths = [e["path"] for e in resp.json()["endpoints"]]
        assert "/v1/hostnames" in paths

    async def test_response_lists_certificates_endpoint(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/")
        paths = [e["path"] for e in resp.json()["endpoints"]]
        assert "/v1/certificates/{fingerprint_sha256}" in paths

    async def test_response_lists_health_endpoint(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/")
        paths = [e["path"] for e in resp.json()["endpoints"]]
        assert "/health" in paths

    async def test_response_lists_stats_endpoint(
        self, http_client: AsyncClient
    ) -> None:
        resp = await http_client.get("/")
        paths = [e["path"] for e in resp.json()["endpoints"]]
        assert "/v1/stats" in paths

    async def test_response_omits_stats_endpoint_when_disabled(self) -> None:
        app = create_app(settings=_DISABLED_STATS_SETTINGS)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/")
        paths = [e["path"] for e in resp.json()["endpoints"]]
        assert "/v1/stats" not in paths

    async def test_response_includes_docs_link(self, http_client: AsyncClient) -> None:
        body = (await http_client.get("/")).json()
        assert body["docs"] == "/docs"

    async def test_response_includes_openapi_link(
        self, http_client: AsyncClient
    ) -> None:
        body = (await http_client.get("/")).json()
        assert body["openapi"] == "/openapi.json"

    async def test_response_includes_service_and_version(
        self, http_client: AsyncClient
    ) -> None:
        body = (await http_client.get("/")).json()
        assert "service" in body
        assert "version" in body
