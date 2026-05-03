"""Internal pipeline data transfer objects.

These Pydantic models carry parsed and normalized data between ctpool
pipeline stages. They are never written to HTTP responses or external
APIs — they cross internal module boundaries only.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ParsedCertificate(BaseModel):
    """Structured representation of a parsed X.509 certificate or precertificate."""

    fingerprint_sha256: str  # hex SHA-256 of the DER bytes
    spki_sha256: str  # hex SHA-256 of SubjectPublicKeyInfo DER
    serial_number: str  # hex serial number
    issuer_dn: str  # full issuer distinguished name string
    issuer_common_name: str | None
    issuer_organization: str | None
    subject_dn: str  # full subject distinguished name string
    subject_common_name: str | None
    not_before: datetime
    not_after: datetime
    signature_algorithm_oid: str
    signature_algorithm_name: str
    public_key_algorithm_oid: str
    public_key_algorithm_name: str
    public_key_bits_or_curve: str | None
    is_precertificate: bool
    san_dns_names: list[str]  # raw DNS SAN values, not yet normalized


class NormalizedEntry(BaseModel):
    """Pipeline record after hostname normalization, ready for database write."""

    parsed_certificate: ParsedCertificate
    hostnames: list[str]  # lowercase, deduplicated, trailing dot stripped
    is_wildcard_present: bool
    log_source_id: uuid.UUID
    log_index: int
