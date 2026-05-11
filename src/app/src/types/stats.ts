/** Mirrors certsapi/stats/models.py — keep in sync with backend. */

export interface LogStatsItem {
  log_id: string;
  description: string;
  url: string;
  log_state: string;
  tail_position: number | null;
  last_tail_sync: string | null;
  backfill_complete_pct: number | null;
  tail_freshness_lag_seconds: number | null;
}

export interface TableStorageItem {
  table_name: string;
  row_estimate: number;
  size_bytes: number;
  size_pretty: string;
}

export interface StorageStats {
  total_size_bytes: number;
  total_size_pretty: string;
  tables: TableStorageItem[];
}

export type StorageProjectionStatus =
  | "available"
  | "insufficient_backfill_plan"
  | "insufficient_observations";

export type ProjectionConfidence = "low" | "medium" | "high";

export interface IngestionWorkload {
  planned_observations_total: number;
  planned_observations_completed: number;
  planned_observations_remaining: number;
  sync_percent: number | null;
  eta_seconds?: number | null;
}

export interface StorageProjectionCategoryBreakdown {
  hostname_index_bytes: number | null;
  certificate_metadata_bytes: number | null;
  certificate_public_key_bytes: number | null;
  raw_cert_der_bytes: number | null;
  ct_observations_bytes: number | null;
  entry_outcomes_bytes: number | null;
  cert_hostname_relationships_bytes: number | null;
  metrics_and_ops_bytes: number | null;
  index_overhead_bytes: number | null;
}

export interface StorageProjection {
  status: StorageProjectionStatus;
  confidence?: ProjectionConfidence | null;
  ingestion_workload?: IngestionWorkload | null;
  projection_basis?: string | null;
  profile?: string | null;
  category_breakdown?: StorageProjectionCategoryBreakdown | null;
  database_size_bytes: number;
  ct_observations_count: number;
  certificates_count: number;
  hostnames_count: number;
  certificate_hostnames_count: number;
  planned_observations_total: number;
  planned_observations_completed: number;
  planned_observations_remaining: number;
  sync_percent_by_observation: number | null;
  bytes_per_observation_current: number | null;
  projected_remaining_database_size_bytes: number | null;
  projected_final_database_size_bytes: number | null;
  storage_percent_of_projected: number | null;
  projection_low_bytes: number | null;
  projection_current_bytes: number | null;
  projection_high_bytes: number | null;
  disk_total_bytes: number | null;
  disk_used_bytes: number | null;
  disk_free_bytes: number | null;
  disk_free_percent: number | null;
  configured_min_free_disk_bytes: number | null;
  projected_disk_free_after_sync_bytes: number | null;
  projected_fits_on_disk: boolean | null;
  notes: string[];
}

export type DbContentionStatus =
  | "disabled"
  | "initializing"
  | "healthy"
  | "throttling"
  | "stale";

export interface DbContentionStats {
  status: DbContentionStatus;
  degraded_mode_active: boolean;
  pressure_ema: number;
  base_sleep_seconds: number;
  shared_batch_size_cap: number | null;
  effective_batch_size_cap: number | null;
  updated_at: string | null;
  notes: string[];
  total_retryable_errors: number;
  retryable_errors_per_min_5min: number | null;
}

export interface IngestionRateWindow {
  window_seconds: number;
  // Legacy fields — kept for backwards compatibility.
  observations_per_sec: number;
  certs_per_min: number;
  hostnames_per_min: number;
  // Sprint 5: precise per-metric labels.
  observations_per_min?: number | null;
  certificates_parsed_per_min?: number | null;
  new_unique_certificates_per_min?: number | null;
  duplicate_certificates_per_min?: number | null;
  hostnames_observed_per_min?: number | null;
  new_unique_hostnames_per_min?: number | null;
  known_hostnames_per_min?: number | null;
  retryable_errors_per_min?: number | null;
  terminal_entry_errors_per_min?: number | null;
}

export interface SnapshotMetadata {
  generated_at: string | null;
  age_seconds: number | null;
  is_stale: boolean;
  stale_threshold_seconds: number | null;
  source: "snapshot" | "live" | "none";
}

export interface IngestionRateStats {
  windows: IngestionRateWindow[];
}

export interface TailFreshnessStats {
  stale_threshold_seconds: number;
  stale_log_count: number;
  oldest_lag_seconds: number | null;
  median_lag_seconds: number | null;
}

export interface EntryOutcomeStats {
  stored: number;
  parse_error: number;
  unsupported_entry_type: number;
  skipped_by_policy: number;
}

export interface BackfillRangeStats {
  pending: number;
  in_progress: number;
  stale_in_progress: number;
  completed: number;
  failed: number;
  dispatch_mode?: string | null;
  is_primary?: boolean;
}

export type BackfillHealthStatus = "ok" | "warning";

export interface BackfillHealth {
  status: BackfillHealthStatus;
  failed_ranges: number;
  stale_ranges: number;
  message: string;
}

export interface MetricsRetentionStats {
  ingestion_metrics_rows: number;
  oldest_ingestion_metric_at: string | null;
  metrics_retention_days: number;
}

export type AuditHealthStatus = "ok" | "attention_needed";

