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
      { table_name: "hostnames", pretty_size: "1 GB", row_estimate: 1000 },
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
      id: 1,
      url: "https://ct.example.com/log",
      description: "Example CT Log",
      state: "running" as const,
      backfill_complete_pct: 80,
      tree_size: 1_000_000,
      latest_sth_timestamp: "2024-01-01T00:00:00Z",
      latest_sth_age_seconds: 3600,
      tail_lag: 100,
      tail_lag_pct: 0.01,
      window_start: "2020-01-01T00:00:00Z",
      window_end: null,
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
      failed: 198,
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

  it("renders the advanced/legacy section heading", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.getByText("Advanced / Legacy Range State"),
    ).toBeInTheDocument();
  });

  it("does NOT show legacy failed ranges as primary red alert", () => {
    render(
      <AllProviders>
        <StatsPanel />
      </AllProviders>,
    );
    expect(
      screen.queryByText(/Failed backfill ranges detected/i),
    ).not.toBeInTheDocument();
  });

  it("uses backfill_ranges metadata when backfill_state is absent", () => {
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
      screen.getByText("Advanced / Legacy Range State"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Failed backfill ranges detected/i),
    ).not.toBeInTheDocument();
  });
});

describe("StatsPanel legacy-ranges primary mode", () => {
  it("renders failed ranges alert as primary when is_primary=true", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...MOCK_DATA,
        backfill_state: {
          total_logs: 0,
          pending: 0,
          claimed: 0,
          processing: 0,
          retrying: 0,
          paused: 0,
          complete: 0,
          error: 0,
          stale: 0,
          items: [],
          dispatch_mode: "legacy-ranges",
          is_primary: false,
        },
        backfill_ranges: {
          pending: 0,
          in_progress: 0,
          stale_in_progress: 0,
          completed: 0,
          failed: 5,
          dispatch_mode: "legacy-ranges",
          is_primary: true,
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
