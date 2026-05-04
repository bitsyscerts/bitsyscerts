"""HTTP-level tests for GET / (root index endpoint)."""

from __future__ import annotations

from httpx import AsyncClient


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
