"""Tests for ctpool.cert_fields — X.509 certificate field extractor.

Consolidation rationale: all cert_fields tests are co-located in one file
because they share build helpers (_make_ec_cert, _make_rsa_cert,
_make_tbs_certificate_der) that are only used here.  The file will be split
if a new extractor module is introduced or the test count exceeds ~300 lines.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from ctpool.cert_fields import extract_certificate_fields
from ctpool.exceptions import ParseError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ec_cert(
    cn: str = "test.example.com",
    sans: list[str] | None = None,
    with_ct_poison: bool = False,
) -> bytes:
    """Build a minimal self-signed EC P-256 certificate and return DER bytes."""
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
    if with_ct_poison:
        # OID 1.3.6.1.4.1.11129.2.4.3 — CT poison extension
        builder = builder.add_extension(
            x509.UnrecognizedExtension(
                x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.4.3"),
                b"\x05\x00",  # ASN.1 NULL
            ),
            critical=True,
        )
    cert = builder.sign(key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.DER)


def _make_tbs_certificate_der() -> bytes:
    """Return a raw TBSCertificate DER, as found inside a CT precert_entry."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "precert.example.com")])
    now = datetime(2024, 1, 1, tzinfo=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("precert.example.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    # tbs_certificate_bytes is the raw TBSCertificate DER — no outer wrapper.
    return cert.tbs_certificate_bytes


def _make_rsa_cert(cn: str = "rsa.example.com") -> bytes:
    """Build a minimal self-signed RSA-2048 certificate and return DER bytes."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime(2024, 1, 1, tzinfo=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.DER)


# ---------------------------------------------------------------------------
# Happy path — EC certificate
# ---------------------------------------------------------------------------


def test_extract_fields_returns_parsed_certificate() -> None:
    """extract_certificate_fields returns a ParsedCertificate for a valid DER."""
    from ctpool.pipeline_schemas import ParsedCertificate

    der = _make_ec_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    assert isinstance(result, ParsedCertificate)


def test_extract_fingerprint_is_sha256_of_der() -> None:
    """fingerprint_sha256 equals SHA-256 of the raw DER bytes."""
    der = _make_ec_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    expected = hashlib.sha256(der).hexdigest()
    assert result.fingerprint_sha256 == expected


def test_extract_san_dns_names_populated() -> None:
    """san_dns_names contains the SANs specified when building the cert."""
    der = _make_ec_cert(sans=["a.example.com", "b.example.com"])
    result = extract_certificate_fields(der, is_precertificate=False)
    assert "a.example.com" in result.san_dns_names
    assert "b.example.com" in result.san_dns_names


def test_extract_san_dns_names_empty_when_no_san() -> None:
    """san_dns_names is an empty list for certificates without SAN extensions."""
    der = _make_ec_cert()  # no SANs
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.san_dns_names == []


def test_extract_not_before_not_after_correct() -> None:
    """not_before and not_after match the certificate validity period."""
    der = _make_ec_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.not_before.year == 2024
    assert result.not_before.tzinfo is not None
    assert result.not_after > result.not_before


def test_extract_is_precertificate_from_flag() -> None:
    """is_precertificate is True when the flag argument is True."""
    der = _make_ec_cert()
    result = extract_certificate_fields(der, is_precertificate=True)
    assert result.is_precertificate is True


def test_extract_is_precertificate_from_ct_poison() -> None:
    """is_precertificate is True when the CT poison extension is present."""
    der = _make_ec_cert(with_ct_poison=True)
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.is_precertificate is True


def test_extract_ec_public_key_algorithm_name() -> None:
    """public_key_algorithm_name is 'EC' for an EC P-256 certificate."""
    der = _make_ec_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.public_key_algorithm_name == "EC"
    assert result.public_key_bits_or_curve is not None


# ---------------------------------------------------------------------------
# Happy path — RSA certificate
# ---------------------------------------------------------------------------


def test_extract_rsa_public_key_algorithm_name() -> None:
    """public_key_algorithm_name is 'RSA' for an RSA-2048 certificate."""
    der = _make_rsa_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.public_key_algorithm_name == "RSA"
    assert result.public_key_bits_or_curve == "2048"


def test_extract_rsa_serial_number_is_hex_string() -> None:
    """serial_number is a non-empty hex string."""
    der = _make_rsa_cert()
    result = extract_certificate_fields(der, is_precertificate=False)
    assert len(result.serial_number) > 0
    # Verify it's valid hex
    int(result.serial_number, 16)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_extract_raises_parse_error_on_garbage_der() -> None:
    """extract_certificate_fields raises ParseError when bytes are not valid DER."""
    with pytest.raises(ParseError, match="Cannot parse DER"):
        extract_certificate_fields(b"\x00\x01\x02\x03garbage", is_precertificate=False)


def test_extract_ed25519_cert_falls_back_to_unknown_key_algorithm() -> None:
    """public_key_algorithm_name is 'unknown' for Ed25519 (not RSA or EC)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ed.example.com")])
    now = datetime(2024, 1, 1, tzinfo=UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .sign(key, None)
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    result = extract_certificate_fields(der, is_precertificate=False)
    assert result.public_key_algorithm_name == "unknown"
    assert result.public_key_bits_or_curve is None


# ---------------------------------------------------------------------------
# Precertificate TBSCertificate wrapping
# ---------------------------------------------------------------------------


def test_precert_raw_tbs_parsed_via_wrapping() -> None:
    """extract_certificate_fields parses a raw TBSCertificate
    when is_precertificate=True.
    """
    tbs_der = _make_tbs_certificate_der()
    result = extract_certificate_fields(tbs_der, is_precertificate=True)
    assert result.is_precertificate is True
    assert result.subject_common_name == "precert.example.com"
    assert "precert.example.com" in result.san_dns_names


def test_raw_tbs_without_precert_flag_raises_parse_error() -> None:
    """extract_certificate_fields raises ParseError for a raw TBS
    when is_precertificate=False.
    """
    tbs_der = _make_tbs_certificate_der()
    with pytest.raises(ParseError, match="Cannot parse DER"):
        extract_certificate_fields(tbs_der, is_precertificate=False)
