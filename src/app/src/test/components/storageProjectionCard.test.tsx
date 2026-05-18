import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StorageProjectionCard } from "@/components/StatsPanel/StorageProjectionCard";
import type { StorageProjection } from "@/types";
import { AllProviders } from "../AllProviders";

function makeProjection(
  overrides: Partial<StorageProjection> = {},
): StorageProjection {
  return {
    status: "available",
    database_size_bytes: 7_300_000_000,
    ct_observations_count: 6_300_000,
    certificates_count: 4_100_000,
    hostnames_count: 6_100_000,
    certificate_hostnames_count: 7_800_000,
    planned_observations_total: 4_800_000_000,
    planned_observations_completed: 6_300_000,
    planned_observations_remaining: 4_793_700_000,
    sync_percent_by_observation: 0.0013,
    bytes_per_observation_current: 1_252.44,
    projected_remaining_database_size_bytes: 6_003_000_000_000,
    projected_final_database_size_bytes: 6_010_300_000_000,
    storage_percent_of_projected: 0.0012,
    projection_low_bytes: 4_507_725_000_000,
    projection_current_bytes: 6_010_300_000_000,
    projection_high_bytes: 9_015_450_000_000,
    disk_total_bytes: 10_995_116_277_760,
    disk_used_bytes: 900_000_000_000,
    disk_free_bytes: 10_095_116_277_760,
    disk_free_percent: 0.91,
    configured_min_free_disk_bytes: 53_687_091_200,
    projected_disk_free_after_sync_bytes: 4_092_116_277_760,
    projected_fits_on_disk: true,
    notes: [
      "Projection is based on current bytes per CT observation and will improve as more data is ingested.",
      "Storage percentage is an estimate, not authoritative sync progress.",
    ],
    ...overrides,
  };
}

describe("StorageProjectionCard", () => {
  it("renders available projection metrics and expands details on demand", () => {
    render(
      <AllProviders>
        <StorageProjectionCard projection={makeProjection()} />
      </AllProviders>,
    );

    expect(screen.getByText("Storage Projection")).toBeInTheDocument();
    expect(screen.getByText(/Sync estimate/i)).toBeInTheDocument();
    // Sync percentage is now shown in the ring; text section shows count only
    expect(screen.getByText(/synced/i)).toBeInTheDocument();
    expect(screen.getByText(/observations/i)).toBeInTheDocument();
    expect(screen.getByText(/Projected range/i)).not.toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: /show details/i }));

    expect(screen.getByText(/Projected range/i)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /hide details/i }),
    ).toBeInTheDocument();
  });

  it("renders unavailable state messaging", () => {
    render(
      <AllProviders>
        <StorageProjectionCard
          projection={makeProjection({
            status: "insufficient_backfill_plan",
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
          })}
        />
      </AllProviders>,
    );

    expect(
      screen.getByText(/Storage projection unavailable\. Backfill ranges/i),
    ).toBeInTheDocument();
  });

  it("renders disk warning when projected space is insufficient", () => {
    render(
      <AllProviders>
        <StorageProjectionCard
          projection={makeProjection({
            projected_fits_on_disk: false,
            notes: [
              "Projected final size leaves less than the configured minimum free disk.",
            ],
          })}
        />
      </AllProviders>,
    );

    expect(
      screen.getByText(/configured minimum free disk/i),
    ).toBeInTheDocument();
  });

  it("shows 'Estimate' badge when sync is not complete", () => {
    render(
      <AllProviders>
        <StorageProjectionCard
          projection={makeProjection({ sync_percent_by_observation: 0.5 })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Estimate")).toBeInTheDocument();
    expect(screen.queryByText("Actual")).not.toBeInTheDocument();
  });

  it("shows 'Actual' badge when sync is fully complete", () => {
    render(
      <AllProviders>
        <StorageProjectionCard
          projection={makeProjection({ sync_percent_by_observation: 1.0 })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Actual")).toBeInTheDocument();
    expect(screen.queryByText("Estimate")).not.toBeInTheDocument();
  });

  it("shows 'Estimate' badge when sync_percent is null", () => {
    render(
      <AllProviders>
        <StorageProjectionCard
          projection={makeProjection({ sync_percent_by_observation: null })}
        />
      </AllProviders>,
    );
    expect(screen.getByText("Estimate")).toBeInTheDocument();
  });
});
