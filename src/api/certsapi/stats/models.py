"""Pydantic models for the ingestion statistics endpoint.

# NOTE (201-500 line warning zone): This module consolidates all stats response
# models in one file.  Splitting by concern would create many small files with
# no reuse — e.g. StorageProjection requires StorageProjectionCategoryBreakdown
# inline.  Resolve by extracting if any model group exceeds 10+ fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProjectionConfidence = Literal["low", "medium", "high"]


class LogStatsItem(BaseModel):
    """Per-CT-log statistics."""

    log_id: uuid.UUID
    description: str
    url: str
    log_state: str
    tail_position: int | None
    last_tail_sync: datetime | None
    backfill_complete_pct: float | None
    tail_freshness_lag_seconds: int | None = None


class TableStorageItem(BaseModel):
    """Disk usage for one database table."""

    table_name: str
    row_estimate: int
    size_bytes: int
    size_pretty: str


class StorageStats(BaseModel):
    """Database-level storage summary."""

    total_size_bytes: int
    total_size_pretty: str
    tables: list[TableStorageItem]


class StorageProjectionCategoryBreakdown(BaseModel):
    """Per-category byte estimates from the profile-aware projection."""

    hostname_index_bytes: int | None = None
    certificate_metadata_bytes: int | None = None
    certificate_public_key_bytes: int | None = None
    raw_cert_der_bytes: int | None = None
    ct_observations_bytes: int | None = None
    entry_outcomes_bytes: int | None = None
    cert_hostname_relationships_bytes: int | None = None
    metrics_and_ops_bytes: int | None = None
    index_overhead_bytes: int | None = None


class IngestionWorkload(BaseModel):
    """Observed vs planned observation counts for the current backfill workload."""

    planned_observations_total: int
    planned_observations_completed: int
    planned_observations_remaining: int
    sync_percent: float | None
    eta_seconds: int | None = None


class StorageProjection(BaseModel):
    """Estimated sync progress and projected database storage usage."""

    status: Literal[
        "available",
        "insufficient_backfill_plan",
        "insufficient_observations",
    ]
    projection_basis: str | None = None
    profile: str | None = None
    category_breakdown: StorageProjectionCategoryBreakdown | None = None
    database_size_bytes: int
    ct_observations_count: int
    certificates_count: int
    hostnames_count: int
    certificate_hostnames_count: int
    planned_observations_total: int
    planned_observations_completed: int
    planned_observations_remaining: int
    sync_percent_by_observation: float | None
    bytes_per_observation_current: float | None
    projected_remaining_database_size_bytes: int | None
    projected_final_database_size_bytes: int | None
    storage_percent_of_projected: float | None
    projection_low_bytes: int | None
    projection_current_bytes: int | None
    projection_high_bytes: int | None
    confidence: ProjectionConfidence | None = None
    ingestion_workload: IngestionWorkload | None = None
    disk_total_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_free_bytes: int | None = None
    disk_free_percent: float | None = None
    configured_min_free_disk_bytes: int | None = None
    projected_disk_free_after_sync_bytes: int | None = None
    projected_fits_on_disk: bool | None = None
    notes: list[str] = Field(default_factory=list)


class DbContentionStats(BaseModel):
    """Operator-facing shared DB contention status."""

    status: Literal[
        "disabled",
        "initializing",
        "healthy",
        "throttling",
        "stale",
    ]
    degraded_mode_active: bool
    pressure_ema: float
    base_sleep_seconds: float
    shared_batch_size_cap: int | None
    effective_batch_size_cap: int | None
    updated_at: datetime | None
    notes: list[str] = Field(default_factory=list)
    total_retryable_errors: int = 0
    retryable_errors_per_min_5min: float | None = None


class IngestionRateWindow(BaseModel):
    """Throughput aggregates for a single time window.

    Sprint 5 introduces precise per-metric labels; the original
    ``observations_per_sec`` / ``certs_per_min`` / ``hostnames_per_min``
    fields remain for backwards compatibility but should be considered
    *legacy aliases*.  Prefer the explicit ``*_per_min`` names below.
    """

    window_seconds: int
    # Legacy fields — kept for compatibility with existing consumers.
    observations_per_sec: float
    certs_per_min: float
    hostnames_per_min: float
    # Sprint 5 precise labels.
    observations_per_min: float | None = None
    certificates_parsed_per_min: float | None = None
    new_unique_certificates_per_min: float | None = None
    duplicate_certificates_per_min: float | None = None
    hostnames_observed_per_min: float | None = None
    new_unique_hostnames_per_min: float | None = None
    known_hostnames_per_min: float | None = None
    retryable_errors_per_min: float | None = None
    terminal_entry_errors_per_min: float | None = None


class IngestionRateStats(BaseModel):
    """Global ingestion throughput across multiple time windows."""

    windows: list[IngestionRateWindow]


class TailFreshnessStats(BaseModel):
    """Aggregate tail-cursor staleness summary across all CT logs."""

    stale_threshold_seconds: int
    stale_log_count: int
    oldest_lag_seconds: int | None
    median_lag_seconds: int | None


class EntryOutcomeStats(BaseModel):
    """Terminal outcome counts for all processed CT log indices."""

    stored: int
    parse_error: int
    unsupported_entry_type: int
    skipped_by_policy: int


class BackfillRangeStats(BaseModel):
    """Status counts for ct_log_backfill_ranges rows."""

    pending: int
    in_progress: int
    stale_in_progress: int
    completed: int
    failed: int
    dispatch_mode: str | None = None
    is_primary: bool = True


class AuditHealth(BaseModel):
    """Counts of open audit findings grouped by severity."""

    open_critical: int
    open_error: int
    open_warning: int
    open_info: int
    total_open: int
    status: Literal["ok", "attention_needed"]


class BackfillHealth(BaseModel):
    """Computed backfill health summary derived from range status counts."""

    status: Literal["ok", "warning"]
    failed_ranges: int
    stale_ranges: int
    message: str


class MetricsRetentionStats(BaseModel):
    """ingestion_metrics table health and retention configuration."""

    ingestion_metrics_rows: int
    oldest_ingestion_metric_at: datetime | None
    metrics_retention_days: int


class WorkerSummaryItem(BaseModel):
    """Per-worker activity row returned in stats responses."""

    worker_id: str
    worker_kind: str
    log_source_id: str | None = None
    log_name: str | None = None
    direction: str | None = None
    status: str
    is_stale: bool
    last_heartbeat_at: str
    last_heartbeat_age_seconds: int
    started_at: str
    current_index: int | None = None
    processed_entries: int
    stored_certificates: int
    duplicate_certificates: int
    observed_hostnames: int
    new_hostnames: int
    parse_errors: int
    retryable_errors: int
    terminal_errors: int
    last_error_type: str | None = None
    last_error_message: str | None = None


class WorkerSummary(BaseModel):
    """Aggregated worker activity included in stats responses."""

    active_total: int
    stale_total: int
    tail_active: int
    backfill_active: int
    items: list[WorkerSummaryItem]


class BackfillStateItem(BaseModel):
    """Per-log backfill state row returned in stats responses."""

    log_source_id: str
    log_name: str | None = None
    log_url: str | None = None
    status: str
    claimed_by: str | None = None
    is_stale: bool = False
    checkpoint_index: int | None = None
    backfill_start_index: int | None = None
    backfill_end_index: int | None = None
    progress_percent: float | None = None
    last_heartbeat_age_seconds: float | None = None
    last_error_type: str | None = None
    last_error_message: str | None = None
    last_error_at: str | None = None
    next_retry_at: str | None = None
    rate_limited_until: str | None = None
    retry_count: int = 0
    retryable_error_count: int = 0
    terminal_error_count: int = 0
    completed_at: str | None = None


class BackfillStateSummary(BaseModel):
    """Aggregated per-log backfill state included in stats responses."""

    total_logs: int = 0
    pending: int = 0
    claimed: int = 0
    processing: int = 0
    retrying: int = 0
    rate_limited: int = 0
    paused: int = 0
    complete: int = 0
    error: int = 0
    stale: int = 0
    items: list[BackfillStateItem] = []
    dispatch_mode: str | None = None
    is_primary: bool = False


class IngestionHealth(BaseModel):
    """Self-healing ingestion summary used by the dashboard error card."""

    retrying_logs: int = 0
    rate_limited_logs: int = 0
    paused_logs: int = 0
    error_logs: int = 0
    stale_workers: int = 0
    retryable_error_total: int = 0
    terminal_error_total: int = 0
    recent_terminal_outcomes: int = 0
    status: Literal["ok", "attention_needed"] = "ok"


class MaintenanceDeleted(BaseModel):
    """Per-table deletion totals for the most recent maintenance run."""

    certificates: int = 0
    certificate_hostnames: int = 0
    observations: int = 0
    entry_outcomes: int = 0
    ingestion_metrics: int = 0


class MaintenanceStatus(BaseModel):
    """Retention-maintenance card surfaced to the dashboard.

    ``status`` of ``"never_ran"`` means no maintenance has executed yet
    and Lite mode may temporarily retain more data.  ``"complete"`` /
    ``"failed"`` mirror the most recent ``ct_maintenance_runs`` row.
    """

    status: Literal["never_ran", "running", "complete", "failed", "unknown"] = (
        "never_ran"
    )
    active_profile: str | None = None
    last_prune_started_at: datetime | None = None
    last_prune_completed_at: datetime | None = None
    last_prune_status: Literal["running", "complete", "failed"] | None = None
    last_prune_mode: Literal["dry_run", "execute"] | None = None
    last_prune_deleted: MaintenanceDeleted = MaintenanceDeleted()
    preserved_hostnames: int | None = None
    duration_ms: int | None = None
    next_prune_due_at: datetime | None = None
    is_enforced: bool = False
    error_message: str | None = None


class StorageProfileSettings(BaseModel):
    """Active instance storage settings embedded in stats responses."""

    storage_profile: str
    cert_storage_mode: str
    hostname_retention_mode: str
    backfill_days: int
    cert_retention_days: int
    observation_retention_days: int
    entry_outcome_retention_days: int
    metrics_retention_days: int
    settings_hash: str
    source: Literal["database", "bootstrap_default", "none"]


class SnapshotMetadata(BaseModel):
    """Freshness metadata for the stats payload (Sprint 5).

    Lets the UI tell the operator how old the displayed numbers are and
    whether the API is serving a stale snapshot.  ``source`` indicates
    where the payload came from: a cached snapshot, a fresh live query,
    or no snapshot at all.
    """

    generated_at: datetime | None = None
    age_seconds: float | None = None
    is_stale: bool = False
    stale_threshold_seconds: int | None = None
    source: Literal["snapshot", "live", "none"] = "live"


class StatsResponse(BaseModel):
    """Global ingestion statistics."""

    snapshot: SnapshotMetadata | None = None
    total_hostnames: int
    storage_profile: StorageProfileSettings | None = None
    total_certificates: int
    total_logs: int
    storage: StorageStats
    storage_projection: StorageProjection
    db_contention: DbContentionStats
    ingestion_rate: IngestionRateStats
    tail_freshness: TailFreshnessStats
    entry_outcomes: EntryOutcomeStats
    backfill_ranges: BackfillRangeStats
    backfill_health: BackfillHealth | None = None
    metrics_retention: MetricsRetentionStats | None = None
    audit_health: AuditHealth | None = None
    logs: list[LogStatsItem]
    workers: WorkerSummary | None = None
    backfill_state: BackfillStateSummary | None = None
    ingestion_health: IngestionHealth | None = None
    maintenance: MaintenanceStatus | None = None


# Resolve the forward reference to SnapshotMetadata, which is defined
# after StatsResponse so the schema reads top-down.
StatsResponse.model_rebuild()
