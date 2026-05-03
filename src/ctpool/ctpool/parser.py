"""CT log entry leaf parser dispatcher.

Exports:
    parse_leaf_entry — Decode a base64 leaf_input and return a ParsedCertificate.
"""

from __future__ import annotations

from ctpool.cert_fields import extract_certificate_fields
from ctpool.leaf_decoder import _X509_ENTRY, decode_merkle_leaf
from ctpool.pipeline_schemas import ParsedCertificate


def parse_leaf_entry(leaf_input_b64: str) -> ParsedCertificate:
    """Decode a base64 ``leaf_input`` field and return a :class:`ParsedCertificate`.

    Args:
        leaf_input_b64: The ``leaf_input`` value from a CT log entry response.

    Returns:
        Populated :class:`ParsedCertificate` with all extracted certificate fields.

    Raises:
        ParseError: If the binary structure or certificate DER is malformed.
    """
    entry_type, cert_der = decode_merkle_leaf(leaf_input_b64)
    is_precert = entry_type != _X509_ENTRY
    return extract_certificate_fields(cert_der, is_precert)
