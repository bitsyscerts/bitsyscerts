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

export interface StorageProjection {
  status: StorageProjectionStatus;
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

export interface StatsResponse {
  total_hostnames: number;
  total_certificates: number;
  total_logs: number;
  storage: StorageStats;
  storage_projection: StorageProjection;
  db_contention: DbContentionStats;
  ingestion_rate: IngestionRateStats;
  tail_freshness: TailFreshnessStats;
  logs: LogStatsItem[];
}
