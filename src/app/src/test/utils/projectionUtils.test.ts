import { describe, expect, it } from "vitest";
import { computeStorageCeiling } from "@/utils/projectionUtils";
import type { StorageProjection } from "@/types";

function makeProjection(
  overrides: Partial<StorageProjection> = {},
): StorageProjection {
  return {
    status: "available",
    database_size_bytes: 73_400_000_000,
    ct_observations_count: 14_800_000_000,
    certificates_count: 9_000_000,
    hostnames_count: 35_000_000,
    certificate_hostnames_count: 19_000_000,
    planned_observations_total: 14_800_000_000,
    planned_observations_completed: 14_800_000_000,
    planned_observations_remaining: 0,
    sync_percent_by_observation: 1.0,
    bytes_per_observation_current: 4.9,
    projected_remaining_database_size_bytes: 0,
    projected_final_database_size_bytes: 73_400_000_000,
    storage_percent_of_projected: 1.0,
    projection_low_bytes: 55_000_000_000,
    projection_current_bytes: 73_400_000_000,
    projection_high_bytes: 110_100_000_000,
    disk_total_bytes: 500_000_000_000,
    disk_used_bytes: 73_400_000_000,
    disk_free_bytes: 426_600_000_000,
    disk_free_percent: 0.85,
    configured_min_free_disk_bytes: 10_737_418_240,
    projected_disk_free_after_sync_bytes: 426_600_000_000,
    projected_fits_on_disk: true,
    notes: [],
    ...overrides,
  };
}

describe("computeStorageCeiling", () => {
  it("uses projection_high_bytes as ceiling when available", () => {
    const { ceilingBytes } = computeStorageCeiling(makeProjection());
    expect(ceilingBytes).toBe(110_100_000_000);
  });

  it("computes pct as database_size_bytes / projection_high_bytes", () => {
    const { pct } = computeStorageCeiling(makeProjection());
    expect(pct).toBeCloseTo(73_400_000_000 / 110_100_000_000);
  });

  it("pct is well below 1.0 even when fully synced — avoids misleading 100%", () => {
    const { pct } = computeStorageCeiling(makeProjection());
    expect(pct).toBeLessThan(0.7);
  });

  it("falls back to projected_final when projection_high_bytes is null", () => {
    const proj = makeProjection({
      projection_high_bytes: null,
      projected_final_database_size_bytes: 80_000_000_000,
    });
    const { ceilingBytes, pct } = computeStorageCeiling(proj);
    expect(ceilingBytes).toBe(80_000_000_000);
    expect(pct).toBeCloseTo(73_400_000_000 / 80_000_000_000);
  });

  it("falls back to storage_percent_of_projected when both ceiling fields are null", () => {
    const proj = makeProjection({
      projection_high_bytes: null,
      projected_final_database_size_bytes: null,
      storage_percent_of_projected: 0.42,
    });
    const { ceilingBytes, pct } = computeStorageCeiling(proj);
    expect(ceilingBytes).toBeNull();
    expect(pct).toBe(0.42);
  });

  it("returns null pct when all projection fields are null", () => {
    const proj = makeProjection({
      projection_high_bytes: null,
      projected_final_database_size_bytes: null,
      storage_percent_of_projected: null,
    });
    const { pct } = computeStorageCeiling(proj);
    expect(pct).toBeNull();
  });

  it("returns null pct when ceilingBytes is zero to avoid division by zero", () => {
    const proj = makeProjection({
      projection_high_bytes: 0,
      projected_final_database_size_bytes: null,
      storage_percent_of_projected: null,
    });
    // projection_high_bytes = 0, so treated as unavailable; both fallbacks null
    const { ceilingBytes, pct } = computeStorageCeiling(proj);
    expect(ceilingBytes).toBe(0);
    expect(pct).toBeNull();
  });
});
