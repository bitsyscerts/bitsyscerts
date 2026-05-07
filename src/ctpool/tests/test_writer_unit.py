"""Unit tests for ctpool.writer.write_normalized_entry (no DB required).

Mocks all three underlying writer functions to verify the orchestration logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from ctpool.pipeline_schemas import NormalizedEntry, ParsedCertificate
from ctpool.writer import write_normalized_entry


def _parsed() -> ParsedCertificate:
    now = datetime(2024, 1, 1, tzinfo=UTC)
    return ParsedCertificate(
        fingerprint_sha256="a" * 64,
        spki_sha256="b" * 64,
        serial_number="01",
        issuer_dn="CN=CA",
        issuer_common_name="CA",
        issuer_organization="Acme",
        subject_dn="CN=example.com",
        subject_common_name="example.com",
        not_before=now,
        not_after=now,
        signature_algorithm_oid="1.2.840.113549.1.1.11",
        signature_algorithm_name="sha256WithRSAEncryption",
        public_key_algorithm_oid="1.2.840.113549.1.1.1",
        public_key_algorithm_name="rsaEncryption",
        public_key_bits_or_curve="2048",
        is_precertificate=False,
        san_dns_names=["example.com"],
    )


def _entry(hostnames: list[str] | None = None) -> NormalizedEntry:
    return NormalizedEntry(
        log_source_id=uuid.uuid4(),
        log_index=42,
        parsed_certificate=_parsed(),
        hostnames=["example.com"] if hostnames is None else hostnames,
        is_wildcard_present=False,
    )


@pytest.mark.asyncio
async def test_write_normalized_entry_calls_all_writers():
    session = AsyncMock()
    cert_id = uuid.uuid4()
    host_id = uuid.uuid4()

    with (
        patch(
            "ctpool.writer.upsert_certificate",
            new=AsyncMock(return_value=cert_id),
        ) as mock_cert,
        patch(
            "ctpool.writer.upsert_hostname",
            new=AsyncMock(return_value=host_id),
        ) as mock_host,
        patch(
            "ctpool.writer.upsert_certificate_hostname",
            new=AsyncMock(),
        ) as mock_join,
        patch(
            "ctpool.writer.upsert_observation",
            new=AsyncMock(),
        ) as mock_obs,
    ):
        await write_normalized_entry(session, _entry())
        mock_cert.assert_awaited_once()
        mock_host.assert_awaited_once()
        mock_join.assert_awaited_once()
        mock_obs.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_normalized_entry_one_call_per_hostname():
    session = AsyncMock()
    cert_id = uuid.uuid4()
    host_id = uuid.uuid4()
    entry = _entry(hostnames=["a.example.com", "b.example.com", "c.example.com"])

    with (
        patch("ctpool.writer.upsert_certificate", new=AsyncMock(return_value=cert_id)),
        patch(
            "ctpool.writer.upsert_hostname",
            new=AsyncMock(return_value=host_id),
        ) as mock_host,
        patch("ctpool.writer.upsert_certificate_hostname", new=AsyncMock()),
        patch("ctpool.writer.upsert_observation", new=AsyncMock()),
    ):
        await write_normalized_entry(session, entry)
        assert mock_host.await_count == 3


@pytest.mark.asyncio
async def test_write_normalized_entry_no_hostnames_skips_hostname_calls():
    session = AsyncMock()
    cert_id = uuid.uuid4()
    entry = _entry(hostnames=[])

    mock_host = AsyncMock()
    mock_obs = AsyncMock()
    with (
        patch("ctpool.writer.upsert_certificate", new=AsyncMock(return_value=cert_id)),
        patch("ctpool.writer.upsert_hostname", mock_host),
        patch("ctpool.writer.upsert_certificate_hostname", new=AsyncMock()),
        patch("ctpool.writer.upsert_observation", mock_obs),
    ):
        await write_normalized_entry(session, entry)
        mock_host.assert_not_awaited()
        mock_obs.assert_awaited_once()
