/** Mirrors certsapi/stats/models.py — keep in sync with backend. */

export interface LogStatsItem {
  log_id: string;
  description: string;
  url: string;
  log_state: string;
  tail_position: number | null;
  last_tail_sync: string | null;
  backfill_complete_pct: number | null;
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

export interface StatsResponse {
  total_hostnames: number;
  total_certificates: number;
  total_logs: number;
  storage: StorageStats;
  logs: LogStatsItem[];
}
