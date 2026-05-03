"""Tests for ctpool.leaf_decoder — RFC 6962 MerkleTreeLeaf binary decoder."""

from __future__ import annotations

import base64
import struct

import pytest

from ctpool.exceptions import ParseError
from ctpool.leaf_decoder import decode_merkle_leaf

# ---------------------------------------------------------------------------
# Shared test fixtures — generated from make_cert_der() in conftest helper
# ---------------------------------------------------------------------------

# Valid x509_entry leaf_input (entry_type 0x0000)
_X509_LEAF_INPUT = (
    "AAAAAAGLz+VoAAAAAAFpMIIBZTCCAQygAwIBAgIUbivzp4KD/7U1b3stb32sNwWOHdYwCgYIKoZI"
    "zj0EAwIwGzEZMBcGA1UEAwwQdGVzdC5leGFtcGxlLmNvbTAeFw0yNDAxMDEwMDAwMDBaFw0yNDEy"
    "MzEwMDAwMDBaMBsxGTAXBgNVBAMMEHRlc3QuZXhhbXBsZS5jb20wWTATBgcqhkjOPQIBBggqhkjO"
    "PQMBBwNCAATQUbM/vQWAAdwTnaEDg9RzxwubAjMkjHxVE7+d29bRUtmzWBxoGB/C/PsdRfezlF2o"
    "QCRrCGZPjviUitCdLy37oy4wLDAqBgNVHREEIzAhghB0ZXN0LmV4YW1wbGUuY29tgg0qLmV4YW1w"
    "bGUuY29tMAoGCCqGSM49BAMCA0cAMEQCIFyhDe7aTLY/2aGIZGRHoMQhSA6SWDC2q/LzQmJjLE1R"
    "AiBlySFg6vJMNmnZTrg0Tr4MZaRmaaQpc00kXEc5bfNdwQ=="
)

# Valid precert_entry leaf_input (entry_type 0x0001)
_PRECERT_LEAF_INPUT = (
    "AAAAAAGLz+VoAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWkwggFlMIIBDKADAgEC"
    "AhRuK/OngoP/tTVvey1vfaw3BY4d1jAKBggqhkjOPQQDAjAbMRkwFwYDVQQDDBB0ZXN0LmV4YW1w"
    "bGUuY29tMB4XDTI0MDEwMTAwMDAwMFoXDTI0MTIzMTAwMDAwMFowGzEZMBcGA1UEAwwQdGVzdC5l"
    "eGFtcGxlLmNvbTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABNBRsz+9BYAB3BOdoQOD1HPHC5sC"
    "MySMfFUTv53b1tFS2bNYHGgYH8L8+x1F97OUXahAJGsIZk+O+JSK0J0vLfujLjAsMCoGA1UdEQQj"
    "MCGCEHRlc3QuZXhhbXBsZS5jb22CDSouZXhhbXBsZS5jb20wCgYIKoZIzj0EAwIDRwAwRAIgXKEN"
    "7tpMtj/ZoYhkZEegxCFIDpJYMLar8vNCYmMsTVECIGXJIWDq8kw2adlOuDROvgxlpGZppClzTSRc"
    "Rzlt813B"
)


