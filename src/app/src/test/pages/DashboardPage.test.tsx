import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardPage } from "@/pages/DashboardPage/DashboardPage";
import { useStats } from "@/hooks/useStats";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStats", () => ({
  useStats: vi.fn(),
}));

const mockUseStats = vi.mocked(useStats);

const STATS_FIXTURE = {
  total_hostnames: 100,
  total_certificates: 200,
  total_logs: 5,
  storage_profile: null,
  storage: {
    total_size_bytes: 1024 ** 3,
    total_size_pretty: "1 GB",
    tables: [],
  },
  storage_projection: {
    status: "available" as const,
    database_size_bytes: 1024 ** 3,
    ct_observations_count: 1000,
    certificates_count: 200,
    hostnames_count: 100,
    certificate_hostnames_count: 250,
    planned_observations_total: 10_000,
    planned_observations_completed: 1000,
    planned_observations_remaining: 9000,
    sync_percent_by_observation: 0.1,
    bytes_per_observation_current: 1024,
    projected_remaining_database_size_bytes: 9 * 1024 ** 3,
    projected_final_database_size_bytes: 10 * 1024 ** 3,
    storage_percent_of_projected: 0.1,
    projection_low_bytes: 8 * 1024 ** 3,
    projection_current_bytes: 10 * 1024 ** 3,
    projection_high_bytes: 15 * 1024 ** 3,
    disk_total_bytes: 20 * 1024 ** 3,
    disk_used_bytes: 5 * 1024 ** 3,
    disk_free_bytes: 15 * 1024 ** 3,
    disk_free_percent: 0.75,
    configured_min_free_disk_bytes: 1024 ** 3,
    projected_disk_free_after_sync_bytes: 6 * 1024 ** 3,
    projected_fits_on_disk: true,
    notes: [],
  },
  db_contention: {
    status: "healthy" as const,
    degraded_mode_active: false,
    pressure_ema: 0.02,
    base_sleep_seconds: 0,
    shared_batch_size_cap: null,
    effective_batch_size_cap: null,
    updated_at: "2025-01-01T00:00:00Z",
    notes: ["Shared DB contention control is active and not throttling."],
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
    completed: 0,
    failed: 0,
  },
  backfill_health: null,
  metrics_retention: null,
  audit_health: null,
  logs: [],
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

function renderPage() {
  return render(
    <AllProviders initialEntries={["/"]}>
      <DashboardPage />
    </AllProviders>,
  );
}

describe("DashboardPage loading state", () => {
  it("renders skeleton when loading", () => {
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });

  it("does not render a Watch checkbox (removed)", () => {
    renderPage();
    expect(screen.queryByRole("checkbox", { name: /watch/i })).toBeNull();
  });
});

describe("DashboardPage with data", () => {
  beforeEach(() => {
    mockUseStats.mockReturnValue({
      data: STATS_FIXTURE,
      isLoading: false,
      isError: false,
      dataUpdatedAt: Date.now(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
  });

  it("renders operational panel headings", () => {
    renderPage();
    expect(screen.getByText("Storage Projection")).toBeInTheDocument();
    expect(screen.getByText("DB Contention Control")).toBeInTheDocument();
    expect(screen.getByText("Database Storage")).toBeInTheDocument();
    expect(screen.getAllByText("CT Logs").length).toBeGreaterThan(0);
  });

  it("renders a manual Refresh button", () => {
    renderPage();
    expect(
      screen.getByRole("button", { name: /refresh statistics/i }),
    ).toBeInTheDocument();
  });

  it("shows last-updated timestamp after data loads", () => {
    renderPage();
    // The "Updated HH:MM:SS" text appears when dataUpdatedAt > 0
    expect(screen.getByText(/Updated /i)).toBeInTheDocument();
  });

  it("does not render StorageProfileCard when profile is null", () => {
    renderPage();
    expect(screen.queryByText("Storage Profile")).toBeNull();
  });

  it("renders StorageProfileCard when profile is present", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...STATS_FIXTURE,
        storage_profile: {
          storage_profile: "standard",
          cert_storage_mode: "fingerprint_only",
          hostname_retention_mode: "rolling",
          backfill_days: 90,
          cert_retention_days: 365,
          observation_retention_days: 90,
          entry_outcome_retention_days: 7,
          metrics_retention_days: 90,
          settings_hash: "abc123",
          source: "database" as const,
        },
      },
      isLoading: false,
      isError: false,
      dataUpdatedAt: Date.now(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
    renderPage();
    expect(screen.getByText("Storage Profile")).toBeInTheDocument();
  });

  it("demotes legacy range diagnostics when per-log mode is primary", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...STATS_FIXTURE,
        backfill_ranges: {
          pending: 0,
          in_progress: 0,
          stale_in_progress: 0,
          completed: 0,
          failed: 5,
          dispatch_mode: "per-log",
          is_primary: false,
        },
        audit_health: {
          open_critical: 0,
          open_error: 1,
          open_warning: 0,
          open_info: 0,
          total_open: 1,
          status: "attention_needed" as const,
        },
      },
      isLoading: false,
      isError: false,
      dataUpdatedAt: Date.now(),
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
    renderPage();
    expect(
      screen.getByText("Advanced / Legacy Range Diagnostics"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Failed backfill ranges detected/i),
    ).not.toBeInTheDocument();
  });
});

describe("DashboardPage error state", () => {
  it("renders error alert when stats fail", () => {
    mockUseStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      dataUpdatedAt: 0,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useStats>);
    renderPage();
    expect(screen.getByText(/could not load statistics/i)).toBeInTheDocument();
  });
});

describe("DashboardPage useStats call", () => {
  it("calls useStats with 10 s refresh interval", () => {
    renderPage();
    expect(mockUseStats).toHaveBeenCalledWith(10_000);
  });
});
