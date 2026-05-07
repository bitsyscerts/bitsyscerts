"""Unit tests for ctpool.hostname_latest_cert.

Covers:
    - should_update_latest_cert: all 5 ranking rules
    - should_update_latest_cert: edge cases (equal stored and incoming)
    - build_latest_cert_fields: output shape and values
"""

from __future__ import annotations

from datetime import UTC, datetime

from ctpool.hostname_latest_cert import (
    IncomingCertSummary,
    StoredCertSummary,
    build_latest_cert_fields,
    should_update_latest_cert,
)

_T1 = datetime(2024, 1, 1, tzinfo=UTC)
_T2 = datetime(2025, 1, 1, tzinfo=UTC)
_T3 = datetime(2026, 1, 1, tzinfo=UTC)
_T4 = datetime(2027, 1, 1, tzinfo=UTC)


def _stored(**kwargs) -> StoredCertSummary:
    defaults = {
        "fingerprint_sha256": "aaaa",
        "not_before": _T1,
        "not_after": _T2,
        "seen_at": _T1,
    }
    defaults.update(kwargs)
    return StoredCertSummary(**defaults)


def _incoming(**kwargs) -> IncomingCertSummary:
    defaults = {
        "fingerprint_sha256": "bbbb",
        "not_before": _T1,
        "not_after": _T2,
        "observed_at": _T2,
        "issuer_cn": None,
        "issuer_org": None,
        "subject_cn": None,
        "is_precert": False,
    }
    defaults.update(kwargs)
    return IncomingCertSummary(**defaults)


# ---------------------------------------------------------------------------
# Rule 1: no stored cert → always update
# ---------------------------------------------------------------------------


def test_no_stored_cert_always_updates():
    stored = StoredCertSummary(
        fingerprint_sha256=None, not_before=None, not_after=None, seen_at=None
    )
    incoming = _incoming()
    assert should_update_latest_cert(stored, incoming) is True


# ---------------------------------------------------------------------------
# Rule 2: incoming.not_after > stored.not_after → update
# ---------------------------------------------------------------------------


def test_longer_validity_triggers_update():
    stored = _stored(not_after=_T2)
    incoming = _incoming(not_after=_T3)
    assert should_update_latest_cert(stored, incoming) is True


def test_shorter_validity_does_not_update():
    stored = _stored(not_after=_T3)
    incoming = _incoming(not_after=_T2)
    assert should_update_latest_cert(stored, incoming) is False


# ---------------------------------------------------------------------------
# Rule 3: equal not_after, incoming.not_before > stored.not_before → update
# ---------------------------------------------------------------------------


def test_equal_not_after_later_not_before_updates():
    stored = _stored(not_after=_T3, not_before=_T1)
    incoming = _incoming(not_after=_T3, not_before=_T2)
    assert should_update_latest_cert(stored, incoming) is True


def test_equal_not_after_earlier_not_before_does_not_update():
    stored = _stored(not_after=_T3, not_before=_T2)
    incoming = _incoming(not_after=_T3, not_before=_T1)
    assert should_update_latest_cert(stored, incoming) is False


# ---------------------------------------------------------------------------
# Rule 4: both dates equal, incoming.observed_at > stored.seen_at → update
# ---------------------------------------------------------------------------


def test_equal_dates_later_observation_updates():
    stored = _stored(not_after=_T3, not_before=_T2, seen_at=_T1)
    incoming = _incoming(not_after=_T3, not_before=_T2, observed_at=_T4)
    assert should_update_latest_cert(stored, incoming) is True


def test_equal_dates_earlier_observation_does_not_update():
    stored = _stored(not_after=_T3, not_before=_T2, seen_at=_T4)
    incoming = _incoming(not_after=_T3, not_before=_T2, observed_at=_T1)
    assert should_update_latest_cert(stored, incoming) is False


# ---------------------------------------------------------------------------
# Rule 5: all equal, incoming fingerprint < stored (lexicographic) → update
# ---------------------------------------------------------------------------


def test_equal_everything_smaller_fingerprint_updates():
    stored = _stored(
        not_after=_T3, not_before=_T2, seen_at=_T4, fingerprint_sha256="cccc"
    )
    incoming = _incoming(
        not_after=_T3, not_before=_T2, observed_at=_T4, fingerprint_sha256="aaaa"
    )
    assert should_update_latest_cert(stored, incoming) is True


def test_equal_everything_larger_fingerprint_does_not_update():
    stored = _stored(
        not_after=_T3, not_before=_T2, seen_at=_T4, fingerprint_sha256="aaaa"
    )
    incoming = _incoming(
        not_after=_T3, not_before=_T2, observed_at=_T4, fingerprint_sha256="cccc"
    )
    assert should_update_latest_cert(stored, incoming) is False


def test_equal_everything_same_fingerprint_does_not_update():
    stored = _stored(
        not_after=_T3, not_before=_T2, seen_at=_T4, fingerprint_sha256="same"
    )
    incoming = _incoming(
        not_after=_T3, not_before=_T2, observed_at=_T4, fingerprint_sha256="same"
    )
    assert should_update_latest_cert(stored, incoming) is False


# ---------------------------------------------------------------------------
# build_latest_cert_fields
# ---------------------------------------------------------------------------


def test_build_latest_cert_fields_returns_expected_keys():
    incoming = _incoming(
        fingerprint_sha256="fp123",
        not_before=_T1,
        not_after=_T2,
        observed_at=_T3,
        issuer_cn="TestCA",
        issuer_org="Acme",
        subject_cn="example.com",
        is_precert=True,
    )
    fields = build_latest_cert_fields(incoming)
    assert fields["latest_cert_fingerprint_sha256"] == "fp123"
    assert fields["latest_cert_not_before"] == _T1
    assert fields["latest_cert_not_after"] == _T2
    assert fields["latest_cert_issuer_cn"] == "TestCA"
    assert fields["latest_cert_issuer_org"] == "Acme"
    assert fields["latest_cert_subject_cn"] == "example.com"
    assert fields["latest_cert_is_precert"] is True
    assert fields["latest_cert_seen_at"] == _T3


def test_build_latest_cert_fields_optional_none():
    incoming = _incoming(issuer_cn=None, issuer_org=None, subject_cn=None)
    fields = build_latest_cert_fields(incoming)
    assert fields["latest_cert_issuer_cn"] is None
    assert fields["latest_cert_issuer_org"] is None
    assert fields["latest_cert_subject_cn"] is None
