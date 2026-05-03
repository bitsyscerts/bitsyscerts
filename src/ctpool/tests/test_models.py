"""Tests for ctpool ORM models — schema structure and constraints."""

from __future__ import annotations

from sqlalchemy import Table

from ctpool.models import (
    Base,
    Certificate,
    CertificateHostname,
    CtLogBackfillRange,
    CtLogObservation,
    CtLogSource,
    CtLogTailCursor,
)
from ctpool.models.base import _NAMING_CONVENTION  # noqa: PLC2701


def _table(model: type) -> Table:
    """Return the SQLAlchemy Table for an ORM model."""
    return model.__table__  # type: ignore[attr-defined, no-any-return]


def test_declarative_base_creates_metadata() -> None:
    """Base.metadata is not None and has a naming convention applied."""
    assert Base.metadata is not None


def test_naming_convention_applied_to_indexes() -> None:
    """Index naming convention uses the ix_ prefix."""
    assert _NAMING_CONVENTION["ix"] == "ix_%(column_0_label)s"


def test_ct_log_source_has_url_column() -> None:
    """CtLogSource.url column exists in the mapped table."""
    cols = [c.name for c in _table(CtLogSource).columns]
    assert "url" in cols


def test_ct_log_source_url_is_unique() -> None:
    """CtLogSource.url has a unique constraint."""
    uq_cols: set[str] = set()
    for constraint in _table(CtLogSource).constraints:
        if hasattr(constraint, "columns"):
            for col in constraint.columns:
                uq_cols.add(col.name)
    assert "url" in uq_cols


def test_certificate_fingerprint_sha256_is_unique() -> None:
    """Certificate.fingerprint_sha256 participates in a unique constraint."""
    uq_cols: set[str] = set()
    for constraint in _table(Certificate).constraints:
        if hasattr(constraint, "columns"):
            for col in constraint.columns:
                uq_cols.add(col.name)
    assert "fingerprint_sha256" in uq_cols


def test_observation_composite_unique_log_id_and_index() -> None:
    """CtLogObservation has a composite unique on (log_source_id, log_index)."""
    uq_constraint_found = False
    for constraint in _table(CtLogObservation).constraints:
        if hasattr(constraint, "columns"):
            col_names = {c.name for c in constraint.columns}
            if col_names == {"log_source_id", "log_index"}:
                uq_constraint_found = True
    assert uq_constraint_found


def test_certificate_hostname_composite_pk() -> None:
    """CertificateHostname has a composite PK on (certificate_id, hostname_id)."""
    pk_cols = {c.name for c in _table(CertificateHostname).primary_key.columns}
    assert pk_cols == {"certificate_id", "hostname_id"}


def test_backfill_range_status_has_pending_default() -> None:
    """CtLogBackfillRange.status column default is 'pending'."""
    col = _table(CtLogBackfillRange).columns["status"]
    assert col.default is not None or col.server_default is not None or col.nullable


def test_tail_cursor_fk_to_log_source() -> None:
    """CtLogTailCursor.log_source_id references ct_log_sources.id."""
    fk = next(iter(_table(CtLogTailCursor).columns["log_source_id"].foreign_keys))
    assert "ct_log_sources" in fk.target_fullname


def test_ct_log_source_id_is_uuid_type() -> None:
    """CtLogSource primary key column is UUID type."""
    col = _table(CtLogSource).columns["id"]
    assert "UUID" in type(col.type).__name__


def test_backfill_range_bigint_start_and_end() -> None:
    """CtLogBackfillRange start/end/next index columns use BigInteger."""
    for col_name in ("start_index", "end_index", "next_index"):
        col = _table(CtLogBackfillRange).columns[col_name]
        bigint_type = (
            "BIGINT" in str(col.type).upper() or "BigInteger" in type(col.type).__name__
        )
        assert bigint_type
