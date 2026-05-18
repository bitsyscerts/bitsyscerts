import { describe, expect, it } from "vitest";
import {
  formatWorkerActivity,
  formatWorkerAge,
  formatWorkerError,
  formatWorkerLog,
  formatWorkerLogMeta,
  formatWorkerWork,
  workerKindColor,
  workerStatusColor,
} from "@/components/StatsPanel/workerActivityFormat";
import type { WorkerSummaryItem } from "@/types";

function makeItem(
  overrides: Partial<WorkerSummaryItem> = {},
): WorkerSummaryItem {
  return {
    worker_id: "host:1",
    worker_kind: "tail",
    log_source_id: null,
    log_name: "Test Log",
    log_url: null,
    log_operator: null,
    direction: null,
    status: "processing",
    is_stale: false,
    last_heartbeat_at: new Date().toISOString(),
    last_heartbeat_age_seconds: 5,
    started_at: new Date().toISOString(),
    current_index: null,
    checkpoint_index: null,
    batch_start_index: null,
    batch_end_index: null,
    processed_entries: 0,
    stored_certificates: 0,
    duplicate_certificates: 0,
    observed_hostnames: 0,
    new_hostnames: 0,
    parse_errors: 0,
    retryable_errors: 0,
    terminal_errors: 0,
    observations_per_min: null,
    new_unique_certificates_per_min: null,
    duplicate_certificates_per_min: null,
    new_unique_hostnames_per_min: null,
    known_hostnames_per_min: null,
    retry_count: null,
    next_retry_at: null,
    rate_limited_until: null,
    last_error_type: null,
    last_error_message: null,
    ...overrides,
  };
}

describe("formatWorkerAge", () => {
  it("formats seconds when age is under 60", () => {
    expect(formatWorkerAge(45)).toBe("45s ago");
  });

  it("formats minutes when age is 60-3599", () => {
    expect(formatWorkerAge(90)).toBe("1m ago");
    expect(formatWorkerAge(3599)).toBe("59m ago");
  });

  it("formats hours when age is 3600 or more", () => {
    expect(formatWorkerAge(3600)).toBe("1h ago");
    expect(formatWorkerAge(7200)).toBe("2h ago");
  });
});

describe("workerStatusColor", () => {
  it("returns red for stale workers", () => {
    expect(workerStatusColor(makeItem({ is_stale: true }))).toBe("red");
  });

  it("returns red for error status", () => {
    expect(workerStatusColor(makeItem({ status: "error" }))).toBe("red");
  });

  it("returns yellow for retrying", () => {
    expect(workerStatusColor(makeItem({ status: "retrying" }))).toBe("yellow");
  });

  it("returns green for processing", () => {
    expect(workerStatusColor(makeItem({ status: "processing" }))).toBe("green");
  });

  it("returns blue for idle", () => {
    expect(workerStatusColor(makeItem({ status: "idle" }))).toBe("blue");
  });

  it("returns gray for unknown status", () => {
    expect(workerStatusColor(makeItem({ status: "unknown" }))).toBe("gray");
  });
});

describe("workerKindColor", () => {
  it("returns blue for tail", () => {
    expect(workerKindColor("tail")).toBe("blue");
  });

  it("returns grape for backfill", () => {
    expect(workerKindColor("backfill")).toBe("grape");
  });

  it("returns teal for stats-snapshotter", () => {
    expect(workerKindColor("stats-snapshotter")).toBe("teal");
  });

  it("returns orange for maintenance", () => {
    expect(workerKindColor("maintenance")).toBe("orange");
  });

  it("returns gray for unknown kinds", () => {
    expect(workerKindColor("unknown")).toBe("gray");
  });
});

describe("formatWorkerLog", () => {
  it("returns log_name when set", () => {
    expect(formatWorkerLog(makeItem({ log_name: "My Log" }))).toBe("My Log");
  });

  it("falls back to log_source_id when log_name is null", () => {
    expect(
      formatWorkerLog(makeItem({ log_name: null, log_source_id: "src-abc" })),
    ).toBe("src-abc");
  });

  it("falls back to Service worker when both are null", () => {
    expect(
      formatWorkerLog(makeItem({ log_name: null, log_source_id: null })),
    ).toBe("Service worker");
  });
});

