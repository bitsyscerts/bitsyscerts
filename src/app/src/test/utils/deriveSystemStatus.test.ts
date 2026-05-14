import { describe, expect, it } from "vitest";
import { deriveSystemStatus } from "@/utils/deriveSystemStatus";
import type { SnapshotMetadata, StatsResponse } from "@/types";

const BASE_SNAPSHOT: SnapshotMetadata = {
  generated_at: "2025-01-01T00:00:00Z",
  age_seconds: 30,
  is_stale: false,
  stale_threshold_seconds: 300,
  source: "snapshot",
};

const BASE_STATS: StatsResponse = {
  snapshot: BASE_SNAPSHOT,
  total_hostnames: 100,
  total_certificates: 200,
  total_logs: 5,
  storage_profile: null,
  storage: {
    total_size_bytes: 1024,
    total_size_pretty: "1 KB",
    tables: [],
  },
  storage_projection: {
    status: "available",
    database_size_bytes: 1024,
    ct_observations_count: 10,
    certificates_count: 200,
    hostnames_count: 100,
    certificate_hostnames_count: 250,
    planned_observations_total: 1000,
    planned_observations_completed: 100,
    planned_observations_remaining: 900,
    sync_percent_by_observation: 0.1,
    bytes_per_observation_current: 100,
    projected_remaining_database_size_bytes: 900,
    projected_final_database_size_bytes: 1000,
    storage_percent_of_projected: 0.1,
    projection_low_bytes: 800,
    projection_current_bytes: 1000,
    projection_high_bytes: 1200,
    disk_total_bytes: 10000,
    disk_used_bytes: 1000,
    disk_free_bytes: 9000,
    disk_free_percent: 0.9,
    configured_min_free_disk_bytes: 100,
    projected_disk_free_after_sync_bytes: 8000,
    projected_fits_on_disk: true,
    notes: [],
  },
  db_contention: {
    status: "healthy",
    degraded_mode_active: false,
    pressure_ema: 0.01,
    base_sleep_seconds: 0,
    shared_batch_size_cap: null,
    effective_batch_size_cap: null,
    updated_at: "2025-01-01T00:00:00Z",
    notes: [],
    total_retryable_errors: 0,
    retryable_errors_per_min_5min: null,
  },
  ingestion_rate: { windows: [] },
  tail_freshness: {
    stale_threshold_seconds: 3600,
    stale_log_count: 0,
    oldest_lag_seconds: null,
    median_lag_seconds: null,
  },
  entry_outcomes: {
    stored: 0,
    parse_error: 0,
    unsupported_entry_type: 0,
    skipped_by_policy: 0,
  },
  backfill_ranges: {
    pending: 0,
    in_progress: 0,
    stale_in_progress: 0,
    completed: 10,
    failed: 0,
    dispatch_mode: "per-log",
    is_primary: false,
  },
  backfill_health: null,
  metrics_retention: null,
  audit_health: null,
  logs: [],
  workers: null,
  backfill_state: null,
};

