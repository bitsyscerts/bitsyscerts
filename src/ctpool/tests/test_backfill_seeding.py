"""Tests for range-seeding behaviour in ctpool.backfill_worker.

Covers: _seed_ranges_for_log (via run_backfill), pivot-index wiring from
ct_backfill_days, log_id filtering for seeding, and on_status callbacks
fired during the seeding phase.

All external boundaries are mocked — no network or database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from ctpool.backfill_worker import run_backfill
from ctpool.config import Settings
from ctpool.ct_api_schemas import SignedTreeHead
from ctpool.models.log_source import CtLogSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
# STH timestamp 365 days after _NOW (in ms) — gives a measurable age.
_STH_TIMESTAMP_1Y = int(_NOW.timestamp() * 1_000) + int(365 * 86_400_000)


def _make_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://ctpool:ctpool@localhost:5432/ctpool_test",
        "ct_default_batch_size": 2,
        "ct_backfill_days": 180,
    }
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


def _make_log(*, log_id: str = "dGVzdA==") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log",
        url="https://ct.example.com/log/",
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _make_sth(tree_size: int = 10, *, timestamp: int = 0) -> SignedTreeHead:
    return SignedTreeHead(
        tree_size=tree_size,
        timestamp=timestamp,
        sha256_root_hash="aa" * 32,
        tree_head_signature="bb",
    )


def _make_session_factory() -> MagicMock:
    session = AsyncMock()
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


# ---------------------------------------------------------------------------
# Seeding: filter and basic wiring
# ---------------------------------------------------------------------------


async def test_backfill_worker_filter_restricts_to_single_log_id() -> None:
    """log_id restricts seed and claim to the matching log only."""
    log_a = _make_log(log_id="YQ==")
    log_b = _make_log(log_id="Yg==")
    settings = _make_settings()
    seeded_ids: list[uuid.UUID] = []

    async def mock_sth(url: str, client: object) -> SignedTreeHead:
        return _make_sth(0)

    async def mock_seed_ranges(
        session: object, log: CtLogSource, start: int, end: int
    ) -> int:
        seeded_ids.append(log.id)
        return 0

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log_a, log_b]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", mock_sth),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_seed_ranges),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(
            _make_session_factory(), settings, once=True, log_id=log_a.id
        )

    assert all(lid == log_a.id for lid in seeded_ids)
    assert log_b.id not in seeded_ids


async def test_backfill_worker_seeds_ranges_from_sth() -> None:
    """On startup, create_backfill_ranges is called with tree_size - 1 as end.

    With timestamp=0 and first_seen_at=2024-01-01 the estimated log age is
    negative, so compute_pivot_index returns 0 — making start_index=0.
    """
    log = _make_log()
    settings = _make_settings()
    range_calls: list[tuple[int, int]] = []

    async def mock_create(session: object, lg: object, start: int, end: int) -> int:
        range_calls.append((start, end))
        return 1

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(100))
        ),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert len(range_calls) == 1
    assert range_calls[0] == (0, 99)  # timestamp=0 → age negative → pivot=0


# ---------------------------------------------------------------------------
# Seeding: pivot index wiring
# ---------------------------------------------------------------------------


async def test_backfill_seeding_uses_pivot_when_days_positive() -> None:
    """Positive days + realistic STH timestamp → start_index != 0."""
    log = _make_log()
    # 1-year-old log, seeding 90 days back → skip ~75% → pivot near 750 of 1000.
    settings = _make_settings(ct_backfill_days=90)
    range_calls: list[tuple[int, int]] = []

    async def mock_create(session: object, lg: object, start: int, end: int) -> int:
        range_calls.append((start, end))
        return 1

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(1_000, timestamp=_STH_TIMESTAMP_1Y)),
        ),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert len(range_calls) == 1
    start, end = range_calls[0]
    assert end == 999
    assert start > 0, "With days=90 and 1-year-old log, pivot should skip old history"
    assert start < 999, "Pivot should not skip everything"


async def test_backfill_seeding_days_zero_seeds_from_zero() -> None:
    """days=0 passed explicitly → full-history seed from index 0."""
    log = _make_log()
    settings = _make_settings(ct_backfill_days=0)
    range_calls: list[tuple[int, int]] = []

    async def mock_create(session: object, lg: object, start: int, end: int) -> int:
        range_calls.append((start, end))
        return 1

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(1_000, timestamp=_STH_TIMESTAMP_1Y)),
        ),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True)

    assert range_calls[0] == (0, 999)


async def test_backfill_seeding_none_days_uses_settings_default() -> None:
    """days=None in run_backfill → falls back to settings.ct_backfill_days."""
    log = _make_log()
    settings = _make_settings(ct_backfill_days=180)
    received_days: list[int] = []

    async def mock_create(session: object, lg: object, start: int, end: int) -> int:
        # Record whatever start_index was computed.
        received_days.append(start)
        return 1

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth",
            AsyncMock(return_value=_make_sth(1_000, timestamp=_STH_TIMESTAMP_1Y)),
        ),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        # days=None → should resolve to settings.ct_backfill_days = 180
        await run_backfill(_make_session_factory(), settings, once=True, days=None)

    # With 180 days of a 365-day-old log: pivot ≈ 507; start != 0
    assert len(received_days) == 1
    assert received_days[0] > 0, "180-day window of 1-year-old log should skip history"


async def test_backfill_seeding_explicit_days_overrides_settings() -> None:
    """Explicit days=30 seeds a later start_index than days=180."""
    log = _make_log()
    settings = _make_settings(ct_backfill_days=180)
    start_30: list[int] = []
    start_180: list[int] = []

    async def mock_create_30(session: object, lg: object, start: int, end: int) -> int:
        start_30.append(start)
        return 1

    async def mock_create_180(session: object, lg: object, start: int, end: int) -> int:
        start_180.append(start)
        return 1

    sth = _make_sth(1_000, timestamp=_STH_TIMESTAMP_1Y)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=sth)),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create_30),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True, days=30)

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch("ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=sth)),
        patch("ctpool.backfill_worker.create_backfill_ranges", mock_create_180),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
    ):
        await run_backfill(_make_session_factory(), settings, once=True, days=180)

    assert start_30[0] > start_180[0], (
        "30-day window should start later (higher index) than 180-day window"
    )


# ---------------------------------------------------------------------------
# on_status callbacks during seeding
# ---------------------------------------------------------------------------


async def test_backfill_worker_on_status_fires_during_seeding() -> None:
    """on_status is called when a new log is seeded."""
    log = _make_log()
    settings = _make_settings()
    status_messages: list[str] = []

    with (
        patch("ctpool.backfill_worker.is_disk_critical", return_value=False),
        patch("ctpool.backfill_worker.is_disk_low", return_value=False),
        patch(
            "ctpool.backfill_worker.get_eligible_backfill_logs",
            AsyncMock(return_value=[log]),
        ),
        patch(
            "ctpool.backfill_worker.has_backfill_ranges", AsyncMock(return_value=False)
        ),
        patch(
            "ctpool.backfill_worker.fetch_sth", AsyncMock(return_value=_make_sth(100))
        ),
        patch(
            "ctpool.backfill_worker.create_backfill_ranges",
            AsyncMock(return_value=10),
        ),
        patch(
            "ctpool.backfill_worker.claim_backfill_range", AsyncMock(return_value=None)
        ),
        patch("ctpool.backfill_worker.httpx.AsyncClient"),
    ):
        await run_backfill(
            _make_session_factory(),
            settings,
            once=True,
            on_status=status_messages.append,
        )

    assert any("Seeding" in m for m in status_messages)
    assert any("seeded" in m for m in status_messages)