describe("formatWorkerLogMeta", () => {
  it("returns log_operator when set", () => {
    expect(formatWorkerLogMeta(makeItem({ log_operator: "Op" }))).toBe("Op");
  });

  it("returns log_url when log_operator is null", () => {
    expect(
      formatWorkerLogMeta(
        makeItem({ log_operator: null, log_url: "https://example.com" }),
      ),
    ).toBe("https://example.com");
  });

  it("returns null when both are null", () => {
    expect(
      formatWorkerLogMeta(makeItem({ log_operator: null, log_url: null })),
    ).toBeNull();
  });
});

describe("formatWorkerWork", () => {
  it("shows no assigned work when all fields are null", () => {
    expect(formatWorkerWork(makeItem())).toBe("No assigned work");
  });

  it("includes direction when set", () => {
    expect(formatWorkerWork(makeItem({ direction: "forward" }))).toBe(
      "forward",
    );
  });

  it("includes batch range when both indexes are set", () => {
    const result = formatWorkerWork(
      makeItem({ batch_start_index: 1000, batch_end_index: 2000 }),
    );
    expect(result).toContain("1,000-2,000");
  });

  it("includes current_index when batch indexes are null", () => {
    const result = formatWorkerWork(makeItem({ current_index: 5000 }));
    expect(result).toContain("idx 5,000");
  });

  it("includes checkpoint when different from current_index", () => {
    const result = formatWorkerWork(
      makeItem({ current_index: 5000, checkpoint_index: 4000 }),
    );
    expect(result).toContain("ckpt 4,000");
  });

  it("omits checkpoint when equal to current_index", () => {
    const result = formatWorkerWork(
      makeItem({ current_index: 5000, checkpoint_index: 5000 }),
    );
    expect(result).not.toContain("ckpt");
  });
});

describe("formatWorkerActivity", () => {
  it("returns no recent activity when all rates are null and counts are zero", () => {
    expect(formatWorkerActivity(makeItem())).toBe("No recent activity");
  });

  it("shows processed entries when counts are non-zero", () => {
    const result = formatWorkerActivity(
      makeItem({ processed_entries: 1000, stored_certificates: 500 }),
    );
    expect(result).toContain("1,000 processed");
    expect(result).toContain("500 certs");
  });

  it("shows obs/min rate when set", () => {
    const result = formatWorkerActivity(
      makeItem({ observations_per_min: 120.5 }),
    );
    expect(result).toContain("120.5 obs/min");
  });

  it("includes cert rate when set alongside obs rate", () => {
    const result = formatWorkerActivity(
      makeItem({
        observations_per_min: 120,
        new_unique_certificates_per_min: 50,
      }),
    );
    expect(result).toContain("50 new cert/min");
  });

  it("includes host rate when set alongside obs rate", () => {
    const result = formatWorkerActivity(
      makeItem({
        observations_per_min: 120,
        new_unique_hostnames_per_min: 30,
      }),
    );
    expect(result).toContain("30 new host/min");
  });
});

describe("formatWorkerError", () => {
  it("returns no recent errors when all fields are null", () => {
    expect(formatWorkerError(makeItem())).toBe("No recent errors");
  });

  it("formats error type with message when both set", () => {
    const result = formatWorkerError(
      makeItem({
        last_error_type: "TimeoutError",
        last_error_message: "deadline exceeded",
      }),
    );
    expect(result).toBe("TimeoutError: deadline exceeded");
  });

  it("formats error type only when message is null", () => {
    const result = formatWorkerError(
      makeItem({ last_error_type: "TimeoutError", last_error_message: null }),
    );
    expect(result).toBe("TimeoutError");
  });

  it("formats retry with next_retry_at when set", () => {
    const result = formatWorkerError(
      makeItem({ retry_count: 3, next_retry_at: "2025-01-01T00:00:00Z" }),
    );
    expect(result).toContain("retry 3");
    expect(result).toContain("2025-01-01T00:00:00Z");
  });

  it("formats retry count only when next_retry_at is null", () => {
    const result = formatWorkerError(
      makeItem({ retry_count: 2, next_retry_at: null }),
    );
    expect(result).toBe("retry 2");
  });

  it("shows rate limited message when rate_limited_until is set", () => {
    const result = formatWorkerError(
      makeItem({ rate_limited_until: "2025-01-01T12:00:00Z" }),
    );
    expect(result).toContain("rate limited until");
  });
});
