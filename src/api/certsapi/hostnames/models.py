"""Pydantic request-parameter and response models for hostname search."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SortField(StrEnum):
    """Valid values for the hostname search sort parameter."""

    not_before_asc = "not_before_asc"
    not_before_desc = "not_before_desc"
    not_after_asc = "not_after_asc"
    not_after_desc = "not_after_desc"


class HostnameSearchParams(BaseModel):
    """Validated query parameters for GET /v1/hostnames."""

    q: str = Field(..., description="Hostname query: exact, *.prefix, re:pattern")
    recursive: bool = Field(
        default=False,
        description="Search by registrable domain instead of exact hostname",
    )
    depth: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of DNS labels above the queried domain to return. "
            "depth=1 returns only direct children (e.g. foo.example.com); "
            "depth=2 returns children and grandchildren; and so on. "
            "Only meaningful when recursive=True."
        ),
    )
    sort: SortField = Field(
        default=SortField.not_before_desc,
        description="Sort order for results",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of results to return",
    )
    cursor: str | None = Field(
        default=None,
        description="Opaque pagination cursor from a previous response",
    )
    include_certs: bool = Field(
        default=False,
        description="Embed latest certificate data in each result",
    )


class CertEmbedResponse(BaseModel):
    """Curated certificate fields embedded in a hostname search result."""

    fingerprint_sha256: str
    spki_sha256: str
    not_before: datetime
    not_after: datetime
    issuer_dn: str
    issuer_common_name: str | None
    issuer_organization: str | None
    subject_common_name: str | None
    is_wildcard_present: bool
    is_precertificate: bool
    subject_alternative_names: list[str]


class HostnameLatestCertSummary(BaseModel):
    """Compact latest-cert summary stored directly on the hostname row."""

    fingerprint_sha256: str
    not_before: datetime
    not_after: datetime
    issuer_cn: str | None
    issuer_org: str | None
    subject_cn: str | None
    is_precert: bool
    seen_at: datetime | None


class HostnameResult(BaseModel):
    """A single hostname record returned by the search endpoint."""

    id: uuid.UUID
    hostname: str
    registrable_domain: str
    is_wildcard: bool
    first_seen_ct: datetime | None
    last_seen_ct: datetime | None
    latest_cert_not_before: datetime | None
    latest_cert_not_after: datetime | None
    latest_cert_summary: HostnameLatestCertSummary | None = None
    latest_cert: CertEmbedResponse | None


class HostnameListResponse(BaseModel):
    """Paginated list of hostname search results."""

    items: list[HostnameResult]
    next_cursor: str | None
    total_returned: int
    total_estimate: int | None = Field(
        default=None,
        description=(
            "Exact row count for the full result set, capped at 10,001. "
            "Values ≤ 10,000 are exact; 10,001 means 'more than 10,000 rows match'. "
            "Only present on the first page (no cursor)."
        ),
    )
