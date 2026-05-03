"""Tests for ctpool.parser — parse_leaf_entry integration."""

from __future__ import annotations

import base64
import struct
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from ctpool.exceptions import ParseError
from ctpool.parser import parse_leaf_entry
from ctpool.pipeline_schemas import ParsedCertificate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cert_der(cn: str = "leaf.example.com", sans: list[str] | None = None) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime(2024, 1, 1, tzinfo=UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
    )
    if sans:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]),
            critical=False,
        )
    return builder.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


def _make_leaf_input(cert_der: bytes, entry_type: int = 0x0000) -> str:
    """Build a base64 MerkleTreeLeaf leaf_input from cert_der bytes."""
    timestamp = 1700000000000
    header = bytes([0x00, 0x00]) + struct.pack(">Q", timestamp)
    header += bytes([(entry_type >> 8) & 0xFF, entry_type & 0xFF])
    if entry_type == 0x0001:
        header += bytes(32)  # issuer_key_hash placeholder
    length = len(cert_der)
    prefix = bytes([(length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    return base64.b64encode(header + prefix + cert_der).decode()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_leaf_entry_returns_parsed_certificate() -> None:
    """parse_leaf_entry returns a ParsedCertificate for a valid x509 leaf_input."""
    der = _cert_der(sans=["leaf.example.com"])
    result = parse_leaf_entry(_make_leaf_input(der))
    assert isinstance(result, ParsedCertificate)


def test_parse_leaf_entry_x509_is_not_precert() -> None:
    """parse_leaf_entry marks an x509_entry as is_precertificate=False."""
    der = _cert_der()
    result = parse_leaf_entry(_make_leaf_input(der, entry_type=0x0000))
    assert result.is_precertificate is False


def test_parse_leaf_entry_precert_is_precert() -> None:
    """parse_leaf_entry marks a precert_entry as is_precertificate=True."""
    der = _cert_der()
    result = parse_leaf_entry(_make_leaf_input(der, entry_type=0x0001))
    assert result.is_precertificate is True


def test_parse_leaf_entry_populates_san_dns_names() -> None:
    """san_dns_names from the certificate are present in the result."""
    der = _cert_der(sans=["a.example.com", "b.example.com"])
    result = parse_leaf_entry(_make_leaf_input(der))
    assert "a.example.com" in result.san_dns_names


def test_parse_leaf_entry_raises_on_invalid_base64() -> None:
    """parse_leaf_entry raises ParseError for non-base64 input."""
    with pytest.raises(ParseError):
        parse_leaf_entry("not!!valid!!base64")


def test_parse_leaf_entry_raises_on_truncated_input() -> None:
    """parse_leaf_entry raises ParseError for a too-short buffer."""
    short = base64.b64encode(b"\x00" * 5).decode()
    with pytest.raises(ParseError):
        parse_leaf_entry(short)
