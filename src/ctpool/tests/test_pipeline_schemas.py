"""Tests for ctpool.pipeline_schemas — internal pipeline DTOs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ctpool.pipeline_schemas import NormalizedEntry, ParsedCertificate

_NOW = datetime.now(UTC)

_VALID_PARSED: dict[str, Any] = {
    "fingerprint_sha256": "a" * 64,
    "spki_sha256": "b" * 64,
    "serial_number": "deadbeef",
    "issuer_dn": "CN=Test CA",
    "issuer_common_name": "Test CA",
    "issuer_organization": "Test Org",
    "subject_dn": "CN=example.com",
    "subject_common_name": "example.com",
    "not_before": _NOW,
    "not_after": _NOW,
    "signature_algorithm_oid": "1.2.840.113549.1.1.11",
    "signature_algorithm_name": "sha256WithRSAEncryption",
    "public_key_algorithm_oid": "1.2.840.113549.1.1.1",
    "public_key_algorithm_name": "RSA",
    "public_key_bits_or_curve": "2048",
    "is_precertificate": False,
    "san_dns_names": ["example.com", "www.example.com"],
}


def _make_parsed(**overrides: Any) -> ParsedCertificate:
    """Return a ParsedCertificate with optional field overrides."""
    return ParsedCertificate.model_validate({**_VALID_PARSED, **overrides})


def test_parsed_certificate_requires_fingerprint_sha256() -> None:
    """Missing fingerprint_sha256 raises ValidationError."""
    data = {k: v for k, v in _VALID_PARSED.items() if k != "fingerprint_sha256"}
    with pytest.raises(ValidationError):
        ParsedCertificate.model_validate(data)


def test_parsed_certificate_not_before_is_datetime() -> None:
    """not_before is stored as a datetime object."""
    cert = _make_parsed()
    assert isinstance(cert.not_before, datetime)


def test_parsed_certificate_san_dns_names_is_list() -> None:
    """san_dns_names is a list of strings."""
    cert = _make_parsed()
    assert isinstance(cert.san_dns_names, list)


def test_normalized_entry_hostnames_is_list() -> None:
    """hostnames is a list of strings."""
    entry = NormalizedEntry(
        parsed_certificate=_make_parsed(),
        hostnames=["example.com"],
        is_wildcard_present=False,
        log_source_id=uuid.uuid4(),
        log_index=0,
    )
    assert isinstance(entry.hostnames, list)


def test_normalized_entry_allows_empty_hostname_list() -> None:
    """An empty hostnames list is valid (cert with no DNS SANs)."""
    entry = NormalizedEntry(
        parsed_certificate=_make_parsed(),
        hostnames=[],
        is_wildcard_present=False,
        log_source_id=uuid.uuid4(),
        log_index=0,
    )
    assert entry.hostnames == []


def test_normalized_entry_is_wildcard_present_false_when_set() -> None:
    """is_wildcard_present set to False is preserved."""
    entry = NormalizedEntry(
        parsed_certificate=_make_parsed(),
        hostnames=[],
        is_wildcard_present=False,
        log_source_id=uuid.uuid4(),
        log_index=0,
    )
    assert entry.is_wildcard_present is False


def test_normalized_entry_log_index_is_int() -> None:
    """log_index is stored as an integer."""
    entry = NormalizedEntry(
        parsed_certificate=_make_parsed(),
        hostnames=[],
        is_wildcard_present=False,
        log_source_id=uuid.uuid4(),
        log_index=42,
    )
    assert entry.log_index == 42


def test_normalized_entry_log_source_id_is_uuid() -> None:
    """log_source_id is a UUID."""
    log_id = uuid.uuid4()
    entry = NormalizedEntry(
        parsed_certificate=_make_parsed(),
        hostnames=[],
        is_wildcard_present=False,
        log_source_id=log_id,
        log_index=0,
    )
    assert entry.log_source_id == log_id
