"""Tests for ctpool.observation_writer — upsert_observation.

All tests use the real ``ctpool_test`` database via the ``db_session`` fixture;
every test is automatically rolled back.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.log_source import CtLogSource
from ctpool.models.observation import CtLogObservation
from ctpool.observation_writer import upsert_observation

pytestmark = pytest.mark.integration


def _make_log_source(
    *,
    log_id_b64: str = "dGVzdA==",
    url: str = "https://ct.example.com/log/",
) -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id_b64,
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="dGVzdGtleQ==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=datetime.now(UTC),
        last_synced_at=datetime.now(UTC),
    )


def _make_certificate(fingerprint: str = "a" * 64, serial: str = "01") -> Certificate:
    """Return a minimal valid Certificate ORM instance."""
    now = datetime.now(UTC)
    return Certificate(
        id=uuid.uuid4(),
        fingerprint_sha256=fingerprint,
        spki_sha256="b" * 64,
        serial_number=serial,
        issuer_dn="CN=CA",
        issuer_common_name=None,
        issuer_organization=None,
        subject_dn="CN=test",
        subject_common_name=None,
        not_before=now,
        not_after=now,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        public_key_bits_or_curve=None,
        is_precertificate=False,
        is_wildcard_present=False,
        san_count=0,
        first_seen_ct=now,
        last_seen_ct=now,
    )


async def test_upsert_observation_inserts_row(db_session: AsyncSession) -> None:
    """First call inserts an observation row."""
    source = _make_log_source()
    cert = _make_certificate()
    db_session.add(source)
    db_session.add(cert)
    await db_session.flush()

    await upsert_observation(db_session, source.id, 42, cert.id)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogObservation).where(
            CtLogObservation.log_source_id == source.id,
            CtLogObservation.log_index == 42,
        )
    )
    row = result.scalars().first()
    assert row is not None
    assert row.certificate_id == cert.id


async def test_upsert_observation_idempotent(db_session: AsyncSession) -> None:
    """Inserting the same observation twice does not raise an error."""
    source = _make_log_source(log_id_b64="dGVzdDI=", url="https://ct2.example.com/log/")
    cert = _make_certificate(fingerprint="c" * 64, serial="02")
    db_session.add(source)
    db_session.add(cert)
    await db_session.flush()

    await upsert_observation(db_session, source.id, 99, cert.id)
    await upsert_observation(db_session, source.id, 99, cert.id)  # must not raise
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogObservation).where(
            CtLogObservation.log_source_id == source.id,
            CtLogObservation.log_index == 99,
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_upsert_observation_different_indexes(
    db_session: AsyncSession,
) -> None:
    """Two calls with different log indexes produce two rows."""
    source = _make_log_source(log_id_b64="dGVzdDM=", url="https://ct3.example.com/log/")
    cert = _make_certificate(fingerprint="e" * 64, serial="03")
    db_session.add(source)
    db_session.add(cert)
    await db_session.flush()

    await upsert_observation(db_session, source.id, 1, cert.id)
    await upsert_observation(db_session, source.id, 2, cert.id)
    await db_session.flush()

    result = await db_session.execute(
        select(CtLogObservation).where(
            CtLogObservation.log_source_id == source.id,
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 2
