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
  observations_per_sec: number;
  certs_per_min: number;
  hostnames_per_min: number;
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
}
