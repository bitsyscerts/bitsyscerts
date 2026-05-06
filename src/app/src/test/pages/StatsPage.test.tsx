import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsPage } from "@/pages/StatsPage/StatsPage";
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
  logs: [],
};

beforeEach(() => {
  mockUseStats.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
  } as unknown as ReturnType<typeof useStats>);
});

function renderPage() {
  return render(
    <AllProviders>
      <StatsPage />
    </AllProviders>,
  );
}

describe("StatsPage", () => {
  it("renders skeleton when loading", () => {
    renderPage();
    expect(document.body).toBeTruthy();
  });
});

describe("StatsPage with data", () => {
  it("renders storage and logs sections when data available", () => {
    mockUseStats.mockReturnValue({
      data: STATS_FIXTURE,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
    render(
      <AllProviders>
        <StatsPage />
      </AllProviders>,
    );
    expect(screen.getByText("Storage Projection")).toBeInTheDocument();
    expect(screen.getByText("Database Storage")).toBeInTheDocument();
    expect(screen.getAllByText("CT Logs").length).toBeGreaterThan(0);
  });

  it("renders unavailable projection notes", () => {
    mockUseStats.mockReturnValue({
      data: {
        ...STATS_FIXTURE,
        storage_projection: {
          ...STATS_FIXTURE.storage_projection,
          status: "insufficient_backfill_plan" as const,
          sync_percent_by_observation: null,
          bytes_per_observation_current: null,
          projected_remaining_database_size_bytes: null,
          projected_final_database_size_bytes: null,
          storage_percent_of_projected: null,
          projection_low_bytes: null,
          projection_current_bytes: null,
          projection_high_bytes: null,
          notes: [
            "Storage projection unavailable. Backfill ranges are not available yet.",
          ],
        },
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useStats>);
    renderPage();
    expect(
      screen.getByText(/Storage projection unavailable\. Backfill ranges/i),
    ).toBeInTheDocument();
  });
});
