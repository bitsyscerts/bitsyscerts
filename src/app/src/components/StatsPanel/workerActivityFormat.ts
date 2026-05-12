import type { WorkerSummaryItem } from "@/types";

const integerFormatter = new Intl.NumberFormat("en-US");
const rateFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});

function formatNumber(value: number): string {
  return integerFormatter.format(value);
}

function formatRate(value: number | null): string | null {
  if (value == null) {
    return null;
  }
  return rateFormatter.format(value);
}

export function formatWorkerAge(ageSeconds: number): string {
  if (ageSeconds < 60) {
    return `${String(ageSeconds)}s ago`;
  }
  if (ageSeconds < 3600) {
    return `${String(Math.floor(ageSeconds / 60))}m ago`;
  }
  return `${String(Math.floor(ageSeconds / 3600))}h ago`;
}

export function workerStatusColor(item: WorkerSummaryItem): string {
  if (item.is_stale || item.status === "error") {
    return "red";
  }
  if (item.status === "retrying") {
    return "yellow";
  }
  if (item.status === "processing") {
    return "green";
  }
  if (item.status === "idle") {
    return "blue";
  }
  return "gray";
}

export function workerKindColor(kind: string): string {
  switch (kind) {
    case "tail":
      return "blue";
    case "backfill":
      return "grape";
    case "stats-snapshotter":
      return "teal";
    case "maintenance":
      return "orange";
    default:
      return "gray";
  }
}

export function formatWorkerLog(item: WorkerSummaryItem): string {
  return item.log_name ?? item.log_source_id ?? "Service worker";
}

export function formatWorkerLogMeta(item: WorkerSummaryItem): string | null {
  return item.log_operator ?? item.log_url;
}

export function formatWorkerWork(item: WorkerSummaryItem): string {
  const parts: string[] = [];
  if (item.direction) {
    parts.push(item.direction);
  }
  if (item.batch_start_index != null && item.batch_end_index != null) {
    parts.push(
      `${formatNumber(item.batch_start_index)}-${formatNumber(item.batch_end_index)}`,
    );
  } else if (item.current_index != null) {
    parts.push(`idx ${formatNumber(item.current_index)}`);
  }
  if (
    item.checkpoint_index != null &&
    item.checkpoint_index !== item.current_index
  ) {
    parts.push(`ckpt ${formatNumber(item.checkpoint_index)}`);
  }
  return parts.length > 0 ? parts.join(" | ") : "No assigned work";
}

export function formatWorkerActivity(item: WorkerSummaryItem): string {
  const observationsRate = formatRate(item.observations_per_min);
  if (observationsRate) {
    const parts = [`${observationsRate} obs/min`];
    const certRate = formatRate(item.new_unique_certificates_per_min);
    const hostRate = formatRate(item.new_unique_hostnames_per_min);
    if (certRate) {
      parts.push(`${certRate} new cert/min`);
    }
    if (hostRate) {
      parts.push(`${hostRate} new host/min`);
    }
    return parts.join(" | ");
  }
  if (item.processed_entries > 0 || item.stored_certificates > 0) {
    return (
      `${formatNumber(item.processed_entries)} processed | ` +
      `${formatNumber(item.stored_certificates)} certs`
    );
  }
  return "No recent activity";
}

export function formatWorkerError(item: WorkerSummaryItem): string {
  if (item.last_error_type) {
    if (item.last_error_message) {
      return `${item.last_error_type}: ${item.last_error_message}`;
    }
    return item.last_error_type;
  }
  if (item.retry_count != null && item.retry_count > 0) {
    if (item.next_retry_at) {
      return `retry ${String(item.retry_count)} until ${item.next_retry_at}`;
    }
    return `retry ${String(item.retry_count)}`;
  }
  if (item.rate_limited_until) {
    return `rate limited until ${item.rate_limited_until}`;
  }
  return "No recent errors";
}