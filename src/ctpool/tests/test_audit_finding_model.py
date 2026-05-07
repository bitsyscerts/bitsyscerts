"""Unit tests for the CtAuditFinding ORM model structure."""

from __future__ import annotations

from sqlalchemy import inspect

from ctpool.audit_constants import STATUS_OPEN
from ctpool.models.audit_finding import CtAuditFinding


def _column_names() -> set[str]:
    mapper = inspect(CtAuditFinding)
    return {c.key for c in mapper.columns}


def test_audit_finding_table_name() -> None:
    """CtAuditFinding maps to ct_audit_findings."""
    assert CtAuditFinding.__tablename__ == "ct_audit_findings"


def test_audit_finding_has_required_detection_columns() -> None:
    """All detection-phase columns are present on the model."""
    cols = _column_names()
    required = {
        "id",
        "log_source_id",
        "finding_type",
        "severity",
        "status",
        "range_id",
        "start_index",
        "end_index",
        "missing_count",
        "details_json",
        "created_at",
    }
    assert required.issubset(cols)


def test_audit_finding_has_repair_columns() -> None:
    """All repair-phase columns are present on the model."""
    cols = _column_names()
    repair = {
        "repair_action",
        "repair_details_json",
        "repair_attempted_at",
        "repair_attempt_count",
        "resolved_at",
        "resolved_by",
    }
    assert repair.issubset(cols)


def test_audit_finding_status_default() -> None:
    """status field has server_default 'open'."""
    table = CtAuditFinding.__table__
    status_col = table.c["status"]
    # server_default is a text expression; check it contains 'open'
    assert "open" in str(status_col.server_default.arg)


def test_audit_finding_repair_attempt_count_default_is_zero() -> None:
    """repair_attempt_count column has server_default of 0."""
    table = CtAuditFinding.__table__
    col = table.c["repair_attempt_count"]
    assert "0" in str(col.server_default.arg)


def test_audit_finding_nullable_fields_accept_none() -> None:
    """Nullable optional fields can be instantiated with None."""
    finding = CtAuditFinding(
        finding_type="stale_backfill_claim",
        severity="warning",
        status=STATUS_OPEN,
        log_source_id=None,
        range_id=None,
        start_index=None,
        end_index=None,
        missing_count=None,
        details_json=None,
    )
    assert finding.log_source_id is None
    assert finding.range_id is None
    assert finding.missing_count is None
