"""X.509 certificate field extractor.

Exports:
    extract_certificate_fields — Parse a DER cert and return a ParsedCertificate.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID

from ctpool.exceptions import ParseError
from ctpool.pipeline_schemas import ParsedCertificate

_logger = logging.getLogger(__name__)

# OID for the CT poison extension (RFC 6962 §3.1) — marks precertificates
_CT_POISON_OID = "1.3.6.1.4.1.11129.2.4.3"

# Minimal DER shells used when wrapping a raw TBSCertificate for precerts.
# sha256WithRSAEncryption AlgorithmIdentifier (tag+OID+NULL params, 15 bytes).
_SHA256_RSA_ALGO_ID: bytes = bytes.fromhex("300d06092a864886f70d01010b0500")
# Empty BIT STRING: tag 0x03, length 1, zero unused-bits padding byte.
_EMPTY_SIG: bytes = bytes([0x03, 0x01, 0x00])


def extract_certificate_fields(
    der: bytes, is_precertificate: bool
) -> ParsedCertificate:
    """Parse a DER-encoded certificate and return a structured data object.

    Args:
        der:               DER-encoded certificate or TBSCertificate bytes.
        is_precertificate: True when the bytes were extracted from a
                           ``precert_entry`` (entry_type == 0x0001).

    Returns:
        Populated :class:`ParsedCertificate`.

    Raises:
        ParseError: If the DER cannot be decoded or required fields are absent.
    """
    cert = _load_certificate(der, is_precertificate)

    fingerprint = hashlib.sha256(der).hexdigest()
    spki = _compute_spki_sha256(cert)
    serial = format(cert.serial_number, "x")
    issuer_dn = cert.issuer.rfc4514_string()
    subject_dn = cert.subject.rfc4514_string()
    not_before = _to_utc(cert.not_valid_before_utc)
    not_after = _to_utc(cert.not_valid_after_utc)
    sig_oid, sig_name = _signature_algorithm(cert)
    pk_oid, pk_name, pk_bits_or_curve = _public_key_info(cert)
    is_precert = is_precertificate or _has_ct_poison(cert)
    san_dns = _extract_san_dns_names(cert)

    return ParsedCertificate(
        fingerprint_sha256=fingerprint,
        spki_sha256=spki,
        serial_number=serial,
        issuer_dn=issuer_dn,
        issuer_common_name=_get_rdn(cert.issuer, x509.NameOID.COMMON_NAME),
        issuer_organization=_get_rdn(cert.issuer, x509.NameOID.ORGANIZATION_NAME),
        subject_dn=subject_dn,
        subject_common_name=_get_rdn(cert.subject, x509.NameOID.COMMON_NAME),
        not_before=not_before,
        not_after=not_after,
        signature_algorithm_oid=sig_oid,
        signature_algorithm_name=sig_name,
        public_key_algorithm_oid=pk_oid,
        public_key_algorithm_name=pk_name,
        public_key_bits_or_curve=pk_bits_or_curve,
        is_precertificate=is_precert,
        san_dns_names=san_dns,
    )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _encode_der_length(n: int) -> bytes:
    """Encode *n* as a DER length field (single or multi-byte form)."""
    if n < 0x80:
        return bytes([n])
    if n < 0x100:
        return bytes([0x81, n])
    if n < 0x10000:
        return bytes([0x82, n >> 8, n & 0xFF])
    return bytes([0x83, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])


def _wrap_tbs_as_certificate(tbs_der: bytes) -> bytes:
    """Wrap a raw TBSCertificate in a minimal Certificate DER shell.

    CT precert entries contain a bare TBSCertificate (RFC 6962 §3.2).
    The ``cryptography`` library requires a full Certificate SEQUENCE,
    so we add a dummy outer wrapper with a placeholder signature to allow
    field extraction.  The signature algorithm stored will be
    sha256WithRSAEncryption regardless of the actual algorithm — only
    TBSCertificate fields (SANs, validity, issuer, subject, public key)
    should be treated as authoritative for precerts.
    """
    inner = tbs_der + _SHA256_RSA_ALGO_ID + _EMPTY_SIG
    return b"\x30" + _encode_der_length(len(inner)) + inner


def _load_certificate(der: bytes, is_precertificate: bool) -> x509.Certificate:
    """Load *der* as a Certificate, falling back to TBS wrapping for precerts."""
    try:
        return x509.load_der_x509_certificate(der)
    except Exception as exc:
        if not is_precertificate:
            raise ParseError(f"Cannot parse DER certificate: {exc}") from exc
    try:
        return x509.load_der_x509_certificate(_wrap_tbs_as_certificate(der))
    except Exception as exc:
        raise ParseError(f"Cannot parse DER certificate: {exc}") from exc


def _compute_spki_sha256(cert: x509.Certificate) -> str:
    """Return hex SHA-256 of the SubjectPublicKeyInfo DER."""
    spki_der = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki_der).hexdigest()


def _to_utc(dt: datetime) -> datetime:
    """Ensure *dt* is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _signature_algorithm(cert: x509.Certificate) -> tuple[str, str]:
    """Return (OID dotted string, human-readable name) for the signature algorithm."""
    oid = cert.signature_algorithm_oid.dotted_string
    alg = cert.signature_hash_algorithm
    name = alg.name if alg is not None else "unknown"
    return oid, name


def _public_key_info(
    cert: x509.Certificate,
) -> tuple[str, str, str | None]:
    """Return (OID, name, bits_or_curve) for the public key algorithm."""
    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    pub = cert.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        oid = "1.2.840.113549.1.1.1"
        return oid, "RSA", str(pub.key_size)
    if isinstance(pub, ec.EllipticCurvePublicKey):
        oid = "1.2.840.10045.2.1"
        return oid, "EC", pub.curve.name
    # Fallback for other key types (e.g., Ed25519, DSA)
    alg_oid = cert.public_key_algorithm_oid.dotted_string
    return alg_oid, "unknown", None


def _has_ct_poison(cert: x509.Certificate) -> bool:
    """Return True if the CT poison extension (RFC 6962) is present."""
    try:
        oid = x509.ObjectIdentifier(_CT_POISON_OID)
        cert.extensions.get_extension_for_oid(oid)
        return True
    except x509.ExtensionNotFound:
        return False
    except ValueError:
        _logger.debug("asn1 error checking CT poison extension; treating as absent")
        return False


def _extract_san_dns_names(cert: x509.Certificate) -> list[str]:
    """Return all DNS SANs as a list of lowercase strings."""
    try:
        san_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        san_value = san_ext.value
        if not isinstance(san_value, x509.SubjectAlternativeName):  # pragma: no cover
            return []
        return [name.lower() for name in san_value.get_values_for_type(x509.DNSName)]
    except x509.ExtensionNotFound:
        return []
    except ValueError:
        _logger.debug("asn1 error reading SAN extension; returning empty list")
        return []


def _get_rdn(name: x509.Name, oid: x509.ObjectIdentifier) -> str | None:
    """Return the first RDN value for *oid* from *name*, or None."""
    attrs = name.get_attributes_for_oid(oid)
    if not attrs:
        return None
    val = attrs[0].value
    return str(val) if val is not None else None
