"""Pydantic response model for the certificate detail endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CertificateResponse(BaseModel):
    """Full certificate record returned by GET /v1/certificates/{fingerprint}."""

    id: uuid.UUID
    fingerprint_sha256: str
    spki_sha256: str
    serial_number: str
    issuer_dn: str
    issuer_common_name: str | None
    issuer_organization: str | None
    subject_dn: str
    subject_common_name: str | None
    not_before: datetime
    not_after: datetime
    signature_algorithm_oid: str
    signature_algorithm_name: str
    public_key_algorithm_oid: str
    public_key_algorithm_name: str
    public_key_bits_or_curve: str | None
    is_precertificate: bool
    is_wildcard_present: bool
    san_count: int
    first_seen_ct: datetime | None
    last_seen_ct: datetime | None
    subject_alternative_names: list[str]
