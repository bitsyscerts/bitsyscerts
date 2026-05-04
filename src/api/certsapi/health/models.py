"""Pydantic model for the health check endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response — always HTTP 200, db field signals DB reachability."""

    status: Literal["ok"] = "ok"
    db: Literal["ok", "error"]
