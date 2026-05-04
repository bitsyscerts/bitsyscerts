"""Health check service: probes the database and returns a HealthResponse."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from certsapi.health.models import HealthResponse


class HealthService:
    """Executes a lightweight DB probe and reports reachability without raising."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check(self) -> HealthResponse:
        """Return HealthResponse with db='ok' or db='error', never raises."""
        try:
            await self._session.execute(text("SELECT 1"))
            return HealthResponse(db="ok")
        except Exception:  # intentional broad catch for health probes
            return HealthResponse(db="error")
