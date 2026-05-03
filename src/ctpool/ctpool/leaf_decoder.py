"""Decode RFC 6962 MerkleTreeLeaf binary format into DER certificate bytes.

Exports:
    decode_merkle_leaf — Base64-decode leaf_input and return (entry_type, cert_der).
"""

from __future__ import annotations

import base64
import struct

from ctpool.exceptions import ParseError

# RFC 6962 entry type constants
_X509_ENTRY: int = 0x0000
_PRECERT_ENTRY: int = 0x0001

# Fixed byte offsets in MerkleTreeLeaf
_VERSION_OFFSET: int = 0
_LEAF_TYPE_OFFSET: int = 1
_TIMESTAMP_OFFSET: int = 2  # 8 bytes, big-endian ms since epoch
_ENTRY_TYPE_OFFSET: int = 10  # 2 bytes
_CERT_DATA_OFFSET: int = 12  # 3-byte length prefix + DER bytes

# For precert_entry: 32-byte issuer_key_hash before the length-prefixed TBSCert
_PRECERT_KEY_HASH_LEN: int = 32


def decode_merkle_leaf(leaf_input_b64: str) -> tuple[int, bytes]:
    """Decode a base64-encoded MerkleTreeLeaf and return (entry_type, cert_der).

    The ``cert_der`` value is:
    - For ``x509_entry``: the full DER-encoded end-entity certificate.
    - For ``precert_entry``: the DER-encoded ``TBSCertificate`` (after stripping
      the 32-byte ``issuer_key_hash`` prefix).

    Args:
        leaf_input_b64: Base64-encoded ``MerkleTreeLeaf`` struct (RFC 6962 §3.4).

    Returns:
        A ``(entry_type, cert_der)`` tuple where ``entry_type`` is either
        ``0x0000`` (x509) or ``0x0001`` (precert).

    Raises:
        ParseError: If the binary structure is malformed or the version/type
                    fields contain unexpected values.
    """
    try:
        raw = base64.b64decode(leaf_input_b64)
    except Exception as exc:
        raise ParseError(f"Cannot base64-decode leaf_input: {exc}") from exc

    if len(raw) < _CERT_DATA_OFFSET + 3:
        raise ParseError(
            f"leaf_input too short: {len(raw)} bytes (minimum {_CERT_DATA_OFFSET + 3})"
        )

    version = raw[_VERSION_OFFSET]
    if version != 0x00:
        raise ParseError(f"Unexpected MerkleTreeLeaf version: {version:#04x}")

    leaf_type = raw[_LEAF_TYPE_OFFSET]
    if leaf_type != 0x00:
        raise ParseError(f"Unexpected MerkleLeafType: {leaf_type:#04x}")

    (entry_type,) = struct.unpack_from(">H", raw, _ENTRY_TYPE_OFFSET)
    if entry_type not in (_X509_ENTRY, _PRECERT_ENTRY):
        raise ParseError(f"Unknown LogEntryType: {entry_type:#06x}")

    return entry_type, _extract_cert_der(raw, entry_type)


def _extract_cert_der(raw: bytes, entry_type: int) -> bytes:
    """Extract the DER certificate bytes from the binary leaf payload.

    Args:
        raw:        Full decoded MerkleTreeLeaf bytes.
        entry_type: 0x0000 for x509, 0x0001 for precert.

    Returns:
        DER certificate bytes.

    Raises:
        ParseError: If the length prefix is invalid or the buffer is too short.
    """
    offset = _CERT_DATA_OFFSET

    if entry_type == _PRECERT_ENTRY:
        # Skip the 32-byte issuer_key_hash
        offset += _PRECERT_KEY_HASH_LEN

    if len(raw) < offset + 3:
        raise ParseError("Truncated leaf_input: cannot read 3-byte length prefix")

    # 3-byte big-endian length
    length = (raw[offset] << 16) | (raw[offset + 1] << 8) | raw[offset + 2]
    offset += 3

    if len(raw) < offset + length:
        raise ParseError(
            f"Truncated leaf_input: declared length {length} but only "
            f"{len(raw) - offset} bytes remain"
        )

    return raw[offset : offset + length]
