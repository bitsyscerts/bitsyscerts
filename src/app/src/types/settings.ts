/** Mirrors certsapi/settings/models.py — keep in sync with backend. */

export interface StorageSettingsResponse {
  storage_profile: string;
  cert_storage_mode: string;
  hostname_retention_mode: string;
  backfill_days: number;
  cert_retention_days: number;
  observation_retention_days: number;
  entry_outcome_retention_days: number;
  metrics_retention_days: number;
  settings_hash: string;
  updated_at: string;
  updated_by: string | null;
  source: "database";
}

export interface UpdateStorageSettingsRequest {
  storage_profile: string;
  cert_storage_mode: string;
  hostname_retention_mode: string;
  backfill_days: number;
  cert_retention_days: number;
  observation_retention_days: number;
  entry_outcome_retention_days: number;
  metrics_retention_days: number;
  updated_by?: string | null;
  archive_explicit_optin?: boolean;
}

export interface UpdateStorageSettingsResult {
  status: "updated";
  storage_profile: string;
  settings_hash: string;
  message: string;
  recommended_actions: string[];
}

export interface StorageSettingsHistoryItem {
  settings_hash: string;
  storage_profile: string;
  cert_storage_mode: string;
  hostname_retention_mode: string;
  backfill_days: number;
  cert_retention_days: number;
  observation_retention_days: number;
  entry_outcome_retention_days: number;
  metrics_retention_days: number;
  first_seen_at: string;
  last_seen_at: string;
  is_current: boolean;
}
