"""Integration tests verifying claim_backfill_range ORDER BY start_index DESC.

Uses the real ``ctpool_test`` database via the ``db_session`` fixture.
Every test rolls back automatically.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.dispatcher import claim_backfill_range, create_backfill_ranges
from ctpool.models.log_source import CtLogSource

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(*, url: str = "https://ct.example.com/log/") -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64="b3JkZXI=",
        operator_name="Order Test Op",
        description="Order Test Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_claim_backfill_range_returns_highest_start_index(
    db_session: AsyncSession,
) -> None:
    """claim_backfill_range returns the range with the highest start_index."""
    source = _make_source(url="https://order1.example.com/")
    db_session.add(source)
    await db_session.flush()

    # Seed two non-adjacent chunks: low=[0,9999] and high=[10000,19999].
    await create_backfill_ranges(
        db_session, source, start_index=0, end_index=9_999, chunk_size=10_000
    )
    await create_backfill_ranges(
        db_session, source, start_index=10_000, end_index=19_999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, source.id, "test-worker")

    assert claimed is not None
    assert claimed.start_index == 10_000


async def test_claim_backfill_range_any_log_returns_highest_start_index(
    db_session: AsyncSession,
) -> None:
    """With log_source_id=None, the highest start_index across all logs is claimed."""
    source_a = _make_source(url="https://order2a.example.com/")
    source_b = _make_source(url="https://order2b.example.com/")
    # Each source needs a unique log_id_b64.
    source_a.log_id_b64 = "b3JkZXIy"  # base64("order2")
    source_b.log_id_b64 = "b3JkZXIz"  # base64("order3")
    db_session.add(source_a)
    db_session.add(source_b)
    await db_session.flush()

    # source_a gets a range starting at 0; source_b gets a higher range.
    await create_backfill_ranges(
        db_session, source_a, start_index=0, end_index=9_999, chunk_size=10_000
    )
    await create_backfill_ranges(
        db_session, source_b, start_index=50_000, end_index=59_999, chunk_size=10_000
    )
    await db_session.flush()

    claimed = await claim_backfill_range(db_session, None, "test-worker")

    assert claimed is not None
    assert claimed.start_index == 50_000
    assert claimed.log_source_id == source_b.id
