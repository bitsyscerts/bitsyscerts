"""Worker pool launchers for concurrent CT log ingestion.

Each pool function spawns *N* asyncio tasks with unique per-task worker IDs
and staggered start-up jitter so they do not all hammer the database
simultaneously on the first iteration.

Exports:
    run_tail_pool     -- Launch ``ct_tail_concurrency`` concurrent tail tasks.
    run_backfill_pool -- Launch ``ct_backfill_concurrency`` concurrent backfill
                         tasks.
"""

from __future__ import annotations

import asyncio
import random
import socket
from collections.abc import Callable
from os import getpid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ctpool.config import Settings


def _pool_worker_id(index: int) -> str:
    """Return a unique worker identity: ``hostname:pid:w<index>``."""
    return f"{socket.gethostname()}:{getpid()}:w{index}"


async def _start_with_jitter(coro: Any, jitter_max: float) -> None:
    """Sleep a random offset in ``[0, jitter_max)`` then await *coro*."""
    await asyncio.sleep(random.uniform(0.0, jitter_max))  # noqa: S311
    await coro


async def run_tail_pool(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    concurrency: int | None = None,
    once: bool = False,
    limit: int | None = None,
    log_id: Any = None,
    on_batch: Callable[[str, int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    init_from_end: int = 0,
    batch_size: int | None = None,
) -> None:
    """Run *concurrency* concurrent tail worker tasks.

    If *concurrency* is ``None`` it is taken from
    ``settings.ct_tail_concurrency``.  Pass ``concurrency=1`` for
    deterministic single-worker behaviour (e.g. ``--once`` / ``--log-id``
    CLI flags).

    Args:
        session_factory: SQLAlchemy async session factory.
        settings:        Validated application settings.
        concurrency:     Override the pool size from settings.
        once:            Forwarded to every tail worker.
        limit:           Forwarded to every tail worker.
        log_id:          Forwarded to every tail worker.
        on_batch:        Forwarded to every tail worker.
        on_status:       Forwarded to every tail worker.
        init_from_end:   Forwarded to every tail worker.
        batch_size:      Forwarded to every tail worker.
    """
    from ctpool.tail_worker import run_tail  # local import avoids circular dep

    n = concurrency if concurrency is not None else settings.ct_tail_concurrency
    if n == 0:
        return

    jitter_max = min(n * 2.0, 30.0)
    tasks = [
        _start_with_jitter(
            run_tail(
                session_factory,
                settings,
                once=once,
                limit=limit,
                log_id=log_id,
                on_batch=on_batch,
                on_status=on_status,
                init_from_end=init_from_end,
                batch_size=batch_size,
                worker_id=_pool_worker_id(i),
            ),
            jitter_max,
        )
        for i in range(n)
    ]
    await asyncio.gather(*tasks)


async def run_backfill_pool(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    concurrency: int | None = None,
    once: bool = False,
    limit: int | None = None,
    days: int | None = None,
    log_id: Any = None,
    on_batch: Callable[[str, int, int], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    batch_size: int | None = None,
    dispatch_mode: str | None = None,
) -> None:
    """Run *concurrency* concurrent backfill worker tasks.

    If *concurrency* is ``None`` it is taken from
    ``settings.ct_backfill_concurrency``.  Pass ``concurrency=1`` for
    deterministic single-worker behaviour (e.g. ``--once`` / ``--log-id``
    CLI flags).

    Args:
        session_factory: SQLAlchemy async session factory.
        settings:        Validated application settings.
        concurrency:     Override the pool size from settings.
        once:            Forwarded to every backfill worker.
        limit:           Forwarded to every backfill worker.
        days:            Forwarded to every backfill worker.
        log_id:          Forwarded to every backfill worker.
        on_batch:        Forwarded to every backfill worker.
        on_status:       Forwarded to every backfill worker.
        batch_size:      Forwarded to every backfill worker.
        dispatch_mode:   Forwarded to every backfill worker.
    """
    from ctpool.backfill_worker import run_backfill  # local import avoids circ

    n = concurrency if concurrency is not None else settings.ct_backfill_concurrency
    if n == 0:
        return

    jitter_max = min(n * 2.0, 30.0)
    tasks = [
        _start_with_jitter(
            run_backfill(
                session_factory,
                settings,
                once=once,
                limit=limit,
                days=days,
                log_id=log_id,
                on_batch=on_batch,
                on_status=on_status,
                batch_size=batch_size,
                dispatch_mode=dispatch_mode,
                worker_id=_pool_worker_id(i),
            ),
            jitter_max,
        )
        for i in range(n)
    ]
    await asyncio.gather(*tasks)
