/**
 * Consolidated StatsPanel render-state coverage stays in one file while the
 * shared stats payload contract remains in active iteration. Split by subpanel
 * once the response shape settles after the Sprint 7 runtime follow-up work.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStats", () => ({
  useStats: vi.fn(),
}));

import { useStats } from "@/hooks/useStats";
import { StatsPanel } from "@/components/StatsPanel/StatsPanel";

const mockUseStats = vi.mocked(useStats);

const MOCK_DATA = {
  total_hostnames: 1_234,
  total_certificates: 5_678,
  total_logs: 3,
  storage: {
    total_size_pretty: "2.5 GB",
    tables: [
      {
        table_name: "hostnames",
        row_estimate: 1000,
        size_bytes: 1_073_741_824,
        size_pretty: "1 GB",
      },
    ],
  },
  ingestion_rate: {
    windows: [],
  },
  tail_freshness: {
    stale_threshold_seconds: 300,
    stale_log_count: 0,
    oldest_lag_seconds: null,
    median_lag_seconds: null,
  },
  entry_outcomes: {
    stored: 100,
    parse_error: 2,
    unsupported_entry_type: 1,
    skipped_by_policy: 0,
  },
  backfill_ranges: {
    pending: 5,
    in_progress: 1,
    stale_in_progress: 0,
    completed: 200,
    failed: 0,
  },
  logs: [
    {
      log_id: "00000000-0000-4000-8000-000000000001",
      url: "https://ct.example.com/log",
      description: "Example CT Log",
      log_state: "running",
      backfill_complete_pct: 80,
      tail_position: 1_000_000,
      last_tail_sync: "2024-01-01T00:00:00Z",
      tail_freshness_lag_seconds: 100,
    },
  ],
};

beforeEach(() => {
  mockUseStats.mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useStats>);
});

describe("StatsPanel loading state", () => {
  it("renders skeleton when loading", () => {
    mockUseStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
    const { container } = render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });
});

describe("StatsPanel error state", () => {
  it("renders error alert when isError", () => {
    mockUseStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useStats>);
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(screen.getByText(/could not load statistics/i)).toBeInTheDocument();
  });
});

describe("StatsPanel with data", () => {
  beforeEach(() => {
    mockUseStats.mockReturnValue({
      data: MOCK_DATA,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
  });

  it("renders accordion panel without crash", () => {
    const { container } = render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });

  it("renders log rows without missing key warnings", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );

    expect(
      consoleError.mock.calls.some(([message]) =>
        String(message).includes(
          'Each child in a list should have a unique "key" prop',
        ),
      ),
    ).toBe(false);

    consoleError.mockRestore();
  });

  it("shows the Ingestion Statistics heading", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(screen.getByText("Ingestion Statistics")).toBeInTheDocument();
  });

  it("does not show stale warning when stale_in_progress is zero", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.queryByText(/stale backfill claims detected/i),
    ).not.toBeInTheDocument();
  });
});

describe("StatsPanel with stale backfill claims", () => {
  it("shows stale warning when stale_in_progress > 0", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...MOCK_DATA,
        backfill_ranges: {
          pending: 0,
          in_progress: 2,
          stale_in_progress: 3,
          completed: 100,
          failed: 0,
        },
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.getByText(/stale backfill claims detected/i),
    ).toBeInTheDocument();
  });
});

describe("StatsPanel per-log primary mode", () => {
  const PER_LOG_DATA = {
    ...MOCK_DATA,
    workers: {
      active_total: 1,
      stale_total: 0,
      tail_active: 0,
      backfill_active: 1,
      stats_active: 0,
      maintenance_active: 0,
      unknown_active: 0,
      items: [],
    },
    backfill_state: {
      total_logs: 2,
      pending: 0,
      claimed: 0,
      processing: 1,
      retrying: 0,
      paused: 0,
      complete: 1,
      error: 0,
      stale: 0,
      items: [],
      dispatch_mode: "per-log",
      is_primary: true,
    },
    backfill_ranges: {
      pending: 0,
      in_progress: 0,
      stale_in_progress: 0,
      completed: 0,
      failed: 0,
      dispatch_mode: "per-log",
      is_primary: false,
    },
  };

  beforeEach(() => {
    mockUseStats.mockReturnValue({
      data: PER_LOG_DATA,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
  });

  it("renders the Per-Log Backfill State card", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(screen.getByText("Per-Log Backfill State")).toBeInTheDocument();
  });

  it("renders the backfill ranges card heading", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(screen.getByText("Backfill Range Status")).toBeInTheDocument();
  });

  it("does NOT show failed ranges alert when no failures", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.queryByText(/Failed backfill ranges detected/i),
    ).not.toBeInTheDocument();
  });

  it("shows failed ranges alert when backfill_ranges has failures", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...MOCK_DATA,
        backfill_ranges: {
          pending: 0,
          in_progress: 0,
          stale_in_progress: 0,
          completed: 0,
          failed: 5,
          dispatch_mode: "per-log",
          is_primary: false,
        },
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.getByText(/Failed backfill ranges detected/i),
    ).toBeInTheDocument();
  });
});
