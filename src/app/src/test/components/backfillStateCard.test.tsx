import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { BackfillStateCard } from "@/components/StatsPanel/BackfillStateCard";
import type { BackfillStateItem, BackfillStateSummary } from "@/types";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

function makeItem(
  overrides: Partial<BackfillStateItem> = {},
): BackfillStateItem {
  return {
    log_source_id: "log-1",
    log_name: "Test Log",
    log_url: "https://ct.example.com/",
    status: "processing",
    claimed_by: "host:1",
    is_stale: false,
    checkpoint_index: 500,
    backfill_start_index: 0,
    backfill_end_index: 999,
    progress_percent: 50.0,
    last_heartbeat_age_seconds: 1.5,
    last_error_type: null,
    last_error_message: null,
    completed_at: null,
    ...overrides,
  };
}

function makeSummary(
  overrides: Partial<BackfillStateSummary> = {},
): BackfillStateSummary {
  return {
    total_logs: 1,
    pending: 0,
    claimed: 0,
    processing: 1,
    retrying: 0,
    paused: 0,
    complete: 0,
    error: 0,
    stale: 0,
    items: [makeItem()],
    ...overrides,
  };
}

describe("BackfillStateCard", () => {
  it("renders the Per-Log Backfill State heading", () => {
    render(<BackfillStateCard state={makeSummary()} />, { wrapper });
    expect(screen.getByText("Per-Log Backfill State")).toBeInTheDocument();
  });

  it("shows 'all fresh' badge when no claims are stale", () => {
    render(<BackfillStateCard state={makeSummary({ stale: 0 })} />, {
      wrapper,
    });
    expect(screen.getByText("all fresh")).toBeInTheDocument();
  });

  it("shows stale count badge when stale > 0", () => {
    render(<BackfillStateCard state={makeSummary({ stale: 2 })} />, {
      wrapper,
    });
    expect(screen.getByText("2 stale")).toBeInTheDocument();
  });

  it("renders a row for each log in items", () => {
    const summary = makeSummary({
      total_logs: 2,
      pending: 1,
      processing: 1,
      items: [
        makeItem({ log_source_id: "L1", log_name: "Log One" }),
        makeItem({
          log_source_id: "L2",
          log_name: "Log Two",
          status: "pending",
        }),
      ],
    });
    render(<BackfillStateCard state={summary} />, { wrapper });
    expect(screen.getByText("Log One")).toBeInTheDocument();
    expect(screen.getByText("Log Two")).toBeInTheDocument();
  });

  it("renders empty-state text when items is empty", () => {
    const summary = makeSummary({
      total_logs: 0,
      processing: 0,
      items: [],
    });
    render(<BackfillStateCard state={summary} />, { wrapper });
    expect(screen.getByText("No backfill state rows yet.")).toBeInTheDocument();
  });

  it("renders progress percentage when set", () => {
    render(<BackfillStateCard state={makeSummary()} />, { wrapper });
    expect(screen.getByText("50.0%")).toBeInTheDocument();
  });
});
