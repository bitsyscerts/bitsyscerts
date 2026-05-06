"""Tests for ctpool.writer — write_normalized_entry.

All tests use the real ``ctpool_test`` database via ``db_session``;
every test rolls back automatically via savepoint.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from ctpool.models.log_source import CtLogSource
from ctpool.models.observation import CtLogObservation
from ctpool.pipeline_schemas import NormalizedEntry, ParsedCertificate
from ctpool.writer import write_normalized_entry

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)


def _make_log_source(
    *,
    url: str = "https://ct.example.com/log/",
    log_id: str = "dGVzdA==",
) -> CtLogSource:
    return CtLogSource(
        id=uuid.uuid4(),
        log_id_b64=log_id,
        operator_name="Test Operator",
        description="Test CT Log",
        url=url,
        public_key_b64="a2V5==",
        log_state="usable",
        is_eligible_for_tail=True,
        is_eligible_for_backfill=True,
        source_list="chrome",
        first_seen_at=_NOW,
        last_synced_at=_NOW,
    )


def _make_entry(
    log_source_id: uuid.UUID,
    *,
    log_index: int = 0,
    fingerprint: str = "a" * 64,
    hostnames: list[str] | None = None,
    is_wildcard_present: bool = False,
) -> NormalizedEntry:
    hosts = hostnames if hostnames is not None else ["example.com"]
    parsed = ParsedCertificate(
        fingerprint_sha256=fingerprint,
        spki_sha256="b" * 64,
        serial_number="0102",
        issuer_dn="CN=Test CA",
        issuer_common_name="Test CA",
        issuer_organization="Test Org",
        subject_dn="CN=example.com",
        subject_common_name="example.com",
        not_before=_NOW,
        not_after=_NOW,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        public_key_bits_or_curve="2048",
        is_precertificate=False,
        san_dns_names=hosts,
    )
    return NormalizedEntry(
        parsed_certificate=parsed,
        hostnames=hosts,
        is_wildcard_present=is_wildcard_present,
        log_source_id=log_source_id,
        log_index=log_index,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_write_normalized_entry_inserts_all_rows(
    db_session: AsyncSession,
) -> None:
    """Happy path: certificate, hostnames, join rows, and observation are created."""
    log = _make_log_source()
    db_session.add(log)
    await db_session.flush()

    entry = _make_entry(log.id, hostnames=["example.com", "www.example.com"])
    await write_normalized_entry(db_session, entry)
    await db_session.flush()

    certs = list((await db_session.execute(select(Certificate))).scalars().all())
    assert len(certs) == 1

    hosts = list((await db_session.execute(select(Hostname))).scalars().all())
    assert len(hosts) == 2

    join_result = await db_session.execute(select(CertificateHostname))
    joins = list(join_result.scalars().all())
    assert len(joins) == 2

    obs = list((await db_session.execute(select(CtLogObservation))).scalars().all())
    assert len(obs) == 1


async def test_write_normalized_entry_with_no_hostnames(
    db_session: AsyncSession,
) -> None:
    """Entry with empty hostnames creates only a certificate and observation row."""
    log = _make_log_source(url="https://ct2.example.com/log/", log_id="bGludXg=")
    db_session.add(log)
    await db_session.flush()

    entry = _make_entry(log.id, log_index=5, hostnames=[])
    await write_normalized_entry(db_session, entry)
    await db_session.flush()

    certs = list((await db_session.execute(select(Certificate))).scalars().all())
    assert len(certs) == 1

    hosts = list((await db_session.execute(select(Hostname))).scalars().all())
    assert len(hosts) == 0

    obs = list((await db_session.execute(select(CtLogObservation))).scalars().all())
    assert len(obs) == 1


async def test_write_normalized_entry_idempotent_on_same_fingerprint(
    db_session: AsyncSession,
) -> None:
    """Same fingerprint at two different indices: one cert row, two observations."""
    log = _make_log_source(url="https://ct3.example.com/log/", log_id="Y3QzMQ==")
    db_session.add(log)
    await db_session.flush()

    entry1 = _make_entry(log.id, log_index=10)
    entry2 = _make_entry(log.id, log_index=11)  # same fingerprint, different index
    await write_normalized_entry(db_session, entry1)
    await write_normalized_entry(db_session, entry2)
    await db_session.flush()

    certs = list((await db_session.execute(select(Certificate))).scalars().all())
    assert len(certs) == 1  # deduplicated by fingerprint

    obs = list((await db_session.execute(select(CtLogObservation))).scalars().all())
    assert len(obs) == 2  # two distinct indices


async def test_write_normalized_entry_idempotent_on_same_index(
    db_session: AsyncSession,
) -> None:
    """Exact duplicate (same fingerprint + same index) keeps one observation row."""
    log = _make_log_source(url="https://ct4.example.com/log/", log_id="Y3Q0MQ==")
    db_session.add(log)
    await db_session.flush()

    entry = _make_entry(log.id, log_index=0)
    await write_normalized_entry(db_session, entry)
    await write_normalized_entry(db_session, entry)  # exact duplicate
    await db_session.flush()

    obs = list((await db_session.execute(select(CtLogObservation))).scalars().all())
    assert len(obs) == 1


async def test_write_normalized_entry_wildcard_sets_flag(
    db_session: AsyncSession,
) -> None:
    """is_wildcard_present=True is stored on the certificate row."""
    log = _make_log_source(url="https://ct5.example.com/log/", log_id="Y3Q1MQ==")
    db_session.add(log)
    await db_session.flush()

    entry = _make_entry(
        log.id,
        hostnames=["*.example.com"],
        is_wildcard_present=True,
    )
    await write_normalized_entry(db_session, entry)
    await db_session.flush()

    cert = (await db_session.execute(select(Certificate))).scalars().first()
    assert cert is not None
    assert cert.is_wildcard_present is True