describe("deriveSystemStatus", () => {
  it("returns healthy when all signals are clear", () => {
    const result = deriveSystemStatus(BASE_STATS);
    expect(result.level).toBe("healthy");
    expect(result.issues).toHaveLength(0);
  });

  it("returns unknown when snapshot is null", () => {
    const result = deriveSystemStatus({ ...BASE_STATS, snapshot: null });
    expect(result.level).toBe("unknown");
  });

  it("returns starting when snapshot source is none", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      snapshot: {
        generated_at: null,
        age_seconds: null,
        is_stale: false,
        stale_threshold_seconds: null,
        source: "none",
      },
    });
    expect(result.level).toBe("starting");
  });

  it("returns warning for stale snapshot", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      snapshot: { ...BASE_SNAPSHOT, is_stale: true },
    });
    expect(result.level).toBe("warning");
    expect(result.issues[0].message).toMatch(/stale/i);
  });

  it("returns action_needed for stale workers", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      workers: {
        active_total: 1,
        stale_total: 1,
        tail_active: 1,
        backfill_active: 0,
        stats_active: 0,
        maintenance_active: 0,
        unknown_active: 0,
        items: [],
      },
    });
    expect(result.level).toBe("action_needed");
    expect(result.issues.some((i) => i.message.match(/stale worker/i))).toBe(
      true,
    );
  });

  it("returns action_needed when projected_fits_on_disk is false", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      storage_projection: {
        ...BASE_STATS.storage_projection,
        projected_fits_on_disk: false,
      },
    });
    expect(result.level).toBe("action_needed");
  });

  it("returns action_needed for failed maintenance", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      maintenance: {
        status: "complete",
        active_profile: "current-osint",
        last_prune_started_at: "2025-01-01T00:00:00Z",
        last_prune_completed_at: "2025-01-01T00:01:00Z",
        last_prune_status: "failed",
        last_prune_mode: "execute",
        last_prune_deleted: {
          certificates: 0,
          certificate_hostnames: 0,
          observations: 0,
          entry_outcomes: 0,
          ingestion_metrics: 0,
        },
        preserved_hostnames: null,
        duration_ms: null,
        next_prune_due_at: null,
        is_enforced: false,
        error_message: null,
      },
    });
    expect(result.level).toBe("action_needed");
  });

  it("stale CT logs do not raise a warning (normal operating state)", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      tail_freshness: { ...BASE_STATS.tail_freshness, stale_log_count: 2 },
    });
    expect(result.level).toBe("healthy");
  });

  it("action_needed takes precedence over warning", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      snapshot: { ...BASE_SNAPSHOT, is_stale: true },
      workers: {
        active_total: 1,
        stale_total: 1,
        tail_active: 0,
        backfill_active: 0,
        stats_active: 0,
        maintenance_active: 0,
        unknown_active: 0,
        items: [],
      },
    });
    expect(result.level).toBe("action_needed");
    expect(result.issues.length).toBeGreaterThan(1);
  });

  it("returns action_needed with inspect-ct-logs hint when logs are paused", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      ingestion_health: {
        retrying_logs: 0,
        rate_limited_logs: 0,
        paused_logs: 2,
        degraded_logs: 0,
        error_logs: 0,
        stale_workers: 0,
        retryable_error_total: 0,
        terminal_error_total: 0,
        recent_terminal_outcomes: 0,
        status: "attention_needed",
      },
    });
    expect(result.level).toBe("action_needed");
    const pausedIssue = result.issues.find((i) => i.message.includes("paused"));
    expect(pausedIssue).toBeDefined();
    expect(pausedIssue?.message).toMatch(/Inspect CT logs/i);
  });

  it("returns healthy (not warning) when only degraded logs present", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      ingestion_health: {
        retrying_logs: 0,
        rate_limited_logs: 0,
        paused_logs: 0,
        degraded_logs: 1,
        error_logs: 0,
        stale_workers: 0,
        retryable_error_total: 0,
        terminal_error_total: 0,
        recent_terminal_outcomes: 0,
        status: "ok",
      },
    });
    expect(result.level).toBe("healthy");
    expect(result.issues).toHaveLength(0);
  });

  it("returns healthy (not warning) when only retrying logs present", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      ingestion_health: {
        retrying_logs: 2,
        rate_limited_logs: 0,
        paused_logs: 0,
        degraded_logs: 0,
        error_logs: 0,
        stale_workers: 0,
        retryable_error_total: 0,
        terminal_error_total: 0,
        recent_terminal_outcomes: 0,
        status: "ok",
      },
    });
    expect(result.level).toBe("healthy");
    expect(result.issues).toHaveLength(0);
  });

  it("returns healthy (not warning) when only rate-limited logs present", () => {
    const result = deriveSystemStatus({
      ...BASE_STATS,
      ingestion_health: {
        retrying_logs: 0,
        rate_limited_logs: 3,
        paused_logs: 0,
        degraded_logs: 0,
        error_logs: 0,
        stale_workers: 0,
        retryable_error_total: 0,
        terminal_error_total: 0,
        recent_terminal_outcomes: 0,
        status: "ok",
      },
    });
    expect(result.level).toBe("healthy");
    expect(result.issues).toHaveLength(0);
  });
});
