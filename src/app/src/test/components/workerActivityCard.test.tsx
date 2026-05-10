import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { WorkerActivityCard } from "@/components/StatsPanel/WorkerActivityCard";
import type { WorkerSummary, WorkerSummaryItem } from "@/types";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

function makeItem(
  overrides: Partial<WorkerSummaryItem> = {},
): WorkerSummaryItem {
  return {
    worker_id: "host:12345",
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
    current_index: 100_000,
    checkpoint_index: null,
    batch_start_index: null,
    batch_end_index: null,
    processed_entries: 2000,
    stored_certificates: 1900,
    duplicate_certificates: 100,
    observed_hostnames: 500,
    new_hostnames: 200,
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

function makeWorkers(overrides: Partial<WorkerSummary> = {}): WorkerSummary {
  return {
    active_total: 1,
    stale_total: 0,
    tail_active: 1,
    backfill_active: 0,
    stats_active: 0,
    maintenance_active: 0,
    unknown_active: 0,
    items: [makeItem()],
    ...overrides,
  };
}

describe("WorkerActivityCard", () => {
  it("renders the Worker Activity heading", () => {
    render(<WorkerActivityCard workers={makeWorkers()} />, { wrapper });
    expect(screen.getByText("Worker Activity")).toBeInTheDocument();
  });

  it("shows 'all fresh' badge when stale_total is 0", () => {
    render(<WorkerActivityCard workers={makeWorkers({ stale_total: 0 })} />, {
      wrapper,
    });
    expect(screen.getByText("all fresh")).toBeInTheDocument();
  });

  it("shows stale count badge when stale_total > 0", () => {
    render(
      <WorkerActivityCard
        workers={makeWorkers({ stale_total: 2, active_total: 0 })}
      />,
      { wrapper },
    );
    expect(screen.getByText("2 stale")).toBeInTheDocument();
  });

  it("renders assignment, work, and operator details for each worker", () => {
    const workers = makeWorkers({
      items: [
        makeItem({
          worker_id: "host-a:1",
          log_name: "Log A",
          log_operator: "Operator A",
          direction: "forward",
          current_index: 125_000,
        }),
        makeItem({
          worker_id: "host-b:2",
          log_name: "Log B",
          log_operator: "Operator B",
          worker_kind: "backfill",
          direction: "backfill",
          batch_start_index: 100,
          batch_end_index: 199,
          checkpoint_index: 90,
        }),
      ],
      active_total: 2,
      tail_active: 1,
      backfill_active: 1,
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText("host-a:1")).toBeInTheDocument();
    expect(screen.getByText("host-b:2")).toBeInTheDocument();
    expect(screen.getByText("Log A")).toBeInTheDocument();
    expect(screen.getByText("Log B")).toBeInTheDocument();
    expect(screen.getByText("Operator A")).toBeInTheDocument();
    expect(screen.getByText("Operator B")).toBeInTheDocument();
    expect(screen.getByText("forward | idx 125,000")).toBeInTheDocument();
    expect(
      screen.getByText("backfill | 100-199 | ckpt 90"),
    ).toBeInTheDocument();
  });

  it("shows enriched rate and error details when present", () => {
    const workers = makeWorkers({
      items: [
        makeItem({
          worker_kind: "backfill",
          status: "retrying",
          direction: "backfill",
          batch_start_index: 150,
          batch_end_index: 199,
          checkpoint_index: 140,
          observations_per_min: 120,
          new_unique_certificates_per_min: 30,
          new_unique_hostnames_per_min: 8,
          retry_count: 2,
          next_retry_at: "2025-01-01T00:05:00Z",
          last_error_type: "RateLimitError",
          last_error_message: "Upstream rate limit",
        }),
      ],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(
      screen.getByText("120 obs/min | 30 new cert/min | 8 new host/min"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("RateLimitError: Upstream rate limit"),
    ).toBeInTheDocument();
  });

  it("shows singleton service counts in the summary area", () => {
    render(
      <WorkerActivityCard
        workers={makeWorkers({ stats_active: 1, maintenance_active: 2 })}
      />,
      { wrapper },
    );
    expect(screen.getByText("Services")).toBeInTheDocument();
    expect(screen.getByText("snapshot 1")).toBeInTheDocument();
    expect(screen.getByText("maintenance 2")).toBeInTheDocument();
  });

  it("shows 'No active workers right now' when items is empty", () => {
    const workers = makeWorkers({
      items: [],
      active_total: 0,
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(
      screen.getByText(/no active workers right now/i),
    ).toBeInTheDocument();
  });

  it("renders heartbeat age in seconds", () => {
    const workers = makeWorkers({
      items: [makeItem({ last_heartbeat_age_seconds: 42 })],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText("42s ago")).toBeInTheDocument();
  });

  it("renders heartbeat age in minutes for older workers", () => {
    const workers = makeWorkers({
      items: [makeItem({ last_heartbeat_age_seconds: 120 })],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText("2m ago")).toBeInTheDocument();
  });
});
