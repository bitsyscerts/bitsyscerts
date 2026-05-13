/**
 * Derives a system-level status summary from a StatsResponse snapshot.
 *
 * This is a pure function — it has no side effects and does not perform I/O.
 * All signal-to-status mappings live here so they can be independently
 * unit-tested.
 */

import type {
  AuditHealth,
  IngestionHealth,
  MaintenanceStatus,
  SnapshotMetadata,
  StatsResponse,
  StorageProjection,
  WorkerSummary,
} from "@/types";

export type SystemStatusLevel =
  | "healthy"
  | "warning"
  | "action_needed"
  | "starting"
  | "unknown";

export interface DerivedIssue {
  severity: "action_needed" | "warning";
  message: string;
}

export interface SystemStatus {
  level: SystemStatusLevel;
  issues: DerivedIssue[];
}

// ---------------------------------------------------------------------------
// Issue collectors — each returns zero or more issues from one data domain.
// ---------------------------------------------------------------------------

function collectSnapshotIssues(
  snapshot: SnapshotMetadata | null | undefined,
): DerivedIssue[] {
  if (!snapshot || snapshot.is_stale) {
    return [{ severity: "warning", message: "Stats snapshot is stale." }];
  }
  return [];
}

function collectWorkerIssues(
  workers: WorkerSummary | null | undefined,
): DerivedIssue[] {
  if (!workers) return [];
  const issues: DerivedIssue[] = [];
  if (workers.stale_total > 0) {
    issues.push({
      severity: "action_needed",
      message: `${String(workers.stale_total)} stale worker(s) detected.`,
    });
  }
  return issues;
}

function collectIngestionIssues(
  health: IngestionHealth | null | undefined,
): DerivedIssue[] {
  if (!health) return [];
  const issues: DerivedIssue[] = [];
  if (health.error_logs > 0) {
    issues.push({
      severity: "action_needed",
      message: `${String(health.error_logs)} CT log(s) in error state.`,
    });
  }
  if (health.paused_logs > 0) {
    issues.push({
      severity: "action_needed",
      message: `${String(health.paused_logs)} CT log(s) paused — open "Inspect CT logs" for error details.`,
    });
  }
  if (health.rate_limited_logs > 0) {
    issues.push({
      severity: "warning",
      message: `${String(health.rate_limited_logs)} CT log(s) rate-limited.`,
    });
  }
  if (health.retrying_logs > 0) {
    issues.push({
      severity: "warning",
      message: `${String(health.retrying_logs)} CT log(s) retrying.`,
    });
  }
  return issues;
}

function collectMaintenanceIssues(
  maintenance: MaintenanceStatus | null | undefined,
): DerivedIssue[] {
  if (!maintenance) return [];
  const issues: DerivedIssue[] = [];
  if (maintenance.last_prune_status === "failed") {
    issues.push({
      severity: "action_needed",
      message: "Last maintenance prune run failed.",
    });
  }
  if (maintenance.status === "never_ran") {
    issues.push({
      severity: "warning",
      message: "Maintenance has never run on this instance.",
    });
  }
  return issues;
}

function collectStorageIssues(
  projection: StorageProjection | null | undefined,
): DerivedIssue[] {
  if (!projection) return [];
  if (projection.projected_fits_on_disk === false) {
    return [
      {
        severity: "action_needed",
        message: "Projected data does not fit on remaining disk space.",
      },
    ];
  }
  return [];
}

function collectAuditIssues(
  auditHealth: AuditHealth | null | undefined,
): DerivedIssue[] {
  if (!auditHealth) return [];
  if (auditHealth.open_critical > 0) {
    return [
      {
        severity: "action_needed",
        message: `${String(auditHealth.open_critical)} critical audit finding(s) open.`,
      },
    ];
  }
  return [];
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Derive a system status summary from a full stats response.
 *
 * Returns ``"starting"`` when no snapshot has been taken yet.
 * Returns ``"unknown"`` when snapshot metadata is not present at all.
 */
export function deriveSystemStatus(data: StatsResponse): SystemStatus {
  const snapshot = data.snapshot;

  // No snapshot metadata present — we cannot determine status.
  if (snapshot === undefined || snapshot === null) {
    return { level: "unknown", issues: [] };
  }

  // Snapshot source is "none" — the instance has just started.
  if (snapshot.source === "none") {
    return { level: "starting", issues: [] };
  }

  const issues: DerivedIssue[] = [
    ...collectSnapshotIssues(snapshot),
    ...collectWorkerIssues(data.workers),
    ...collectIngestionIssues(data.ingestion_health),
    ...collectMaintenanceIssues(data.maintenance),
    ...collectStorageIssues(data.storage_projection),
    ...collectAuditIssues(data.audit_health),
  ];

  if (issues.some((i) => i.severity === "action_needed")) {
    return { level: "action_needed", issues };
  }
  if (issues.some((i) => i.severity === "warning")) {
    return { level: "warning", issues };
  }
  return { level: "healthy", issues: [] };
}
