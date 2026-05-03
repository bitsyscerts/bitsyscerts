"""Fetch the Chrome CT log list and upsert CtLogSource rows.

Exports:
    fetch_log_list   — Fetch and validate the CT log list JSON.
    sync_log_sources — Upsert log sources from a validated log list response.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.ct_api_schemas import CtLogListResponse
from ctpool.exceptions import FetchError
from ctpool.models.log_source import CtLogSource

# Compile-time constant — never user-supplied (SSRF prevention).
_CHROME_LOG_LIST_URL = "https://www.gstatic.com/ct/log_list/v3/log_list.json"


async def fetch_log_list(
    client: httpx.AsyncClient,
    url: str = _CHROME_LOG_LIST_URL,
) -> CtLogListResponse:
    """Fetch and validate the Chrome CT log list JSON.

    Args:
        client: Shared :class:`httpx.AsyncClient`.
        url:    Log list URL; defaults to the Chrome list constant.

    Returns:
        Validated :class:`CtLogListResponse`.

    Raises:
        FetchError: On HTTP error or Pydantic validation failure.
    """
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FetchError(
            f"HTTP {exc.response.status_code} fetching CT log list"
        ) from exc
    except httpx.RequestError as exc:
        raise FetchError(f"Request error fetching CT log list: {exc}") from exc

    try:
        return CtLogListResponse.model_validate(response.json())
    except Exception as exc:
        raise FetchError(f"Invalid CT log list response: {exc}") from exc


async def sync_log_sources(
    session: AsyncSession,
    log_list: CtLogListResponse,
    source_list: str = "chrome",
) -> tuple[int, int]:
    """Upsert ``CtLogSource`` rows from a validated log list.

    Each log entry is inserted; on URL conflict the row is updated in-place.
    Counts are approximate because PostgreSQL's ``ON CONFLICT DO UPDATE``
    does not distinguish inserted vs updated rows via a single RETURNING.

    Args:
        session:     Active async database session.
        log_list:    Validated log list from :func:`fetch_log_list`.
        source_list: Label stored in ``source_list`` column (e.g. ``"chrome"``).

    Returns:
        A ``(upserted_count, operator_count)`` tuple.
    """
    now = datetime.now(UTC)
    upserted = 0

    for operator in log_list.operators:
        for log in operator.logs:
            # Determine eligibility: only "usable" logs get tail/backfill.
            state = (log.state or {}).get("usable") if log.state else None
            is_usable = state is not None

            shard_start: datetime | None = None
            shard_end: datetime | None = None
            if log.temporal_interval:
                if log.temporal_interval.start_inclusive:
                    try:
                        shard_start = datetime.fromisoformat(
                            log.temporal_interval.start_inclusive.rstrip("Z")
                        ).replace(tzinfo=UTC)
                    except ValueError:
                        pass
                if log.temporal_interval.end_exclusive:
                    try:
                        shard_end = datetime.fromisoformat(
                            log.temporal_interval.end_exclusive.rstrip("Z")
                        ).replace(tzinfo=UTC)
                    except ValueError:
                        pass

            stmt = (
                pg_insert(CtLogSource)
                .values(
                    log_id_b64=log.log_id,
                    operator_name=operator.name,
                    description=log.description,
                    url=log.url,
                    public_key_b64=log.key,
                    log_state=_extract_state_name(log.state),
                    temporal_shard_start=shard_start,
                    temporal_shard_end=shard_end,
                    is_eligible_for_tail=is_usable,
                    is_eligible_for_backfill=is_usable,
                    source_list=source_list,
                    first_seen_at=now,
                    last_synced_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["url"],
                    set_={
                        "operator_name": operator.name,
                        "description": log.description,
                        "log_state": _extract_state_name(log.state),
                        "is_eligible_for_tail": is_usable,
                        "is_eligible_for_backfill": is_usable,
                        "last_synced_at": now,
                        "temporal_shard_start": shard_start,
                        "temporal_shard_end": shard_end,
                    },
                )
            )
            await session.execute(stmt)
            upserted += 1

    return upserted, len(log_list.operators)


def _extract_state_name(state: dict[str, object] | None) -> str:
    """Return the first key from the *state* dict, or ``'unknown'``."""
    if not state:
        return "unknown"
    return next(iter(state), "unknown")
