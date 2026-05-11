import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CTLogsDrawer } from "@/components/StatsPanel/CTLogsDrawer";
import type { BackfillStateSummary, LogStatsItem } from "@/types";
import { AllProviders } from "../AllProviders";

const LOGS: LogStatsItem[] = [
  {
    log_id: "argon2024",
    description: "Argon2024",
    url: "https://ct.example.com/log",
    log_state: "active",
    tail_position: 1000,
    last_tail_sync: "2025-01-01T00:00:00Z",
    backfill_complete_pct: 0.9,
    tail_freshness_lag_seconds: null,
  },
];

const BACKFILL_STATE: BackfillStateSummary = {
  total_logs: 3,
  pending: 0,
  claimed: 0,
  processing: 1,
  retrying: 0,
  paused: 0,
  complete: 900,
  error: 0,
  stale: 0,
  items: [],
};

describe("CTLogsDrawer", () => {
  it("does not render content when closed", () => {
    render(
      <AllProviders>
        <CTLogsDrawer
          opened={false}
          onClose={vi.fn()}
          logs={[]}
          backfillState={null}
        />
      </AllProviders>,
    );
    expect(screen.queryByText("CT Logs")).toBeNull();
  });

  it("renders title when open", () => {
    render(
      <AllProviders>
        <CTLogsDrawer
          opened
          onClose={vi.fn()}
          logs={[]}
          backfillState={null}
        />
      </AllProviders>,
    );
    expect(screen.getByText("CT Logs")).toBeInTheDocument();
  });

  it("renders without crashing when logs are provided", () => {
    const { container } = render(
      <AllProviders>
        <CTLogsDrawer
          opened
          onClose={vi.fn()}
          logs={LOGS}
          backfillState={null}
        />
      </AllProviders>,
    );
    // Drawer title is accessible outside ScrollArea
    expect(screen.getByText("CT Logs")).toBeInTheDocument();
    expect(container).toBeTruthy();
  });

  it("renders without crashing when backfillState is provided", () => {
    const { container } = render(
      <AllProviders>
        <CTLogsDrawer
          opened
          onClose={vi.fn()}
          logs={LOGS}
          backfillState={BACKFILL_STATE}
        />
      </AllProviders>,
    );
    expect(screen.getByText("CT Logs")).toBeInTheDocument();
    expect(container).toBeTruthy();
  });

  it("calls onClose when back button is clicked", () => {
    const onClose = vi.fn();
    render(
      <AllProviders>
        <CTLogsDrawer
          opened
          onClose={onClose}
          logs={[]}
          backfillState={null}
        />
      </AllProviders>,
    );
    const backBtn = screen.getByRole("button", { name: /back/i });
    fireEvent.click(backBtn);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
