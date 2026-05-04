"""Pydantic models for the ingestion statistics endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class LogStatsItem(BaseModel):
    """Per-CT-log statistics."""

    log_id: uuid.UUID
    description: str
    url: str
    log_state: str
    tail_position: int | None
    last_tail_sync: datetime | None
    backfill_complete_pct: float | None


class StatsResponse(BaseModel):
    """Global ingestion statistics."""

    total_hostnames: int
    total_certificates: int
    total_logs: int
    logs: list[LogStatsItem]
