"""Pydantic models for the ingestion statistics endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    """Throughput aggregates for a single time window."""

    window_seconds: int
    observations_per_sec: float
    certs_per_min: float
    hostnames_per_min: float


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


class StatsResponse(BaseModel):
    """Global ingestion statistics."""

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