export interface AuditHealth {
  open_critical: number;
  open_error: number;
  open_warning: number;
  open_info: number;
  total_open: number;
  status: AuditHealthStatus;
}

export interface WorkerSummaryItem {
  worker_id: string;
  worker_kind: string;
  log_source_id: string | null;
  log_name: string | null;
  log_url: string | null;
  log_operator: string | null;
  direction: string | null;
  status: string;
  is_stale: boolean;
  last_heartbeat_at: string;
  last_heartbeat_age_seconds: number;
  started_at: string;
  current_index: number | null;
  checkpoint_index: number | null;
  batch_start_index: number | null;
  batch_end_index: number | null;
  processed_entries: number;
  stored_certificates: number;
  duplicate_certificates: number;
  observed_hostnames: number;
  new_hostnames: number;
  parse_errors: number;
  retryable_errors: number;
  terminal_errors: number;
  observations_per_min: number | null;
  new_unique_certificates_per_min: number | null;
  duplicate_certificates_per_min: number | null;
  new_unique_hostnames_per_min: number | null;
  known_hostnames_per_min: number | null;
  retry_count: number | null;
  next_retry_at: string | null;
  rate_limited_until: string | null;
  last_error_type: string | null;
  last_error_message: string | null;
}

export interface WorkerSummary {
  active_total: number;
  stale_total: number;
  tail_active: number;
  backfill_active: number;
  stats_active: number;
  maintenance_active: number;
  unknown_active: number;
  items: WorkerSummaryItem[];
}

export interface BackfillStateItem {
  log_source_id: string;
  log_name: string | null;
  log_url: string | null;
  status: string;
  claimed_by: string | null;
  is_stale: boolean;
  checkpoint_index: number | null;
  backfill_start_index: number | null;
  backfill_end_index: number | null;
  progress_percent: number | null;
  last_heartbeat_age_seconds: number | null;
  last_error_type: string | null;
  last_error_message: string | null;
  last_error_at?: string | null;
  next_retry_at?: string | null;
  rate_limited_until?: string | null;
  retry_count?: number;
  retryable_error_count?: number;
  terminal_error_count?: number;
  completed_at: string | null;
}

export interface BackfillStateSummary {
  total_logs: number;
  pending: number;
  claimed: number;
  processing: number;
  retrying: number;
  rate_limited?: number;
  paused: number;
  complete: number;
  error: number;
  stale: number;
  items: BackfillStateItem[];
  dispatch_mode?: string | null;
  is_primary?: boolean;
}

export interface IngestionHealth {
  retrying_logs: number;
  rate_limited_logs: number;
  paused_logs: number;
  error_logs: number;
  stale_workers: number;
  retryable_error_total: number;
  terminal_error_total: number;
  recent_terminal_outcomes: number;
  status: "ok" | "attention_needed";
}

export interface MaintenanceDeleted {
  certificates: number;
  certificate_hostnames: number;
  observations: number;
  entry_outcomes: number;
  ingestion_metrics: number;
}

export interface MaintenanceStatus {
  status: "never_ran" | "running" | "complete" | "failed" | "unknown";
  active_profile: string | null;
  last_prune_started_at: string | null;
  last_prune_completed_at: string | null;
  last_prune_status: "running" | "complete" | "failed" | null;
  last_prune_mode: "dry_run" | "execute" | null;
  last_prune_deleted: MaintenanceDeleted;
  preserved_hostnames: number | null;
  duration_ms: number | null;
  next_prune_due_at: string | null;
  is_enforced: boolean;
  error_message: string | null;
}

export interface StorageProfileSettings {
  storage_profile: string;
  cert_storage_mode: string;
  hostname_retention_mode: string;
  backfill_days: number;
  cert_retention_days: number;
  observation_retention_days: number;
  entry_outcome_retention_days: number;
  metrics_retention_days: number;
  settings_hash: string;
  source: "database" | "bootstrap_default" | "none";
}

export interface StatsResponse {
  snapshot?: SnapshotMetadata | null;
  total_hostnames: number;
  storage_profile: StorageProfileSettings | null;
  total_certificates: number;
  total_logs: number;
  storage: StorageStats;
  storage_projection: StorageProjection;
  db_contention: DbContentionStats;
  ingestion_rate: IngestionRateStats;
  tail_freshness: TailFreshnessStats;
  entry_outcomes: EntryOutcomeStats;
  backfill_ranges: BackfillRangeStats;
  backfill_health: BackfillHealth | null;
  metrics_retention: MetricsRetentionStats | null;
  audit_health: AuditHealth | null;
  logs: LogStatsItem[];
  workers: WorkerSummary | null;
  backfill_state: BackfillStateSummary | null;
  ingestion_health?: IngestionHealth | null;
  maintenance?: MaintenanceStatus | null;
  host_capacity?: HostCapacityStats | null;
}

export interface HostCapacityStats {
  cpu_percent: number | null;
  memory_total_bytes: number | null;
  memory_available_bytes: number | null;
  memory_used_bytes: number | null;
  memory_percent: number | null;
  disk_total_bytes: number | null;
  disk_used_bytes: number | null;
  disk_free_bytes: number | null;
  disk_percent: number | null;
  disk_io_read_bytes: number | null;
  disk_io_write_bytes: number | null;
  net_bytes_sent: number | null;
  net_bytes_recv: number | null;
}
