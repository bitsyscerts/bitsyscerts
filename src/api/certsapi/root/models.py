"""Pydantic models for the API root index endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class EndpointEntry(BaseModel):
    """Description of a single API endpoint."""

    path: str
    method: str
    description: str


class RootResponse(BaseModel):
    """JSON index of all available API endpoints."""

    service: str
    version: str
    docs: str
    openapi: str
    endpoints: list[EndpointEntry]
