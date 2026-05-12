"""Typed result objects for per-entry persistence decisions.

These dataclasses let the ingestion pipeline carry precise write
classification forward without re-querying hot tables later.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CertificateUpsertResult:
    """Describe the outcome of one certificate upsert."""

    certificate_id: uuid.UUID
    inserted: bool


@dataclass(frozen=True)
class HostnameUpsertResult:
    """Describe the outcome of one hostname upsert."""

    hostname_id: uuid.UUID
    inserted: bool


@dataclass(frozen=True)
class EntryWriteMetrics:
    """Summarize one successfully persisted entry for metrics emission."""

    observations_processed: int = 1
    certificates_parsed: int = 1
    new_unique_certificates: int = 0
    duplicate_certificates: int = 0
    hostnames_observed: int = 0
    new_unique_hostnames: int = 0
    known_hostnames: int = 0

    @classmethod
    def from_persisted_entry(
        cls,
        *,
        certificate_inserted: bool,
        hostnames_observed: int,
        new_unique_hostnames: int,
    ) -> EntryWriteMetrics:
        """Build metrics for one stored entry from local write decisions."""
        return cls(
            new_unique_certificates=1 if certificate_inserted else 0,
            duplicate_certificates=0 if certificate_inserted else 1,
            hostnames_observed=hostnames_observed,
            new_unique_hostnames=new_unique_hostnames,
            known_hostnames=hostnames_observed - new_unique_hostnames,
        )
