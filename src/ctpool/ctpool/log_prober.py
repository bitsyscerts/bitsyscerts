"""Probe a CT log's get-sth endpoint and update CtLogRuntimeState.

Exports:
    probe_log — Probe a log and persist its updated runtime state.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.exceptions import FetchError
from ctpool.fetcher import fetch_sth
from ctpool.models.log_runtime_state import CtLogRuntimeState
from ctpool.models.log_source import CtLogSource


async def probe_log(
    log_source: CtLogSource,
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> CtLogRuntimeState:
    """Probe ``get-sth`` for *log_source* and upsert its runtime state row.

    On success the ``tree_size``, ``sth_timestamp``, ``health_status``, and
    ``last_success_at`` fields are updated.  On failure the ``health_status``,
    ``last_error_at``, and ``last_error_message`` fields are updated instead.

    Args:
        log_source: The CT log to probe.
        client:     Shared :class:`httpx.AsyncClient`.
        session:    Active async database session.

    Returns:
        The upserted :class:`CtLogRuntimeState` ORM instance.
    """
    now = datetime.now(UTC)
    try:
        sth = await fetch_sth(log_source.url, client)
        sth_ts = datetime.fromtimestamp(sth.timestamp / 1000.0, tz=UTC)
        values = {
            "log_source_id": log_source.id,
            "tree_size": sth.tree_size,
            "sth_timestamp": sth_ts,
            "health_status": "ok",
            "last_probe_at": now,
            "last_success_at": now,
        }
        update_set = {
            "tree_size": sth.tree_size,
            "sth_timestamp": sth_ts,
            "health_status": "ok",
            "last_probe_at": now,
            "last_success_at": now,
            "consecutive_failures": 0,
        }
    except FetchError as exc:
        values = {
            "log_source_id": log_source.id,
            "health_status": "error",
            "last_probe_at": now,
            "last_error_at": now,
            "last_error_message": str(exc)[:1024],
        }
        update_set = {
            "health_status": "error",
            "last_probe_at": now,
            "last_error_at": now,
            "last_error_message": str(exc)[:1024],
        }

    stmt = (
        pg_insert(CtLogRuntimeState)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["log_source_id"],
            set_=update_set,
        )
        .returning(CtLogRuntimeState)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    # row is always set because RETURNING guarantees one result
    assert row is not None  # noqa: S101
    return row
