import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardOverview } from "@/pages/DashboardPage/DashboardOverview";
import { useStats } from "@/hooks/useStats";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStats", () => ({
  useStats: vi.fn(),
}));

const mockUseStats = vi.mocked(useStats);

const SNAPSHOT = {
  generated_at: "2025-01-01T00:00:00Z",
  age_seconds: 30,
  is_stale: false,
  stale_threshold_seconds: 300,
  source: "snapshot" as const,
};

const STATS_FIXTURE = {
  snapshot: SNAPSHOT,
  total_hostnames: 500,
  total_certificates: 1000,
  total_logs: 3,
  storage_profile: null,
  storage: {
    total_size_bytes: 2048,
    total_size_pretty: "2 KB",
    tables: [],
  },
  storage_projection: {
    status: "available" as const,
    database_size_bytes: 2048,
    ct_observations_count: 100,
    certificates_count: 1000,
    hostnames_count: 500,
    certificate_hostnames_count: 1200,
    planned_observations_total: 5000,
    planned_observations_completed: 100,
    planned_observations_remaining: 4900,
    sync_percent_by_observation: 0.02,
    bytes_per_observation_current: 20,
    projected_remaining_database_size_bytes: 98000,
    projected_final_database_size_bytes: 100000,
    storage_percent_of_projected: 0.02,
    projection_low_bytes: 80000,
    projection_current_bytes: 100000,
    projection_high_bytes: 120000,
    disk_total_bytes: 500000,
    disk_used_bytes: 2048,
    disk_free_bytes: 497952,
    disk_free_percent: 0.996,
    configured_min_free_disk_bytes: 1024,
    projected_disk_free_after_sync_bytes: 397952,
    projected_fits_on_disk: true,
    notes: [],
  },
  db_contention: {
    status: "healthy" as const,
    degraded_mode_active: false,
    pressure_ema: 0.01,
    base_sleep_seconds: 0,
    shared_batch_size_cap: null,
    effective_batch_size_cap: null,
    updated_at: "2025-01-01T00:00:00Z",
    notes: [],
    total_retryable_errors: 0,
    retryable_errors_per_min_5min: null,
  },
  ingestion_rate: { windows: [] },
  tail_freshness: {
    stale_threshold_seconds: 3600,
    stale_log_count: 0,
    oldest_lag_seconds: null,
    median_lag_seconds: null,
  },
  entry_outcomes: {
    stored: 0,
    parse_error: 0,
    unsupported_entry_type: 0,
    skipped_by_policy: 0,
  },
  backfill_ranges: {
    pending: 0,
    in_progress: 0,
    stale_in_progress: 0,
    completed: 100,
    failed: 0,
    dispatch_mode: "global",
    is_primary: false,
  },
  backfill_health: null,
  metrics_retention: null,
  audit_health: null,
  logs: [],
  workers: null,
  backfill_state: null,
};

beforeEach(() => {
  mockUseStats.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
    dataUpdatedAt: 0,
    refetch: vi.fn(),
  } as unknown as ReturnType<typeof useStats>);
});

function renderOverview() {
  return render(
    <AllProviders initialEntries={["/"]}>
      <DashboardOverview />
    </AllProviders>,
  );
}

describe("DashboardOverview loading state", () => {
  it("renders skeleton while loading", () => {
    const { container } = renderOverview();
    expect(container).toBeTruthy();
    expect(screen.queryByText("Index Summary")).toBeNull();
  });
});

describe("DashboardOverview error state", () => {
  it("renders error alert when stats fail", () => {
    mockUseStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      dataUpdatedAt: 0,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
    renderOverview();
    expect(screen.getByText(/could not load statistics/i)).toBeInTheDocument();
  });
});

describe("DashboardOverview with data", () => {
  beforeEach(() => {
    mockUseStats.mockReturnValue({
      data: STATS_FIXTURE,
      isLoading: false,
      isError: false,
      dataUpdatedAt: Date.now(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
  });

  it("renders all three summary card headings", () => {
    renderOverview();
    expect(screen.getByText("Index Summary")).toBeInTheDocument();
    expect(screen.getByText("Indexer Activity")).toBeInTheDocument();
    expect(screen.getByText("Storage")).toBeInTheDocument();
  });

  it("renders system status card", () => {
    renderOverview();
    expect(screen.getByText("All systems healthy")).toBeInTheDocument();
  });

  it("renders refresh button", () => {
    renderOverview();
    expect(
      screen.getByRole("button", { name: /refresh statistics/i }),
    ).toBeInTheDocument();
  });

  it("renders last-updated timestamp when dataUpdatedAt > 0", () => {
    renderOverview();
    expect(screen.getByText(/Updated /i)).toBeInTheDocument();
  });

  it("renders total hostname count", () => {
    renderOverview();
    expect(screen.getByText("500")).toBeInTheDocument();
  });

  it("does not show issues panel when all systems healthy", () => {
    renderOverview();
    expect(screen.queryByText("No action needed.")).toBeNull();
  });

  it("renders diagnostics accordion", () => {
    renderOverview();
    expect(screen.getByText("Advanced diagnostics")).toBeInTheDocument();
  });

  it("has Inspect workers button that opens worker drawer", async () => {
    renderOverview();
    const btn = screen.getByRole("button", { name: /inspect workers/i });
    expect(btn).toBeInTheDocument();
    // Click does not throw
    await userEvent.click(btn);
  });

  it("has Inspect CT logs button that opens logs drawer", async () => {
    renderOverview();
    const btn = screen.getByRole("button", { name: /inspect ct logs/i });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
  });

  it("has Storage details button that opens storage drawer", async () => {
    renderOverview();
    const btn = screen.getByRole("button", { name: /storage details/i });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
  });
});

describe("DashboardOverview issues panel", () => {
  it("renders issues panel when snapshot is stale", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...STATS_FIXTURE,
        snapshot: { ...SNAPSHOT, is_stale: true },
      },
      isLoading: false,
      isError: false,
      dataUpdatedAt: Date.now(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
    renderOverview();
    expect(screen.getByText("Warnings detected")).toBeInTheDocument();
    expect(screen.getByText("Stats snapshot is stale.")).toBeInTheDocument();
  });
});
