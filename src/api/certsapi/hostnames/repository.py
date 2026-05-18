"""Hostname database queries: filtered search with keyset cursor pagination."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from ctpool.models.certificate import Certificate
from ctpool.models.certificate_hostname import CertificateHostname
from ctpool.models.hostname import Hostname
from sqlalchemy import ColumnElement, asc, desc, func, literal_column, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from certsapi.hostnames.cursor import PageCursor
from certsapi.hostnames.filter_builder import build_where_clause
from certsapi.hostnames.models import (
    CertEmbedResponse,
    HostnameLatestCertSummary,
    HostnameResult,
    HostnameSearchParams,
    SortField,
)
from certsapi.hostnames.query_parser import ParsedQuery

# Maps each SortField to (column_attribute, is_ascending)
_SORT_CONFIG: dict[SortField, tuple[InstrumentedAttribute[Any], bool]] = {
    SortField.not_before_asc: (Hostname.latest_cert_not_before, True),
    SortField.not_before_desc: (Hostname.latest_cert_not_before, False),
    SortField.not_after_asc: (Hostname.latest_cert_not_after, True),
    SortField.not_after_desc: (Hostname.latest_cert_not_after, False),
}


def _keyset_cond(
    col: InstrumentedAttribute[Any],
    is_asc: bool,
    cursor: PageCursor,
) -> ColumnElement[bool]:
    """Build the keyset WHERE condition that resumes pagination after *cursor*."""
    ts = datetime.fromtimestamp(cursor.timestamp_ms / 1000, tz=UTC)
    cid = uuid.UUID(cursor.id_uuid)
    if is_asc:
        return tuple_(col, Hostname.id) > (ts, cid)
    return tuple_(col, Hostname.id) < (ts, cid)


def _order_clauses(col: InstrumentedAttribute[Any], is_asc: bool) -> list[Any]:
    """Return ORDER BY expressions for the given column and direction."""
    if is_asc:
        return [asc(col).nullsfirst(), asc(Hostname.id)]
    return [desc(col).nullslast(), desc(Hostname.id)]


def _cert_embed(cert: Certificate | None, sans: list[str]) -> CertEmbedResponse | None:
    """Convert a Certificate ORM row + SAN list to a CertEmbedResponse, or None."""
    if cert is None:
        return None
    return CertEmbedResponse(
        fingerprint_sha256=cert.fingerprint_sha256,
        spki_sha256=cert.spki_sha256,
        not_before=cert.not_before,
        not_after=cert.not_after,
        issuer_dn=cert.issuer_dn,
        issuer_common_name=cert.issuer_common_name,
        issuer_organization=cert.issuer_organization,
        subject_common_name=cert.subject_common_name,
        is_wildcard_present=cert.is_wildcard_present,
        is_precertificate=cert.is_precertificate,
        subject_alternative_names=sans,
    )


def _latest_cert_summary(hostname: Hostname) -> HostnameLatestCertSummary | None:
    """Build a HostnameLatestCertSummary from stored hostname columns, or None."""
    if hostname.latest_cert_fingerprint_sha256 is None:
        return None
    if (
        hostname.latest_cert_not_before is None
        or hostname.latest_cert_not_after is None
    ):
        return None
    return HostnameLatestCertSummary(
        fingerprint_sha256=hostname.latest_cert_fingerprint_sha256,
        not_before=hostname.latest_cert_not_before,
        not_after=hostname.latest_cert_not_after,
        issuer_cn=hostname.latest_cert_issuer_cn,
        issuer_org=hostname.latest_cert_issuer_org,
        subject_cn=hostname.latest_cert_subject_cn,
        is_precert=bool(hostname.latest_cert_is_precert),
        seen_at=hostname.latest_cert_seen_at,
    )


def _to_result(
    hostname: Hostname,
    cert: Certificate | None,
    embed: bool,
    sans: list[str] | None = None,
) -> HostnameResult:
    """Convert ORM row(s) to a HostnameResult response model."""
    return HostnameResult(
        id=hostname.id,
        hostname=hostname.hostname,
        registrable_domain=hostname.registrable_domain,
        is_wildcard=hostname.is_wildcard,
        first_seen_ct=hostname.first_seen_ct,
        last_seen_ct=hostname.last_seen_ct,
        latest_cert_not_before=hostname.latest_cert_not_before,
        latest_cert_not_after=hostname.latest_cert_not_after,
        latest_cert_summary=_latest_cert_summary(hostname),
        latest_cert=_cert_embed(cert, sans or []) if embed else None,
    )


class HostnameRepository:
    """Executes hostname search queries with keyset pagination against the DB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    _ESTIMATE_CAP: int = 10_000

    async def count_estimate(
        self,
        parsed: ParsedQuery,
        params: HostnameSearchParams,
    ) -> int:
        """Return a bounded exact row count for this query.

        Counts up to _ESTIMATE_CAP rows exactly, then returns _ESTIMATE_CAP + 1
        to signal "more than _ESTIMATE_CAP". Accurate regardless of table
        statistics freshness; fast because the inner query stops scanning early.
        """
        where = build_where_clause(parsed, params.recursive, params.depth)
        inner: Any = (
            select(literal_column("1"))
            .select_from(Hostname)
            .where(*where)
            .limit(self._ESTIMATE_CAP + 1)
        )
        stmt = select(func.count()).select_from(inner.subquery())
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def search(
        self,
        parsed: ParsedQuery,
        params: HostnameSearchParams,
        cursor: PageCursor | None,
    ) -> list[HostnameResult]:
        """Run the hostname search and return up to params.limit + 1 results."""
        col, is_asc = _SORT_CONFIG[params.sort]
        where = list(build_where_clause(parsed, params.recursive, params.depth))
        if cursor is not None:
            where.append(_keyset_cond(col, is_asc, cursor))
        order = _order_clauses(col, is_asc)
        if params.include_certs:
            return await self._query_with_certs(where, order, params.limit)
        return await self._query_hostnames_only(where, order, params.limit)

    async def _query_with_certs(
        self,
        where: list[ColumnElement[bool]],
        order: list[Any],
        limit: int,
    ) -> list[HostnameResult]:
        """SELECT hostnames LEFT JOIN certificates, returning embedded cert data."""
        stmt = (
            select(Hostname, Certificate)
            .outerjoin(
                Certificate,
                Certificate.fingerprint_sha256
                == Hostname.latest_cert_fingerprint_sha256,
            )
            .where(*where)
            .order_by(*order)
            .limit(limit + 1)
        )
        rows = (await self._session.execute(stmt)).all()
        cert_ids = [row[1].id for row in rows if row[1] is not None]
        sans_map = await self._fetch_sans_for_certs(cert_ids)
        return [
            _to_result(
                row[0],
                row[1],
                True,
                sans_map.get(row[1].id) if row[1] is not None else None,
            )
            for row in rows
        ]

    async def _fetch_sans_for_certs(
        self, cert_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        """Return {cert_id: sorted_hostnames} for the given cert IDs in one query."""
        if not cert_ids:
            return {}
        stmt = (
            select(CertificateHostname.certificate_id, Hostname.hostname)
            .join(Hostname, Hostname.id == CertificateHostname.hostname_id)
            .where(CertificateHostname.certificate_id.in_(cert_ids))
            .order_by(CertificateHostname.certificate_id, Hostname.hostname)
        )
        rows = (await self._session.execute(stmt)).all()
        result: dict[uuid.UUID, list[str]] = {}
        for cert_id, hn in rows:
            result.setdefault(cert_id, []).append(hn)
        return result

    async def _query_hostnames_only(
        self,
        where: list[ColumnElement[bool]],
        order: list[Any],
        limit: int,
    ) -> list[HostnameResult]:
        """SELECT hostnames only, omitting certificate data."""
        stmt = select(Hostname).where(*where).order_by(*order).limit(limit + 1)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_result(h, None, False) for h in rows]
