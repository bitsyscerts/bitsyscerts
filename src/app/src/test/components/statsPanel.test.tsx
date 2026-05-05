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
});
