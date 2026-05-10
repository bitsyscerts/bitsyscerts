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
    direction: null,
    status: "processing",
    is_stale: false,
    last_heartbeat_at: new Date().toISOString(),
    last_heartbeat_age_seconds: 5,
    started_at: new Date().toISOString(),
    current_index: 100_000,
    processed_entries: 2000,
    stored_certificates: 1900,
    duplicate_certificates: 100,
    observed_hostnames: 500,
    new_hostnames: 200,
    parse_errors: 0,
    retryable_errors: 0,
    terminal_errors: 0,
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

  it("renders a row for each worker in items", () => {
    const workers = makeWorkers({
      items: [
        makeItem({ worker_id: "host-a:1", log_name: "Log A" }),
        makeItem({
          worker_id: "host-b:2",
          log_name: "Log B",
          worker_kind: "backfill",
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
  });

  it("shows 'No active workers' when items is empty", () => {
    const workers = makeWorkers({
      items: [],
      active_total: 0,
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText(/no active workers/i)).toBeInTheDocument();
  });

  it("renders heartbeat age in seconds", () => {
    const workers = makeWorkers({
      items: [makeItem({ last_heartbeat_age_seconds: 42 })],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText("42s ago")).toBeInTheDocument();
  });

  it("displays current_index when present", () => {
    const workers = makeWorkers({
      items: [makeItem({ current_index: 99_000 })],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    expect(screen.getByText("99,000")).toBeInTheDocument();
  });

  it("displays dash when current_index is null", () => {
    const workers = makeWorkers({
      items: [makeItem({ current_index: null })],
    });
    render(<WorkerActivityCard workers={workers} />, { wrapper });
    // There may be multiple "-" cells; we just want at least one
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
  });
});