def _build_x509_leaf(cert_der: bytes) -> str:
    """Build a minimal x509_entry leaf_input for *cert_der*."""
    timestamp = 1700000000000
    length = len(cert_der)
    header = bytes([0x00, 0x00]) + struct.pack(">Q", timestamp) + bytes([0x00, 0x00])
    prefix = bytes([(length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    return base64.b64encode(header + prefix + cert_der).decode()


def _build_precert_leaf(cert_der: bytes) -> str:
    """Build a minimal precert_entry leaf_input for *cert_der*."""
    timestamp = 1700000000000
    length = len(cert_der)
    header = bytes([0x00, 0x00]) + struct.pack(">Q", timestamp) + bytes([0x00, 0x01])
    key_hash = bytes(32)
    prefix = bytes([(length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    return base64.b64encode(header + key_hash + prefix + cert_der).decode()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_decode_x509_entry_type_and_der_length() -> None:
    """decode_merkle_leaf returns entry_type=0 and non-empty DER for x509 leaf."""
    entry_type, der = decode_merkle_leaf(_X509_LEAF_INPUT)
    assert entry_type == 0x0000
    assert len(der) > 0


def test_decode_precert_entry_type_and_der_length() -> None:
    """decode_merkle_leaf returns entry_type=1 and non-empty DER for precert leaf."""
    entry_type, der = decode_merkle_leaf(_PRECERT_LEAF_INPUT)
    assert entry_type == 0x0001
    assert len(der) > 0


def test_decode_x509_der_is_parseable() -> None:
    """The DER bytes from an x509 leaf_input decode as a valid certificate."""
    from cryptography import x509

    _, der = decode_merkle_leaf(_X509_LEAF_INPUT)
    cert = x509.load_der_x509_certificate(der)
    assert cert.serial_number > 0


def test_decode_precert_der_is_parseable() -> None:
    """The DER bytes from a precert leaf_input decode as a valid certificate."""
    from cryptography import x509

    _, der = decode_merkle_leaf(_PRECERT_LEAF_INPUT)
    cert = x509.load_der_x509_certificate(der)
    assert cert.serial_number > 0


def test_roundtrip_small_cert_der() -> None:
    """A minimal synthetic x509 leaf_input round-trips correctly."""
    cert_der = bytes(range(16))  # 16 arbitrary bytes as fake DER
    leaf = _build_x509_leaf(cert_der)
    entry_type, decoded = decode_merkle_leaf(leaf)
    assert entry_type == 0x0000
    assert decoded == cert_der


def test_roundtrip_precert_der() -> None:
    """A minimal synthetic precert leaf_input round-trips correctly."""
    cert_der = bytes(range(20))
    leaf = _build_precert_leaf(cert_der)
    entry_type, decoded = decode_merkle_leaf(leaf)
    assert entry_type == 0x0001
    assert decoded == cert_der


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_decode_raises_on_invalid_base64() -> None:
    """decode_merkle_leaf raises ParseError when input is not valid base64."""
    with pytest.raises(ParseError, match="Cannot base64-decode"):
        decode_merkle_leaf("not-valid-base64!!!")


def test_decode_raises_on_too_short_input() -> None:
    """decode_merkle_leaf raises ParseError when the buffer is fewer than 15 bytes."""
    short = base64.b64encode(bytes(10)).decode()
    with pytest.raises(ParseError, match="too short"):
        decode_merkle_leaf(short)


def test_decode_raises_on_wrong_version() -> None:
    """decode_merkle_leaf raises ParseError when version byte is not 0x00."""
    bad = bytearray(20)
    bad[0] = 0x01  # version != 0
    with pytest.raises(ParseError, match="version"):
        decode_merkle_leaf(base64.b64encode(bytes(bad)).decode())


def test_decode_raises_on_wrong_leaf_type() -> None:
    """decode_merkle_leaf raises ParseError when leaf_type byte is not 0x00."""
    bad = bytearray(20)
    bad[1] = 0x02  # leaf_type != 0
    with pytest.raises(ParseError, match="MerkleLeafType"):
        decode_merkle_leaf(base64.b64encode(bytes(bad)).decode())


def test_decode_raises_on_unknown_entry_type() -> None:
    """decode_merkle_leaf raises ParseError when entry_type is not 0x0000 or 0x0001."""
    # entry_type bytes at offset 10-11
    bad = bytearray(20)
    bad[10] = 0x00
    bad[11] = 0x02  # unknown entry type
    with pytest.raises(ParseError, match="LogEntryType"):
        decode_merkle_leaf(base64.b64encode(bytes(bad)).decode())


def test_decode_raises_when_cert_truncated() -> None:
    """decode_merkle_leaf raises ParseError when the DER length exceeds the buffer."""
    # Build a valid header then claim 1000 bytes but provide none
    timestamp = 1700000000000
    header = bytes([0x00, 0x00]) + struct.pack(">Q", timestamp) + bytes([0x00, 0x00])
    prefix = bytes([0x00, 0x03, 0xE8])  # length = 1000
    raw = header + prefix  # no actual cert bytes
    with pytest.raises(ParseError, match="Truncated"):
        decode_merkle_leaf(base64.b64encode(raw).decode())
