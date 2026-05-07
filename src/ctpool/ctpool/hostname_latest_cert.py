"""Deterministic ranking logic for updating hostname latest-cert summary fields.

Exports:
    StoredCertSummary      — Dataclass carrying the currently-stored cert fields.
    IncomingCertSummary    — Dataclass carrying the incoming cert's relevant fields.
    should_update_latest_cert — Pure ranking predicate.
    build_latest_cert_fields  — Build the dict of fields to write on update.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredCertSummary:
    """Fields from the currently-stored hostname latest-cert summary."""

    fingerprint_sha256: str | None
    not_before: datetime | None
    not_after: datetime | None
    seen_at: datetime | None


@dataclass(frozen=True)
class IncomingCertSummary:
    """Fields from the incoming certificate being evaluated."""

    fingerprint_sha256: str
    not_before: datetime
    not_after: datetime
    issuer_cn: str | None
    issuer_org: str | None
    subject_cn: str | None
    is_precert: bool
    observed_at: datetime


def should_update_latest_cert(
    stored: StoredCertSummary,
    incoming: IncomingCertSummary,
) -> bool:
    """Return True if the incoming cert should replace the stored summary.

    Ranking rule (deterministic, no ties):
    1. No cert stored yet → always update.
    2. incoming.not_after > stored.not_after → update.
    3. Equal not_after + incoming.not_before > stored.not_before → update.
    4. Both dates equal + incoming.observed_at > stored.seen_at → update.
    5. All equal + incoming.fingerprint < stored.fingerprint (lex) → update.

    Args:
        stored:   Summary of the currently-stored cert (may have None fields).
        incoming: Summary of the new cert being considered.

    Returns:
        True if the hostname's latest-cert summary should be updated.
    """
    if stored.fingerprint_sha256 is None:
        return True

    if stored.not_after is None or incoming.not_after > stored.not_after:
        return True
    if incoming.not_after < stored.not_after:
        return False

    # not_after is equal
    if stored.not_before is None or incoming.not_before > stored.not_before:
        return True
    if incoming.not_before < stored.not_before:
        return False

    # both dates equal — use seen_at as tiebreaker
    if stored.seen_at is None or incoming.observed_at > stored.seen_at:
        return True
    if incoming.observed_at < stored.seen_at:
        return False

    # all equal — lexicographic fingerprint tiebreaker (lower wins to be stable)
    return incoming.fingerprint_sha256 < stored.fingerprint_sha256


def build_latest_cert_fields(
    incoming: IncomingCertSummary,
) -> dict[str, object]:
    """Return the dict of hostname column updates for a new latest-cert.

    Args:
        incoming: The cert that won the ranking comparison.

    Returns:
        Column-value mapping ready to pass to a SQLAlchemy update statement.
    """
    return {
        "latest_cert_fingerprint_sha256": incoming.fingerprint_sha256,
        "latest_cert_not_before": incoming.not_before,
        "latest_cert_not_after": incoming.not_after,
        "latest_cert_issuer_cn": incoming.issuer_cn,
        "latest_cert_issuer_org": incoming.issuer_org,
        "latest_cert_subject_cn": incoming.subject_cn,
        "latest_cert_is_precert": incoming.is_precert,
        "latest_cert_seen_at": incoming.observed_at,
    }
