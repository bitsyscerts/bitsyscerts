"""FastAPI application factory: assembles routers, handlers, and Scalar docs."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from certsapi.certificates.exceptions import CertificateNotFoundError
from certsapi.certificates.router import certificate_router
from certsapi.config import get_settings
from certsapi.health.router import health_router
from certsapi.hostnames.exceptions import InvalidCursorError, InvalidQueryError
from certsapi.hostnames.router import hostname_router
from certsapi.root.router import root_router
from certsapi.stats.router import stats_router


async def _cert_not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _invalid_cursor(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def _invalid_query(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=None,  # Replaced by Scalar below
        redoc_url=None,
    )

    # Domain exception → HTTP status mappings
    app.add_exception_handler(CertificateNotFoundError, _cert_not_found)
    app.add_exception_handler(InvalidCursorError, _invalid_cursor)
    app.add_exception_handler(InvalidQueryError, _invalid_query)

    # Routers
    app.include_router(hostname_router)
    app.include_router(certificate_router)
    app.include_router(health_router)
    app.include_router(stats_router)
    app.include_router(root_router)

    # Scalar interactive docs at /docs
    @app.get("/docs", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:
        from scalar_fastapi import (
            get_scalar_api_reference,
        )

        return get_scalar_api_reference(
            openapi_url=app.openapi_url or "/openapi.json",
            title=settings.app_name,
        )

    return app
